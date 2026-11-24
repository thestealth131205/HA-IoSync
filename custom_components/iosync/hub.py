"""Speicher und Verteiler für alles, was die IoSync-App an Home Assistant meldet.

Die App beschreibt ihre Sensoren selbst (Name, Typ, Icon, Geräteklasse, …). Neue Werte
brauchen deshalb kein Update dieser Integration – unbekannte Sensoren werden beim ersten
Eintreffen angelegt. Letzter Stand wird gespeichert und steht nach einem Neustart sofort
wieder zur Verfügung (die App meldet nur bei Änderungen).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DATA,
    ATTR_DEVICE,
    ATTR_DEVICE_ID,
    ATTR_EVENTS,
    ATTR_ID,
    ATTR_KEY,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SENSORS,
    ATTR_SW_VERSION,
    ATTR_TYPE,
    ATTR_UPDATED,
    DOMAIN,
    EVENT_IOSYNC,
    SAVE_DELAY,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

type AddEntitiesCallback = Callable[[list[str]], None]


def sensor_key(device_id: str, sensor_type: str, key: str) -> str:
    """Interner Schlüssel; derselbe key darf als sensor und binary_sensor existieren."""
    return f"{sensor_type}:{device_id}:{key}"


class IoSyncHub:
    """Hält Geräte und Sensoren einer Config-Entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.devices: dict[str, dict[str, Any]] = {}
        self.sensors: dict[str, dict[str, Any]] = {}
        self._platforms: dict[str, AddEntitiesCallback] = {}
        self._listeners: dict[str, CALLBACK_TYPE] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.devices = data.get("devices", {})
        self.sensors = data.get("sensors", {})
        # Geräte vor den Entitäten anlegen (falls die Registry sie verloren hat)
        for device_id, device in self.devices.items():
            self._update_device_registry(device_id, device)

    async def async_flush(self) -> None:
        await self._store.async_save(self._data())

    async def async_remove_store(self) -> None:
        await self._store.async_remove()

    @callback
    def _data(self) -> dict[str, Any]:
        return {"devices": self.devices, "sensors": self.sensors}

    @callback
    def async_register_platform(self, sensor_type: str, add: AddEntitiesCallback) -> None:
        """Plattform meldet sich an und bekommt sofort alle gespeicherten Sensoren."""
        self._platforms[sensor_type] = add
        existing = [k for k, s in self.sensors.items() if s[ATTR_TYPE] == sensor_type]
        if existing:
            add(existing)

    @callback
    def async_add_listener(self, skey: str, update: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners[skey] = update

        @callback
        def _remove() -> None:
            if self._listeners.get(skey) is update:
                del self._listeners[skey]

        return _remove

    @callback
    def async_handle_update(self, payload: dict[str, Any]) -> int:
        """Bereits validierte Meldung der App verarbeiten. Liefert Anzahl der Sensoren."""
        device = payload[ATTR_DEVICE]
        device_id = device[ATTR_ID]
        info = {
            ATTR_NAME: device[ATTR_NAME],
            ATTR_MANUFACTURER: device.get(ATTR_MANUFACTURER),
            ATTR_MODEL: device.get(ATTR_MODEL),
            ATTR_SW_VERSION: device.get(ATTR_SW_VERSION),
        }
        if self.devices.get(device_id) != info:
            self.devices[device_id] = info
            self._update_device_registry(device_id, info)
        ha_device = dr.async_get(self.hass).async_get_device(identifiers={(DOMAIN, device_id)})

        now = dt_util.utcnow().isoformat()
        new: dict[str, list[str]] = {}
        for sensor in payload[ATTR_SENSORS]:
            skey = sensor_key(device_id, sensor[ATTR_TYPE], sensor[ATTR_KEY])
            is_new = skey not in self.sensors
            self.sensors[skey] = {**sensor, ATTR_DEVICE_ID: device_id, ATTR_UPDATED: now}
            if is_new:
                new.setdefault(sensor[ATTR_TYPE], []).append(skey)
            elif listener := self._listeners.get(skey):
                listener()

        for sensor_type, keys in new.items():
            if add := self._platforms.get(sensor_type):
                add(keys)

        for event in payload[ATTR_EVENTS]:
            self.hass.bus.async_fire(
                EVENT_IOSYNC,
                {
                    ATTR_DEVICE_ID: ha_device.id if ha_device else None,
                    "iosync_device": device_id,
                    ATTR_TYPE: event[ATTR_TYPE],
                    ATTR_DATA: event[ATTR_DATA],
                },
            )

        self._store.async_delay_save(self._data, SAVE_DELAY)
        return len(payload[ATTR_SENSORS])

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Gerät wurde in HA gelöscht; meldet die App es erneut, wird es neu angelegt."""
        self.devices.pop(device_id, None)
        for skey in [k for k, s in self.sensors.items() if s[ATTR_DEVICE_ID] == device_id]:
            del self.sensors[skey]
            self._listeners.pop(skey, None)
        self._store.async_delay_save(self._data, SAVE_DELAY)

    @callback
    def _update_device_registry(self, device_id: str, info: dict[str, Any]) -> None:
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, device_id)},
            name=info[ATTR_NAME],
            manufacturer=info.get(ATTR_MANUFACTURER),
            model=info.get(ATTR_MODEL),
            sw_version=info.get(ATTR_SW_VERSION),
        )

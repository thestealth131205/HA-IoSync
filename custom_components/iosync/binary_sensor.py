"""Binärsensoren der IoSync-App (z. B. Schlaf-/Wachstatus)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoSyncConfigEntry
from .const import ATTR_DEVICE_CLASS, ATTR_STATE, TYPE_BINARY_SENSOR
from .entity import IoSyncEntity

_ON = {"on", "true", "1", "yes"}
_OFF = {"off", "false", "0", "no"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IoSyncConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    hub.async_register_platform(
        TYPE_BINARY_SENSOR,
        lambda keys: async_add_entities(IoSyncBinarySensor(hub, k) for k in keys),
    )


class IoSyncBinarySensor(IoSyncEntity, BinarySensorEntity):
    @callback
    def _apply(self, data: dict[str, Any]) -> None:
        super()._apply(data)
        device_class = data.get(ATTR_DEVICE_CLASS)
        self._attr_device_class = BinarySensorDeviceClass(device_class) if device_class else None
        self._attr_is_on = _to_bool(data.get(ATTR_STATE))


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _ON:
            return True
        if text in _OFF:
            return False
    return None

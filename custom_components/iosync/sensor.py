"""Sensoren der IoSync-App (Zeitstempel, Messwerte, Texte)."""

from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import IoSyncConfigEntry
from .const import ATTR_DEVICE_CLASS, ATTR_STATE, ATTR_STATE_CLASS, ATTR_UNIT, TYPE_SENSOR
from .entity import IoSyncEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IoSyncConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = entry.runtime_data
    hub.async_register_platform(
        TYPE_SENSOR, lambda keys: async_add_entities(IoSyncSensor(hub, k) for k in keys)
    )


class IoSyncSensor(IoSyncEntity, SensorEntity):
    @callback
    def _apply(self, data: dict[str, Any]) -> None:
        super()._apply(data)
        device_class = data.get(ATTR_DEVICE_CLASS)
        state_class = data.get(ATTR_STATE_CLASS)
        self._attr_device_class = SensorDeviceClass(device_class) if device_class else None
        self._attr_state_class = SensorStateClass(state_class) if state_class else None
        self._attr_native_unit_of_measurement = data.get(ATTR_UNIT)
        self._attr_native_value = self._convert(data.get(ATTR_STATE))

    def _convert(self, value: Any) -> Any:
        """Wert passend zur Geräteklasse umwandeln; Unpassendes wird zu „unbekannt“."""
        if value is None:
            return None
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
            parsed: datetime | None = dt_util.parse_datetime(str(value))
            if parsed is None:
                return self._invalid(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_util.UTC)
        if self._attr_device_class == SensorDeviceClass.DATE:
            parsed_date: date | None = dt_util.parse_date(str(value))
            return parsed_date if parsed_date is not None else self._invalid(value)
        if self._attr_native_unit_of_measurement or self._attr_state_class:
            # Messwerte müssen numerisch sein, sonst verweigert HA den Zustand
            try:
                return float(value) if not isinstance(value, bool) else self._invalid(value)
            except (TypeError, ValueError):
                return self._invalid(value)
        if isinstance(value, bool):
            return "on" if value else "off"
        return value

    def _invalid(self, value: Any) -> None:
        _LOGGER.warning(
            "%s: Wert %r passt nicht zur Konfiguration, wird ignoriert", self.entity_id or self.unique_id, value
        )
        return None

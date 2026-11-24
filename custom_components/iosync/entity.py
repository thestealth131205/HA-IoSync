"""Gemeinsame Basis der IoSync-Entitäten."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_ATTRIBUTES,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_CATEGORY,
    ATTR_ICON,
    ATTR_KEY,
    ATTR_NAME,
    DOMAIN,
)
from .hub import IoSyncHub


class IoSyncEntity(Entity):
    """Entität, deren Beschreibung und Wert vollständig von der App kommen."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: IoSyncHub, skey: str) -> None:
        self._hub = hub
        self._skey = skey
        data = hub.sensors[skey]
        self._attr_unique_id = f"{data[ATTR_DEVICE_ID]}_{data[ATTR_KEY]}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, data[ATTR_DEVICE_ID])})
        self._apply(data)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._hub.async_add_listener(self._skey, self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self._apply(self._hub.sensors[self._skey])
        self.async_write_ha_state()

    @callback
    def _apply(self, data: dict[str, Any]) -> None:
        self._attr_name = data[ATTR_NAME]
        self._attr_icon = data.get(ATTR_ICON)
        category = data.get(ATTR_ENTITY_CATEGORY)
        self._attr_entity_category = EntityCategory(category) if category else None
        self._attr_extra_state_attributes = data.get(ATTR_ATTRIBUTES) or {}

"""HTTP-Schnittstelle für die IoSync-App.

Die App authentifiziert sich mit dem Langzeit-Token, den sie ohnehin für Home Assistant
nutzt. Ist die Integration nicht eingerichtet, antworten beide Endpunkte mit 404 – die App
fällt dann auf ihren alten Weg (mobile_app) zurück.

POST /api/iosync/update
{
  "device":  {"id": "…", "name": "Healthy", "manufacturer": "…", "model": "…", "sw_version": "…"},
  "sensors": [{"key": "sleeping", "type": "binary_sensor", "name": "Schlaf", "state": true,
               "icon": "mdi:sleep", "device_class": null, "unit": null, "state_class": null,
               "entity_category": null, "attributes": {…}}],
  "events":  [{"type": "…", "data": {…}}]
}
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import (
    API_VERSION,
    ATTR_ATTRIBUTES,
    ATTR_DATA,
    ATTR_DEVICE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_CATEGORY,
    ATTR_EVENTS,
    ATTR_ICON,
    ATTR_ID,
    ATTR_KEY,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SENSORS,
    ATTR_STATE,
    ATTR_STATE_CLASS,
    ATTR_SW_VERSION,
    ATTR_TYPE,
    ATTR_UNIT,
    DOMAIN,
    TYPE_BINARY_SENSOR,
    TYPE_SENSOR,
    TYPES,
    URL_INFO,
    URL_UPDATE,
)
from .hub import IoSyncHub

_DEVICE_CLASSES = {
    TYPE_SENSOR: {c.value for c in SensorDeviceClass},
    TYPE_BINARY_SENSOR: {c.value for c in BinarySensorDeviceClass},
}

_OPT_STR = vol.Any(None, vol.All(str, vol.Length(max=255)))


def _check_sensor(sensor: dict[str, Any]) -> dict[str, Any]:
    device_class = sensor.get(ATTR_DEVICE_CLASS)
    if device_class is not None and device_class not in _DEVICE_CLASSES[sensor[ATTR_TYPE]]:
        raise vol.Invalid(f"unbekannte device_class '{device_class}' für {sensor[ATTR_TYPE]}")
    if sensor[ATTR_TYPE] == TYPE_BINARY_SENSOR and (
        sensor.get(ATTR_UNIT) is not None or sensor.get(ATTR_STATE_CLASS) is not None
    ):
        raise vol.Invalid("binary_sensor unterstützt weder unit noch state_class")
    return sensor


SENSOR_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_KEY): vol.All(str, vol.Match(r"^[a-z0-9_]{1,64}$")),
            vol.Required(ATTR_TYPE): vol.In(TYPES),
            vol.Required(ATTR_NAME): vol.All(str, vol.Length(min=1, max=100)),
            vol.Optional(ATTR_STATE): vol.Any(None, bool, int, float, vol.All(str, vol.Length(max=255))),
            vol.Optional(ATTR_ICON): vol.Any(None, vol.All(str, vol.Match(r"^mdi:[a-z0-9-]+$"))),
            vol.Optional(ATTR_DEVICE_CLASS): _OPT_STR,
            vol.Optional(ATTR_UNIT): _OPT_STR,
            vol.Optional(ATTR_STATE_CLASS): vol.Any(None, vol.In([c.value for c in SensorStateClass])),
            vol.Optional(ATTR_ENTITY_CATEGORY): vol.Any(None, vol.In([c.value for c in EntityCategory])),
            vol.Optional(ATTR_ATTRIBUTES, default=dict): dict,
        },
        extra=vol.REMOVE_EXTRA,
    ),
    _check_sensor,
)

EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TYPE): vol.All(str, vol.Match(r"^[a-z0-9_]{1,64}$")),
        vol.Optional(ATTR_DATA, default=dict): dict,
    },
    extra=vol.REMOVE_EXTRA,
)

UPDATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE): vol.Schema(
            {
                vol.Required(ATTR_ID): vol.All(str, vol.Match(r"^[A-Za-z0-9_-]{1,64}$")),
                vol.Required(ATTR_NAME): vol.All(str, vol.Length(min=1, max=100)),
                vol.Optional(ATTR_MANUFACTURER): _OPT_STR,
                vol.Optional(ATTR_MODEL): _OPT_STR,
                vol.Optional(ATTR_SW_VERSION): _OPT_STR,
            },
            extra=vol.REMOVE_EXTRA,
        ),
        vol.Optional(ATTR_SENSORS, default=list): vol.All([SENSOR_SCHEMA], vol.Length(max=100)),
        vol.Optional(ATTR_EVENTS, default=list): vol.All([EVENT_SCHEMA], vol.Length(max=20)),
    },
    extra=vol.REMOVE_EXTRA,
)


def _hub(hass: HomeAssistant) -> IoSyncHub | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


class IoSyncInfoView(HomeAssistantView):
    """Lässt die App prüfen, ob die Integration installiert und eingerichtet ist."""

    url = URL_INFO
    name = "api:iosync:info"

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        if _hub(hass) is None:
            return self.json_message("IoSync-Integration nicht eingerichtet", HTTPStatus.NOT_FOUND)
        integration = await async_get_integration(hass, DOMAIN)
        return self.json({"api_version": API_VERSION, "version": str(integration.version)})


class IoSyncUpdateView(HomeAssistantView):
    """Nimmt Sensorwerte und Ereignisse der App entgegen."""

    url = URL_UPDATE
    name = "api:iosync:update"

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        hub = _hub(hass)
        if hub is None:
            return self.json_message("IoSync-Integration nicht eingerichtet", HTTPStatus.NOT_FOUND)
        try:
            payload = UPDATE_SCHEMA(await request.json())
        except ValueError:
            return self.json_message("Ungültiges JSON", HTTPStatus.BAD_REQUEST)
        except vol.Invalid as err:
            return self.json_message(f"Ungültige Daten: {err}", HTTPStatus.BAD_REQUEST)
        count = hub.async_handle_update(payload)
        return self.json({"success": True, "sensors": count, "api_version": API_VERSION})

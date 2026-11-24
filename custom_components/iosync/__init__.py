"""IoSync – Daten der IoSync-App (Android/Wear OS) in Home Assistant.

Erster Anwendungsfall: Schlaf-/Wachstatus der Healthy-Uhr-App. Die App beschreibt ihre
Sensoren selbst, weitere Werte kommen ohne Update dieser Integration dazu.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .hub import IoSyncHub
from .views import IoSyncInfoView, IoSyncUpdateView

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type IoSyncConfigEntry = ConfigEntry[IoSyncHub]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    # Views lassen sich nicht abmelden → einmalig registrieren; ohne geladene
    # Config-Entry antworten sie mit 404.
    hass.http.register_view(IoSyncInfoView())
    hass.http.register_view(IoSyncUpdateView())
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IoSyncConfigEntry) -> bool:
    hub = IoSyncHub(hass, entry)
    await hub.async_load()
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IoSyncConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_flush()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: IoSyncConfigEntry) -> None:
    await IoSyncHub(hass, entry).async_remove_store()


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: IoSyncConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Löschen eines Geräts in der HA-Oberfläche erlauben."""
    for domain, device_id in device.identifiers:
        if domain == DOMAIN:
            entry.runtime_data.async_remove_device(device_id)
    return True

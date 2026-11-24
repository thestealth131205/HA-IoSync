"""Tests der IoSync-Integration (HTTP-Schnittstelle, Entitäten, Speicher)."""

from http import HTTPStatus

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.iosync.const import DOMAIN, EVENT_IOSYNC

DEVICE = {"id": "1b2c3d4e-0000-4000-8000-000000000001", "name": "Healthy",
          "manufacturer": "letheapp", "model": "Schlafstatus Uhr", "sw_version": "5.3.1"}


def sleep_payload(sleeping: bool, **extra):
    return {
        "device": DEVICE,
        "sensors": [
            {"key": "healthy_sleeping", "type": "binary_sensor", "name": "Schlaf", "state": sleeping,
             "icon": "mdi:sleep" if sleeping else "mdi:sleep-off", "device_class": None,
             "attributes": {"status": "schläft" if sleeping else "wach"}},
            {"key": "healthy_sleep_start", "type": "sensor", "name": "Eingeschlafen",
             "state": "2026-11-23T22:41:00Z", "icon": "mdi:bed-clock", "device_class": "timestamp"},
            {"key": "healthy_sleep_end", "type": "sensor", "name": "Aufgewacht",
             "state": None, "icon": "mdi:weather-sunset-up", "device_class": "timestamp"},
        ],
        **extra,
    }


@pytest.fixture
async def entry(hass: HomeAssistant) -> MockConfigEntry:
    assert await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(domain=DOMAIN, title="IoSync", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_single_instance(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_info_and_auth(hass: HomeAssistant, entry, hass_client, hass_client_no_auth) -> None:
    client = await hass_client()
    resp = await client.get("/api/iosync")
    assert resp.status == HTTPStatus.OK
    assert (await resp.json())["api_version"] == 1

    anon = await hass_client_no_auth()
    resp = await anon.post("/api/iosync/update", json=sleep_payload(True))
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_update_creates_and_updates_entities(hass: HomeAssistant, entry, hass_client) -> None:
    client = await hass_client()
    events = async_capture_events(hass, EVENT_IOSYNC)

    resp = await client.post("/api/iosync/update", json=sleep_payload(True, events=[{"type": "fell_asleep"}]))
    assert resp.status == HTTPStatus.OK, await resp.text()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.healthy_schlaf")
    assert state.state == "on"
    assert state.attributes["status"] == "schläft"
    assert state.attributes["icon"] == "mdi:sleep"
    assert hass.states.get("sensor.healthy_eingeschlafen").state == "2026-11-23T22:41:00+00:00"
    assert hass.states.get("sensor.healthy_aufgewacht").state == "unknown"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, DEVICE["id"])})
    assert device.name == "Healthy" and device.sw_version == "5.3.1"
    assert len(events) == 1 and events[0].data["device_id"] == device.id
    assert events[0].data["type"] == "fell_asleep"

    resp = await client.post("/api/iosync/update", json=sleep_payload(False))
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.healthy_schlaf").state == "off"
    assert hass.states.get("binary_sensor.healthy_schlaf").attributes["icon"] == "mdi:sleep-off"


async def test_numeric_sensor(hass: HomeAssistant, entry, hass_client) -> None:
    client = await hass_client()
    payload = {"device": DEVICE, "sensors": [
        {"key": "heart_rate", "type": "sensor", "name": "Puls", "state": 62,
         "unit": "bpm", "state_class": "measurement"},
        {"key": "heart_rate_text", "type": "sensor", "name": "Puls kaputt", "state": "abc", "unit": "bpm"},
    ]}
    resp = await client.post("/api/iosync/update", json=payload)
    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()
    assert hass.states.get("sensor.healthy_puls").state == "62.0"
    assert hass.states.get("sensor.healthy_puls_kaputt").state == "unknown"


@pytest.mark.parametrize(
    "payload",
    [
        {"sensors": []},
        {"device": DEVICE, "sensors": [{"key": "x", "type": "switch", "name": "X"}]},
        {"device": DEVICE, "sensors": [{"key": "Bad Key", "type": "sensor", "name": "X"}]},
        {"device": DEVICE, "sensors": [{"key": "x", "type": "sensor", "name": "X", "device_class": "nope"}]},
        {"device": DEVICE, "sensors": [{"key": "x", "type": "binary_sensor", "name": "X", "unit": "°C"}]},
    ],
)
async def test_invalid_payload(hass: HomeAssistant, entry, hass_client, payload) -> None:
    client = await hass_client()
    resp = await client.post("/api/iosync/update", json=payload)
    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_not_set_up_returns_404(hass: HomeAssistant, entry, hass_client) -> None:
    assert await hass.config_entries.async_unload(entry.entry_id)
    client = await hass_client()
    assert (await client.get("/api/iosync")).status == HTTPStatus.NOT_FOUND
    assert (await client.post("/api/iosync/update", json=sleep_payload(True))).status == HTTPStatus.NOT_FOUND


async def test_state_survives_reload(hass: HomeAssistant, entry, hass_client) -> None:
    client = await hass_client()
    await client.post("/api/iosync/update", json=sleep_payload(True))
    await hass.async_block_till_done()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.healthy_schlaf").state == "on"

    # Nach dem Neuladen gehen Updates weiter an dieselbe Entität
    await client.post("/api/iosync/update", json=sleep_payload(False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.healthy_schlaf").state == "off"


async def test_remove_device(hass: HomeAssistant, entry, hass_client, hass_ws_client) -> None:
    assert await async_setup_component(hass, "config", {})
    ws = await hass_ws_client(hass)  # vor hass_client, sonst ist der Router schon eingefroren
    client = await hass_client()
    await client.post("/api/iosync/update", json=sleep_payload(True))
    await hass.async_block_till_done()

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, DEVICE["id"])})
    await ws.send_json({"id": 1, "type": "config/device_registry/remove_config_entry",
                        "config_entry_id": entry.entry_id, "device_id": device.id})
    assert (await ws.receive_json())["success"]
    await hass.async_block_till_done()
    assert dr.async_get(hass).async_get(device.id) is None
    assert er.async_get(hass).async_get("binary_sensor.healthy_schlaf") is None
    assert entry.runtime_data.sensors == {}

    # App meldet erneut → alles wird neu angelegt
    await client.post("/api/iosync/update", json=sleep_payload(False))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.healthy_schlaf").state == "off"

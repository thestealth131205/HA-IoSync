"""Konstanten für die IoSync-Integration."""

DOMAIN = "iosync"

# Version der HTTP-Schnittstelle zur App. Erhöhen, wenn sich das Format inkompatibel ändert.
API_VERSION = 1

URL_INFO = "/api/iosync"
URL_UPDATE = "/api/iosync/update"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
SAVE_DELAY = 10  # Sekunden; mehrere Meldungen kurz nacheinander → ein Schreibvorgang

EVENT_IOSYNC = "iosync_event"

TYPE_SENSOR = "sensor"
TYPE_BINARY_SENSOR = "binary_sensor"
TYPES = [TYPE_SENSOR, TYPE_BINARY_SENSOR]

# Felder im Payload der App
ATTR_DEVICE = "device"
ATTR_SENSORS = "sensors"
ATTR_EVENTS = "events"
ATTR_ID = "id"
ATTR_NAME = "name"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_SW_VERSION = "sw_version"
ATTR_KEY = "key"
ATTR_TYPE = "type"
ATTR_STATE = "state"
ATTR_ICON = "icon"
ATTR_DEVICE_CLASS = "device_class"
ATTR_UNIT = "unit"
ATTR_STATE_CLASS = "state_class"
ATTR_ENTITY_CATEGORY = "entity_category"
ATTR_ATTRIBUTES = "attributes"
ATTR_DATA = "data"
ATTR_DEVICE_ID = "device_id"
ATTR_UPDATED = "updated"

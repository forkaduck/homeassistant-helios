"""Constants for the Helios easyControls integration."""

DOMAIN = "helios"
DEFAULT_NAME = "Helios"

CONF_PASSWORD = "password"
DEFAULT_PASSWORD = "!helios!"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 20
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 600

# easyControls batch pages (full page map in helioslib/variables.py).
PAGE_SENSORS = 8      # all sensor + fan values: 103 variables, ONE request
PAGE_IDENTITY = 20    # device type, article, MAC, serial
PAGE_VERSION = 11     # firmware versions

# (key, name, variable, unit, device_class, icon)
SENSOR_DEFINITIONS = [
    ("outside_air", "Outside Air", "v00104", "°C", "temperature", None),
    ("supply_air", "Supply Air", "v00105", "°C", "temperature", None),
    ("extract_air", "Extract Air", "v00106", "°C", "temperature", None),
    ("exhaust_air", "Exhaust Air", "v00107", "°C", "temperature", None),
    ("extract_humidity", "Extract Air Humidity", "v02136", "%", "humidity", None),
    ("supply_rpm", "Supply Air Speed", "v00348", "rpm", None, "mdi:fan"),
    ("extract_rpm", "Extract Air Speed", "v00349", "rpm", None, "mdi:fan"),
    ("fan_stage", "Fan Speed", "v00102", None, None, "mdi:fan"),
    ("fan_percentage", "Fan Percentage", "v00103", "%", None, "mdi:fan"),
]

# The unit's own percentage per stage (v00103), measured live:
# stage 0 = 0 % (standby), 1 = 40 %, 2 = 60 %, 3 = 80 %, 4 = 100 %.
FAN_STAGE_PERCENTAGES = {0: 0, 1: 40, 2: 60, 3: 80, 4: 100}

# (key_prefix, name, first variable number, unit, device_class, icon)
EXTERNAL_SENSOR_BLOCKS = [
    ("ext_humidity", "External Humidity", 111, "%",
     "humidity", "mdi:water-percent"),
    ("ext_temperature", "External Temperature", 119, "°C",
     "temperature", None),
    ("ext_co2", "External CO2", 128, "ppm",
     "carbon_dioxide", "mdi:molecule-co2"),
    ("ext_voc", "Gas concentration", 136, "ppm", None, "mdi:gas-cylinder"),
]
EXTERNAL_SENSOR_COUNT = 8

# Fan mapping (easyControls stages 0..4).
FAN_MODE = "v00101"   # 0 = automatic, 1 = manual
FAN_STAGE = "v00102"  # 0..4
FAN_PERCENTAGE = "v00103"
FAN_PRESET_MODES = ["Low", "Mid Low", "Mid High", "High"]
BOOST_STAGES = {"off": 0, "low": 1, "medium": 2, "high": 3, "max": 4}

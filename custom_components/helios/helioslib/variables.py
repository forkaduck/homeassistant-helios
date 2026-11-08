"""Variable and page definitions for Helios easyControls KWL units.

The page -> variable map was recorded live against a KWL EC 500W R
(easyControls 2.27 web files) by enumerating the generated ``werteN.xml``
batch pages (``tools/test_client.py -> discover``).

The device generates these pages on the fly: one HTTP POST to
``/data/werteN.xml`` returns every variable of that page as
``<ID>vXXXXX</ID><VA>value</VA>`` pairs.
"""


def _v(*specs):
    """Build a tuple of variable names: ints, (first, last) ranges or strings."""
    out = []
    for spec in specs:
        if isinstance(spec, int):
            out.append("v%05d" % spec)
        elif isinstance(spec, tuple):
            out.extend("v%05d" % i for i in range(spec[0], spec[1] + 1))
        else:
            out.append(str(spec))
    return tuple(out)


# Interesting pages by purpose.
PAGE_IDENTITY = 20  # device type, article, MAC, serial, additional status
PAGE_SENSORS = 8    # ALL sensor + fan values: 103 variables, ONE request
PAGE_FAN = 4        # light fan/status page (14 variables)
PAGE_VERSION = 11   # firmware versions
PAGE_CONFIG = 12    # system configuration (incl. v01200 'Modbus activated')
PAGE_DATETIME = 2
PAGE_ERRORS = 16

# Page -> variables (live discovery, 2026-11-08, strict <ID> extraction).
PAGE_VARIABLES = {
    1: _v(0, 1, 2, 3, 4, 5, 6, 7, 8, (12, 43), 51, 52, 53, 1017, (1071, 1078),
          1306, (2020, 2027), 2103, 2116, 2134, 2137, (2142, 2152)),
    2: _v(3, 4, 5, 6, 7, 8, (12, 43), 51, 52, 53, 1306),
    3: _v(91, 92, 93, 94, 96, 97, 98, 99, 1306),
    4: _v(0, 1, 2, 93, 94, 98, 99, 101, 102, 103, 601, 604, 1020, 1306),
    5: _v(0, 1, 2, 201, (220, 229), 1306, 2122, 2123, 2130, 2131),
    6: _v(601, 602, 603, 604, 605, 606, 1050, 1051, 1306),
    7: _v(0, 1, 2, 303, 304, 343, 1306),
    8: _v(24, 33, 37, 40, 92, 94, 97, 99, 101, 102, 103, (104, 118), (119, 126),
          (128, 143), 144, 146, 201, 348, 349, 601, 602, 1020, 1050, 1051,
          (1071, 1078), (1081, 1088), (1091, 1098), 1300, 1301, 1302, 1306,
          (2020, 2027), 2117, 2118, 2119, 2136, 2137, 2142, 2152),
    9: _v(0, 1, 2, 901, (920, 929), 1306),
    10: _v((1001, 1007), 1306),
    11: _v(3, 4, 5, 6, 7, 8, 51, 52, 348, 349, (1101, 1106), 1108, 1109, 1306,
           2103, 2116, 2134),
    12: _v(21, 22, 23, 24, 53, 201, 1010, 1017, 1019, 1020, 1021, 1031, 1032,
           1033, 1035, 1036, 1037, 1041, 1042, 1200, 1306, 2115, 2120, 2121,
           2128, 2129),
    13: _v((12, 20), 1050, 1051, (1061, 1066), 1068, 1306),
    14: _v((25, 43), (1071, 1078), (1081, 1088), (1091, 1098), 1306, 2137,
           (2142, 2152)),
    15: _v(1306),
    16: _v((1300, 1305), 1306, 2104),
    17: _v(1306),
    20: _v(0, 1, 2, 3, 303, 304, (310, 323), (331, 337), 340, 341, 343, 344,
           345, 346, 347, 348, 349, (350, 357), 1306, 2100, 2101, 2102, 2136,
           2137, 2138, 2139, 2140, (2150, 2154)),
}

# Variable -> page, preferring the lightest page that contains the variable.
PAGE_FOR_VAR = {}
for _page, _vars in sorted(PAGE_VARIABLES.items(), key=lambda kv: len(kv[1])):
    for _var in _vars:
        PAGE_FOR_VAR.setdefault(_var, _page)
del _page, _vars, _var

# Sensor groups (see Helios doc 82269-001 'Modbus Gateway TCP/IP', chapter 4).
FAN_MODE = "v00101"    # 0 = automatic, 1 = manual
FAN_STAGE = "v00102"   # 0..4
FAN_PERCENTAGE = "v00103"
TEMPERATURE_VARS = ("v00104", "v00105", "v00106", "v00107", "v00108",
                    "v00109", "v00110", "v00144", "v00146")
SUPPLY_RPM = "v00348"
EXTRACT_RPM = "v00349"
EXTRACT_HUMIDITY = "v02136"
BYPASS = "v02119"
FILTER_REMAINING = "v01033"
EXT_HUMIDITY_VARS = tuple("v%05d" % i for i in range(111, 119))
EXT_TEMPERATURE_VARS = tuple("v%05d" % i for i in range(119, 127))
EXT_CO2_VARS = tuple("v%05d" % i for i in range(128, 136))
EXT_VOC_VARS = tuple("v%05d" % i for i in range(136, 144))


def valid(value):
    """False for the easyControls 'no value' markers ('' and '-')."""
    return value is not None and value != "" and value.strip() != "-"


def describe_pages():
    """Return the page map in human readable form (used by test_client)."""
    return {page: list(vars_) for page, vars_ in sorted(PAGE_VARIABLES.items())}

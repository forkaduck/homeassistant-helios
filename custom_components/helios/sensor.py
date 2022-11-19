from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import get_helios_var

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    SIGNAL_HELIOS_STATE_UPDATE
)

# Add some of the available sensors to the entity list.
async def async_setup_entry(hass, entry, async_add_entities):
    client = hass.data[DOMAIN]["client"]
    name = hass.data[DOMAIN]["name"] + ' '
    state_proxy = hass.data[DOMAIN]["state_proxy"]

    # Add all the installation independent sensors which every unit should support.
    entries = [
        HeliosTempSensor(client, state_proxy, name + "Outside Air", "temp_outside_air"),
        HeliosTempSensor(client, state_proxy, name + "Supply Air", "temp_supply_air"),
        HeliosTempSensor(client, state_proxy, name + "Extract Air", "temp_extract_air"),
        HeliosTempSensor(client, state_proxy, name + "Exhaust Air", "temp_outgoing_air"),
        HeliosSensor(client, state_proxy, name + "Extract Air Humidity", "v02136", 2, "%", "mdi:water-percent"),
        HeliosSensor(client, state_proxy, name + "Supply Air Speed", "v00348", 4, "rpm", "mdi:fan"),
        HeliosSensor(client, state_proxy, name + "Extract Air Speed", "v00349", 4, "rpm", "mdi:fan"),
        HeliosFanSpeedSensor(state_proxy, name)
    ]

    # Test if any sensors return values.
    for i in range(0, 8):
        current_variable = "v00" + str(128 + i)

        temp = get_helios_var(client, current_variable, 4)
        if isinstance(temp, str):
            if temp != "-":
                entries.append(HeliosSensor(client, state_proxy, name + "External CO2 " + str(i), current_variable, 4, "ppm", "mdi:molecule-co2"))

    # Add all entries from the list above.
    async_add_entities(entries, update_before_add=False)

class HeliosTempSensor(Entity):
    def __init__(self, client, state_proxy, name, metric):
        self._attr_unique_id = state_proxy._base_unique_id + "-" + metric

        self._state = None
        self._name = name
        self._metric = metric
        self._client = client

    def update(self):
        self._state = self._client.get_feature(self._metric)

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS

class HeliosSensor(Entity):
    def __init__(self, client, state_proxy, name, var, var_length, units, icon):
        self._attr_unique_id = state_proxy._base_unique_id + "-" + var

        self._state = None
        self._name = name
        self._variable = var
        self._var_length = var_length
        self._units = units
        self._icon = icon
        self._client = client

    def update(self):
        temp =  get_helios_var(self._client, self._variable, self._var_length)

        if isinstance(temp, str):
            self._state =  int(temp)
        else:
            self._state = 0
        
    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return self._units

class HeliosFanSpeedSensor(Entity):
    def __init__(self, state_proxy, name):
        self._attr_unique_id = state_proxy._base_unique_id + "-FanSpeed"

        self._state_proxy = state_proxy
        self._name = name + "Fan Speed"

    @property
    def should_poll(self):
        return False

    async def async_added_to_hass(self):
        async_dispatcher_connect(
            self.hass, SIGNAL_HELIOS_STATE_UPDATE, self._update_callback
        )

    @callback
    def _update_callback(self):
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state_proxy.get_speed()

    @property
    def icon(self):
        return "mdi:fan"

    @property
    def unit_of_measurement(self):
        return "%"

"""Sensor platform for the Helios easyControls integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    EXTERNAL_SENSOR_BLOCKS,
    EXTERNAL_SENSOR_COUNT,
    SENSOR_DEFINITIONS,
)

_DEVICE_CLASSES = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "carbon_dioxide": SensorDeviceClass.CARBON_DIOXIDE,
}


def _definitions():
    for key, name, var, unit, device_class, icon in SENSOR_DEFINITIONS:
        yield key, name, var, unit, device_class, icon
    for block_key, block_name, start, unit, device_class, icon \
            in EXTERNAL_SENSOR_BLOCKS:
        for index in range(EXTERNAL_SENSOR_COUNT):
            yield ("%s_%d" % (block_key, index),
                   "%s %d" % (block_name, index),
                   "v%05d" % (start + index),
                   unit, device_class, icon)


def _numeric(value):
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "-"):
        return None
    for convert in (int, float):
        try:
            return convert(text)
        except ValueError:
            continue
    return text


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    mac = (data["device"] or {}).get("v00002") or ""
    base_unique_id = format_mac(mac) if mac else entry.entry_id

    known = coordinator.data or {}
    entities = [
        HeliosSensor(coordinator, data, base_unique_id,
                     key, name, var, unit, device_class, icon)
        for key, name, var, unit, device_class, icon in _definitions()
        if var in known
    ]
    async_add_entities(entities)


class HeliosSensor(CoordinatorEntity, SensorEntity):
    """One easyControls variable, fed by the shared coordinator."""

    def __init__(self, coordinator, data, base_unique_id,
                 key, name, var, unit, device_class, icon):
        super().__init__(coordinator)
        self._var = var
        self._data = data
        self._base_unique_id = base_unique_id
        self._attr_unique_id = "%s-%s" % (base_unique_id, key)
        self._attr_name = "%s %s" % (data["name"], name)
        if unit:
            self._attr_native_unit_of_measurement = unit
        if icon:
            self._attr_icon = icon
        if device_class:
            self._attr_device_class = _DEVICE_CLASSES[device_class]
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "rpm":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return _numeric((self.coordinator.data or {}).get(self._var))

    @property
    def available(self) -> bool:
        return self.native_value is not None and super().available

    @property
    def device_info(self) -> DeviceInfo:
        device = self._data["device"] or {}
        versions = self._data["versions"] or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._base_unique_id)},
            name=self._data["name"],
            manufacturer="Helios",
            model=device.get("v00000"),
            sw_version=versions.get("v01101"),
        )

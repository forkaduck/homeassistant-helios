"""Support for Helios ventilation units (easyControls web interface)."""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BOOST_STAGES,
    CONF_SCAN_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PAGE_SENSORS,
)
from .helioslib import HeliosAuthError, HeliosClient, HeliosError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "fan"]

BOOST_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_ids,
    vol.Required("speed"): vol.In(BOOST_STAGES),
    vol.Optional("duration", default=60): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=720)),
})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant,
                            entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    client = HeliosClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PASSWORD) or DEFAULT_PASSWORD,
    )

    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    async def async_update_data():
        """Poll ONE batch page (103 variables) instead of per variable."""
        try:
            return await hass.async_add_executor_job(
                client.get_page, PAGE_SENSORS)
        except HeliosAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HeliosError as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN} {entry.data.get(CONF_NAME, DOMAIN)}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=interval),
    )

    await coordinator.async_config_entry_first_refresh()

    try:
        device = await hass.async_add_executor_job(client.identify)
        versions = await hass.async_add_executor_job(client.versions)
    except HeliosError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "name": entry.data.get(CONF_NAME, DOMAIN),
        "device": device,
        "versions": versions,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_fan_boost(hass)
    return True


async def _async_update_listener(hass: HomeAssistant,
                                 entry: ConfigEntry) -> None:
    """Reload the entry when its options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant,
                             entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "fan_boost")
    return unload_ok


def _register_fan_boost(hass: HomeAssistant) -> None:
    """Register helios.fan_boost (temporary fan speed)."""
    if hass.services.has_service(DOMAIN, "fan_boost"):
        return

    async def handle_fan_boost(call: ServiceCall) -> None:
        entity_ids = call.data["entity_id"]
        stage = BOOST_STAGES[call.data["speed"]]
        duration = call.data["duration"]
        for data in hass.data[DOMAIN].values():
            fan = data.get("fan")
            if fan is not None and fan.entity_id in entity_ids:
                await fan.async_boost(stage, duration)

    hass.services.async_register(
        DOMAIN, "fan_boost", handle_fan_boost, schema=BOOST_SCHEMA)

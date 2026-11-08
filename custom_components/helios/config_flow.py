"""Config flow for the Helios easyControls integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import callback

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .helioslib import HeliosAuthError, HeliosClient, HeliosError


class HeliosConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for one Helios unit."""

    VERSION = 1

    @staticmethod
    def _schema(defaults):
        return vol.Schema({
            vol.Required(CONF_NAME,
                         default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_HOST,
                         default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(
                CONF_PASSWORD,
                default=defaults.get(CONF_PASSWORD, DEFAULT_PASSWORD),
            ): str,
        })

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._async_validate(user_input)
            except HeliosAuthError:
                errors["base"] = "invalid_auth"
            except HeliosError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(user_input or {}),
            errors=errors,
        )

    async def _async_validate(self, user_input):
        client = HeliosClient(
            user_input[CONF_HOST],
            user_input.get(CONF_PASSWORD) or DEFAULT_PASSWORD,
            timeout=6,
        )
        await self.hass.async_add_executor_job(client.login)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HeliosOptionsFlow(config_entry)


class HeliosOptionsFlow(config_entries.OptionsFlow):
    """Options: polling interval (the unit is slow - keep >= 20 s)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
        })
        return self.async_show_form(step_id="user", data_schema=schema)

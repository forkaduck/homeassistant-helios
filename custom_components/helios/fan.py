"""Fan platform for the Helios easyControls integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    FAN_MODE,
    FAN_PRESET_MODES,
    FAN_STAGE,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                           async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    mac = (data["device"] or {}).get("v00002") or ""
    base_unique_id = format_mac(mac) if mac else entry.entry_id
    fan = HeliosFan(data["coordinator"], data, base_unique_id)
    data["fan"] = fan
    async_add_entities([fan])


class HeliosFan(CoordinatorEntity, FanEntity):
    """Fan entity mapping the easyControls stages 0..4.

    ``on`` = manual mode (v00101 = 1), ``off`` = automatic mode, like
    the original integration. All writes are write-on-change and are
    batched into a single request.
    """

    def __init__(self, coordinator, data, base_unique_id):
        super().__init__(coordinator)
        self._data = data
        self._client = data["client"]
        self._base_unique_id = base_unique_id
        self._boost_unsub = None
        self._attr_unique_id = "%s-fan" % base_unique_id
        self._attr_name = data["name"]
        self._attr_icon = "mdi:air-filter"
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        self._attr_preset_modes = FAN_PRESET_MODES
        self._attr_speed_count = 4

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

    def _value(self, var):
        value = (self.coordinator.data or {}).get(var)
        return value.strip() if isinstance(value, str) else value

    def _stage(self):
        try:
            return int(float(self._value(FAN_STAGE)))
        except (TypeError, ValueError):
            return None

    @property
    def is_on(self) -> bool:
        return self._value(FAN_MODE) == "1"

    @property
    def preset_mode(self) -> Optional[str]:
        """Active preset while in manual mode (stage 1..4)."""
        if self.is_on:
            stage = self._stage()
            if stage is not None and 1 <= stage <= len(FAN_PRESET_MODES):
                return FAN_PRESET_MODES[stage - 1]
        return None

    @property
    def percentage(self) -> Optional[int]:
        stage = self._stage()
        return None if stage is None else stage * 25

    async def async_set_percentage(self, percentage: int) -> None:
        await self._async_apply_stage(round(percentage / 25.0))

    async def async_turn_on(self, percentage: Optional[int] = None,
                            preset_mode: Optional[str] = None,
                            **kwargs: Any) -> None:
        changes = {}
        if self._value(FAN_MODE) != "1":
            changes[FAN_MODE] = 1
        if preset_mode is not None:
            changes[FAN_STAGE] = FAN_PRESET_MODES.index(preset_mode) + 1
        elif percentage is not None:
            changes[FAN_STAGE] = round(percentage / 25.0)
        await self._async_write(changes)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on:
            await self._async_write({FAN_MODE: 0})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._async_apply_stage(FAN_PRESET_MODES.index(preset_mode) + 1)

    async def _async_apply_stage(self, stage: int) -> None:
        stage = max(0, min(4, int(stage)))
        changes = {}
        if self._value(FAN_MODE) != "1":
            changes[FAN_MODE] = 1
        current = self._stage()
        if current is None or current != stage:
            changes[FAN_STAGE] = stage
        await self._async_write(changes)

    async def _async_write(self, changes: dict) -> None:
        """Write-on-change: ONE request even for mode + stage changes."""
        if not changes:
            return
        await self.hass.async_add_executor_job(
            self._client.set_variables, changes)
        await self.coordinator.async_request_refresh()

    async def async_boost(self, stage: int, duration_minutes: int) -> None:
        """Service handler: temporary boost stage, then restore."""
        if self._boost_unsub is not None:
            self._boost_unsub()
            self._boost_unsub = None
        previous_stage = self._stage()
        await self._async_apply_stage(stage)
        if previous_stage is None:
            return

        async def _restore(_now):
            self._boost_unsub = None
            await self._async_apply_stage(previous_stage)

        self._boost_unsub = async_call_later(
            self.hass, timedelta(minutes=duration_minutes), _restore)

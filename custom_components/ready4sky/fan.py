#!/usr/local/bin/python3
# coding: utf-8

from homeassistant.components.fan import (
    SUPPORT_SET_SPEED,
    FanEntity,
    FanEntityDescription
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SIGNAL_UPDATE_DATA, STATUS_ON, MODE_BOIL


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    kettle = hass.data[DOMAIN][config_entry.entry_id]
    if kettle._type == 3:
        async_add_entities([RedmondFan(kettle)])


class RedmondFan(FanEntity):
    def __init__(self, kettle):
        self._kettle = kettle
        self.entity_description = FanEntityDescription(
            key="fan_on",
            name=kettle._name + " Fan",
            icon="mdi:fan",
        )

        self._attr_unique_id = f'{DOMAIN}[{kettle._mac}][fan][{self.entity_description.key}]'
        self._attr_device_info = DeviceInfo(connections={("mac", kettle._mac)})

        self._attr_is_on = False
        # self._perc = 0
        self._speed = '01'

    async def async_added_to_hass(self):
        self.update()
        self.async_on_remove(async_dispatcher_connect(self._kettle.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._attr_is_on = False
        if self._kettle._mode == MODE_BOIL:
            self._speed = '01'
        else:
            self._speed = self._kettle._mode
        #        if self._kettler._mode == '00' or not self._kettler._status == STATUS_ON:
        #            self._perc = 0
        #        else:
        #            self._perc = ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, self._kettler._mode)
        if self._kettle._status == STATUS_ON:
            self._attr_is_on = True
        self.schedule_update_ha_state()

    #    async def async_set_percentage(self, percentage: int) -> None:
    #        if percentage == 0:
    #            await self.async_turn_off()
    #        else:
    #            speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
    #            await self._kettler.modeFan(speed)

    async def async_set_speed(self, speed: str) -> None:
        if speed == '00':
            await self._kettle.modeOff()
        else:
            await self._kettle.modeFan(speed)

    async def async_turn_on(self, speed: str = None, percentage: int = None, preset_mode: str = None, **kwargs, ) -> None:
        if speed is not None:
            await self.async_set_speed(speed)
        else:
            await self.async_set_speed('01')

    #        if percentage is not None:
    #            await self.async_set_percentage(percentage)
    #        else:
    #            await self.async_set_percentage(0)

    async def async_turn_off(self, **kwargs) -> None:
        await self._kettle.modeOff()

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self._kettle._available

    @property
    def speed(self):
        return self._speed

    @property
    def speed_list(self):
        return ['01', '02', '03', '04', '05', '06']

    #    @property
    #    def percentage(self) -> int:
    #        return self._perc

    @property
    def supported_features(self) -> int:
        return SUPPORT_SET_SPEED

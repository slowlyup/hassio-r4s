#!/usr/local/bin/python3
# coding: utf-8

from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    ATTR_BRIGHTNESS,
    LightEntity,
    ColorMode,
    LightEntityDescription
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from . import (
    DOMAIN,
    SIGNAL_UPDATE_DATA,
    MODE_LIGHT,
    STATUS_ON
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    kettle = hass.data[DOMAIN][config_entry.entry_id]

    if kettle._type in [1, 2]:
        async_add_entities([RedmondNightlight(kettle)], True)


class RedmondNightlight(LightEntity):
    def __init__(self, kettle):
        self._kettle = kettle
        self.entity_description = LightEntityDescription(
            key="nightlight_on",
            name=kettle._name + " Nightlight",
            icon="mdi:floor-lamp",
        )

        self._attr_unique_id = f'{DOMAIN}[{kettle._mac}][light][{self.entity_description.key}]'
        self._attr_device_info = DeviceInfo(connections={("mac", kettle._mac)})

        self._rgb_color = kettle._rgb1
        self._attr_is_on = False

    async def async_added_to_hass(self):
        self.update()
        self.async_on_remove(async_dispatcher_connect(self._kettle.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._rgb_color = self._kettle._rgb1
        self._attr_is_on = False

        if self._kettle._status == STATUS_ON and self._kettle._mode == MODE_LIGHT:
            self._attr_is_on = True

        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self._kettle._available

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._rgb_color

    @property
    def brightness(self):
        return self._kettle._nightlight_brightness

    @property
    def color_mode(self) -> ColorMode:
        return ColorMode.RGB

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported color modes."""
        return {self.color_mode}

    async def async_turn_on(self, **kwargs):
        self._rgb_color = kwargs.get(ATTR_RGB_COLOR, self._rgb_color)
        self._kettle._nightlight_brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        self._kettle._rgb1 = self._rgb_color

        await self._kettle.startNightColor()

    async def async_turn_off(self, **kwargs):
        await self._kettle.modeOff()

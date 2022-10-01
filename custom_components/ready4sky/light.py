#!/usr/local/bin/python3
# coding: utf-8

from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    ATTR_BRIGHTNESS,
    LightEntity,
    ColorMode
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_UPDATE_DATA


async def async_setup_entry(hass, config_entry, async_add_entities):
    kettler = hass.data[DOMAIN][config_entry.entry_id]

    if kettler._type in [1, 2]:
        async_add_entities([RedmondLight(kettler)], True)


class RedmondLight(LightEntity):
    def __init__(self, kettler):
        self._name = 'Light ' + kettler._name
        self._rgb_color = kettler._rgb1
        self._icon = 'mdi:floor-lamp'
        self._kettler = kettler
        self._ison = False

    async def async_added_to_hass(self):
        self._handle_update()
        self.async_on_remove(async_dispatcher_connect(self._kettler.hass, SIGNAL_UPDATE_DATA, self._handle_update))

    def _handle_update(self):
        self._rgb_color = self._kettler._rgb1
        self._ison = False

        if self._kettler._status == '02' and self._kettler._mode == '03':
            self._ison = True

        self.schedule_update_ha_state()

    @property
    def device_info(self):
        return {
            "connections": {
                ("mac", self._kettler._mac)
            }
        }

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def is_on(self):
        return self._ison

    @property
    def available(self):
        return self._kettler._available

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._rgb_color

    @property
    def brightness(self):
        return self._kettler._nightlight_brightness

    @property
    def color_mode(self) -> ColorMode | None:
        return ColorMode.RGB

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported color modes."""
        return {self.color_mode}

    async def async_turn_on(self, **kwargs):
        self._rgb_color = kwargs.get(ATTR_RGB_COLOR, self._rgb_color)
        self._kettler._nightlight_brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        self._kettler._rgb1 = self._rgb_color

        await self._kettler.startNightColor()

    async def async_turn_off(self, **kwargs):
        await self._kettler.modeOff()

    @property
    def unique_id(self):
        return f'{DOMAIN}[{self._kettler._mac}][{self._name}]'

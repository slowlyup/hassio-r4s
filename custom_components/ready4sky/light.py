#!/usr/local/bin/python3
# coding: utf-8

from homeassistant.components.light import (
    ATTR_HS_COLOR,
    ATTR_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
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
        self._hs = (0, 0)
        self._icon = 'mdi:floor-lamp'
        self._kettler = kettler
        self._ison = False
        self._hs = None

    async def async_added_to_hass(self):
        self._handle_update()
        self.async_on_remove(async_dispatcher_connect(self._kettler.hass, SIGNAL_UPDATE_DATA, self._handle_update))

    def _handle_update(self):
        self._hs = self._kettler.rgbhex_to_hs(self._kettler._rgb1)
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
        return True

    @property
    def hs_color(self):
        return self._hs

    @property
    def brightness(self):
        return self._kettler._nightlight_brightness

    @property
    def supported_features(self):
        return SUPPORT_COLOR

    async def async_turn_on(self, **kwargs):
        self._hs = kwargs.get(ATTR_HS_COLOR, self._hs)
        self._kettler._nightlight_brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._kettler._rgb1 = self._kettler.hs_to_rgbhex(self._hs)

        await self._kettler.startNightColor()

    async def async_turn_off(self, **kwargs):
        await self._kettler.modeOff()

    @property
    def unique_id(self):
        return f'{DOMAIN}[{self._kettler._mac}][{self._name}]'

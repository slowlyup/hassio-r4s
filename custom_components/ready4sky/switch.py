#!/usr/local/bin/python3
# coding: utf-8

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from . import DOMAIN, SIGNAL_UPDATE_DATA, RedmondKettler, MODE_BOIL


async def async_setup_entry(hass, config_entry, async_add_entities):
    kettle = hass.data[DOMAIN][config_entry.entry_id]

    if kettle._type in [1, 2]:
        async_add_entities([
            RedmondConfSwitchSound(kettle)
        ])
    elif kettle._type == 3:
        async_add_entities([
            RedmondSwitchIon(kettle)
        ])
    elif kettle._type == 4:
        async_add_entities([
            RedmondSwitch(kettle)
        ])


class RedmondSwitch(SwitchEntity):
    def __init__(self, kettler: RedmondKettler):
        self._name = 'Switch ' + kettler._name
        self._icon = 'mdi:air-filter'
        self._kettler = kettler
        self._ison = False

    async def async_added_to_hass(self):
        self.update()
        self.async_on_remove(async_dispatcher_connect(self._kettler.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._ison = False
        if self._kettler._status == '02' and self._kettler._mode == MODE_BOIL:
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

    async def async_turn_on(self, **kwargs):
        await self._kettler.modeOn()

    async def async_turn_off(self, **kwargs):
        await self._kettler.modeOff()

    @property
    def unique_id(self):
        return f'{DOMAIN}[{self._kettler._mac}][{self._name}]'


class RedmondSwitchIon(SwitchEntity):

    def __init__(self, kettler):
        self._name = 'Switch ' + kettler._name
        self._icon = 'mdi:flash'
        self._kettler = kettler
        self._ison = False

    async def async_added_to_hass(self):
        self.update()
        self.async_on_remove(async_dispatcher_connect(self._kettler.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._ison = False
        if self._kettler._ion == '01':
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

    async def async_turn_on(self, **kwargs):
        await self._kettler.modeIon('01')

    async def async_turn_off(self, **kwargs):
        await self._kettler.modeIon('00')

    @property
    def unique_id(self):
        return f'{DOMAIN}[{self._kettler._mac}][{self._name}]'


class RedmondConfSwitchSound(SwitchEntity):
    def __init__(self, kettle: RedmondKettler):
        self._name = 'Switch ' + kettle._name + ' enable sound'
        self._icon = 'mdi:volume-high'
        self._kettle = kettle

    async def async_added_to_hass(self):
        self.update()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        return f'{DOMAIN}[{self._kettle._mac}][{self._name}]'

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return SwitchDeviceClass.SWITCH

    @property
    def device_info(self):
        return {
            "connections": {
                ("mac", self._kettle._mac)
            }
        }

    @property
    def should_poll(self):
        return False

    @property
    def assumed_state(self):
        return False

    @property
    def available(self):
        return self._kettle._available

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    @property
    def is_on(self):
        return self._kettle._conf_sound_on

    async def async_turn_on(self, **kwargs):
        await self._kettle.setConfEnableSound(True)

    async def async_turn_off(self, **kwargs):
        await self._kettle.setConfEnableSound(False)

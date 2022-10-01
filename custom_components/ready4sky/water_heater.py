#!/usr/local/bin/python3
# coding: utf-8

import logging
import voluptuous as vol
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    ATTR_TEMPERATURE
)
from homeassistant.const import (
    STATE_OFF,
    TEMP_CELSIUS
)
from homeassistant.helpers import entity_platform

from . import (
    DOMAIN,
    SIGNAL_UPDATE_DATA,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    MODE_HEAT,
    MODE_BOIL
)
from .r4sconst import COOKER_PROGRAMS

_LOGGER = logging.getLogger(__name__)

STATE_BOIL = 'boil'
STATE_HEAT = 'heat'

SUPPORT_FLAGS_HEATER = WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.OPERATION_MODE


async def async_setup_entry(hass, config_entry, async_add_entities):
    kettler = hass.data[DOMAIN][config_entry.entry_id]

    if kettler._type in [0, 1, 2]:
        async_add_entities([RedmondWaterHeater(kettler)], True)
    elif kettler._type == 5:
        async_add_entities([RedmondCooker(kettler)], True)
        platform = entity_platform.current_platform.get()
        platform.async_register_entity_service("set_timer", {
            vol.Required("hours"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59))
        }, "async_set_timer", )

        platform.async_register_entity_service("set_manual_program", {
            vol.Required("prog"): vol.All(vol.Coerce(int), vol.Range(min=0, max=12)),
            vol.Required("subprog"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
            vol.Required("temp"): vol.All(vol.Coerce(int), vol.Range(min=30, max=180)),
            vol.Required("hours"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
            vol.Required("dhours"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            vol.Required("dminutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
            vol.Required("heat"): vol.All(vol.Coerce(int), vol.Range(min=0, max=1))
        }, "async_set_manual_program", )


class RedmondWaterHeater(WaterHeaterEntity):
    def __init__(self, kettler):
        self._name = 'Kettle ' + kettler._name
        self._icon = 'mdi:kettle'
        self._kettler = kettler
        self._temp = 0
        self._tgtemp = CONF_MIN_TEMP
        self._co = ''

    async def async_added_to_hass(self):
        self._handle_update()
        self.async_on_remove(async_dispatcher_connect(self._kettler.hass, SIGNAL_UPDATE_DATA, self._handle_update))

    def _handle_update(self):
        self._temp = self._kettler._temp
        self._tgtemp = self._kettler._tgtemp
        self._co = STATE_OFF

        if self._kettler._status == '02':
            if self._kettler._mode == MODE_BOIL:
                self._co = STATE_BOIL
            elif self._kettler._mode == MODE_HEAT:
                self._co = STATE_HEAT

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
    def supported_features(self):
        return SUPPORT_FLAGS_HEATER

    @property
    def available(self):
        return self._kettler._available

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self._temp

    @property
    def target_temperature(self):
        return self._tgtemp

    @property
    def extra_state_attributes(self):
        data = {"target_temp_step": 5}
        return data

    @property
    def current_operation(self):
        return self._co

    @property
    def operation_list(self):
        return [
            STATE_OFF,
            STATE_BOIL,
            STATE_HEAT
        ]

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode == STATE_OFF:
            await self._kettler.modeOff()
        elif operation_mode == STATE_BOIL:
            await self._kettler.modeOn()
        elif operation_mode == STATE_HEAT:
            await self._kettler.modeOn(MODE_HEAT, self._tgtemp)

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if not temperature:
            return

        if self.state == STATE_HEAT:
            self._kettler._tgtemp = self._tgtemp = int(temperature)
            await self.async_set_operation_mode(STATE_HEAT)
        else:
            await self._kettler.setTemperatureHeat(int(temperature))

        self._handle_update()

    async def async_turn_on(self):
        await self.async_set_operation_mode(STATE_BOIL)

    async def async_turn_off(self):
        await self.async_set_operation_mode(STATE_OFF)

    @property
    def min_temp(self):
        return CONF_MIN_TEMP

    @property
    def max_temp(self):
        return CONF_MAX_TEMP

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def unique_id(self):
        return f'{DOMAIN}[{self._kettler._mac}][{self._name}]'


class RedmondCooker(WaterHeaterEntity):
    def __init__(self, kettler):
        self._name = 'Cooker ' + kettler._name
        self._icon = 'mdi:chef-hat'
        self._kettler = kettler
        self._tgtemp = CONF_MIN_TEMP
        self._co = ''

    async def async_added_to_hass(self):
        self._handle_update()
        self.async_on_remove(async_dispatcher_connect(self._kettler.hass, SIGNAL_UPDATE_DATA, self._handle_update))

    def _handle_update(self):
        self._tgtemp = self._kettler._tgtemp
        self._co = STATE_OFF

        if self._kettler._status == '02' or self._kettler._status == '04' or self._kettler._status == '05':
            self._co = 'manual'
            for key, value in COOKER_PROGRAMS.items():
                if value[0] == self._kettler._prog:
                    self._co = key

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
    def supported_features(self):
        return SUPPORT_FLAGS_HEATER

    @property
    def available(self):
        return self._kettler._available

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self._tgtemp

    @property
    def target_temperature(self):
        return self._tgtemp

    @property
    def extra_state_attributes(self):
        data = {"target_temp_step": 5}
        return data

    @property
    def operation_list(self):
        return [program for program, value in COOKER_PROGRAMS.items()].append(STATE_OFF)

    @property
    def current_operation(self):
        return self._co

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode == STATE_OFF:
            await self._kettler.modeOff()
        else:
            program = COOKER_PROGRAMS[operation_mode]
            await self._kettler.modeOnCook(program[0],program[1],program[2],program[3],program[4],program[5],program[6],program[7])

    async def async_set_manual_program(self, prog=None, subprog=None, temp=None, hours=None, minutes=None, dhours=None, dminutes=None, heat=None):
        if prog == None or subprog == None or temp == None or hours == None or minutes == None or dhours == None or dminutes == None or heat == None:
            return
        try:
            progh = self._kettler.decToHex(prog)
            subprogh = self._kettler.decToHex(subprog)
            temph = self._kettler.decToHex(temp)
            hoursh = self._kettler.decToHex(hours)
            minutesh = self._kettler.decToHex(minutes)
            dhoursh = self._kettler.decToHex(dhours)
            dminutesh = self._kettler.decToHex(dminutes)
            heath = self._kettler.decToHex(heat)
            await self._kettler.modeOnCook(progh, subprogh, temph, hoursh, minutesh, dhoursh, dminutesh, heath)
        except:
            pass

    async def async_set_timer(self, hours=None, minutes=None):
        if hours == None or minutes == None:
            return
        try:
            hoursh = self._kettler.decToHex(hours)
            minutesh = self._kettler.decToHex(minutes)
            await self._kettler.modeTimeCook(hoursh, minutesh)
        except:
            pass

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            return

        await self._kettler.modeTempCook(self._kettler.decToHex(int(temperature)))

    @property
    def min_temp(self):
        return 30

    @property
    def max_temp(self):
        return 180

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def unique_id(self):
        return f'{DOMAIN}[{self._kettler._mac}][{self._name}]'

#!/usr/local/bin/python3
# coding: utf-8

import logging

import voluptuous as vol
from homeassistant.components.water_heater import (
    WaterHeaterEntityFeature
)
from homeassistant.helpers import entity_platform

from .water_heaters.cooker import RedmondCooker
from .water_heaters.kettle import RedmondKettle
from . import (
    DOMAIN
)

_LOGGER = logging.getLogger(__name__)

STATE_BOIL = 'boil'
STATE_KEEP_WARM = 'keep_warm'

SUPPORT_FLAGS_HEATER = WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.OPERATION_MODE


async def async_setup_entry(hass, config_entry, async_add_entities):
    kettle = hass.data[DOMAIN][config_entry.entry_id]

    if kettle._type in [0, 1, 2]:
        async_add_entities([RedmondKettle(kettle)], True)

    elif kettle._type == 5:
        async_add_entities([RedmondCooker(kettle)], True)

        platform = entity_platform.current_platform.get()
        platform.async_register_entity_service(
            "set_timer",
            {
                vol.Required("hours"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59))
            },
            "async_set_timer"
        )

        platform.async_register_entity_service(
            "set_manual_program",
            {
                vol.Required("prog"): vol.All(vol.Coerce(int), vol.Range(min=0, max=12)),
                vol.Required("subprog"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
                vol.Required("temp"): vol.All(vol.Coerce(int), vol.Range(min=30, max=180)),
                vol.Required("hours"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
                vol.Required("dhours"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required("dminutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
                vol.Required("heat"): vol.All(vol.Coerce(int), vol.Range(min=0, max=1))
            },
            "async_set_manual_program"
        )

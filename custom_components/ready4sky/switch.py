#!/usr/local/bin/python3
# coding: utf-8

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .switches.humidifier_ionization import RedmondSwitchIonization
from .switches.power_switch import RedmondPowerSwitch
from .switches.conf_sound import RedmondConfSwitchSound
from . import DOMAIN


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    kettle = hass.data[DOMAIN][config_entry.entry_id]

    if kettle._type in [1, 2]:
        async_add_entities([
            RedmondConfSwitchSound(kettle)
        ])
    elif kettle._type == 3:
        async_add_entities([
            RedmondSwitchIonization(kettle)
        ])
    elif kettle._type == 4:
        async_add_entities([
            RedmondPowerSwitch(kettle)
        ])

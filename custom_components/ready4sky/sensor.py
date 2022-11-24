#!/usr/local/bin/python3
# coding: utf-8

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .sensors.energy import RedmondEnergySensor
from .sensors.status import RedmondSensor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    kettle = hass.data[DOMAIN][config_entry.entry_id]

    if kettle._type in [0, 1, 2, 3, 4, 5]:
        async_add_entities([
            RedmondSensor(kettle),
            RedmondEnergySensor(kettle)
        ])

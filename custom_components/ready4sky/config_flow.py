#!/usr/local/bin/python3
# coding: utf-8

import secrets

from homeassistant import config_entries
from homeassistant.const import (
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL
)
from homeassistant.helpers import config_validation
from voluptuous import Schema, Required, Optional, In

from . import DOMAIN, CONF_USE_BACKLIGHT
from .btle import BTLEConnection
from .r4sconst import SUPPORTED_DEVICES

DEFAULT_SCAN_INTERVAL = 60
DEFAULT_USE_BACKLIGHT = True


# @config_entries.HANDLERS.register(DOMAIN)
class RedmondKettleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self.data = {}
        self._bleDevices = {}

    async def async_step_user(self, user_input={}):
        if user_input:
            return await self.check_valid(user_input)
        return await self.show_form()

    async def async_step_info(self, user_input={}):
        return await self.create_entryS()

    async def show_form(self, user_input={}, errors={}):
        self._bleDevices = await BTLEConnection.getDiscoverDevices(self.hass)
        bleDevices = self._bleDevices.copy()

        for address, name in bleDevices.items():
            if address.replace(':', '') != bleDevices[address].replace('-', ''):
                bleDevices[address] += ' (' + address + ')'

            bleDevices[address] += ' - Supported' if not SUPPORTED_DEVICES.get(name) is None else ' - Not supported'

        mac = str(user_input.get(CONF_MAC)).upper()
        password = user_input.get(CONF_PASSWORD, secrets.token_hex(8))
        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        backlight = user_input.get(CONF_USE_BACKLIGHT, DEFAULT_USE_BACKLIGHT)

        SCHEMA = Schema({
            Required(CONF_MAC, default=mac): In(bleDevices),
            Required(CONF_PASSWORD, default=password): str,
            Optional(CONF_SCAN_INTERVAL, default=scan_interval): int,
            Optional(CONF_USE_BACKLIGHT, default=backlight): config_validation.boolean
        })

        return self.async_show_form(step_id='user', data_schema=SCHEMA, errors=errors)

    def show_form_info(self):
        return self.async_show_form(step_id='info')

    async def create_entryS(self):
        await self.async_set_unique_id(f'{DOMAIN}[{self.data.get(CONF_MAC)}]')
        return self.async_create_entry(title=self.context["title_placeholders"]['name'], data=self.data)

    async def check_valid(self, user_input):
        mac = user_input.get(CONF_MAC)
        password = user_input.get(CONF_PASSWORD)
        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        identifier = f'{DOMAIN}[{mac}]'
        if identifier in self._async_current_ids():
            return self.async_abort(reason='already_configured')

        if len(password) != 16:
            return await self.show_form(
                user_input=user_input,
                errors={
                    'base': 'wrong_password'
                }
            )

        if scan_interval < 10 or scan_interval > 300:
            return await self.show_form(
                user_input=user_input,
                errors={
                    'base': 'wrong_scan_interval'
                }
            )

        if SUPPORTED_DEVICES.get(self._bleDevices[mac]) is None:
            return await self.show_form(
                user_input=user_input,
                errors={
                    'base': 'device_not_supported'
                }
            )

        self.data = user_input
        self.context["title_placeholders"] = {"name": self._bleDevices[mac]}

        return self.show_form_info()

import secrets
import logging

from home_assistant_bluetooth import BluetoothServiceInfo
from homeassistant import config_entries
from homeassistant.components import onboarding
from typing import Any
from homeassistant.const import (
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation
from voluptuous import Schema, Required, Optional, In

from .r4sconst import SUPPORTED_DEVICES
from . import DOMAIN, CONF_USE_BACKLIGHT
from .btle import BTLEConnection

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_USE_BACKLIGHT = True

_LOGGER = logging.getLogger(__name__)


# @config_entries.HANDLERS.register(DOMAIN)
class RedmondKettleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self.data = {}
        self._bleDevices = {}

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfo) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.error(discovery_info)

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        _LOGGER.error(discovery_info.name)

        device = SUPPORTED_DEVICES.get(discovery_info.name)
        if not device:
            return self.async_abort(reason="not_supported")

        _LOGGER.error('SUPPORT')
        self.context["title_placeholders"] = {"name": discovery_info.name}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm discovery."""

        _LOGGER.error('CONFIRM')

        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self.async_create_entry(title=self.context["title_placeholders"]["name"], data={})

        _LOGGER.error('user_input')

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"]
        )

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

            bleDevices[address] += ' - Supported' if SUPPORTED_DEVICES.get(name) else ' - Not supported'

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
        mac = self.data.get(CONF_MAC)
        identifier = f'{DOMAIN}[{mac}]'
        await self.async_set_unique_id(identifier)
        return self.async_create_entry(title=mac, data=self.data)

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

        return self.show_form_info()

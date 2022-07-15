#!/usr/local/bin/python3
# coding: utf-8

from bleak import (BleakScanner, BleakClient, BleakError)
from re import search
from textwrap import wrap
import logging
import binascii
import asyncio
import os

from .r4sconst import SUPPORTED_DEVICES

_LOGGER = logging.getLogger(__name__)

DEFAULT_ADAPTER = "hci0"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


class BTLEConnection:
    def __init__(self, mac, key, device):
        self._type = None
        self._auth = False
        self._name = ''
        self._mac = mac
        self._key = key
        self._adapter = device
        self._iter = 0
        self._callbacks = {}
        self._conn = BleakClient(self._mac, adapter=self._adapter)

        self.setCallback('ff', self.responseAuth)

    async def setNameAndType(self):
        bleDevices = await self.getDiscoverDevices(self._adapter)
        self._name = bleDevices.get(self._mac, 'None')
        self._type = SUPPORTED_DEVICES.get(self._name, None)

        if self._type is None:
            raise BleakError('type device not supported')

        return self

    async def __aenter__(self):
        for i in range(3):
            isConnected = self._conn.is_connected

            _LOGGER.debug('IS CONNECTED: ' + str(isConnected))

            if isConnected:
                break

            try:
                await self._conn.connect()
                await self._conn.start_notify(UART_TX_CHAR_UUID, self.handleNotification)
                await self.sendAuth()
                break
            except BaseException as ex:
                _LOGGER.error('Unable to connect')
                _LOGGER.exception(ex)

                if i < 2:
                    await asyncio.sleep(1 + i)
                else:
                    await self.disconnect()
                    raise ex

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        #await self.disconnect()
        pass

    @staticmethod
    def getIfaces():
        try:
            lines = os.listdir('/sys/class/bluetooth/')
            return {name: name for name in lines if 'hci' in name}
        except:
            return {DEFAULT_ADAPTER: DEFAULT_ADAPTER}

    @staticmethod
    async def getDiscoverDevices(iface=DEFAULT_ADAPTER, timeout=5.0):
        devices = await BleakScanner.discover(timeout, adapter=iface)
        return {str(device.address): str(device.name) for device in devices}

    async def disconnect(self):
        try:
            await asyncio.sleep(2.0)
            await self._conn.disconnect()

            self._iter = 0
        except BaseException as ex:
            _LOGGER.error('disconect failed')
            _LOGGER.exception(ex)

    def handleNotification(self, handle, data):
        arrData = wrap(binascii.b2a_hex(data).decode("utf-8"), 2)
        respType = arrData[2]

        _LOGGER.debug('NOTIF: handle: ' + str(handle) + ' cmd: ' + str(respType) + ' full: ' + str(arrData))

        if respType in self._callbacks:
            self._callbacks[respType](arrData)

    @property
    def mac(self):
        return self._mac

    def setCallback(self, type, function):
        self._callbacks[type] = function

    async def makeRequest(self, value):
        _LOGGER.debug('MAKE REQUEST: ' + value)

        try:
            await self._conn.write_gatt_char(UART_RX_CHAR_UUID, binascii.a2b_hex(bytes(value, 'utf-8')), True)

            return True
        except BleakError as ex:
            _LOGGER.error('not send request %s', inspect.getouterframes(inspect.currentframe(), 2)[1][3])
            _LOGGER.exception(ex)

        return False

    def hexToDec(self, hexStr) -> int:
        return int.from_bytes(binascii.a2b_hex(bytes(hexStr, 'utf-8')), 'little')

    def decToHex(self, num) -> str:
        return num.to_bytes((num.bit_length() + 7) // 8, 'little').hex() or '00'

    def getHexNextIter(self) -> str:
        current = self._iter
        self._iter = 0 if self._iter > 254 else self._iter + 1

        return self.decToHex(current)

    async def sendAuth(self):
        await self.makeRequest('55' + self.getHexNextIter() + 'ff' + self._key + 'aa')
        await asyncio.sleep(1.0)

        if not self._auth:
            raise BleakError('error auth')

        return True

    def responseAuth(self, arrayHex):
        if self._type in [0, 1, 3, 4, 5] and arrayHex[3] == '01':
            self._auth = True
        elif self._type == 2 and arrayHex[3] == '02':
            self._auth = True
        else:
            self._auth = False

        return self._auth

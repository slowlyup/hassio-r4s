#!/usr/local/bin/python3
# coding: utf-8

from bleak import (BleakScanner, BleakClient, BleakError)
from re import search
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
        self._conn = None
        self._type = None
        self._ready = True
        self._auth = None
        self._name = ''
        self._mac = mac
        self._key = key
        self._iface = 0
        self._iter = 0
        self._callbacks = {}
        self._adapter = device

    async def setNameAndType(self):
        bleDevices = await self.getDiscoverDevices(self._adapter)
        self._name = bleDevices.get(self._mac, 'None')
        self._type = SUPPORTED_DEVICES.get(self._name, None)

        if self._type is None:
            raise BleakError('type device not supported')

        return self

    async def __aenter__(self):
        if not self.isConnected():
            if not self._conn:
                self._conn = BleakClient(self._mac, adapter=self._adapter)

            for i in range(3):
                try:
                    await self._conn.connect()
                    await self._conn.start_notify(UART_TX_CHAR_UUID, self.handleNotification)
                    await self.sendAuth()
                    break
                except BaseException as ex:
                    if i == 2:
                        _LOGGER.error('Unable to connect')
                        _LOGGER.exception(ex)
                        await self.disconnect(True)
                        raise ex

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        #await self.disconnect()
        pass

    def isConnected(self):
        return self._conn and self._conn.is_connected

    async def sendAuth(self):
        await self.make_request('55' + str(self._iter).zfill(2) + 'ff' + self._key + 'aa')
        await asyncio.sleep(2.0)

        if not self._auth:
            raise BleakError('error auth')

        return True

    async def disconnect(self, force=False):
        await asyncio.sleep(2.0)
        if self.isConnected() or force:
            try:
                if self._conn is not None:
                    await self._conn.disconnect()

                self._conn = None
                self._iter = 0
            except BaseException as ex:
                _LOGGER.error('disconect failed')
                _LOGGER.exception(ex)

    def handleNotification(self, handle, data):
        s = binascii.b2a_hex(data).decode("utf-8")
        arrData = [s[x: x + 2] for x in range(0, len(s), 2)]

        # sendAuth
        if handle == 10 and arrData[2] == 'ff':
            if self._type in [0, 1, 3, 4, 5] and arrData[3] == '01':
                self._auth = True
            elif self._type == 2 and arrData[3] == '02':
                self._auth = True
            else:
                self._auth = False
            return None

        if handle in self._callbacks:
            self._callbacks[handle](arrData)

    @property
    def mac(self):
        return self._mac

    def set_callback(self, handle, function):
        self._callbacks[handle] = function

    async def make_request(self, value):
        answ = False

        while not self._ready:
            continue

        try:
            self._ready = False

            await self._conn.write_gatt_char(UART_RX_CHAR_UUID, binascii.a2b_hex(bytes(value, 'utf-8')), True)

            self.nextIter()

            answ = True
        except BleakError as ex:
            _LOGGER.error('not send request %s', inspect.getouterframes(inspect.currentframe(), 2)[1][3])
            _LOGGER.exception(ex)

        self._ready = True

        return answ

    def nextIter(self):
        self._iter = 0 if self._iter > 254 else self._iter + 1

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

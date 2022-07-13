#!/usr/local/bin/python3
# coding: utf-8

import binascii
import asyncio
import inspect
import time
import logging

from functools import partial
from datetime import (timedelta)
from textwrap import wrap

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.util import color as color_util
from homeassistant.const import (
    CONF_DEVICE,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL
)

from .r4sconst import SUPPORTED_DEVICES
from .btle import BTLEConnection

DOMAIN = "ready4sky"
SUPPORTED_DOMAINS = [
    "water_heater",
    "sensor",
    "light",
    "switch",
    "fan"
]
SIGNAL_UPDATE_DATA = 'ready4skyupdate'

CONF_USE_BACKLIGHT = 'use_backlight'

CONF_MIN_TEMP = 40
CONF_MAX_TEMP = 100
CONF_TARGET_TEMP = 100

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    config = config_entry.data
    mac = str(config.get(CONF_MAC)).upper()
    device = config.get(CONF_DEVICE)
    password = config.get(CONF_PASSWORD)
    scan_delta = timedelta(seconds=config.get(CONF_SCAN_INTERVAL))
    backlight = config.get(CONF_USE_BACKLIGHT)

    kettler = RedmondKettler(hass, mac, password, device, backlight)
    await kettler.setNameAndType()

    try:
        await kettler.firstConnect()
    except BaseException as ex:
        _LOGGER.error("Connect to %s through device %s failed", mac, device)
        _LOGGER.exception(ex)
        return False

    hass.data[DOMAIN][config_entry.entry_id] = kettler

    dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        manufacturer="Redmond",
        name="Ready4Sky",
    )

    async_track_time_interval(hass, hass.data[DOMAIN][config_entry.entry_id].update, scan_delta)

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, component))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    try:
        for component in SUPPORTED_DOMAINS:
            await hass.config_entries.async_forward_entry_unload(entry, component)
        hass.data[DOMAIN].pop(entry.entry_id)
    except ValueError:
        pass
    return True


class RedmondKettler:
    def __init__(self, hass, addr, key, device, backlight):
        self.hass = hass
        self._mac = addr
        self._key = key
        self._adapter = device
        self._use_backlight = backlight
        self._mntemp = CONF_MIN_TEMP
        self._mxtemp = CONF_MAX_TEMP
        self._tgtemp = CONF_TARGET_TEMP
        self._temp = 0
        self._Watts = 0
        self._alltime = 0
        self._times = 0
        self._time_upd = '00:00'
        self._boiltime = '80'
        self._rgb1 = '0000ff'
        self._rgb2 = 'ff0000'
        self._rand = '5e'
        self._mode = '00'  # '00' - boil, '01' - heat to temp, '03' - backlight  for cooker 00 - heat after cook   01 - off after cook        for fan 00-06 - speed 
        self._status = '00'  #may be '00' - OFF or '02' - ON         for cooker 00 - off   01 - setup program   02 - on  04 - heat   05 - delayed start
        self._prog = '00'  #  program
        self._sprog = '00'  # subprogram
        self._ph = 0  #  program hours
        self._pm = 0  #  program min
        self._th = 0  #  timer hours
        self._tm = 0  #  timer min
        self._ion = '00'  # 00 - off   01 - on
        self._conn = BTLEConnection(self._mac, self._key, self._adapter)
        self.initCallbacks()

    async def setNameAndType(self):
        await self._conn.setNameAndType()
        self._type = self._conn._type
        self._name = self._conn._name

    def initCallbacks(self):
        # sendOn, sendOff, sendMode, sendSync, sendSetLights, sendGetLights, sendUseBacklight
        # ['03', '04', '05', '6e', '32', '33', '37']
        self._conn.setCallback('06', self.responseStatus)
        self._conn.setCallback('47', self.responseStat)
        self._conn.setCallback('50', self.responseStat)

    def calcMidColor(self, rgb1, rgb2):
        try:
            hs1 = self.rgbhex_to_hs(rgb1)
            hs2 = self.rgbhex_to_hs(rgb2)
            hmid = int((hs1[0] + hs2[0]) /2)
            smid = int((hs1[1] + hs2[1]) / 2)
            hsmid = (hmid, smid)
            return self.hs_to_rgbhex(hsmid)
        except:
            return '00ff00'

    def rgbhex_to_hs(self, rgbhex):
        rgb = color_util.rgb_hex_to_rgb_list(rgbhex)
        return color_util.color_RGB_to_hs(*rgb)

    def hs_to_rgbhex(self, hs):
        rgb = color_util.color_hs_to_RGB(*hs)
        return color_util.color_rgb_to_hex(*rgb)

    def hexToDec(self, chr) -> int:
        return int(str(chr), 16)

    def decToHex(self, num) -> str:
        return hex(int(num))[2:].zfill(2)

    async def sendOn(self, conn):
        if self._type == 0:
            return True

        if self._type in [1, 2, 3, 4, 5]:
            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '03aa')

        return False

    async def sendOff(self, conn):
        return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '04aa')

    async def sendSyncDateTime(self, conn):
        if self._type in [0, 3, 4, 5]:
            return True

        if self._type in [1, 2]:
            now = int(time.time())
            offset = time.timezone * -1

            now = "".join(list(reversed(wrap(self.decToHex(now), 2))))
            offset = "".join(list(reversed(wrap(self.decToHex(offset), 2))))

            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '6e' + now + offset + '0000aa')

        return False

    async def sendStat(self, conn):
        if await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '4700aa'):
            if await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '5000aa'):
                return True
        return False

    def responseStat(self, arrHex):
        if arrHex[2] == '47':  # state watt
            self._Watts = self.hexToDec(str(arrHex[11] + arrHex[10] + arrHex[9]))  # in Watts
            self._alltime = round(self._Watts / 2200, 1)  # in hours
        elif arrHex[2] == '50':  # state time
            self._times = self.hexToDec(str(arrHex[7] + arrHex[6]))

    async def sendStatus(self, conn):
        if await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '06aa'):
            return True

        return False

    def responseStatus(self, arrHex):
        if self._type == 0:
            self._temp = self.hexToDec(str(arrHex[13]))
            self._status = str(arrHex[11])
            self._mode = str(arrHex[3])
            tgtemp = str(arrHex[5])
            if tgtemp != '00':
                self._tgtemp = self.hexToDec(tgtemp)
            else:
                self._tgtemp = 100
        elif self._type in [1, 2]:
            self._temp = self.hexToDec(str(arrHex[8]))
            self._status = str(arrHex[11])
            self._mode = str(arrHex[3])
            tgtemp = str(arrHex[5])
            if tgtemp != '00':
                self._tgtemp = self.hexToDec(tgtemp)
            else:
                self._tgtemp = 100
        elif self._type == 3:
            self._status = str(arrHex[11])
            self._mode = str(arrHex[5])
            self._ion = str(arrHex[14])
        elif self._type == 4:
            self._status = str(arrHex[11])
            self._mode = str(arrHex[3])
        elif self._type == 5:
            self._prog = str(arrHex[3])
            self._sprog = str(arrHex[4])
            self._temp = self.hexToDec(str(arrHex[5]))
            self._tgtemp = self.hexToDec(str(arrHex[5]))
            self._ph = self.hexToDec(str(arrHex[6]))
            self._pm = self.hexToDec(str(arrHex[7]))
            self._th = self.hexToDec(str(arrHex[8]))
            self._tm = self.hexToDec(str(arrHex[9]))
            self._mode = str(arrHex[10])
            self._status = str(arrHex[11])

        self._time_upd = time.strftime("%H:%M")
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_DATA)

    # 00 - boil
    # 01 - heat
    # 03 - backlight (boil by default)
    # temp - temp or rgb in HEX
    async def sendMode(self, conn, mode, temp):
        if self._type in [3, 4, 5]:
            return True

        if self._type == 0:
            str2b = '55' + self.decToHex(self._conn._iter) + '05' + mode + '00' + temp + '00aa'
        elif self._type in [1, 2]:
            str2b = '55' + self.decToHex(self._conn._iter) + '05' + mode + '00' + temp + '00000000000000000000800000aa'

        return await conn.makeRequest(str2b)

    async def sendModeCook(self, conn, prog, sprog, temp, hours, minutes, dhours, dminutes, heat):
        if self._type == 5:
            str2b = '55' + self.decToHex(self._conn._iter) + '05' + prog + sprog + temp + hours + minutes + dhours + dminutes + heat + 'aa'
            return await conn.makeRequest(str2b)
        else:
            return True

        return False

    async def sendTimerCook(self, conn, hours, minutes):
        if self._type == 5:
            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '0c' + hours + minutes + 'aa')
        else:
            return True

        return False

    async def sendTempCook(self, conn, temp):  #temp in HEX or speed 00-06
        if self._type in [3, 5]:
            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '0b' + temp + 'aa')
        else:
            return True

        return False

    async def sendIonCmd(self, conn, onoff):  #00-off 01-on
        if self._type == 3:
            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '1b' + onoff + 'aa', True)

        return True

    async def sendAfterSpeed(self, conn):
        if self._type == 3:
            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '0900aa', True)

        return True

    async def sendUseBackLight(self, conn):
        if self._type in [0, 3, 4, 5]:
            return True

        onoff = "00"
        if self._type in [1, 2]:
            if self._use_backlight:
                onoff = "01"

            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '37c8c8' + onoff + 'aa')

        return False

    async def sendSetLights(self, conn, boilOrLight='01', rgb1='0000ff'):  # 00 - boil light    01 - backlight
        if self._type in [0, 3, 4, 5]:
            return True

        if self._type in [1, 2]:
            rgb_mid = rgb1
            rgb2 = rgb1

            if boilOrLight == "00":
                scale_light = ['28', '46', '64']
            else:
                scale_light = ['00', '32', '64']

            return await conn.makeRequest('55' + self.decToHex(self._conn._iter) + '32' + boilOrLight + scale_light[0] + self._rand + rgb1 + scale_light[1] + self._rand + rgb_mid + scale_light[2] + self._rand + rgb2 + 'aa')

        return False

    async def startNightColor(self):
        try:
           async with self._conn as conn:
                offed = False
                if self._status == '02':
                    if self.sendOff(conn):
                        offed = True
                else:
                    offed = True

                if offed:
                    if await self.sendSetLights(conn, '01', self._rgb1):
                        if await self.sendMode(conn, '03', '00'):
                            if await self.sendOn(conn):
                                if await self.sendStatus(conn):
                                    return True
        except:
            pass

        return False

    async def modeOn(self, mode= "00", temp= "00"):
        try:
           async with self._conn as conn:
                offed = False
                if self._status == '02':
                    if self.sendOff(conn):
                        offed = True
                else:
                    offed = True

                if offed and await self.sendMode(conn, mode, temp) and await self.sendOn(conn) and await self.sendStatus(conn):
                    return True
        except:
            pass

        return False

    async def modeOnCook(self, prog, sprog, temp, hours, minutes, dhours='00', dminutes='00', heat = '01'):
        answ = False
        try:
           async with self._conn as conn:
                offed = False
                if self._status != '00':
                    if self.sendOff(conn):
                        offed = True
                else:
                    offed = True
                if offed:
                    if await self.sendModeCook(conn, prog, sprog, temp, hours, minutes, dhours, dminutes, heat):
                        if await self.sendOn(conn):
                            if await self.sendStatus(conn):
                                answ = True
        except:
            pass

        return answ

    async def modeTempCook(self, temp):
        try:
           async with self._conn as conn:
                if await self.sendTempCook(conn, temp) and await self.sendStatus(conn):
                    return True
        except:
            pass

        return False

    async def modeFan(self, speed):
        answ = False
        try:
           async with self._conn as conn:
                if await self.sendTempCook(conn, speed):
                    if await self.sendAfterSpeed(conn):
                        if self._status == '00':
                            answ1 = self.sendOn(conn)
                        if await self.sendStatus(conn):
                            answ = True
        except:
            pass

        return answ

    async def modeIon(self, onoff):
        answ = False
        try:
           async with self._conn as conn:
                if await self.sendIonCmd(conn, onoff):
                    if await self.sendStatus(conn):
                        answ = True
        except:
            pass

        return answ

    async def modeTimeCook(self, hours, minutes):
        try:
           async with self._conn as conn:
                if await self.sendTimerCook(conn, hours, minutes) and await self.sendStatus(conn):
                    return True
        except:
            pass

        return False

    async def modeOff(self):
        answ = False
        try:
           async with self._conn as conn:
                if await self.sendOff(conn):
                    if await self.sendStatus(conn):
                        answ = True
        except:
            pass

        return answ

    async def update(self, now, **kwargs) -> None:
        try:
           async with self._conn as conn:
                if await self.sendSyncDateTime(conn) and await self.sendStatus(conn) and await self.sendStat(conn):
                    return True
        except:
            pass

        return False

    async def firstConnect(self):
        _LOGGER.debug('FIRST CONNECT')

        async with self._conn as conn:
            if await self.sendUseBackLight(conn) and await self.update(1):
                    return True

        return False

#!/usr/local/bin/python3
# coding: utf-8

import asyncio
import logging
import time
from datetime import (timedelta)
from enum import Enum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import color as color_util

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

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    config = config_entry.data
    mac = str(config.get(CONF_MAC)).upper()
    password = config.get(CONF_PASSWORD)
    scan_delta = timedelta(seconds=config.get(CONF_SCAN_INTERVAL))
    backlight = config.get(CONF_USE_BACKLIGHT)

    kettler = RedmondKettler(hass, mac, password, backlight)
    await kettler.setNameAndType()

    try:
        await kettler.firstConnect()
    except BaseException as ex:
        _LOGGER.error("Connect to %s through device %s failed", mac)
        _LOGGER.exception(ex)
        return False

    hass.data[DOMAIN][config_entry.entry_id] = kettler

    dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (DOMAIN, config_entry.unique_id)
        },
        connections={
            (dr.CONNECTION_NETWORK_MAC, mac)
        },
        manufacturer="Redmond",
        model=kettler._name,
        name=kettler._name,
        sw_version=kettler._firmware_ver
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


class RedmondCommand(Enum):
    AUTH = 'ff'
    VERSION = '01'
    RUN_CURRENT_MODE = '03'  # sendOn
    STOP_CURRENT_MODE = '04'  # sendOff
    SET_STATUS_MODE = '05'  # sendMode
    GET_STATUS_MODE = '06'
    SET_TEMPERATURE = '07'
    SET_DELAY = '08'
    SET_COLOR = '32'  # sendSetLights
    GET_COLOR = '33'  # sendGetLights
    SET_BACKLIGHT_MODE = '37'  # sendUseBacklight
    SET_SOUND = '3c'
    SET_LOCK_BUTTONS = '3e'
    GET_STATISTICS_WATT = '47'
    GET_STARTS_COUNT = '50'
    SET_TIME = '6e'  # sendSync
    SET_IONIZATION = '1b'
    SET_TIME_COOKER = '0c'
    SET_TEMP_COOKER = '0b'

    def __str__(self):
        return str(self.value)


class RedmondKettler:
    def __init__(self, hass, addr, key, backlight):
        self.hass = hass
        self._type = None
        self._name = None
        self._mac = addr
        self._key = key
        self._use_backlight = backlight
        self._mntemp = CONF_MIN_TEMP
        self._mxtemp = CONF_MAX_TEMP
        self._tgtemp = CONF_MAX_TEMP
        self._temp = 0
        self._Watts = 0
        self._alltime = 0
        self._times = 0
        self._firmware_ver = None
        self._time_upd = '00:00'
        self._boiltime = '80'
        self._nightlight_brightness = 255
        self._rgb1 = '0000ff'
        self._rgb2 = 'ff0000'
        self._mode = '00'  # '00' - boil, '01' - heat to temp, '03' - backlight  for cooker 00 - heat after cook   01 - off after cook        for fan 00-06 - speed 
        self._status = '00'  # may be '00' - OFF or '02' - ON         for cooker 00 - off   01 - setup program   02 - on  04 - heat   05 - delayed start
        self._prog = '00'  # program
        self._sprog = '00'  # subprogram
        self._ph = 0  # program hours
        self._pm = 0  # program min
        self._th = 0  # timer hours
        self._tm = 0  # timer min
        self._ion = '00'  # 00 - off   01 - on
        self._auth = False
        self._conn = BTLEConnection(self.hass, self._mac, self._key)
        self.initCallbacks()

    async def setNameAndType(self):
        await self._conn.setNameAndType()
        self._type = self._conn._type
        self._name = self._conn._name

    def initCallbacks(self):
        self._conn.setConnectAfter(self.sendAuth)
        self._conn.setCallback(RedmondCommand.AUTH, self.responseAuth)
        self._conn.setCallback(RedmondCommand.VERSION, self.responseGetVersion)
        self._conn.setCallback(RedmondCommand.GET_STATUS_MODE, self.responseStatus)
        self._conn.setCallback(RedmondCommand.GET_STATISTICS_WATT, self.responseStat)
        self._conn.setCallback(RedmondCommand.GET_STARTS_COUNT, self.responseStat)

    def calcMidColor(self, rgb1, rgb2):
        try:
            hs1 = self.rgbhex_to_hs(rgb1)
            hs2 = self.rgbhex_to_hs(rgb2)
            hmid = int((hs1[0] + hs2[0]) / 2)
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

    def hexToDec(self, hexChr: str) -> int:
        return self._conn.hexToDec(hexChr)

    def decToHex(self, num: int) -> str:
        return self._conn.decToHex(num)

    def getHexNextIter(self) -> str:
        return self._conn.getHexNextIter()

    async def sendAuth(self, conn):
        await conn.sendRequest(RedmondCommand.AUTH, self._key)
        await asyncio.sleep(1.5)

        if not self._auth:
            raise Exception('error auth')

        return True

    def responseAuth(self, arrayHex):
        if self._type in [0, 1, 3, 4, 5] and arrayHex[3] == '01':
            self._auth = True
        elif self._type == 2 and arrayHex[3] == '02':
            self._auth = True
        else:
            self._auth = False

        return self._auth

    async def sendGetVersion(self, conn):
        return await conn.sendRequest(RedmondCommand.VERSION)

    def responseGetVersion(self, arrHex):
        self._firmware_ver = str(self.hexToDec(arrHex[3])) + '.' + str(self.hexToDec(arrHex[4]))

    async def sendOn(self, conn):
        if self._type == 0:
            return True

        if self._type in [1, 2, 3, 4, 5]:
            return await conn.sendRequest(RedmondCommand.RUN_CURRENT_MODE)

        return False

    async def sendOff(self, conn):
        return await conn.sendRequest(RedmondCommand.STOP_CURRENT_MODE)

    async def sendSyncDateTime(self, conn):
        if self._type in [0, 3, 4, 5]:
            return True

        if self._type in [1, 2]:
            now = self.decToHex(int(time.time()))
            offset = self.decToHex(time.timezone * -1)

            return await conn.sendRequest(RedmondCommand.SET_TIME, now + offset + '0000')

        return False

    async def sendStat(self, conn):
        if await conn.sendRequest(RedmondCommand.GET_STATISTICS_WATT, '00'):
            if await conn.sendRequest(RedmondCommand.GET_STARTS_COUNT, '00'):
                return True
        return False

    def responseStat(self, arrHex):
        if arrHex[2] == '47':  # state watt
            self._Watts = self.hexToDec(str(arrHex[9] + arrHex[10] + arrHex[11]))  # in Watts
            self._alltime = round(self._Watts / 2200, 1)  # in hours
        elif arrHex[2] == '50':  # state time
            self._times = self.hexToDec(str(arrHex[6] + arrHex[7]))

    async def sendStatus(self, conn):
        if await conn.sendRequest(RedmondCommand.GET_STATUS_MODE):
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
                self._tgtemp = CONF_MAX_TEMP
        elif self._type in [1, 2]:
            self._temp = self.hexToDec(str(arrHex[8]))
            self._status = str(arrHex[11])
            self._mode = str(arrHex[3])
            tgtemp = str(arrHex[5])
            if tgtemp != '00':
                self._tgtemp = self.hexToDec(tgtemp)
            else:
                self._tgtemp = CONF_MAX_TEMP
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
            str2b = mode + '00' + temp + '00'
        elif self._type in [1, 2]:
            str2b = mode + '00' + temp + '00000000000000000000800000'
        else:
            return True

        return await conn.sendRequest(RedmondCommand.SET_STATUS_MODE, str2b)

    async def sendModeCook(self, conn, prog, sprog, temp, hours, minutes, dhours, dminutes, heat):
        if self._type == 5:
            str2b = prog + sprog + temp + hours + minutes + dhours + dminutes + heat
            return await conn.sendRequest(RedmondCommand.SET_STATUS_MODE, str2b)
        else:
            return True

    async def sendTimerCook(self, conn, hours, minutes):
        if self._type == 5:
            return await conn.sendRequest(RedmondCommand.SET_TIME_COOKER, hours + minutes)
        else:
            return True

    async def sendTempCook(self, conn, temp):  # temp in HEX or speed 00-06
        if self._type in [3, 5]:
            return await conn.sendRequest(RedmondCommand.SET_TEMP_COOKER, temp)
        else:
            return True

    async def sendIonCmd(self, conn, onoff):  # 00-off 01-on
        if self._type == 3:
            return await conn.sendRequest(RedmondCommand.SET_IONIZATION, onoff)

        return True

    async def sendAfterSpeed(self, conn):
        if self._type == 3:
            return await conn.makeRequest('55' + self.getHexNextIter() + '0900aa', True)

        return True

    async def sendUseBackLight(self, conn):
        if self._type in [0, 3, 4, 5]:
            return True

        onoff = "00"
        if self._type in [1, 2]:
            if self._use_backlight:
                onoff = "01"

            return await conn.sendRequest(RedmondCommand.SET_BACKLIGHT_MODE, 'c8c8' + onoff)

        return False

    async def sendSetLights(self, conn, boilOrLight='01', rgb1='0000ff'):  # 00 - boil light  01 - backlight
        if self._type in [0, 3, 4, 5]:
            return True

        if self._type in [1, 2]:
            rgb_mid = rgb1
            rgb2 = rgb1
            bright = self.decToHex(self._nightlight_brightness)

            if boilOrLight == "00":
                scale_light = ['28', '46', '64']
            else:
                scale_light = ['00', '32', '64']

            return await conn.sendRequest(RedmondCommand.SET_COLOR, boilOrLight + scale_light[0] + bright + rgb1 + scale_light[1] + bright + rgb_mid + scale_light[2] + bright + rgb2)

        return False

    async def startNightColor(self):
        try:
            async with self._conn as conn:
                isOff = True
                if self._status == '02' and self._mode != '03':
                    isOff = await self.sendOff(conn)

                if isOff and await self.sendSetLights(conn, '01', self._rgb1):
                    if await self.sendMode(conn, '03', '00'):
                        if await self.sendOn(conn):
                            if await self.sendStatus(conn):
                                return True
        except:
            pass

        return False

    async def modeOn(self, mode="00", temp="00"):
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

    async def modeOnCook(self, prog, sprog, temp, hours, minutes, dhours='00', dminutes='00', heat='01'):
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

    async def update(self, now, **kwargs) -> bool:
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
            if await self.sendUseBackLight(conn):
                if await self.sendGetVersion(conn):
                    if await self.update(1):
                        return True

        return False

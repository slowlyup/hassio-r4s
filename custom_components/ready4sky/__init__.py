
#!/usr/local/bin/python3
# coding: utf-8

import binascii
import asyncio
import inspect
import time
import logging

from re import search
from bluepy import btle
from functools import partial
from datetime import (datetime, timedelta)
from textwrap import wrap
from random import (seed, randint)

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

CONF_USE_BACKLIGHT = 'use_backlight'

CONF_MIN_TEMP = 40
CONF_MAX_TEMP = 100
CONF_TARGET_TEMP = 100

_LOGGER = logging.getLogger(__name__)

SUPPORTED_DOMAINS = [
    "water_heater",
    "sensor",
    "light",
    "switch",
    "fan"
]

DOMAIN = "ready4sky"

async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):

    config = config_entry.data

    mac = config.get(CONF_MAC)
    device = config.get(CONF_DEVICE)
    password = config.get(CONF_PASSWORD)
    scan_delta = timedelta(seconds=config.get(CONF_SCAN_INTERVAL))
    backlight = config.get(CONF_USE_BACKLIGHT)

    kettler = RedmondKettler(hass, mac, password, device, backlight)

    seed(1)
    valueR = randint(5, 10)
    await asyncio.sleep(valueR)

    try:
        await kettler.async_firstConnect()
        if not kettler._connected:
            _LOGGER.error("Connection error")
            return False
    except:
        _LOGGER.error("Connect to %s through device %s failed", mac, device)
        return False

    hass.data[DOMAIN][config_entry.entry_id] = kettler

    dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        manufacturer="Redmond",
        name="Ready4Sky",
    )

    async_track_time_interval(hass, hass.data[DOMAIN][config_entry.entry_id].async_update, scan_delta)

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True

async def async_unload_entry(hass:HomeAssistant, entry:ConfigEntry):
    try:
        for component in SUPPORTED_DOMAINS:
            await hass.config_entries.async_forward_entry_unload(entry, component)
        hass.data[DOMAIN].pop(entry.entry_id)
    except ValueError:
        pass
    return True

class BTLEConnection(btle.DefaultDelegate):
    def __init__(self, mac, device):
        btle.DefaultDelegate.__init__(self)

        self._conn = None
        self._mac = mac
        self._iface = 0
        self._iter = 0
        self._callbacks = {}

        match_result = search(r'hci([\d]+)', device)
        if match_result is not None:
            self._iface = int(match_result.group(1))

    def __enter__(self, i = 0):
        self.disconnect()

        try:
            self._conn = btle.Peripheral(deviceAddr=self._mac, addrType=btle.ADDR_TYPE_RANDOM, iface=self._iface)
            self._conn.withDelegate(self)
        except BaseException as ex:
            i += 1

            if i < 5:
                time.sleep(1)
                return self.__enter__(i)
            else:
                _LOGGER.error('unable to connect to device')
                _LOGGER.exception(e)
                self.disconnect()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def disconnect(self):
        try:
            if self._conn is not None:
                self._conn.disconnect()
                self._conn = None
        except:
            pass
        self._conn = None

    def handleNotification(self, handle, data):
        if handle in self._callbacks:
            self._callbacks[handle](data)

    @property
    def mac(self):
        return self._mac

    def set_callback(self, handle, function):
        self._callbacks[handle] = function

    def make_request(self, handle, value, nextInter=False, with_response=True):
        try:
            self._conn.writeCharacteristic(handle, value, withResponse=with_response)
            self._conn.waitForNotifications(2.0)
            if nextInter:
                self._iter = 0 if self._iter > 99 else self._iter + 1

            return True
        except BaseException as ex:
            _LOGGER.error('not send request %s', inspect.getouterframes(inspect.currentframe(), 2)[1][3])
            _LOGGER.exception(ex)

        return False

class RedmondKettler:

    def __init__(self, hass, addr, key, device, backlight):
        self.hass = hass
        self._mac = addr
        self._key = key
        self._device = device
        self._use_backlight = backlight
        self._type = 1
        self._name = 'redmond sky'
        self._mntemp = CONF_MIN_TEMP
        self._mxtemp = CONF_MAX_TEMP
        self._tgtemp = CONF_TARGET_TEMP
        self._temp = 0
        self._time_upd = '00:00'
        self._boiltime = '80'
        self._rgb1 = '0000ff'
        self._rgb2 = 'ff0000'
        self._rand = '5e'
        self._mode = '00' # '00' - boil, '01' - heat to temp, '03' - backlight  for cooker 00 - heat after cook   01 - off after cook        for fan 00-06 - speed 
        self._status = '00' #may be '00' - OFF or '02' - ON         for cooker 00 - off   01 - setup program   02 - on  04 - heat   05 - delayed start
        self._prog = '00' #  program
        self._sprog = '00' # subprogram
        self._ph = 0 #  program hours
        self._pm = 0 #  program min
        self._th = 0 #  timer hours
        self._tm = 0 #  timer min
        self._ion = '00' # 00 - off   01 - on
        self._connected = False
        self._conn = BTLEConnection(self._mac, self._device)
        self._conn.set_callback(11, self.handle_notification)

    def handle_notification(self, data):
        s = binascii.b2a_hex(data).decode("utf-8")
        arr = [s[x:x+2] for x in range(0, len(s), 2)]

        ### sendAuth
        if arr[2] == 'ff':
            if self._type in [0, 1, 3, 4, 5]:
                if arr[3] == '01':
                    self._connected = True
                else:
                    self._connected = False
            elif self._type == 2:
                if arr[3] == '02':
                    self._connected = True
                else:
                    self._connected = False

        ### sendOn, sendOff, sendMode, sendSync, sendSetLights, sendGetLights, sendUseBacklight
        elif arr[2] in ['03', '04', '6e', '32' , '33', '37']:
            pass

        ### sendStatus
        elif arr[2] == '06': 
            if self._type == 0:
                self._temp = self.hexToDec(str(arr[13]))
                self._status = str(arr[11])
                self._mode = str(arr[3])
                tgtemp = str(arr[5])
                if tgtemp != '00':
                    self._tgtemp = self.hexToDec(tgtemp)
                else:
                    self._tgtemp = 100
            elif self._type in [1, 2]:
                self._temp = self.hexToDec(str(arr[8]))
                self._status = str(arr[11])
                self._mode = str(arr[3])
                tgtemp = str(arr[5])
                if tgtemp != '00':
                    self._tgtemp = self.hexToDec(tgtemp)
                else:
                    self._tgtemp = 100
            elif self._type == 3:
                self._status = str(arr[11])
                self._mode = str(arr[5])
                self._ion = str(arr[14])
            elif self._type == 4:
                self._status = str(arr[11])
                self._mode = str(arr[3])
            elif self._type == 5:
                self._prog = str(arr[3])
                self._sprog = str(arr[4])
                self._temp = self.hexToDec(str(arr[5]))
                self._tgtemp = self.hexToDec(str(arr[5]))
                self._ph = self.hexToDec(str(arr[6]))
                self._pm = self.hexToDec(str(arr[7]))
                self._th = self.hexToDec(str(arr[8]))
                self._tm = self.hexToDec(str(arr[9]))
                self._mode = str(arr[10])
                self._status = str(arr[11])

            async_dispatcher_send(self.hass, 'ready4skyupdate')

    def calcMidColor(self, rgb1, rgb2):
        try:
            hs1 = self.rgbhex_to_hs(rgb1)
            hs2 = self.rgbhex_to_hs(rgb2)
            hmid = int((hs1[0]+hs2[0])/2)
            smid = int((hs1[1]+hs2[1])/2)
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

    def hexToDec(self, chr):
        return int(str(chr), 16)

    def decToHex(self, num):
        char = str(hex(int(num))[2:])
        if len(char) < 2:
            char = '0' + char
        return char

    def sendResponse(self, conn):
        if self._connected:
            return conn.make_request(12, binascii.a2b_hex(bytes('0100', 'utf-8')))
        return False

    def sendAuth(self, conn):
        return self.sendResponse(conn) and conn.make_request(14, binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + 'ff' + self._key + 'aa', 'utf-8')), True)

    def sendOn(self,conn):
        if self._type == 0:
            return True

        if self._type in [1, 2, 3, 4, 5]:
            return conn.make_request(14, binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '03aa', 'utf-8')), True)

        return False

    def sendOff(self,conn):
        return conn.make_request(14, binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '04aa', 'utf-8')), True)

    def sendSync(self, conn, timezone = 4):
        if self._type in [0, 3, 4, 5]:
            return True

        if self._type in [1, 2]:
            if not self._use_backlight:
                return True

            tmz_hex_list = wrap(str(self.decToHex(timezone*60*60)), 2)
            tmz_str = ''
            for i in reversed(tmz_hex_list):
                tmz_str+=i
            timeNow_list = wrap(str(self.decToHex(time.mktime(datetime.now().timetuple()))), 2)
            timeNow_str = ''
            for i in reversed(timeNow_list):
                timeNow_str+=i

            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '6e' + timeNow_str + tmz_str + '0000aa', 'utf-8'))
            return conn.make_request(14, str2b, True)

        return False

    def sendStat(self,conn):
        return True

    def sendStatus(self,conn):
        return conn.make_request(14, binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '06aa', 'utf-8')), True)

    # 00 - boil
    # 01 - heat
    # temp 03 - backlight (boil by default)
    # temp - in HEX
    def sendMode(self, conn, mode, temp):
        if self._type in [3, 4, 5]:
            return True

        if self._type == 0:
            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '05' + mode + '00' + temp + '00aa', 'utf-8'))
        elif self._type in [1, 2]:
            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '05' + mode + '00' + temp + '00000000000000000000800000aa', 'utf-8'))

        return conn.make_request(14, str2b, True)

    def sendModeCook(self, conn, prog, sprog, temp, hours, minutes, dhours, dminutes, heat):
        if self._type == 5:
            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '05' + prog + sprog + temp + hours + minutes + dhours + dminutes + heat + 'aa', 'utf-8'))
            return conn.make_request(14, str2b, True)
        else:
            return True

        return False

    def sendTimerCook(self, conn, hours, minutes): #
        if self._type == 5:
            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '0c' + hours + minutes + 'aa', 'utf-8'))
            return conn.make_request(14, str2b, True)
        else:
            return True

        return False

    def sendTempCook(self, conn, temp): #temp in HEX or speed 00-06
        if self._type in [3, 5]:
            return conn.make_request(14, binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '0b' + temp + 'aa', 'utf-8')), True)
        else:
            return True

        return False

    def sendIonCmd(self, conn, onoff): #00-off 01-on
        if self._type == 3:
            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '1b' + onoff + 'aa', 'utf-8'))
            return conn.make_request(14, str2b, True)
        else:
            return True
        return False

    def sendAfterSpeed(self, conn):
        if self._type == 3:
            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '0900aa', 'utf-8'))
            return conn.make_request(14, str2b, True)
        else:
            return  True
        return False

    def sendUseBackLight(self, conn):
        if self._type in [0, 3, 4, 5]:
            return True

        if self._type in [1, 2]:
            onoff = "01" if self._use_backlight else "00"
            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '37c8c8' + onoff + 'aa', 'utf-8'))
            return conn.make_request(14, str2b, True)

        return False

    def sendSetLights(self, conn, boilOrLight = '01', rgb1 = '0000ff'): # 00 - boil light    01 - backlight
        if self._type in [0, 3, 4, 5]:
            return True

        if self._type in [1, 2]:
            rgb_mid = rgb1
            rgb2 = rgb1

            if boilOrLight == "00":
                scale_light = ['28', '46', '64']
            else:
                scale_light = ['00', '32', '64']

            str2b = binascii.a2b_hex(bytes('55' + self.decToHex(self._conn._iter) + '32' + boilOrLight + scale_light[0] + self._rand + rgb1 + scale_light[1] + self._rand + rgb_mid + scale_light[2] + self._rand + rgb2 + 'aa', 'utf-8'))
            return conn.make_request(14, str2b, True)

        return False

    ### composite methods
    def startNightColor(self, i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    offed = False
                    if self._status == '02':
                        if self.sendOff(conn):
                            offed = True
                    else:
                        offed = True
                    if offed:
                        if self.sendSetLights(conn, '01', self._rgb1):
                            if self.sendMode(conn, '03', '00'):
                                if self.sendOn(conn):
                                    if self.sendStatus(conn):
                                        self._time_upd = time.strftime("%H:%M")
                                        answ = True
        except:
            pass

        return answ

    async def async_startNightColor(self):
        await self.hass.async_add_executor_job(self.startNightColor)

    def modeOn(self, mode = "00", temp = "00", i = 0):
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    offed = False
                    if self._status == '02':
                        if self.sendOff(conn):
                            offed = True
                    else:
                        offed = True

                    if offed and self.sendMode(conn, mode, temp) and self.sendOn(conn) and self.sendStatus(conn):
                        self._time_upd = time.strftime("%H:%M")
                        return True
        except:
            pass

        return False

    async def async_modeOn(self, mode = "00", temp = "00"):
        await self.hass.async_add_executor_job(partial(self.modeOn, mode, temp, 0))

    def modeOnCook(self, prog, sprog, temp, hours, minutes, dhours='00', dminutes='00', heat = '01', i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    offed = False
                    if self._status != '00':
                        if self.sendOff(conn):
                            offed = True
                    else:
                        offed = True
                    if offed:
                        if self.sendModeCook(conn, prog, sprog, temp, hours, minutes, dhours, dminutes, heat):
                            if self.sendOn(conn):
                                if self.sendStatus(conn):
                                    self._time_upd = time.strftime("%H:%M")
                                    answ = True
        except:
            pass

        return answ

    async def async_modeOnCook(self, prog, sprog, temp, hours, minutes, dhours='00', dminutes='00', heat = '01'):
        await self.hass.async_add_executor_job(partial(self.modeOnCook, prog, sprog, temp, hours, minutes, dhours, dminutes, heat, 0))

    def modeTempCook(self, temp, i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    if self.sendTempCook(conn, temp):
                        if self.sendStatus(conn):
                            self._time_upd = time.strftime("%H:%M")
                            answ = True
        except:
            pass

        return answ

    async def async_modeTempCook(self, temp):
        await self.hass.async_add_executor_job(partial(self.modeTempCook, temp, 0))

    def modeFan(self, speed, i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    if self.sendTempCook(conn, speed):
                        if self.sendAfterSpeed(conn):
                            if self._status == '00':
                                answ1 = self.sendOn(conn)
                            if self.sendStatus(conn):
                                self._time_upd = time.strftime("%H:%M")
                                answ = True
        except:
            pass

        return answ

    async def async_modeFan(self, speed):
        await self.hass.async_add_executor_job(partial(self.modeFan, speed, 0))

    def modeIon(self, onoff, i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    if self.sendIonCmd(conn, onoff):
                        if self.sendStatus(conn):
                            self._time_upd = time.strftime("%H:%M")
                            answ = True
        except:
            pass

        return answ

    async def async_modeIon(self, onoff):
        await self.hass.async_add_executor_job(partial(self.modeIon, onoff, 0))

    def modeTimeCook(self, hours, minutes, i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    if self.sendTimerCook(conn, hours, minutes):
                        if self.sendStatus(conn):
                            self._time_upd = time.strftime("%H:%M")
                            answ = True
        except:
            pass
        if not answ:
            i=i+1
            if i<5:
                answ = self.modeTimeCook(hours, minutes, i)
            else:
                _LOGGER.warning('five attempts of modeTimeCook failed')
        return answ

    async def async_modeTimeCook(self, hours, minutes):
        await self.hass.async_add_executor_job(partial(self.modeTimeCook, hours, minutes, 0))

    def modeOff(self, i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    if self.sendOff(conn):
                        if self.sendStatus(conn):
                            self._time_upd = time.strftime("%H:%M")
                            answ = True
        except:
            pass

        return answ

    async def async_modeOff(self):
        await self.hass.async_add_executor_job(self.modeOff)

    def firstConnect(self, i = 0):
        self.findType()
        self._connected = False

        try:
            with self._conn as conn:
                for i in range(10): # 10 attempts to auth
                    if self.sendAuth(conn):
                        break
                    time.sleep(1)

                if self._connected:
                    if self.sendUseBackLight(conn) and self.sendSync(conn) and self.sendStatus(conn):
                        self._time_upd = time.strftime("%H:%M")
                        return True
        except BaseException as ex:
            _LOGGER.exception(ex)

        return False

    async def async_firstConnect(self):
        await self.hass.async_add_executor_job(self.firstConnect)

    def findType(self):
        #try:
        match_result = search(r'hci([\d]+)', self._device)
        if match_result is not None:
            iface = int(match_result.group(1))
            scanner = btle.Scanner(iface=iface)
            ble_devices = {device.addr:str(device.getValueText(9)) for device in scanner.scan(3.0)}
            dev_name = ble_devices.get(self._mac, 'None')
            self._type = SUPPORTED_DEVICES.get(dev_name, 1)
            if dev_name != 'None':
                self._name = dev_name
        #except:
            #_LOGGER.error('unable to know the type of device...use default')

    def modeUpdate(self, i=0):
        answ = False
        try:
            with self._conn as conn:
                if self.sendAuth(conn):
                    if self.sendSync(conn):
                        if self.sendStatus(conn):
                            self._time_upd = time.strftime("%H:%M")
                            answ = True
        except:
            pass

        return answ

    async def async_modeUpdate(self):
        await self.hass.async_add_executor_job(self.modeUpdate)

    async def async_update(self, now, **kwargs) -> None:
        await self.async_modeUpdate()

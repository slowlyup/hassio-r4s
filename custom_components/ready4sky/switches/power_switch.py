from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription, SwitchDeviceClass
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .. import DOMAIN, SIGNAL_UPDATE_DATA, RedmondKettle, MODE_BOIL, STATUS_ON


class RedmondPowerSwitch(SwitchEntity):
    def __init__(self, kettle: RedmondKettle):
        self._kettle = kettle
        self.entity_description = SwitchEntityDescription(
            key="power_on",
            name=kettle._name + " Turn power"
        )
        self._attr_is_on = False

        self._attr_unique_id = f'{DOMAIN}[{kettle._mac}][switch][{self.entity_description.key}]'
        self._attr_device_info = DeviceInfo(connections={("mac", kettle._mac)})

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self._kettle.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._attr_is_on = False
        if self._kettle._status == STATUS_ON and self._kettle._mode == MODE_BOIL:
            self._attr_is_on = True
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self._kettle._available

    async def async_turn_on(self, **kwargs):
        await self._kettle.modeOn()

    async def async_turn_off(self, **kwargs):
        await self._kettle.modeOff()

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription, SwitchDeviceClass
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .. import DOMAIN, SIGNAL_UPDATE_DATA


class RedmondSwitchIonization(SwitchEntity):

    def __init__(self, kettle):
        self._kettle = kettle
        self.entity_description = SwitchEntityDescription(
            key="ionization_on",
            name=kettle._name + " Enable Ionization",
            icon="mdi:flash",
            device_class=SwitchDeviceClass.SWITCH,
        )
        self._attr_is_on = False

        self._attr_unique_id = f'{DOMAIN}[{kettle._mac}][switch][{self.entity_description.key}]'
        self._attr_device_info = DeviceInfo(connections={("mac", kettle._mac)})

    @property
    def unique_id(self):
        return f"{DOMAIN}[{self._kettle._mac}][switch][{self.entity_description.key}]"

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self._kettle.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._attr_is_on = False
        if self._kettle._ion == '01':
            self._attr_is_on = True
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self._kettle._available

    async def async_turn_on(self, **kwargs):
        await self._kettle.modeIon('01')

    async def async_turn_off(self, **kwargs):
        await self._kettle.modeIon('00')

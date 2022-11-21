from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass, SwitchEntityDescription
from homeassistant.helpers.entity import EntityCategory, DeviceInfo

from .. import DOMAIN, RedmondKettle


class RedmondConfSwitchSound(SwitchEntity):
    def __init__(self, kettle: RedmondKettle):
        self._kettle = kettle
        self.entity_description = SwitchEntityDescription(
            key="conf_sound_on",
            name=kettle._name + " Enable sound",
            icon="mdi:volume-high",
            device_class=SwitchDeviceClass.SWITCH,
            entity_category=EntityCategory.CONFIG,
        )

        self._attr_unique_id = f'{DOMAIN}[{kettle._mac}][switch][{self.entity_description.key}]'
        self._attr_device_info = DeviceInfo(connections={("mac", kettle._mac)})

    @property
    def should_poll(self):
        return False

    @property
    def assumed_state(self):
        return False

    @property
    def available(self):
        return self._kettle._available

    @property
    def is_on(self):
        return self._kettle._conf_sound_on

    async def async_turn_on(self, **kwargs):
        await self._kettle.setConfEnableSound(True)

    async def async_turn_off(self, **kwargs):
        await self._kettle.setConfEnableSound(False)

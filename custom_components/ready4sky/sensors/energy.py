from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity, SensorEntityDescription
from homeassistant.const import ENERGY_WATT_HOUR
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .. import (
    DOMAIN,
    SIGNAL_UPDATE_DATA,
    ATTR_WORK_ALLTIME,
    ATTR_TIMES
)


class RedmondEnergySensor(SensorEntity):
    def __init__(self, kettle):
        self._kettle = kettle
        self.entity_description = SensorEntityDescription(
            key="energy",
            name=kettle._name + " Energy",
            icon="mdi:lightning-bolt",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=ENERGY_WATT_HOUR
        )

        self._attr_unique_id = f'{DOMAIN}[{kettle._mac}][sensor][{self.entity_description.key}]'
        self._attr_device_info = DeviceInfo(connections={("mac", kettle._mac)})
        self._attr_native_value = self._kettle._Watts

    async def async_added_to_hass(self):
        self.update()
        self.async_on_remove(async_dispatcher_connect(self._kettle.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._attr_native_value = self._kettle._Watts
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self._kettle._available

    @property
    def extra_state_attributes(self):
        return {
            ATTR_TIMES: self._kettle._times,
            ATTR_WORK_ALLTIME: self._kettle._alltime,
        }

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .. import (
    DOMAIN,
    SIGNAL_UPDATE_DATA,
    STATUS_ON,
    MODE_BOIL,
    MODE_KEEP_WARM,
    MODE_LIGHT,
    ATTR_SYNC,
    COOKER_STATUS_PROGRAM,
    COOKER_STATUS_KEEP_WARM,
    COOKER_STATUS_DELAYED_START, ATTR_TIMER_SET, ATTR_TIMER_CURR
)


class RedmondSensor(SensorEntity):
    def __init__(self, kettle):
        self._kettle = kettle
        self.entity_description = SensorEntityDescription(
            key="status",
            name=kettle._name + " Status",
        )
        self._sync = None

        self._attr_unique_id = f'{DOMAIN}[{kettle._mac}][sensor][{self.entity_description.key}]'
        self._attr_device_info = DeviceInfo(connections={("mac", kettle._mac)})

    async def async_added_to_hass(self):
        self.update()
        self.async_on_remove(async_dispatcher_connect(self._kettle.hass, SIGNAL_UPDATE_DATA, self.update))

    def update(self):
        self._attr_native_value = 'off'

        # Cooker
        if self._kettle._type == 5:
            if self._kettle._status == COOKER_STATUS_PROGRAM:
                self._attr_native_value = 'program'
            elif self._kettle._status == STATUS_ON:
                self._attr_native_value = 'on'
            elif self._kettle._status == COOKER_STATUS_KEEP_WARM:
                self._attr_native_value = 'keep_warm'
            elif self._kettle._status == COOKER_STATUS_DELAYED_START:
                self._attr_native_value = 'delayed_start'

        elif self._kettle._status == STATUS_ON:
            if self._kettle._type in [3, 4]:
                self._attr_native_value = 'on'
            elif self._kettle._mode == MODE_BOIL:
                self._attr_native_value = 'boil'
            elif self._kettle._mode == MODE_KEEP_WARM:
                self._attr_native_value = 'keep_warm'
            elif self._kettle._mode == MODE_LIGHT:
                self._attr_native_value = 'light'
    
        self._sync = str(self._kettle._time_upd)

        if self._kettle._type == 5:
            self._timer_prog = str(self._kettle._ph) + ':' + str(self._kettle._pm)
            self._timer_curr = str(self._kettle._th) + ':' + str(self._kettle._tm)

        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        return False

    @property
    def icon(self):
        return 'mdi:toggle-switch' if self._attr_native_value != 'off' else 'mdi:toggle-switch-off'

    @property
    def available(self):
        return self._kettle._available

    @property
    def extra_state_attributes(self):
        attributes = {
            ATTR_SYNC: str(self._sync)
        }

        if self._kettle._type == 5:
            attributes[ATTR_TIMER_SET] = self._timer_prog
            attributes[ATTR_TIMER_CURR] = self._timer_curr

        return attributes

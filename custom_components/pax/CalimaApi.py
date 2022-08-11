import logging
import threading

from .Calima import Calima
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

class CalimaApi:
    def __init__(self, hass, name, mac, pin):
        self._hass = hass
        self._name = name
        self._mac = mac
        self._pin = pin
        self._state = { }

    def get_data(self, key):
        if key in self._state:
            return self._state[key]
        return STATE_UNKNOWN

    def set_data(self, key, value):
        _LOGGER.debug("Set_Data: %s %s", key, value)
        self._state[key] = value

    async def write_data(self, key):
        _LOGGER.debug("Write_Data: %s", key)

        # Create device
        fan = Calima(self._hass)

        try:
            # Connect to device
            await fan.init(self._mac, self._pin)
            if not fan.isConnected():
                return False

            # Write data
            match key:
                case 'automatic_cycles':
                    await fan.setAutomaticCycles(int(self._state['automatic_cycles']))
                case 'boostmode':
                    # Use default values if not set up
                    if int(self._state['boostmodesec']) == 0:
                        self._state['boostmodespeed'] = 2400
                        self._state['boostmodesec'] = 600
                        
                    await fan.setBoostMode(int(self._state['boostmode']), int(self._state['boostmodespeed']), int(self._state['boostmodesec']))          
                case 'lightsensorsettings_delayedstart' | 'lightsensorsettings_runningtime':
                    await fan.setLightSensorSettings(int(self._state['lightsensorsettings_delayedstart']), int(self._state['lightsensorsettings_runningtime']))
                case 'sensitivity_humidity' | 'sensitivity_light':
                    await fan.setSensorsSensitivity(int(self._state['sensitivity_humidity']), int(self._state['sensitivity_light']))
                case 'trickledays_weekdays' | 'trickledays_weekends':
                    await fan.setTrickleDays(int(self._state['trickledays_weekdays']), int(self._state['trickledays_weekends']))

                case 'fanspeed_humidity' | 'fanspeed_light' | 'fanspeed_trickle':
                    await fan.setFanSpeedSettings(int(self._state['fanspeed_humidity']), int(self._state['fanspeed_light']), int(self._state['fanspeed_trickle']))
                case 'heatdistributorsettings_temperaturelimit' | 'heatdistributorsettings_fanspeedbelow' | 'heatdistributorsettings_fanspeedabove':
                    """ Not implemented """
                case 'silenthours_on' | 'silenthours_startinghour' | 'silenthours_startingminute' | 'silenthours_endinghour' | 'silenthours_endingminute':
                    await fan.setSilentHours(int(self._state['silenthours_on']), int(self._state['silenthours_startinghour']), int(self._state['silenthours_startingminute']), int(self._state['silenthours_endinghour']), int(self._state['silenthours_endingminute']))
  
                case _:
                    return False
        except Exception as e:
            _LOGGER.debug('Not connected: ' + str(e))
            return False

        if fan is not None:
            await fan.disconnect()
        return True

    @property
    def name(self):
        return self._name

    @property
    def mac(self):
        return self._mac

    @property
    def pin(self):
        return self._pin

    async def update_data(self, fan):
        FanState = await fan.getState()
        FanMode = await fan.getMode()
        FanSpeeds = await fan.getFanSpeedSettings()
        Sensitivity = await fan.getSensorsSensitivity()
        LightSensorSettings = await fan.getLightSensorSettings()
        HeatDistributorSettings = await fan.getHeatDistributor()
        BoostMode = await fan.getBoostMode()
        SilentHours = await fan.getSilentHours()
        TrickleDays = await fan.getTrickleDays()
        AutomaticCycles = await fan.getAutomaticCycles()

        if (FanState is None):
            _LOGGER.debug('Could not read data')
        else: 
            self._state['humidity'] = FanState.Humidity
            self._state['temperature'] = FanState.Temp
            self._state['light'] = FanState.Light
            self._state['rpm'] = FanState.RPM
            self._state['state'] = FanState.Mode

            self._state['mode'] = FanMode

            self._state['fanspeed_humidity'] = FanSpeeds.Humidity
            self._state['fanspeed_light'] = FanSpeeds.Light
            self._state['fanspeed_trickle'] = FanSpeeds.Trickle

            self._state['sensitivity_humidity'] = Sensitivity.Humidity
            self._state['sensitivity_light'] = Sensitivity.Light

            self._state['lightsensorsettings_delayedstart'] = LightSensorSettings.DelayedStart
            self._state['lightsensorsettings_runningtime'] = LightSensorSettings.RunningTime

            self._state['heatdistributorsettings_temperaturelimit'] = HeatDistributorSettings.TemperatureLimit
            self._state['heatdistributorsettings_fanspeedbelow'] = HeatDistributorSettings.FanSpeedBelow
            self._state['heatdistributorsettings_fanspeedabove'] = HeatDistributorSettings.FanSpeedAbove

            self._state['boostmode'] = BoostMode.OnOff
            self._state['boostmodespeed'] = BoostMode.Speed
            self._state['boostmodesec'] = BoostMode.Seconds

            self._state['silenthours_on'] = SilentHours.On
            self._state['silenthours_startinghour'] = SilentHours.StartingHour
            self._state['silenthours_startingminute'] = SilentHours.StartingMinute
            self._state['silenthours_endinghour'] = SilentHours.EndingHour
            self._state['silenthours_endingminute'] = SilentHours.EndingMinute

            self._state['trickledays_weekdays'] = TrickleDays.Weekdays
            self._state['trickledays_weekends'] = TrickleDays.Weekends

            self._state['automatic_cycles'] = AutomaticCycles

    async def async_fetch_data(self):
        try:
            # Create device
            fan = Calima(self._hass)

            # Connect to device
            await fan.init(self._mac, self._pin)
            if not fan.isConnected():
                return False

            # Fetch data
            await self.update_data(fan)
        except Exception as e:
            _LOGGER.debug('Not connected: ' + str(e))
        finally:
            if fan is not None:
                await fan.disconnect()

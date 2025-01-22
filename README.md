# Home assistant Custom component for Pax Calima

## Installation

Download using HACS (manually add repo) or manually put it in the custom_components folder.

## Supported devices

This integration was originally meant to just support Pax Calima, but as other fans have been made that builds on the same concept, this 
integration now supports:
* Pax Calima
* Pax Levante 50
* Vent-Axia Svara (Same as the Calima)
* Vent-Axia Svensa (same as PureAir Sense and Fresh Intellivent SKY)

If you've got other fans of the same'ish type, just give it a go and let me know how it works out :)

## Add device

The integration supports discovery of devices, but only for Calima (until someone tells me how I can add multiple device-types in manifest "local_name", or if there's another way...)
If discovery doesn't work you may try to add it manually through the integration configuration.
If you have issues connecting, try cycling power on the device. It seems that the Bluetooth interface easily hangs if it's messed around with a bit.

For Svensa-specific instructions, see [here](svensa.md).

## PIN code

A valid PIN code is required to be able to control the fan. You can add the fan without PIN, but then you'll only be able to read values.
* For Calima/Svara you just enter the decimal value printed on the fan motor (remove from base)
* For Svensa, the PIN is not written on the device, but should be requested from it. See [instructions for Svensa](svensa.md).
* For Levante 50, select Calima as model but request the PIN using the steps outlined for Svensa. Enter pairing mode by powercycling the fan using the switch on the side.

## Sensor data

The sensors for temp/humidity/light seem to be a bit inaccurate, or I'm not converting them correctly, so don't expect them to be as accurate as from other dedicated sensors.
The humidity sensor will show 0 when humidity is low!
Airflow is just a conversion of the fan speed based on a linear correlation between those two. This is a bit inaccurate at best, as the true flow will vary greatly depending on how your fan is mounted.

## Good to know

Speed and duration for boostmode are local variables in home assistant, and as such will not influence boostmode from the app. These variables will also be reset to default if you re-add a device.

Configuration parameters are read only on Home Assistant startup, and subsequently once every day, to get any changes made from elsewhere.

Fast scan interval refers to the interval after a write has been made. This allows for quick feedback when the fan is controlled and does not disconnect between reads. This fast interval will remain for 10 reads.

Setting speed to less than 800 RPM might stall the fan, depending on the specific application. I don't know if stalling like this could damage the fan/motor, so do this with care.

## Thanks

- [@PatrickE94](https://github.com/PatrickE94/pycalima) for the Calima driver
- [@MarkoMarjamaa](https://github.com/MarkoMarjamaa/homeassistant-paxcalima) for a good starting point for the HA-implementation

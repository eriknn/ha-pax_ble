# Home assistant Custom component for Pax Calima

## Installation

Download using HACS or manually put it in custom_components folder.

## Add device

The integration supports discovery of devices, so any fans should be automatically discovered.
If not you may try to add it manually through the integration configuration.

## Debugging

If there are problems, please enable debugging in configuration.yaml

```
# Logging
logger:
  default: warning
  logs:
    custom_components.pax_ble: debug
```

## Good to know

Speed and duration for boostmode are local variables in home assistant, and as such will not influence boostmode from the app. These variables will also be reset to default if you re-add a device.

## Thanks

@PatrickE94 for the Calima driver:
https://github.com/PatrickE94/pycalima

@MarkoMarjamaa for a good starting point for the HA-implementation
https://github.com/MarkoMarjamaa/homeassistant-paxcalima

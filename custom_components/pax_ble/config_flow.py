"""Config flow to configure Pax integration"""
import logging
import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from typing import Any

from .calima import Calima
from .const import DOMAIN, CONF_NAME, CONF_MAC, CONF_PIN, CONF_SCAN_INTERVAL, CONF_SCAN_INTERVAL_FAST
from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_FAST

_LOGGER = logging.getLogger(__name__)


class PaxConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.currInput = {}

    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return PaxOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        self.setCurrInput("", "", "", DEFAULT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_FAST)

        return await self.async_step_add_device()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by bluetooth discovery."""
        await self.async_set_unique_id(dr.format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.setCurrInput(
            discovery_info.name,
            dr.format_mac(discovery_info.address),
            "",
            DEFAULT_SCAN_INTERVAL,
            DEFAULT_SCAN_INTERVAL_FAST
        )

        return await self.async_step_add_device()

    """##################################################
    ##################### ADD DEVICE ####################
    ##################################################"""

    async def async_step_add_device(self, user_input=None):
        """Common handler for adding device."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(dr.format_mac(user_input[CONF_MAC]))

            self._abort_if_unique_id_configured()

            fan = Calima(self.hass, user_input[CONF_MAC], user_input[CONF_PIN])

            if await fan.connect():
                await fan.setAuth(user_input[CONF_PIN])
                pin_verified = await fan.checkAuth()
                await fan.disconnect()

                if pin_verified:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )
                else:
                    errors["base"] = "wrong_pin"
                    # Store values for new attempt
                    self.currInput = user_input
            else:
                errors["base"] = "cannot_connect"
                # Store values for new attempt
                self.currInput = user_input

        data_schema = getDeviceSchema(self.currInput)
        return self.async_show_form(
            step_id="add_device", data_schema=data_schema, errors=errors
        )

    def setCurrInput(self, name: str, mac: str, pin: str, scan_interval: int, scan_interval_fast: int):
        self.currInput[CONF_NAME] = name
        self.currInput[CONF_MAC] = mac
        self.currInput[CONF_PIN] = pin
        self.currInput[CONF_SCAN_INTERVAL] = scan_interval
        self.currInput[CONF_SCAN_INTERVAL_FAST] = scan_interval_fast
        

class PaxOptionsFlowHandler(OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        # Manage the options for the custom component."""
        return await self.async_step_configure_device()

    """##################################################
    ################## CONFIGURE DEVICE #################
    ##################################################"""

    async def async_step_configure_device(self, user_input=None):
        """Common handler for configuring device."""
        errors = {}

        if user_input is not None:
            # Add data from original config entry
            user_input[CONF_NAME] = self.config_entry.data[CONF_NAME]
            user_input[CONF_MAC] = self.config_entry.data[CONF_MAC]
            user_input[CONF_PIN] = self.config_entry.data[CONF_PIN]
            
            # Update config entry
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input, options=self.config_entry.options
            )

            # Store no options - we have updated config entry
            return self.async_create_entry(title="", data={})

        data_schema = getDeviceSchemaOptions(self.config_entry.data)
        return self.async_show_form(
            step_id="configure_device", data_schema=data_schema, errors=errors
        )


""" Schema Helper functions """


def getDeviceSchema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    data_schema = vol.Schema(
        {
            vol.Required(
                CONF_NAME, description="Name", default=user_input[CONF_NAME]
            ): cv.string,
            vol.Required(
                CONF_MAC, description="MAC Address", default=user_input[CONF_MAC]
            ): cv.string,
            vol.Required(
                CONF_PIN, description="Pin Code", default=user_input[CONF_PIN]
            ): cv.string,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
            vol.Optional(
                CONF_SCAN_INTERVAL_FAST, default=user_input[CONF_SCAN_INTERVAL_FAST]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
        }
    )

    return data_schema


def getDeviceSchemaOptions(user_input: dict[str, Any] | None = None) -> vol.Schema:
    data_schema = vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
            vol.Optional(
                CONF_SCAN_INTERVAL_FAST, default=user_input[CONF_SCAN_INTERVAL_FAST]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
        }
    )

    return data_schema

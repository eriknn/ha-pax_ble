"""Config flow to configure Pax integration"""

import logging

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
import voluptuous as vol
from homeassistant import config_entries

from .const import (DOMAIN, CONF_NAME, CONF_MAC, CONF_PIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

_LOGGER = logging.getLogger(__name__)

class PaxConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        pass

    # This doesn't really work well at the  
    #def async_get_options_flow(config_entry):
    #    """Get the options flow for this handler."""
    #    return PaxOptionsFlowHandler(config_entry) 

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""        
        self.context['device_data'] = {'name': '',
                                       'mac': ''
                                      }
        
        return await self.async_step_add_device()

    async def async_step_bluetooth(self, discovery_info):
        """Handle a flow initialized by bluetooth discovery."""
        await self.async_set_unique_id(dr.format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.context['device_data'] = {'name': discovery_info.name,
                                       'mac': dr.format_mac(discovery_info.address)
                                      }

        return await self.async_step_add_device()

    """##################################################
    ##################### ADD DEVICE ####################
    ##################################################"""
    async def async_step_add_device(self, user_input=None):       
        """ Common handler for adding device. """
        errors = {}
        
        data_schema = getDeviceSchema(mac=self.context['device_data']['mac'])

        if user_input is not None:
            await self.async_set_unique_id(dr.format_mac(user_input[CONF_MAC]))
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title="Pax Calima",data=user_input)

        return self.async_show_form(step_id="add_device", data_schema=data_schema, errors=errors)

class PaxOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        # Manage the options for the custom component."""
        return await self.async_step_configure_device()

    """##################################################
    ################## CONFIGURE DEVICE #################
    ##################################################"""
    async def async_step_configure_device(self, user_input=None):
        """ Common handler for configuring device. """
        errors = {}

        name = self.config_entry.data[CONF_NAME]
        mac = self.config_entry.data[CONF_MAC]
        pin = self.config_entry.data[CONF_PIN]
        scan_interval = self.config_entry.data[CONF_SCAN_INTERVAL]
        
        data_schema = getDeviceSchema(name, mac, pin, scan_interval)

        if user_input is not None:
            # Update config entry
            self.hass.config_entries.async_update_entry(self.config_entry, data=user_input, options=self.config_entry.options)            

            # Store no options - we have updated config entry
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="configure_device", data_schema=data_schema, errors=errors)

""" Schema Helper functions """
def getDeviceSchema(name='', mac='', pin='', scan_interval=DEFAULT_SCAN_INTERVAL):
    data_schema = vol.Schema(
        {
            vol.Required(CONF_NAME, description="Name", default=name): cv.string,
            vol.Required(CONF_MAC, description="MAC Address", default=mac): cv.string,
            vol.Required(CONF_PIN, description="Pin Code", default=pin): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=scan_interval): vol.All(vol.Coerce(int), vol.Range(min=1, max=999)),  
        }
    )

    return data_schema

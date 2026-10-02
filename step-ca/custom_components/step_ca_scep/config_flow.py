"""Config flow for the Step CA SCEP integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import CONF_ENROLL_PORT, CONF_PORTAL_PORT, CONF_ROOT_PEM, DOMAIN


class StepCaScepConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up forwarding to the Step CA SCEP add-on."""

    VERSION = 1

    _discovered: dict[str, Any]

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle the add-on announcing itself through Supervisor discovery."""
        config = discovery_info.config
        data = {
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: int(config[CONF_PORT]),
            CONF_ROOT_PEM: config.get(CONF_ROOT_PEM, ""),
            CONF_ENROLL_PORT: int(config.get(CONF_ENROLL_PORT) or 0),
            CONF_PORTAL_PORT: int(config.get(CONF_PORTAL_PORT) or 8102),
        }
        # There is only one CA; keep its entry pointed at the add-on's current
        # hostname and root even if the add-on is reinstalled.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates=data)

        self._discovered = data
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm enabling SCEP on the Home Assistant port."""
        if user_input is not None:
            return self.async_create_entry(title="Step CA SCEP", data=self._discovered)
        return self.async_show_form(step_id="hassio_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup for a step-ca SCEP endpoint without Supervisor."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Step CA SCEP",
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_ROOT_PEM: "",
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=9080): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
        )

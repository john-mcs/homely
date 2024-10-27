"""Config flow for Homely integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LOCATION, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .homely import Homely, HomelyError, LoginError

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class HomelyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Your Alarm Control Panel Integration."""

    VERSION = 1
    MINOR_VERSION = 0

    homely_session: Homely
    username: str
    password: str

    async def async_step_user(self, user_input=None):
        """Handle the first step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        errors = {}

        self.username = user_input[CONF_USERNAME]
        self.password = user_input[CONF_PASSWORD]

        # Create an instance of the API-obect.
        self.homely_session = Homely(
            self.username, self.password, session=async_get_clientsession(self.hass)
        )

        # Attempt to log in with the given credentials.
        try:
            session_valid = await self.homely_session.get_token()
        except LoginError:
            # Invalid credentials.
            _LOGGER.debug("Homely: Bad credentials")
            errors["base"] = "invalid_auth"
            session_valid = False
        except HomelyError:
            # Any other error.
            _LOGGER.error("Unknown error getting access token")
            errors["base"] = "response_error"
            session_valid = False

        if not session_valid:
            # Could not get access token.
            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
                errors=errors,
            )
        return await self.async_step_installation()

    async def async_step_installation(self, user_input: dict[str, Any] | None = None):
        """Second step to select installation."""
        errors = {}
        try:
            user_locations = await self.homely_session.get_users_locations()
        except HomelyError as err:
            _LOGGER.debug("Homely: Failed to get users locations: %s", err)
            return self.async_abort(reason="locations_error")

        installations = {
            inst["locationId"]: f"{inst['name']}" for inst in (user_locations)
        }

        if user_input is None:
            if len(installations) == 0:
                # No locations returned
                return self.async_abort(reason="locations_none")

            if len(installations) > 1:
                # Multiple locations. Make the user choose which one.
                return self.async_show_form(
                    step_id="installation",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_LOCATION): vol.In(installations)}
                    ),
                    errors=errors,
                )
            # If only one installation available. Just Select it.
            user_input = {CONF_LOCATION: list(installations)[0]}

        await self.async_set_unique_id(str(self.username))
        self._abort_if_unique_id_configured()

        # Save settings.
        return self.async_create_entry(
            title=str(self.username),
            data={
                CONF_USERNAME: self.username,
                CONF_PASSWORD: self.password,
                CONF_LOCATION: user_input[CONF_LOCATION],
            },
        )

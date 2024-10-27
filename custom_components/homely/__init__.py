"""The Homely integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATION, CONF_PASSWORD, CONF_USERNAME, DATA_COORDINATOR, DOMAIN
from .coordinator import HomelyDataUpdateCoordinator
from .homely import Homely, HomelyError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homely from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    homely_api = Homely(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        location_id=entry.data[CONF_LOCATION],
    )

    try:
        # Get API access-token.
        await homely_api.get_token()
    except HomelyError:
        raise ConfigEntryAuthFailed("...") from None

    coordinator = HomelyDataUpdateCoordinator(hass, entry, homely_api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

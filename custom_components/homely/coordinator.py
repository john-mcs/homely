"""Homepy API Data Coordinator."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .homely import Homely, HomelyError

_LOGGER = logging.getLogger(__name__)


class HomelyDataUpdateCoordinator(DataUpdateCoordinator):
    """Homely Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, homely_api: Homely
    ) -> None:
        """Init. Homely API."""
        self.entry = entry
        self._system_state = None
        self._devices = []

        self._client = homely_api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            always_update=True,
        )

    async def _async_update_data(self):
        """Fetch data from Homely."""
        try:
            return await self._client.get_data()
        except HomelyError as ex:
            _LOGGER.debug("Coordinater data update failed")
            raise UpdateFailed(ex) from ex

    def get_device_data(self, device_id):
        """Return a device details based on its ID."""
        for device in self.data["devices"]:
            if device.get("id") == device_id:
                return device
        return None

"""Support for Homely sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LOCATION, DATA_COORDINATOR, DOMAIN
from .coordinator import HomelyDataUpdateCoordinator

STATE_DISARMED = "state_disarmed"
STATE_ARMED_AWAY = "state_armed_away"
STATE_ARMED_HOME = "state_armed_home"
STATE_ARMED_NIGHT = "state_armed_night"
STATE_BREACHED = "state_breached"
STATE_PENDING = "state_pending"
STATE_UNKNOWN = "state_unknown"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homely sensors based on a config entry."""
    coordinator: HomelyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    sensors: list[Entity] = []
    sensors.append(HomelyAlarmState(coordinator))  # The Alarm state sensor.

    for device in coordinator.data["devices"]:
        if "temperature" in device["features"]:
            sensors.append(HomelyThermometer(coordinator, device))  # noqa: PERF401
        if "battery" in device["features"]:
            sensors.append(HomelyBattery(coordinator, device))
    async_add_entities(sensors)


class HomelyAlarmState(CoordinatorEntity[HomelyDataUpdateCoordinator], SensorEntity):
    """Representation of Homely Alarm State."""

    # Alarm state translations
    # In case Homely change the states.
    _alarm_states = {
        "DISARMED": STATE_DISARMED,
        "ARMED_AWAY": STATE_ARMED_AWAY,
        "ARMED_STAY": STATE_ARMED_HOME,
        "ARMED_NIGHT": STATE_ARMED_NIGHT,
        "BREACHED": STATE_BREACHED,
        "ALARM_PENDING": STATE_PENDING,
        "ALARM_STAY_PENDING": STATE_PENDING,
        "ARMED_NIGHT_PENDING": STATE_PENDING,
        "UNKNOWN": STATE_UNKNOWN,
    }

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_options = list(dict.fromkeys(_alarm_states.values()))
    _attr_translation_key = "system_state"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name="Homely Alarm",
            manufacturer="Homely",
            model="Homely",
            identifiers={(DOMAIN, self.coordinator.entry.data[CONF_LOCATION])},
            configuration_url="https://www.homely.no",
        )

    @property
    def unique_id(self):
        """Return the unique ID for this location."""
        return self.coordinator.entry.data[CONF_LOCATION]

    @property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        return self._alarm_states.get(
            self.coordinator.data.get("alarmState", "UNKNOWN")
        )


class HomelyThermometer(CoordinatorEntity[HomelyDataUpdateCoordinator], SensorEntity):
    """Representation of a Homely thermometer."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomelyDataUpdateCoordinator, device_data) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_data = device_data  # All device data from API
        self._device_id = device_data["id"]  # Homely-Device ID
        self._attr_unique_id = f"{self._device_id}_temperature"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name=f"{self._device_data["modelName"]} {self._device_data["name"]}",
            manufacturer="Homely",
            model=self._device_data["modelName"],
            identifiers={(DOMAIN, self._device_id)},
            configuration_url="https://www.homely.no",
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_LOCATION]),
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        self._device_data = self.coordinator.get_device_data(self._device_id)
        return self._device_data["features"]["temperature"]["states"][
            "temperature"
        ].get("value", None)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        self._device_data = self.coordinator.get_device_data(self._device_id)

        return super().available and self._device_data.get("online", False)


class HomelyBattery(CoordinatorEntity[HomelyDataUpdateCoordinator], SensorEntity):
    """Representation of a Homely device battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomelyDataUpdateCoordinator, device_data) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_data = device_data  # All device data from API
        self._device_id = device_data["id"]  # Homely-Device ID
        self._attr_unique_id = f"{self._device_id}_battery"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            manufacturer="Homely",
            model=self._device_data["modelName"],
            identifiers={(DOMAIN, f"{self._device_id}")},
            configuration_url="https://www.homely.no",
            via_device=(DOMAIN, self._device_id),
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        self._device_data = self.coordinator.get_device_data(self._device_id)
        # Assume all batteries are 3V.
        # Limit the value between 0 and 100
        battery_percent = max(
            (
                min(
                    (
                        float(
                            self._device_data["features"]["battery"]["states"][
                                "voltage"
                            ].get("value", "0.0")
                        )
                        * 33.33333
                    ),
                    100.0,
                )
            ),
            0.0,
        )
        return f"{battery_percent:.0f}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        self._device_data = self.coordinator.get_device_data(self._device_id)

        return super().available and self._device_data.get("online", False)

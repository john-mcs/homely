import asyncio
from datetime import datetime, timedelta
import json
import logging

from aiohttp import ClientError

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class HomelyError(Exception):
    """Homely Error class."""


class ResponseError(HomelyError):
    """Unexcpected response."""

    def __init__(self, status_code, text) -> None:
        """ "Initialize Response Error."""
        super().__init__(f"Invalid response, status code: {status_code} - Data: {text}")


class TokenExpiredError(HomelyError):
    """Access-token expired."""


class InvalidArgument(HomelyError):
    """Invalid argument."""


class RequestFailed(HomelyError):
    """HTTP Request failed."""


class LoginError(HomelyError):
    """Login failed."""


class NoAuth(HomelyError):
    """Auth error."""


REQ_TIMEOUT = 10


class Homely:
    """Class for handling interaction with Homely API."""

    URL_API = "https://sdk.iotiliti.cloud/homely"
    URL_TOKEN = URL_API + "/oauth/token"
    URL_TOKEN_REFRESH = URL_API + "/oauth/refresh-token"
    URL_LOCATIONS = URL_API + "/locations"
    URL_LOCATION_DATA = URL_API + "/home/"

    """Minimum time between requests"""
    REFRESH_LIMIT = 10
    """Seconds subtracted from the token expiation time"""
    TOKEN_EXPIRE_MARGIN = 20

    def __init__(self, username, password, session, location_id=None) -> None:
        """Test Init."""
        self._session = session
        self._token = None
        self._username = username
        self._password = password
        self._access_token = None
        self._access_token_expire = datetime.now() - timedelta(hours=1)
        self._refresh_token = None
        self._refresh_token_expire = datetime.now() - timedelta(hours=1)

        self._locations = {}

        self._location_id = location_id
        self._location_data = None
        self._data_refreshed = datetime.now() - timedelta(
            seconds=(self.REFRESH_LIMIT + 60)
        )

    async def _request(self, url, data=None, req_type="GET"):
        """Handle requests to API."""
        try:
            if req_type == "GET":
                # GET
                async with asyncio.timeout(REQ_TIMEOUT):
                    response = await self._session.get(url=url, headers=data)
            elif req_type == "POST":
                # POST.
                async with asyncio.timeout(REQ_TIMEOUT):
                    response = await self._session.post(url=url, data=data)
            else:
                raise InvalidArgument("req_type must be either GET or POST")

            _LOGGER.debug("Homely Request status code: %s", response.status)
            if response.status > 201:
                _LOGGER.debug("Homely Request status code: %s", response.text)

            return response  # noqa: TRY300

        except ClientError as ex:
            raise RequestFailed(f"Homely unexpected error {url} ({ex=})") from Homely
        except TimeoutError:
            _LOGGER.exception("Homely, request timed out")
            raise RequestFailed("Request timeout") from Homely

    async def _refresh_access_token(self):
        """Request API ti refresh the Acces-token."""
        if self._refresh_token is None or self._token_expired(
            self._refresh_token_expire
        ):
            raise TokenExpiredError("No valid refresh-token")

        # Connect to API and refresh the access-token.
        data = {"refresh_token": self._refresh_token}
        response = await self._request(
            url=self.URL_TOKEN_REFRESH, data=data, req_type="POST"
        )

        if response.status >= 500:
            raise ResponseError(response.status, response.text)

        if response.status == 400:
            raise LoginError("Invalid refresh token")

        if response.status >= 401:
            raise LoginError("Unauthorized")

        if response.status in [200, 201]:
            # Success
            resp_data = json.loads(await response.text())

            self._access_token = resp_data["access_token"]
            self._access_token_expire = datetime.now() + timedelta(
                seconds=(int(resp_data["expires_in"]) - self.TOKEN_EXPIRE_MARGIN)
            )
            self._refresh_token = resp_data["refresh_token"]
            self._refresh_token_expire = datetime.now() + timedelta(
                seconds=(
                    int(resp_data["refresh_expires_in"]) - self.TOKEN_EXPIRE_MARGIN
                )
            )
            return True

        return False

    def _token_expired(self, expire: datetime):
        if datetime.now() > expire:
            return True
        return False

    def _access_token_valid(self):
        """Check if we have an access token and that it is not expired."""
        if self._access_token is None or self._token_expired(self._access_token_expire):
            return False
        return True

    def set_location_id(self, location_id) -> None:
        """Set the location ID for update requests."""
        self._location_id = location_id

    async def _get_location_data(self, location_id=None):
        """Get the current data from the selected location."""

        if self._location_id is None and location_id is None:
            raise LoginError("Invalid location ID")

        # Make sure access-token is up to date.
        await self.get_token()

        # Prioritize location ID from parameter.
        if location_id is not None:
            req_loc_id = location_id
        else:
            req_loc_id = self._location_id

        next_refresh = self._data_refreshed + timedelta(seconds=self.REFRESH_LIMIT)
        if datetime.now() < next_refresh:
            _LOGGER.debug("Location data is still valid")
            return True

        data = {"Authorization": f"Bearer {self._access_token}"}
        response = await self._request(
            url=f"{self.URL_LOCATION_DATA}{req_loc_id}", data=data, req_type="GET"
        )

        if response.status >= 500:
            raise ResponseError(response.status, response.text)

        if response.status == 400:
            raise LoginError("Invalid location ID")

        if response.status >= 401:
            raise LoginError("Unauthorized")

        if response.status in [200, 201]:
            # Success
            self._location_data = json.loads(await response.text())
            self._data_refreshed = datetime.now()
            return True

        return False

    async def get_token(self):
        """Request or refresh access token."""

        if self._access_token_valid():
            # Access token still valid. No reason to get a new one.
            _LOGGER.debug("Homely Access token still valid")
            return True

        # Access token not valid. Try refresh.
        if self._refresh_token is not None and not self._token_expired(
            self._refresh_token_expire
        ):
            await self._refresh_access_token()
            # Check if acess-token is valid now.
            if self._access_token_valid():
                _LOGGER.debug("Homely Access token refreshed sucessfully")
                return True

        # Connect to API and get a new access-token.
        data = {"username": self._username, "password": self._password}
        response = await self._request(url=self.URL_TOKEN, data=data, req_type="POST")

        if response.status >= 500:
            raise ResponseError(response.status, response.text)

        if response.status >= 400:
            raise LoginError("Invalid credentials")

        if response.status in [200, 201]:
            # Success
            resp_data = json.loads(await response.text())

        # Set access and refresh tokens.
        self._access_token = resp_data["access_token"]
        self._access_token_expire = datetime.now() + timedelta(
            seconds=(int(resp_data["expires_in"]) - self.TOKEN_EXPIRE_MARGIN)
        )
        self._refresh_token = resp_data["refresh_token"]
        self._refresh_token_expire = datetime.now() + timedelta(
            seconds=(int(resp_data["refresh_expires_in"]) - self.TOKEN_EXPIRE_MARGIN)
        )
        return True

    async def get_users_locations(self):
        """Return a list of all locations this user have access to."""
        # raise HomelyError("test")

        if not self._access_token_valid():
            raise LoginError("No valid access token")

        # User must be owner or administrator to be able to access locations
        data = {"Authorization": f"Bearer {self._access_token}"}
        response = await self._request(
            url=self.URL_LOCATIONS, data=data, req_type="GET"
        )

        if response.status >= 500:
            raise ResponseError(response.status, response.text)

        if response.status >= 400:
            raise LoginError("Unauthorized")

        if response.status in [200, 201]:
            # Success
            resp_data = json.loads(await response.text())

        self._locations = resp_data
        return self._locations

    async def get_system_state(self, location_id=None):
        """Get the alarm state."""
        # First refresh data.
        await self._get_location_data(location_id)

        return self._location_data.get("alarmState", "UNKNOWN")

    async def get_devices(self, location_id=None):
        """Get a list of all location devices."""
        # First refresh data.
        await self._get_location_data(location_id)

        return self._location_data.get("devices", [])

    async def get_data(self, location_id=None):
        """Get all data from the selected location."""
        # First refresh data.
        await self._get_location_data(location_id)

        return self._location_data

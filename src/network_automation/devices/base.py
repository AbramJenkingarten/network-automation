"""Base device class and abstractions."""

from abc import ABC, abstractmethod
from typing import Any

from ..devices.models import (
    VLAN,
    ConfigDiff,
    DeviceConfig,
    DeviceFacts,
    Interface,
)
from ..exceptions import (
    AuthenticationError,
    CommandError,
    ConnectionError,
    TimeoutError,
)


class BaseDevice(ABC):
    """Abstract base class for network devices."""

    def __init__(self, config: DeviceConfig):
        self.config = config
        self._connection = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to device."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to device."""
        pass

    @abstractmethod
    def get_facts(self) -> DeviceFacts:
        """Get device facts."""
        pass

    @abstractmethod
    def get_interfaces(self) -> list[Interface]:
        """Get interface list."""
        pass

    @abstractmethod
    def get_vlans(self) -> list[VLAN]:
        """Get VLAN list."""
        pass

    @abstractmethod
    def send_command(self, command: str, **kwargs) -> str:
        """Send a show command and return output."""
        pass

    @abstractmethod
    def send_config(self, commands: list[str], **kwargs) -> ConfigDiff:
        """Send configuration commands."""
        pass

    @abstractmethod
    def get_config(self, config_type: str = "running") -> str:
        """Get device configuration."""
        pass

    @abstractmethod
    def replace_config(self, config: str, **kwargs) -> ConfigDiff:
        """Replace entire configuration."""
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit configuration changes."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback configuration changes."""
        pass

    @abstractmethod
    def save_config(self) -> None:
        """Save configuration to startup."""
        pass

    @abstractmethod
    def ping(self, destination: str, **kwargs) -> dict[str, Any]:
        """Ping from device."""
        pass

    @abstractmethod
    def traceroute(self, destination: str, **kwargs) -> dict[str, Any]:
        """Traceroute from device."""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def _handle_connection_error(self, e: Exception) -> None:
        """Handle and wrap connection errors."""
        error_msg = str(e).lower()
        if "authentication" in error_msg or "auth" in error_msg:
            raise AuthenticationError(f"Authentication failed: {e}") from e
        elif "timeout" in error_msg:
            raise TimeoutError(f"Connection timeout: {e}") from e
        else:
            raise ConnectionError(f"Connection failed: {e}") from e

    def _handle_command_error(self, e: Exception, command: str) -> None:
        """Handle and wrap command execution errors."""
        raise CommandError(f"Command failed: {command}") from e

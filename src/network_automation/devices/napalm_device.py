"""NAPALM-based device implementation for Cisco devices."""

from typing import Any

from napalm import get_network_driver
from napalm.base import NetworkDriver
from napalm.base.exceptions import (
    CommandErrorException,
    ConnectAuthError,
    ConnectionException,
    MergeConfigException,
    ReplaceConfigException,
)

from ..devices.models import (
    VLAN,
    ConfigDiff,
    DeviceConfig,
    DeviceFacts,
    Interface,
    Vendor,
)
from ..exceptions import (
    AuthenticationError,
    CommandError,
    ConfigurationError,
    ConnectionError,
    UnsupportedDeviceError,
)
from .base import BaseDevice


class NapalmDevice(BaseDevice):
    """NAPALM-based device driver for Cisco and other NAPALM-supported vendors."""

    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._driver: NetworkDriver | None = None
        self._driver_class = None

    def connect(self) -> None:
        """Establish NAPALM connection."""
        if self._connected:
            return

        try:
            self._driver_class = get_network_driver(self.config.napalm_driver)
            self._driver = self._driver_class(
                hostname=self.config.hostname,
                username=self.config.credentials.username,
                password=self.config.credentials.password,
                port=self.config.port,
                timeout=self.config.timeout,
                optional_args=self._get_optional_args()
            )
            self._driver.open()
            self._connected = True
        except ConnectAuthError as e:
            raise AuthenticationError(f"Authentication failed for {self.config.name}") from e
        except ConnectionException as e:
            raise ConnectionError(f"Connection failed to {self.config.name}: {e}") from e
        except Exception as e:
            raise ConnectionError(f"Unexpected error connecting to {self.config.name}: {e}") from e

    def _get_optional_args(self) -> dict[str, Any]:
        """Build optional arguments for NAPALM driver."""
        args = {
            "global_delay_factor": self.config.global_delay_factor,
        }
        # Add enable password if provided
        if self.config.credentials.enable_password:
            args["secret"] = self.config.credentials.enable_password
        # Add SSH key if provided
        if self.config.credentials.ssh_key_file:
            args["key_file"] = self.config.credentials.ssh_key_file
        # Merge with custom napalm_args
        args.update(self.config.napalm_args)
        return args

    def disconnect(self) -> None:
        """Close NAPALM connection."""
        if self._driver and self._connected:
            try:
                self._driver.close()
            except Exception:
                pass  # Ignore errors on disconnect
            finally:
                self._connected = False
                self._driver = None

    def get_facts(self) -> DeviceFacts:
        """Get device facts via NAPALM."""
        self._ensure_connected()
        try:
            facts = self._driver.get_facts()
            return DeviceFacts(
                hostname=facts.get("hostname", self.config.name),
                vendor=facts.get("vendor", self.config.vendor.value),
                model=facts.get("model", "Unknown"),
                serial_number=facts.get("serial_number"),
                os_version=facts.get("os_version", "Unknown"),
                uptime=facts.get("uptime"),
                fqdn=facts.get("fqdn"),
                domain_name=facts.get("domain_name"),
                interfaces=self.get_interfaces(),
                vlans=self.get_vlans(),
            )
        except Exception as e:
            raise CommandError(f"Failed to get facts: {e}") from e

    def get_interfaces(self) -> list[Interface]:
        """Get interface list via NAPALM."""
        self._ensure_connected()
        try:
            interfaces_data = self._driver.get_interfaces()
            interfaces = []
            for name, data in interfaces_data.items():
                interfaces.append(Interface(
                    name=name,
                    description=data.get("description"),
                    enabled=data.get("is_enabled", True),
                    mtu=data.get("mtu"),
                    mac_address=data.get("mac_address"),
                    ipv4_address=data.get("ipv4", {}).get("address"),
                    ipv4_mask=str(data.get("ipv4", {}).get("prefix_length", "")) if data.get("ipv4", {}).get("prefix_length") else None,
                    speed=data.get("speed"),
                    duplex=data.get("duplex"),
                ))
            return interfaces
        except Exception as e:
            raise CommandError(f"Failed to get interfaces: {e}") from e

    def get_vlans(self) -> list[VLAN]:
        """Get VLAN list via NAPALM."""
        self._ensure_connected()
        try:
            vlans_data = self._driver.get_vlans()
            vlans = []
            for vlan_id, data in vlans_data.items():
                vlans.append(VLAN(
                    id=int(vlan_id),
                    name=data.get("name"),
                    interfaces=data.get("interfaces", []),
                ))
            return vlans
        except Exception as e:
            raise CommandError(f"Failed to get VLANs: {e}") from e

    def send_command(self, command: str, **kwargs) -> str:
        """Send a show command via NAPALM."""
        self._ensure_connected()
        try:
            # NAPALM doesn't have a generic send_command, use device-specific method
            if hasattr(self._driver, "device") and hasattr(self._driver.device, "send_command"):
                return self._driver.device.send_command(command)
            # Fallback for some drivers
            raise UnsupportedDeviceError(f"send_command not supported by {self.config.napalm_driver} driver")
        except CommandErrorException as e:
            raise CommandError(f"Command failed: {command}") from e
        except Exception as e:
            raise CommandError(f"Command execution failed: {e}") from e

    def send_config(self, commands: list[str], **kwargs) -> ConfigDiff:
        """Send configuration commands via NAPALM merge."""
        self._ensure_connected()
        try:
            config_text = "\n".join(commands)
            self._driver.load_merge_candidate(config=config_text)
            diff = self._driver.compare_config()
            if diff:
                self._driver.commit_config()
                return self._parse_diff(diff)
            self._driver.discard_config()
            return ConfigDiff()
        except MergeConfigException as e:
            self._driver.discard_config()
            raise ConfigurationError(f"Configuration merge failed: {e}") from e
        except ReplaceConfigException as e:
            self._driver.discard_config()
            raise ConfigurationError(f"Configuration replace failed: {e}") from e
        except Exception as e:
            self._driver.discard_config()
            raise ConfigurationError(f"Configuration failed: {e}") from e

    def get_config(self, config_type: str = "running") -> str:
        """Get device configuration via NAPALM."""
        self._ensure_connected()
        try:
            configs = self._driver.get_config()
            return configs.get(config_type, "")
        except Exception as e:
            raise CommandError(f"Failed to get config: {e}") from e

    def replace_config(self, config: str, **kwargs) -> ConfigDiff:
        """Replace entire configuration via NAPALM."""
        self._ensure_connected()
        try:
            self._driver.load_replace_candidate(config=config)
            diff = self._driver.compare_config()
            if diff:
                self._driver.commit_config()
                return self._parse_diff(diff)
            self._driver.discard_config()
            return ConfigDiff()
        except ReplaceConfigException as e:
            self._driver.discard_config()
            raise ConfigurationError(f"Configuration replace failed: {e}") from e
        except Exception as e:
            self._driver.discard_config()
            raise ConfigurationError(f"Configuration replace failed: {e}") from e

    def commit(self) -> None:
        """Commit pending configuration changes."""
        self._ensure_connected()
        try:
            self._driver.commit_config()
        except Exception as e:
            raise ConfigurationError(f"Commit failed: {e}") from e

    def rollback(self) -> None:
        """Rollback configuration changes."""
        self._ensure_connected()
        try:
            self._driver.discard_config()
            # Some drivers support rollback
            if hasattr(self._driver, "rollback"):
                self._driver.rollback()
        except Exception as e:
            raise ConfigurationError(f"Rollback failed: {e}") from e

    def save_config(self) -> None:
        """Save running config to startup."""
        self._ensure_connected()
        try:
            self._driver.save_config()
        except Exception as e:
            raise ConfigurationError(f"Save config failed: {e}") from e

    def ping(self, destination: str, **kwargs) -> dict[str, Any]:
        """Ping from device via NAPALM."""
        self._ensure_connected()
        try:
            return self._driver.ping(destination, **kwargs)
        except Exception as e:
            raise CommandError(f"Ping failed: {e}") from e

    def traceroute(self, destination: str, **kwargs) -> dict[str, Any]:
        """Traceroute from device via NAPALM."""
        self._ensure_connected()
        try:
            if hasattr(self._driver, "traceroute"):
                return self._driver.traceroute(destination, **kwargs)
            raise UnsupportedDeviceError("Traceroute not supported by this driver")
        except Exception as e:
            raise CommandError(f"Traceroute failed: {e}") from e

    def _ensure_connected(self) -> None:
        """Ensure device is connected."""
        if not self._connected or not self._driver:
            raise ConnectionError(f"Device {self.config.name} is not connected")

    def _parse_diff(self, diff: str) -> ConfigDiff:
        """Parse NAPALM diff output."""
        added = []
        removed = []
        changed = []
        for line in diff.splitlines():
            line = line.strip()
            if line.startswith("+"):
                added.append(line[1:].strip())
            elif line.startswith("-"):
                removed.append(line[1:].strip())
            elif line.startswith("~") or line.startswith("!"):
                changed.append(line[1:].strip())
        return ConfigDiff(added=added, removed=removed, changed=changed)


def create_cisco_device(config: DeviceConfig) -> NapalmDevice:
    """Factory function to create Cisco NAPALM device."""
    if config.vendor != Vendor.CISCO:
        raise UnsupportedDeviceError(f"Expected Cisco device, got {config.vendor}")
    return NapalmDevice(config)

"""Netmiko-based device implementation for Eltex and other SSH/Telnet devices."""

from typing import Any

from netmiko import ConnectHandler
from netmiko.exceptions import (
    ConfigInvalidException,
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
    SSHException,
)

from ..devices.models import VLAN, ConfigDiff, DeviceConfig, DeviceFacts, Interface, Vendor
from ..exceptions import (
    AuthenticationError,
    CommandError,
    ConfigurationError,
    ConnectionError,
    TimeoutError,
    UnsupportedDeviceError,
)
from .base import BaseDevice


class NetmikoDevice(BaseDevice):
    """Netmiko-based device driver for Eltex and other SSH/Telnet devices."""

    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._connection = None
        self._prompt = None

    def connect(self) -> None:
        """Establish Netmiko connection."""
        if self._connected:
            return

        try:
            device_params = self._get_device_params()
            self._connection = ConnectHandler(**device_params)
            self._connected = True
            # Get base prompt
            self._prompt = self._connection.find_prompt()
            # Enter enable mode if needed
            if self.config.credentials.enable_password:
                self._connection.enable()
        except NetmikoAuthenticationException as e:
            raise AuthenticationError(f"Authentication failed for {self.config.name}") from e
        except NetmikoTimeoutException as e:
            raise TimeoutError(f"Connection timeout to {self.config.name}: {e}") from e
        except SSHException as e:
            raise ConnectionError(f"SSH error connecting to {self.config.name}: {e}") from e
        except Exception as e:
            raise ConnectionError(f"Unexpected error connecting to {self.config.name}: {e}") from e

    def _get_device_params(self) -> dict[str, Any]:
        """Build device parameters for Netmiko."""
        params = {
            "device_type": self.config.netmiko_device_type,
            "host": self.config.hostname,
            "username": self.config.credentials.username,
            "password": self.config.credentials.password,
            "port": self.config.port,
            "timeout": self.config.timeout,
            "global_delay_factor": self.config.global_delay_factor,
            "session_log": self.config.netmiko_args.get("session_log"),
        }

        # SSH key authentication
        if self.config.credentials.ssh_key_file:
            params["use_keys"] = True
            params["key_file"] = self.config.credentials.ssh_key_file
            if self.config.credentials.ssh_key_password:
                params["passphrase"] = self.config.credentials.ssh_key_password

        # Merge custom netmiko_args
        params.update(self.config.netmiko_args)
        return params

    def disconnect(self) -> None:
        """Close Netmiko connection."""
        if self._connection and self._connected:
            try:
                self._connection.disconnect()
            except Exception:
                pass
            finally:
                self._connected = False
                self._connection = None

    def get_facts(self) -> DeviceFacts:
        """Get device facts via CLI commands."""
        self._ensure_connected()
        try:
            # This is vendor-specific - implement for Eltex
            if self.config.vendor == Vendor.ELTEX:
                return self._get_eltex_facts()
            else:
                return self._get_generic_facts()
        except Exception as e:
            raise CommandError(f"Failed to get facts: {e}") from e

    def _get_eltex_facts(self) -> DeviceFacts:
        """Get facts from Eltex device."""
        # Get version info
        version_output = self.send_command("show version")
        hostname = self.config.name
        model = "Unknown"
        os_version = "Unknown"
        serial_number = None

        # Parse version output (Eltex specific)
        for line in version_output.splitlines():
            line = line.strip()
            if "Software version" in line or "Version" in line:
                os_version = line.split(":")[-1].strip()
            elif "Hardware" in line or "Model" in line:
                model = line.split(":")[-1].strip()
            elif "Serial" in line:
                serial_number = line.split(":")[-1].strip()
            elif "Hostname" in line or "System name" in line:
                hostname = line.split(":")[-1].strip()

        return DeviceFacts(
            hostname=hostname,
            vendor=self.config.vendor.value,
            model=model,
            serial_number=serial_number,
            os_version=os_version,
            interfaces=self.get_interfaces(),
            vlans=self.get_vlans(),
        )

    def _get_generic_facts(self) -> DeviceFacts:
        """Get generic facts."""
        return DeviceFacts(
            hostname=self.config.name,
            vendor=self.config.vendor.value,
            model="Unknown",
            os_version="Unknown",
            interfaces=self.get_interfaces(),
            vlans=self.get_vlans(),
        )

    def get_interfaces(self) -> list[Interface]:
        """Get interface list via CLI."""
        self._ensure_connected()
        try:
            if self.config.vendor == Vendor.ELTEX:
                return self._get_eltex_interfaces()
            else:
                return self._get_generic_interfaces()
        except Exception as e:
            raise CommandError(f"Failed to get interfaces: {e}") from e

    def _get_eltex_interfaces(self) -> list[Interface]:
        """Get interfaces from Eltex device."""
        # Eltex CLI commands for interfaces
        output = self.send_command("show interfaces brief")
        interfaces = []

        # Parse Eltex "show interfaces brief" output
        # Typical format:
        # Port    Type         Speed    Duplex   Status    Description
        # gi1/1   1000BASE-T   1000     Full     Up        Link to Core
        lines = output.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Port") or line.startswith("--"):
                continue

            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                # Try to determine status
                status_idx = -1
                for i, part in enumerate(parts):
                    if part.lower() in ("up", "down", "admin down"):
                        status_idx = i
                        break

                interface = Interface(
                    name=name,
                    enabled=(parts[status_idx].lower() == "up" if status_idx > 0 else True),
                    description=" ".join(parts[status_idx+1:]) if status_idx > 0 and status_idx+1 < len(parts) else None,
                )
                interfaces.append(interface)

        return interfaces

    def _get_generic_interfaces(self) -> list[Interface]:
        """Get generic interfaces."""
        output = self.send_command("show interfaces")
        return [Interface(name="unknown", description=output[:200])]

    def get_vlans(self) -> list[VLAN]:
        """Get VLAN list via CLI."""
        self._ensure_connected()
        try:
            if self.config.vendor == Vendor.ELTEX:
                return self._get_eltex_vlans()
            else:
                return []
        except Exception as e:
            raise CommandError(f"Failed to get VLANs: {e}") from e

    def _get_eltex_vlans(self) -> list[VLAN]:
        """Get VLANs from Eltex device."""
        output = self.send_command("show vlan brief")
        vlans = []

        # Parse Eltex VLAN output
        lines = output.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("VLAN") or line.startswith("--"):
                continue

            parts = line.split()
            if len(parts) >= 2:
                try:
                    vlan_id = int(parts[0])
                    name = parts[1] if len(parts) > 1 else None
                    vlans.append(VLAN(id=vlan_id, name=name))
                except ValueError:
                    continue

        return vlans

    def send_command(self, command: str, **kwargs) -> str:
        """Send a show command via Netmiko."""
        self._ensure_connected()
        try:
            # Handle pagination
            if "expect_string" not in kwargs:
                kwargs["expect_string"] = self._prompt
            output = self._connection.send_command(command, **kwargs)
            return output
        except ConfigInvalidException as e:
            raise CommandError(f"Command failed: {command}") from e
        except Exception as e:
            raise CommandError(f"Command execution failed: {e}") from e

    def send_config(self, commands: list[str], **kwargs) -> ConfigDiff:
        """Send configuration commands via Netmiko."""
        self._ensure_connected()
        try:
            # Enter config mode
            self._connection.config_mode()
            output = self._connection.send_config_set(commands, **kwargs)
            self._connection.exit_config_mode()

            # Parse output for diff (Netmiko doesn't provide native diff)
            # This is a best-effort approximation
            return ConfigDiff(
                added=[c for c in commands if not c.startswith("no ")],
                removed=[c[3:] for c in commands if c.startswith("no ")],
            )
        except ConfigInvalidException as e:
            raise ConfigurationError(f"Configuration failed: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Configuration failed: {e}") from e

    def get_config(self, config_type: str = "running") -> str:
        """Get device configuration via CLI."""
        self._ensure_connected()
        try:
            if config_type == "running":
                return self.send_command("show running-config")
            elif config_type == "startup":
                return self.send_command("show startup-config")
            else:
                raise ValueError(f"Unknown config type: {config_type}")
        except Exception as e:
            raise CommandError(f"Failed to get config: {e}") from e

    def replace_config(self, config: str, **kwargs) -> ConfigDiff:
        """Replace entire configuration - not directly supported via Netmiko for most devices."""
        self._ensure_connected()
        try:
            # For Eltex, we can try to load from file or apply section by section
            # This is a simplified implementation
            commands = config.splitlines()
            return self.send_config(commands, **kwargs)
        except Exception as e:
            raise ConfigurationError(f"Configuration replace failed: {e}") from e

    def commit(self) -> None:
        """Commit configuration changes - typically automatic in CLI."""
        # For most CLI devices, config is applied immediately
        # For Eltex, might need "commit" or "confirm"
        self._ensure_connected()
        try:
            # Eltex may require explicit commit
            if self.config.vendor == Vendor.ELTEX:
                self.send_command("commit")
        except Exception as e:
            raise ConfigurationError(f"Commit failed: {e}") from e

    def rollback(self) -> None:
        """Rollback configuration changes."""
        self._ensure_connected()
        try:
            if self.config.vendor == Vendor.ELTEX:
                self.send_command("rollback")
            else:
                # Try to reload startup config
                self.send_command("configure replace startup-config force")
        except Exception as e:
            raise ConfigurationError(f"Rollback failed: {e}") from e

    def save_config(self) -> None:
        """Save running config to startup."""
        self._ensure_connected()
        try:
            if self.config.vendor == Vendor.ELTEX:
                self.send_command("copy running-config startup-config")
            else:
                self.send_command("write memory")
        except Exception as e:
            raise ConfigurationError(f"Save config failed: {e}") from e

    def ping(self, destination: str, **kwargs) -> dict[str, Any]:
        """Ping from device via CLI."""
        self._ensure_connected()
        try:
            count = kwargs.get("count", 5)
            output = self.send_command(f"ping {destination} count {count}")
            return {"output": output, "destination": destination}
        except Exception as e:
            raise CommandError(f"Ping failed: {e}") from e

    def traceroute(self, destination: str, **kwargs) -> dict[str, Any]:
        """Traceroute from device via CLI."""
        self._ensure_connected()
        try:
            output = self.send_command(f"traceroute {destination}")
            return {"output": output, "destination": destination}
        except Exception as e:
            raise CommandError(f"Traceroute failed: {e}") from e

    def _ensure_connected(self) -> None:
        """Ensure device is connected."""
        if not self._connected or not self._connection:
            raise ConnectionError(f"Device {self.config.name} is not connected")

    def send_command_timing(self, command: str, **kwargs) -> str:
        """Send command using timing-based approach."""
        self._ensure_connected()
        return self._connection.send_command_timing(command, **kwargs)


def create_eltex_device(config: DeviceConfig) -> NetmikoDevice:
    """Factory function to create Eltex Netmiko device."""
    if config.vendor != Vendor.ELTEX:
        raise UnsupportedDeviceError(f"Expected Eltex device, got {config.vendor}")
    return NetmikoDevice(config)

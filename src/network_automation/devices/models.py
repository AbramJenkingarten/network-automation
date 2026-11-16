"""Device models and data structures."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Vendor(str, Enum):
    """Supported network device vendors."""
    CISCO = "cisco"
    ELTEX = "eltex"


class DeviceType(str, Enum):
    """Supported device types."""
    # Cisco
    IOS = "ios"
    IOS_XE = "iosxe"
    NXOS = "nxos"
    IOS_XR = "iosxr"
    ASA = "asa"
    # Eltex
    ESR = "esr"
    MES = "mes"
    LTP = "ltp"
    # Generic
    GENERIC = "generic"


class ConnectionProtocol(str, Enum):
    """Connection protocols."""
    SSH = "ssh"
    TELNET = "telnet"
    API = "api"


class DeviceCredentials(BaseModel):
    """Device authentication credentials."""
    username: str
    password: str
    enable_password: str | None = None
    ssh_key_file: str | None = None
    ssh_key_password: str | None = None


class DeviceConfig(BaseModel):
    """Network device configuration."""
    name: str
    hostname: str
    vendor: Vendor
    device_type: DeviceType
    port: int = 22
    protocol: ConnectionProtocol = ConnectionProtocol.SSH
    credentials: DeviceCredentials
    timeout: int = 30
    global_delay_factor: float = 1.0
    # NAPALM specific
    napalm_driver: str | None = None
    napalm_args: dict[str, Any] = Field(default_factory=dict)
    # Netmiko specific
    netmiko_device_type: str | None = None
    netmiko_args: dict[str, Any] = Field(default_factory=dict)
    # Metadata
    description: str | None = None
    location: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def set_drivers(self) -> "DeviceConfig":
        """Auto-set NAPALM and Netmiko drivers based on device type."""
        # NAPALM driver
        if self.napalm_driver is None:
            napalm_mapping = {
                (Vendor.CISCO, DeviceType.IOS): "ios",
                (Vendor.CISCO, DeviceType.IOS_XE): "ios",
                (Vendor.CISCO, DeviceType.NXOS): "nxos",
                (Vendor.CISCO, DeviceType.IOS_XR): "iosxr",
                (Vendor.CISCO, DeviceType.ASA): "asa",
            }
            self.napalm_driver = napalm_mapping.get((self.vendor, self.device_type), "generic")

        # Netmiko device type
        if self.netmiko_device_type is None:
            netmiko_mapping = {
                (Vendor.CISCO, DeviceType.IOS): "cisco_ios",
                (Vendor.CISCO, DeviceType.IOS_XE): "cisco_ios",
                (Vendor.CISCO, DeviceType.NXOS): "cisco_nxos",
                (Vendor.CISCO, DeviceType.IOS_XR): "cisco_xr",
                (Vendor.CISCO, DeviceType.ASA): "cisco_asa",
                (Vendor.ELTEX, DeviceType.ESR): "eltex_esr",
                (Vendor.ELTEX, DeviceType.MES): "eltex",
                (Vendor.ELTEX, DeviceType.LTP): "eltex",
            }
            self.netmiko_device_type = netmiko_mapping.get((self.vendor, self.device_type), "generic")

        return self


class Interface(BaseModel):
    """Network interface model."""
    name: str
    description: str | None = None
    enabled: bool = True
    mtu: int | None = None
    mac_address: str | None = None
    ipv4_address: str | None = None
    ipv4_mask: str | None = None
    ipv6_addresses: list[str] = Field(default_factory=list)
    speed: int | None = None
    duplex: str | None = None
    mode: str | None = None  # access, trunk, routed
    vlan: int | None = None
    allowed_vlans: list[int] = Field(default_factory=list)
    ip_addresses: list[str] = Field(default_factory=list)


class VLAN(BaseModel):
    """VLAN model."""
    id: int
    name: str | None = None
    description: str | None = None
    interfaces: list[str] = Field(default_factory=list)


class DeviceFacts(BaseModel):
    """Device facts collected from device."""
    hostname: str
    vendor: str
    model: str
    serial_number: str | None = None
    os_version: str
    uptime: int | None = None
    interfaces: list[Interface] = Field(default_factory=list)
    vlans: list[VLAN] = Field(default_factory=list)
    fqdn: str | None = None
    domain_name: str | None = None


class ConfigDiff(BaseModel):
    """Configuration diff result."""
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    changed: list[str] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def __str__(self) -> str:
        lines = []
        for line in self.added:
            lines.append(f"+ {line}")
        for line in self.removed:
            lines.append(f"- {line}")
        for line in self.changed:
            lines.append(f"~ {line}")
        return "\n".join(lines) if lines else "No changes"

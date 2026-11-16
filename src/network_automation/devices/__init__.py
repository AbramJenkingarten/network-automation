"""Devices package - Network device abstractions and implementations."""

from .base import BaseDevice
from .factory import create_device, get_driver_for_vendor, get_supported_vendors
from .models import (
    VLAN,
    ConfigDiff,
    ConnectionProtocol,
    DeviceConfig,
    DeviceCredentials,
    DeviceFacts,
    DeviceType,
    Interface,
    Vendor,
)
from .napalm_device import NapalmDevice, create_cisco_device
from .netmiko_device import NetmikoDevice, create_eltex_device

__all__ = [
    # Models
    "Vendor", "DeviceType", "ConnectionProtocol",
    "DeviceCredentials", "DeviceConfig",
    "Interface", "VLAN", "DeviceFacts", "ConfigDiff",
    # Base
    "BaseDevice",
    # Factory
    "create_device", "get_supported_vendors", "get_driver_for_vendor",
    # Implementations
    "NapalmDevice", "create_cisco_device",
    "NetmikoDevice", "create_eltex_device",
]

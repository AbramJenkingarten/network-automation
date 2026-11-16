"""Device factory for creating appropriate device instances."""

from ..devices.models import DeviceConfig, Vendor
from .base import BaseDevice
from .napalm_device import NapalmDevice, create_cisco_device
from .netmiko_device import NetmikoDevice, create_eltex_device


def create_device(config: DeviceConfig) -> BaseDevice:
    """Create appropriate device instance based on vendor and configuration.

    Args:
        config: Device configuration

    Returns:
        Device instance (NapalmDevice or NetmikoDevice)

    Raises:
        UnsupportedDeviceError: If vendor/type combination is not supported
    """
    vendor = config.vendor

    # Prefer NAPALM for supported vendors
    if vendor == Vendor.CISCO:
        return create_cisco_device(config)
    elif vendor == Vendor.ELTEX:
        return create_eltex_device(config)
    else:
        # Try NAPALM first for unknown vendors
        try:
            return NapalmDevice(config)
        except Exception:
            # Fall back to Netmiko
            return NetmikoDevice(config)


def get_supported_vendors() -> dict:
    """Get dictionary of supported vendors and their device types."""
    return {
        "cisco": [
            "ios", "iosxe", "nxos", "iosxr", "asa"
        ],
        "eltex": [
            "esr", "mes", "ltp"
        ],
    }


def get_driver_for_vendor(vendor: str) -> str:
    """Get recommended driver for vendor."""
    drivers = {
        "cisco": "napalm",
        "eltex": "netmiko",
    }
    return drivers.get(vendor.lower(), "netmiko")

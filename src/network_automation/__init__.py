"""Network Automation Framework - Main Package."""

from .core import ConfigBuilder, Inventory, InventoryManager, TemplateManager
from .devices import (
    VLAN,
    BaseDevice,
    ConfigDiff,
    ConnectionProtocol,
    DeviceConfig,
    DeviceCredentials,
    DeviceFacts,
    DeviceType,
    Interface,
    NapalmDevice,
    NetmikoDevice,
    Vendor,
    create_device,
    get_supported_vendors,
)
from .exceptions import (
    AuthenticationError,
    CommandError,
    ConfigurationError,
    ConnectionError,
    NetworkAutomationError,
    TemplateError,
    TimeoutError,
    UnsupportedDeviceError,
    ValidationError,
)

__version__ = "0.1.0"
__author__ = "AbramJenkingarten"

__all__ = [
    # Version
    "__version__", "__author__",
    # Models
    "Vendor", "DeviceType", "ConnectionProtocol",
    "DeviceCredentials", "DeviceConfig",
    "Interface", "VLAN", "DeviceFacts", "ConfigDiff",
    # Devices
    "BaseDevice", "create_device", "get_supported_vendors",
    "NapalmDevice", "NetmikoDevice",
    # Core
    "TemplateManager", "ConfigBuilder", "Inventory", "InventoryManager",
    # Exceptions
    "NetworkAutomationError", "ConnectionError", "AuthenticationError",
    "ConfigurationError", "CommandError", "TemplateError", "ValidationError",
    "UnsupportedDeviceError", "TimeoutError",
]

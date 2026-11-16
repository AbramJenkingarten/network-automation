from network_automation.devices.models import (
    VLAN,
    ConfigDiff,
    DeviceConfig,
    DeviceCredentials,
    DeviceType,
    Interface,
    Vendor,
)
from network_automation.exceptions import (
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


class TestDeviceModels:
    """Test device models."""

    def test_device_credentials(self):
        creds = DeviceCredentials(username="admin", password="secret")
        assert creds.username == "admin"
        assert creds.password == "secret"
        assert creds.enable_password is None

    def test_device_credentials_with_enable(self):
        creds = DeviceCredentials(
            username="admin",
            password="secret",
            enable_password="enable_secret"
        )
        assert creds.enable_password == "enable_secret"

    def test_device_config_cisco(self):
        config = DeviceConfig(
            name="test-cisco",
            hostname="10.0.0.1",
            vendor=Vendor.CISCO,
            device_type=DeviceType.IOS_XE,
            credentials=DeviceCredentials(username="admin", password="secret"),
        )
        assert config.napalm_driver == "ios"
        assert config.netmiko_device_type == "cisco_ios"

    def test_device_config_eltex(self):
        config = DeviceConfig(
            name="test-eltex",
            hostname="10.0.0.2",
            vendor=Vendor.ELTEX,
            device_type=DeviceType.ESR,
            credentials=DeviceCredentials(username="admin", password="secret"),
        )
        assert config.napalm_driver == "generic"
        assert config.netmiko_device_type == "eltex_esr"

    def test_interface_model(self):
        iface = Interface(
            name="GigabitEthernet0/0",
            description="Uplink",
            enabled=True,
            ipv4_address="10.0.0.1",
            ipv4_mask="24",
        )
        assert iface.name == "GigabitEthernet0/0"
        assert iface.enabled is True

    def test_vlan_model(self):
        vlan = VLAN(id=100, name="Servers", interfaces=["Gi1/0", "Gi1/1"])
        assert vlan.id == 100
        assert len(vlan.interfaces) == 2

    def test_config_diff(self):
        diff = ConfigDiff(
            added=["interface Gi1/0", " description Test"],
            removed=["interface Gi1/1"],
            changed=["interface Gi1/2", " description Changed"],
        )
        assert diff.has_changes is True
        assert len(diff.added) == 2
        assert len(diff.removed) == 1
        assert len(diff.changed) == 2

    def test_config_diff_empty(self):
        diff = ConfigDiff()
        assert diff.has_changes is False
        assert str(diff) == "No changes"


class TestExceptions:
    """Test custom exceptions."""

    def test_exception_hierarchy(self):
        assert issubclass(ConnectionError, NetworkAutomationError)
        assert issubclass(AuthenticationError, NetworkAutomationError)
        assert issubclass(ConfigurationError, NetworkAutomationError)
        assert issubclass(CommandError, NetworkAutomationError)
        assert issubclass(TemplateError, NetworkAutomationError)
        assert issubclass(ValidationError, NetworkAutomationError)
        assert issubclass(UnsupportedDeviceError, NetworkAutomationError)
        assert issubclass(TimeoutError, NetworkAutomationError)

    def test_exception_creation(self):
        exc = ConnectionError("Failed to connect")
        assert str(exc) == "Failed to connect"

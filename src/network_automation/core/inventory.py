"""Device inventory management."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ..devices.models import ConnectionProtocol, DeviceConfig, DeviceCredentials, DeviceType, Vendor
from ..exceptions import ValidationError


class InventoryGroup(BaseModel):
    """Group of devices in inventory."""
    name: str
    description: str | None = None
    device_names: list[str] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    parent_groups: list[str] = Field(default_factory=list)
    children_groups: list[str] = Field(default_factory=list)

    def get_all_devices(self, inventory: "Inventory") -> list[str]:
        """Get all device names in this group including children."""
        devices = set(self.device_names)
        for child_name in self.children_groups:
            child_group = inventory.groups.get(child_name)
            if child_group:
                devices.update(child_group.get_all_devices(inventory))
        return list(devices)


class Inventory(BaseModel):
    """Network device inventory."""
    devices: dict[str, DeviceConfig] = Field(default_factory=dict)
    groups: dict[str, InventoryGroup] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_device(self, device: DeviceConfig) -> None:
        """Add device to inventory."""
        self.devices[device.name] = device

    def remove_device(self, name: str) -> bool:
        """Remove device from inventory."""
        if name in self.devices:
            del self.devices[name]
            # Remove from all groups
            for group in self.groups.values():
                if name in group.device_names:
                    group.device_names.remove(name)
            return True
        return False

    def get_device(self, name: str) -> DeviceConfig | None:
        """Get device by name."""
        return self.devices.get(name)

    def get_devices_by_vendor(self, vendor: Vendor) -> list[DeviceConfig]:
        """Get all devices of a specific vendor."""
        return [d for d in self.devices.values() if d.vendor == vendor]

    def get_devices_by_type(self, device_type: DeviceType) -> list[DeviceConfig]:
        """Get all devices of a specific type."""
        return [d for d in self.devices.values() if d.device_type == device_type]

    def get_devices_by_tag(self, tag: str) -> list[DeviceConfig]:
        """Get all devices with a specific tag."""
        return [d for d in self.devices.values() if tag in d.tags]

    def add_group(self, group: InventoryGroup) -> None:
        """Add group to inventory."""
        self.groups[group.name] = group

    def remove_group(self, name: str) -> bool:
        """Remove group from inventory."""
        if name in self.groups:
            del self.groups[name]
            # Remove from parent/children references
            for group in self.groups.values():
                if name in group.parent_groups:
                    group.parent_groups.remove(name)
                if name in group.children_groups:
                    group.children_groups.remove(name)
            return True
        return False

    def get_group(self, name: str) -> InventoryGroup | None:
        """Get group by name."""
        return self.groups.get(name)

    def get_group_devices(self, group_name: str) -> list[DeviceConfig]:
        """Get all devices in a group (including children)."""
        group = self.groups.get(group_name)
        if not group:
            return []
        device_names = group.get_all_devices(self)
        return [self.devices[name] for name in device_names if name in self.devices]

    @classmethod
    def from_yaml(cls, path: str) -> "Inventory":
        """Load inventory from YAML file."""
        data = yaml.safe_load(Path(path).read_text())
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Inventory":
        """Create inventory from dictionary."""
        inventory = cls()

        # Load defaults
        inventory.defaults = data.get("defaults", {})

        # Load devices
        for device_data in data.get("devices", []):
            device = Inventory._parse_device(device_data, inventory.defaults)
            inventory.add_device(device)

        # Load groups
        for group_data in data.get("groups", []):
            group = InventoryGroup(**group_data)
            inventory.add_group(group)

        # Load metadata
        inventory.metadata = data.get("metadata", {})

        return inventory

    @staticmethod
    def _parse_device(data: dict[str, Any], defaults: dict[str, Any]) -> DeviceConfig:
        """Parse device configuration with defaults applied."""
        # Merge defaults
        merged = {**defaults, **data}

        # Parse credentials
        creds_data = merged.pop("credentials", {})
        credentials = DeviceCredentials(**creds_data)

        # Parse enums
        vendor = Vendor(merged.pop("vendor"))
        device_type = DeviceType(merged.pop("device_type"))
        protocol = ConnectionProtocol(merged.pop("protocol", "ssh"))

        return DeviceConfig(
            credentials=credentials,
            vendor=vendor,
            device_type=device_type,
            protocol=protocol,
            **merged
        )

    def to_yaml(self, path: str) -> None:
        """Save inventory to YAML file."""
        data = {
            "defaults": self.defaults,
            "devices": [self._device_to_dict(d) for d in self.devices.values()],
            "groups": [g.model_dump() for g in self.groups.values()],
            "metadata": self.metadata,
        }
        Path(path).write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def _device_to_dict(self, device: DeviceConfig) -> dict[str, Any]:
        """Convert device to dictionary for YAML serialization."""
        data = device.model_dump()
        # Convert enums to strings
        data["vendor"] = device.vendor.value
        data["device_type"] = device.device_type.value
        data["protocol"] = device.protocol.value
        return data


class InventoryManager:
    """High-level inventory management with multiple sources."""

    def __init__(self):
        self.inventories: dict[str, Inventory] = {}
        self.primary: str | None = None

    def load_from_file(self, name: str, path: str, make_primary: bool = False) -> Inventory:
        """Load inventory from file."""
        inventory = Inventory.from_yaml(path)
        self.inventories[name] = inventory
        if make_primary or self.primary is None:
            self.primary = name
        return inventory

    def get_inventory(self, name: str | None = None) -> Inventory:
        """Get inventory by name or primary."""
        name = name or self.primary
        if not name or name not in self.inventories:
            raise ValidationError(f"Inventory '{name}' not found")
        return self.inventories[name]

    def get_device(self, device_name: str, inventory_name: str | None = None) -> DeviceConfig | None:
        """Get device from any inventory."""
        if inventory_name:
            return self.inventories[inventory_name].get_device(device_name)
        for inv in self.inventories.values():
            device = inv.get_device(device_name)
            if device:
                return device
        return None

    def get_all_devices(self) -> dict[str, DeviceConfig]:
        """Get all devices from all inventories."""
        all_devices = {}
        for inv in self.inventories.values():
            all_devices.update(inv.devices)
        return all_devices

    def merge_inventories(self, target_name: str, source_names: list[str]) -> Inventory:
        """Merge multiple inventories into one."""
        target = self.inventories.get(target_name, Inventory())
        for name in source_names:
            source = self.inventories.get(name)
            if source:
                target.devices.update(source.devices)
                target.groups.update(source.groups)
        self.inventories[target_name] = target
        return target

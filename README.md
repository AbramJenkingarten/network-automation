# Network Automation Framework

A Python-based network automation framework for managing **Cisco** and **Eltex** network devices using NAPALM and Netmiko.

## Features

- **Multi-vendor support**: Cisco (via NAPALM) and Eltex (via Netmiko)
- **Unified API**: Consistent interface for different device types
- **Configuration management**: Template-based config generation with Jinja2
- **Inventory management**: YAML-based inventory with groups and variables
- **CLI tool**: Rich command-line interface for common operations
- **Type safety**: Full type hints with Pydantic models
- **Extensible**: Easy to add new vendors and device types

## Installation

```bash
# From source
git clone https://github.com/AbramJenkingarten/network-automation
cd network-automation
pip install -e ".[dev,cisco,eltex]"

# Or install directly
pip install git+https://github.com/AbramJenkingarten/network-automation.git
```

## Quick Start

### 1. Initialize a project

```bash
net-auto init ./my-network-project
cd my-network-project
```

### 2. Configure your inventory

Edit `inventories/inventory.yaml`:

```yaml
defaults:
  port: 22
  protocol: ssh
  timeout: 30

devices:
  - name: "core-sw-01"
    hostname: "10.10.10.1"
    vendor: "cisco"
    device_type: "iosxe"
    credentials:
      username: "admin"
      password: "secret"
      enable_password: "secret"
    tags: ["core", "datacenter"]

  - name: "branch-rtr-01"
    hostname: "10.10.20.1"
    vendor: "eltex"
    device_type: "esr"
    credentials:
      username: "admin"
      password: "secret"
    tags: ["edge", "branch"]

groups:
  - name: "core"
    device_names: ["core-sw-01"]
  - name: "edge"
    device_names: ["branch-rtr-01"]
```

### 3. List devices

```bash
net-auto inventory --list
```

### 4. Connect to a device

```bash
# Get facts
net-auto facts core-sw-01

# Run a command
net-auto connect core-sw-01 --command "show version"

# Interactive shell
net-auto connect core-sw-01 --interactive
```

### 5. Manage configuration

```bash
# View running config
net-auto config core-sw-01 --get running

# Apply commands
net-auto config core-sw-01 --set "interface GigabitEthernet1/0" --set "description Connected to WAN"

# Apply from template
net-auto config core-sw-01 --template base_config.j2 --commit --save
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `net-auto init` | Initialize new project |
| `net-auto inventory` | Manage inventory |
| `net-auto connect` | Connect to device |
| `net-auto config` | Manage configuration |
| `net-auto facts` | Get device facts |
| `net-auto ping` | Ping from device |
| `net-auto vendors` | Show supported vendors |

## Python API

```python
from network_automation import (
    DeviceConfig, DeviceCredentials, Vendor, DeviceType,
    create_device, Inventory, TemplateManager, ConfigBuilder
)

# Create device config
device = DeviceConfig(
    name="core-01",
    hostname="10.10.10.1",
    vendor=Vendor.CISCO,
    device_type=DeviceType.IOS_XE,
    credentials=DeviceCredentials(
        username="admin",
        password="secret",
        enable_password="secret"
    )
)

# Connect and get facts
with create_device(device) as dev:
    facts = dev.get_facts()
    print(f"Model: {facts.model}, Version: {facts.os_version}")

    # Send command
    output = dev.send_command("show ip interface brief")
    print(output)

    # Configure
    diff = dev.send_config([
        "interface GigabitEthernet1/0",
        "description WAN Link"
    ])
    print(f"Changes: {diff}")

# Using inventory
inventory = Inventory.from_yaml("inventories/inventory.yaml")
device = inventory.get_device("core-01")

# Using templates
template_manager = TemplateManager()
builder = ConfigBuilder(template_manager)
config = builder.build_from_template("base_config.j2", device.model_dump())
```

## Project Structure

```
network-automation/
├── src/network_automation/
│   ├── __init__.py           # Main exports
│   ├── cli.py                # CLI entry point
│   ├── devices/              # Device abstractions
│   │   ├── models.py         # Pydantic models
│   │   ├── base.py           # Abstract base class
│   │   ├── factory.py        # Device factory
│   │   ├── napalm_device.py  # NAPALM implementation (Cisco)
│   │   └── netmiko_device.py # Netmiko implementation (Eltex)
│   ├── core/                 # Core functionality
│   │   ├── config.py         # Template management
│   │   └── inventory.py      # Inventory management
│   ├── exceptions.py         # Custom exceptions
│   └── utils/                # Utility functions
├── tests/                    # Test suite
├── configs/                  # Device-specific variables
├── templates/                # Jinja2 templates
├── inventories/              # Inventory files
├── pyproject.toml            # Project configuration
└── README.md
```

## Supported Vendors

| Vendor | Types | Driver |
|--------|-------|--------|
| Cisco | ios, iosxe, nxos, iosxr, asa | NAPALM |
| Eltex | esr, mes, ltp | Netmiko |

## Requirements

- Python 3.10+
- Network connectivity to devices via SSH
- Valid credentials with appropriate privileges

## License

MIT License
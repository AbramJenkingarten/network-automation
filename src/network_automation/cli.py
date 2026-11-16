"""CLI entry point for network automation."""

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from network_automation.core.config import ConfigBuilder, TemplateManager
from network_automation.core.inventory import Inventory, InventoryManager
from network_automation.devices.factory import create_device, get_supported_vendors
from network_automation.exceptions import NetworkAutomationError

app = typer.Typer(
    name="net-auto",
    help="Network Automation Framework for Cisco and Eltex",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()
inventory_manager = InventoryManager()


def _load_inventory(ctx: typer.Context) -> Inventory:
    """Load inventory from context or default."""
    inventory_name = ctx.obj.get("inventory") if ctx.obj else None
    return inventory_manager.get_inventory(inventory_name)


@app.command()
def init(
    path: str = typer.Argument(".", help="Directory to initialize project"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """Initialize a new network automation project."""
    project_path = Path(path)
    project_path.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    dirs = ["configs", "templates", "inventories", "scripts", "logs"]
    for d in dirs:
        (project_path / d).mkdir(exist_ok=True)

    # Create sample inventory
    inventory_file = project_path / "inventories" / "inventory.yaml"
    if not inventory_file.exists() or force:
        sample_inventory = {
            "defaults": {
                "port": 22,
                "protocol": "ssh",
                "timeout": 30,
            },
            "devices": [
                {
                    "name": "cisco-core-01",
                    "hostname": "10.0.1.1",
                    "vendor": "cisco",
                    "device_type": "iosxe",
                    "credentials": {
                        "username": "admin",
                        "password": "changeme",
                        "enable_password": "changeme",
                    },
                    "tags": ["core", "datacenter"],
                },
                {
                    "name": "eltex-edge-01",
                    "hostname": "10.0.2.1",
                    "vendor": "eltex",
                    "device_type": "esr",
                    "credentials": {
                        "username": "admin",
                        "password": "changeme",
                    },
                    "tags": ["edge", "branch"],
                },
            ],
            "groups": [
                {
                    "name": "core",
                    "description": "Core switches",
                    "device_names": ["cisco-core-01"],
                },
                {
                    "name": "edge",
                    "description": "Edge routers",
                    "device_names": ["eltex-edge-01"],
                },
            ],
        }
        inventory_file.write_text(yaml.dump(sample_inventory, default_flow_style=False))
        console.print(f"[green]Created sample inventory:[/green] {inventory_file}")

    # Create sample template
    template_file = project_path / "templates" / "base_config.j2"
    if not template_file.exists() or force:
        template_content = """!
! Base configuration for {{ device.name }}
!
hostname {{ device.name }}
!
{% if device.vendor == 'cisco' %}
enable secret {{ device.credentials.enable_password }}
!
ip domain-name {{ device.domain_name | default('local') }}
crypto key generate rsa modulus 2048
!
ip ssh version 2
ip ssh authentication-retries 3
!
line vty 0 4
 transport input ssh
 login local
!
{% elif device.vendor == 'eltex' %}
enable password {{ device.credentials.enable_password }}
!
ip domain-name {{ device.domain_name | default('local') }}
!
line vty 0 4
 transport input ssh
 login local
!
{% endif %}
!
! Management interface
interface {{ device.mgmt_interface | default('GigabitEthernet0/0') }}
 description Management
 ip address {{ device.mgmt_ip | default('10.0.0.1/24') }}
 no shutdown
!
! NTP
ntp server {{ device.ntp_server | default('pool.ntp.org') }}
!
! Logging
logging buffered 512000
logging host {{ device.syslog_server | default('10.0.0.100') }}
!
end
"""
        template_file.write_text(template_content)
        console.print(f"[green]Created sample template:[/green] {template_file}")

    # Create sample config
    config_file = project_path / "configs" / "devices.yaml"
    if not config_file.exists() or force:
        config_content = """# Device-specific configuration variables
devices:
  cisco-core-01:
    domain_name: "corp.example.com"
    mgmt_interface: "GigabitEthernet0/0"
    mgmt_ip: "10.0.1.1/24"
    ntp_server: "10.0.0.10"
    syslog_server: "10.0.0.100"

  eltex-edge-01:
    domain_name: "branch.example.com"
    mgmt_interface: "gi1/0"
    mgmt_ip: "10.0.2.1/24"
    ntp_server: "10.0.0.10"
    syslog_server: "10.0.0.100"
"""
        config_file.write_text(config_content)
        console.print(f"[green]Created sample config:[/green] {config_file}")

    console.print(Panel.fit(
        "[bold green]Project initialized![/bold green]\n\n"
        f"Directory: {project_path}\n\n"
        "Next steps:\n"
        "1. Edit inventories/inventory.yaml with your devices\n"
        "2. Edit configs/devices.yaml with device-specific variables\n"
        "3. Run: net-auto inventory list\n"
        "4. Run: net-auto connect <device-name>",
        title="Network Automation"
    ))


@app.command()
def inventory(
    ctx: typer.Context,
    list_devices: bool = typer.Option(False, "--list", "-l", help="List all devices"),
    list_groups: bool = typer.Option(False, "--groups", "-g", help="List all groups"),
    show: str | None = typer.Option(None, "--show", "-s", help="Show device/group details"),
    load: str | None = typer.Option(None, "--load", help="Load inventory file"),
    name: str | None = typer.Option(None, "--name", "-n", help="Inventory name"),
):
    """Manage device inventory."""
    if load:
        inv_name = name or "default"
        inventory = inventory_manager.load_from_file(inv_name, load, make_primary=True)
        console.print(f"[green]Loaded inventory:[/green] {inv_name} ({len(inventory.devices)} devices)")
        return

    inventory = _load_inventory(ctx)

    if list_devices:
        table = Table(title="Devices")
        table.add_column("Name", style="cyan")
        table.add_column("Hostname", style="green")
        table.add_column("Vendor", style="yellow")
        table.add_column("Type", style="magenta")
        table.add_column("Tags", style="blue")
        for device in inventory.devices.values():
            table.add_row(
                device.name,
                device.hostname,
                device.vendor.value,
                device.device_type.value,
                ", ".join(device.tags) if device.tags else "-",
            )
        console.print(table)

    elif list_groups:
        table = Table(title="Groups")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Devices", style="yellow")
        table.add_column("Children", style="blue")
        for group in inventory.groups.values():
            devices = group.get_all_devices(inventory)
            table.add_row(
                group.name,
                group.description or "-",
                str(len(devices)),
                ", ".join(group.children_groups) if group.children_groups else "-",
            )
        console.print(table)

    elif show:
        # Try device first
        device = inventory.get_device(show)
        if device:
            console.print(Panel.fit(
                f"[bold]{device.name}[/bold]\n"
                f"Hostname: {device.hostname}\n"
                f"Vendor: {device.vendor.value}\n"
                f"Type: {device.device_type.value}\n"
                f"Port: {device.port}\n"
                f"Protocol: {device.protocol.value}\n"
                f"User: {device.credentials.username}\n"
                f"Tags: {', '.join(device.tags) if device.tags else 'none'}\n"
                f"Location: {device.location or 'not set'}\n"
                f"Description: {device.description or 'not set'}",
                title="Device Details"
            ))
            return

        # Try group
        group = inventory.get_group(show)
        if group:
            devices = group.get_all_devices(inventory)
            console.print(Panel.fit(
                f"[bold]{group.name}[/bold]\n"
                f"Description: {group.description or 'none'}\n"
                f"Devices ({len(devices)}): {', '.join(devices)}\n"
                f"Children: {', '.join(group.children_groups) if group.children_groups else 'none'}",
                title="Group Details"
            ))
            return

        console.print(f"[red]Device or group '{show}' not found[/red]")
        raise typer.Exit(1)

    else:
        console.print(f"[bold]Inventory:[/bold] {len(inventory.devices)} devices, {len(inventory.groups)} groups")
        console.print("Use --list to see devices, --groups to see groups")


@app.command()
def connect(
    ctx: typer.Context,
    device_name: str = typer.Argument(..., help="Device name from inventory"),
    command: str | None = typer.Option(None, "--command", "-c", help="Command to execute"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive shell"),
):
    """Connect to a device and optionally run a command."""
    inventory = _load_inventory(ctx)
    device_config = inventory.get_device(device_name)

    if not device_config:
        console.print(f"[red]Device '{device_name}' not found in inventory[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Connecting to {device_name} ({device_config.hostname})...[/bold]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Connecting...", total=None)
            device = create_device(device_config)
            device.connect()
            progress.update(task, description="Connected!")

        console.print(f"[green]Connected to {device_name}[/green]")

        if command:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Executing: {command}", total=None)
                output = device.send_command(command)
                progress.update(task, description="Done")

            console.print(Panel(output, title=f"Output of '{command}' on {device_name}"))

        elif interactive:
            console.print("[bold]Interactive mode - type 'exit' to quit[/bold]")
            while True:
                try:
                    cmd = console.input(f"[cyan]{device_name}#[/cyan] ")
                    if cmd.strip().lower() in ("exit", "quit"):
                        break
                    if cmd.strip():
                        output = device.send_command(cmd)
                        console.print(output)
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break

        else:
            # Show basic info
            facts = device.get_facts()
            console.print(Panel.fit(
                f"Hostname: {facts.hostname}\n"
                f"Vendor: {facts.vendor}\n"
                f"Model: {facts.model}\n"
                f"OS Version: {facts.os_version}\n"
                f"Uptime: {facts.uptime}s" if facts.uptime else "Uptime: unknown",
                title=f"Device Facts: {device_name}"
            ))

    except NetworkAutomationError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if 'device' in locals():
            device.disconnect()


@app.command()
def config(
    ctx: typer.Context,
    device_name: str = typer.Argument(..., help="Device name from inventory"),
    get: str | None = typer.Option(None, "--get", "-g", help="Get config type (running/startup)"),
    set_commands: list[str] | None = typer.Option(None, "--set", "-s", help="Configuration commands to apply"),
    from_file: str | None = typer.Option(None, "--from-file", "-f", help="Load commands from file"),
    template: str | None = typer.Option(None, "--template", "-t", help="Template name to render"),
    commit: bool = typer.Option(False, "--commit", help="Commit changes"),
    diff: bool = typer.Option(True, "--diff/--no-diff", help="Show diff before applying"),
    save: bool = typer.Option(False, "--save", help="Save to startup config"),
):
    """Manage device configuration."""
    inventory = _load_inventory(ctx)
    device_config = inventory.get_device(device_name)

    if not device_config:
        console.print(f"[red]Device '{device_name}' not found[/red]")
        raise typer.Exit(1)

    try:
        device = create_device(device_config)
        device.connect()

        if get:
            output = device.get_config(get)
            console.print(Panel(output, title=f"{get.capitalize()} config for {device_name}"))

        elif set_commands or from_file or template:
            commands = []

            if set_commands:
                commands.extend(set_commands)

            if from_file:
                commands.extend(Path(from_file).read_text().strip().splitlines())

            if template:
                # Load device-specific variables
                config_vars = {}
                config_file = Path("configs/devices.yaml")
                if config_file.exists():
                    all_vars = yaml.safe_load(config_file.read_text())
                    config_vars = all_vars.get("devices", {}).get(device_name, {})

                template_manager = TemplateManager()
                builder = ConfigBuilder(template_manager)
                rendered = builder.build_from_template(template, device_config.model_dump(), config_vars)
                commands.extend(rendered.strip().splitlines())

            if not commands:
                console.print("[yellow]No commands to apply[/yellow]")
                return

            if diff:
                # Try to get diff
                try:
                    current = device.get_config("running")
                    console.print("[bold]Current config will be modified with:[/bold]")
                    for cmd in commands:
                        console.print(f"  + {cmd}")
                except Exception:
                    pass

                if not typer.confirm("Apply these changes?"):
                    console.print("[yellow]Aborted[/yellow]")
                    return

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Applying configuration...", total=None)
                result = device.send_config(commands)
                progress.update(task, description="Done")

            if result.has_changes:
                console.print("[green]Configuration applied:[/green]")
                console.print(str(result))
            else:
                console.print("[yellow]No changes made[/yellow]")

            if commit:
                device.commit()
                console.print("[green]Committed[/green]")

            if save:
                device.save_config()
                console.print("[green]Saved to startup[/green]")

        else:
            console.print("[yellow]Specify --get, --set, --from-file, or --template[/yellow]")

    except NetworkAutomationError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if 'device' in locals():
            device.disconnect()


@app.command()
def facts(
    ctx: typer.Context,
    device_name: str = typer.Argument(..., help="Device name from inventory"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Get device facts."""
    inventory = _load_inventory(ctx)
    device_config = inventory.get_device(device_name)

    if not device_config:
        console.print(f"[red]Device '{device_name}' not found[/red]")
        raise typer.Exit(1)

    try:
        device = create_device(device_config)
        device.connect()
        facts = device.get_facts()

        if output == "json":
            import json
            console.print_json(json.dumps(facts.model_dump(), default=str, indent=2))
        elif output == "yaml":
            console.print(yaml.dump(facts.model_dump(), default_flow_style=False))
        else:
            # Table output
            table = Table(title=f"Device Facts: {device_name}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            for key, value in facts.model_dump().items():
                if key not in ("interfaces", "vlans") and value is not None:
                    table.add_row(key, str(value))
            console.print(table)

            # Interfaces
            if facts.interfaces:
                iface_table = Table(title="Interfaces")
                iface_table.add_column("Name", style="cyan")
                iface_table.add_column("Description", style="green")
                iface_table.add_column("Enabled", style="yellow")
                iface_table.add_column("IPv4", style="magenta")
                iface_table.add_column("Speed", style="blue")
                for iface in facts.interfaces:
                    iface_table.add_row(
                        iface.name,
                        iface.description or "-",
                        "✓" if iface.enabled else "✗",
                        f"{iface.ipv4_address}/{iface.ipv4_mask}" if iface.ipv4_address else "-",
                        str(iface.speed) if iface.speed else "-",
                    )
                console.print(iface_table)

            # VLANs
            if facts.vlans:
                vlan_table = Table(title="VLANs")
                vlan_table.add_column("ID", style="cyan")
                vlan_table.add_column("Name", style="green")
                vlan_table.add_column("Interfaces", style="yellow")
                for vlan in facts.vlans:
                    vlan_table.add_row(
                        str(vlan.id),
                        vlan.name or "-",
                        ", ".join(vlan.interfaces) if vlan.interfaces else "-",
                    )
                console.print(vlan_table)

    except NetworkAutomationError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if 'device' in locals():
            device.disconnect()


@app.command()
def ping(
    ctx: typer.Context,
    device_name: str = typer.Argument(..., help="Device name from inventory"),
    destination: str = typer.Argument(..., help="Destination IP or hostname"),
    count: int = typer.Option(5, "--count", "-c", help="Number of pings"),
):
    """Ping from device."""
    inventory = _load_inventory(ctx)
    device_config = inventory.get_device(device_name)

    if not device_config:
        console.print(f"[red]Device '{device_name}' not found[/red]")
        raise typer.Exit(1)

    try:
        device = create_device(device_config)
        device.connect()
        result = device.ping(destination, count=count)
        console.print(Panel(result.get("output", str(result)), title=f"Ping {destination} from {device_name}"))
    except NetworkAutomationError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if 'device' in locals():
            device.disconnect()


@app.command()
def vendors():
    """Show supported vendors and device types."""
    supported = get_supported_vendors()
    table = Table(title="Supported Vendors")
    table.add_column("Vendor", style="cyan")
    table.add_column("Device Types", style="green")
    table.add_column("Driver", style="yellow")
    for vendor, types in supported.items():
        table.add_row(vendor, ", ".join(types), "NAPALM" if vendor == "cisco" else "Netmiko")
    console.print(table)


if __name__ == "__main__":
    app()

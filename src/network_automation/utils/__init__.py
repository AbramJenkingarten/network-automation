"""Utility functions for network automation."""

import ipaddress
import re
from typing import List, Optional, Tuple, Union


def parse_interface_name(name: str) -> tuple[str, str, int | None]:
    """Parse interface name into type, slot, and port.
    
    Returns:
        Tuple of (type, slot, port) where port may be None
    """
    # Cisco patterns
    patterns = [
        (r"^([A-Za-z]+)(\d+)/(\d+)$", lambda m: (m.group(1).lower(), m.group(2), int(m.group(3)))),
        (r"^([A-Za-z]+)(\d+)/(\d+)/(\d+)$", lambda m: (m.group(1).lower(), f"{m.group(2)}/{m.group(3)}", int(m.group(4)))),
        (r"^([A-Za-z]+)(\d+)$", lambda m: (m.group(1).lower(), m.group(2), None)),
        # Eltex patterns
        (r"^(gi|te|fe|eth)(\d+)/(\d+)$", lambda m: (m.group(1), m.group(2), int(m.group(3)))),
        (r"^(gi|te|fe|eth)(\d+)$", lambda m: (m.group(1), m.group(2), None)),
    ]

    for pattern, extractor in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            return extractor(match)

    return (name.lower(), "", None)


def normalize_interface_name(name: str, vendor: str) -> str:
    """Normalize interface name for vendor."""
    name = name.strip().lower()

    if vendor == "cisco":
        # Expand common abbreviations
        replacements = {
            "gi": "GigabitEthernet",
            "te": "TenGigabitEthernet",
            "fo": "FortyGigabitEthernet",
            "hu": "HundredGigabitEthernet",
            "fa": "FastEthernet",
            "eth": "Ethernet",
            "vl": "Vlan",
            "lo": "Loopback",
            "po": "Port-channel",
            "tu": "Tunnel",
        }
        for abbr, full in replacements.items():
            if name.startswith(abbr):
                return full + name[len(abbr):]

    elif vendor == "eltex":
        # Eltex uses lowercase with slash
        replacements = {
            "gigabitethernet": "gi",
            "tengigabitethernet": "te",
            "fortygigabitethernet": "fo",
            "fastethernet": "fe",
            "ethernet": "eth",
            "vlan": "vlan",
            "loopback": "lo",
            "port-channel": "po",
            "tunnel": "tu",
        }
        for full, abbr in replacements.items():
            if name.startswith(full):
                return abbr + name[len(full):]

    return name


def is_valid_ipv4(ip: str) -> bool:
    """Check if string is valid IPv4 address."""
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False


def is_valid_ipv6(ip: str) -> bool:
    """Check if string is valid IPv6 address."""
    try:
        ipaddress.IPv6Address(ip)
        return True
    except ValueError:
        return False


def is_valid_cidr(cidr: str) -> bool:
    """Check if string is valid CIDR notation."""
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False


def cidr_to_netmask(cidr: str | int) -> str:
    """Convert CIDR to netmask."""
    if isinstance(cidr, str) and "/" in cidr:
        cidr = int(cidr.split("/")[1])
    cidr = int(cidr)
    if not 0 <= cidr <= 32:
        raise ValueError(f"Invalid CIDR: {cidr}")
    mask = (0xffffffff << (32 - cidr)) & 0xffffffff
    return ".".join(str((mask >> (8 * i)) & 0xff) for i in [3, 2, 1, 0])


def netmask_to_cidr(netmask: str) -> int:
    """Convert netmask to CIDR."""
    parts = netmask.split(".")
    if len(parts) != 4:
        raise ValueError(f"Invalid netmask: {netmask}")
    mask = sum(int(p) << (8 * i) for i, p in enumerate(reversed(parts)))
    cidr = 0
    while mask & 0x80000000:
        cidr += 1
        mask <<= 1
    return cidr


def get_network_address(ip_cidr: str) -> str:
    """Get network address from IP/CIDR."""
    network = ipaddress.ip_network(ip_cidr, strict=False)
    return str(network.network_address)


def get_broadcast_address(ip_cidr: str) -> str:
    """Get broadcast address from IP/CIDR."""
    network = ipaddress.ip_network(ip_cidr, strict=False)
    return str(network.broadcast_address)


def get_usable_range(ip_cidr: str) -> tuple[str, str]:
    """Get first and last usable IP in network."""
    network = ipaddress.ip_network(ip_cidr, strict=False)
    hosts = list(network.hosts())
    if len(hosts) < 2:
        return (str(hosts[0]), str(hosts[0])) if hosts else ("", "")
    return (str(hosts[0]), str(hosts[-1]))


def expand_interface_range(range_str: str) -> list[str]:
    """Expand interface range string to list of interfaces.
    
    Examples:
        "Gi1/0-3" -> ["Gi1/0", "Gi1/1", "Gi1/2", "Gi1/3"]
        "Gi1/0,Gi1/2" -> ["Gi1/0", "Gi1/2"]
        "Gi1/0-1,Gi1/3" -> ["Gi1/0", "Gi1/1", "Gi1/3"]
    """
    interfaces = []
    parts = range_str.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part and not part.startswith("-"):
            # Range like Gi1/0-3
            base, end = part.rsplit("-", 1)
            match = re.match(r"^(.+/)(\d+)$", base)
            if match:
                prefix = match.group(1)
                start = int(match.group(2))
                end_num = int(end)
                for i in range(start, end_num + 1):
                    interfaces.append(f"{prefix}{i}")
            else:
                interfaces.append(part)
        else:
            interfaces.append(part)

    return interfaces


def parse_mac_address(mac: str) -> str:
    """Normalize MAC address to standard format (aa:bb:cc:dd:ee:ff)."""
    # Remove separators
    mac = mac.replace(".", "").replace("-", "").replace(":", "").replace(" ", "").lower()
    if len(mac) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    return ":".join(mac[i:i+2] for i in range(0, 12, 2))


def is_private_ip(ip: str) -> bool:
    """Check if IP is private (RFC 1918)."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private
    except ValueError:
        return False


def get_vendor_from_sysobjectid(oid: str) -> str | None:
    """Determine vendor from SNMP sysObjectID."""
    vendor_oids = {
        "1.3.6.1.4.1.9.": "cisco",
        "1.3.6.1.4.1.89.": "eltex",
        "1.3.6.1.4.1.311.": "microsoft",
        "1.3.6.1.4.1.11.": "hp",
        "1.3.6.1.4.1.1916.": "extreme",
        "1.3.6.1.4.1.4526.": "netapp",
        "1.3.6.1.4.1.14988.": "mikrotik",
        "1.3.6.1.4.1.2011.": "huawei",
        "1.3.6.1.4.1.2636.": "juniper",
        "1.3.6.1.4.1.30065.": "arista",
    }

    for prefix, vendor in vendor_oids.items():
        if oid.startswith(prefix):
            return vendor
    return None


def sanitize_config_line(line: str) -> str:
    """Sanitize config line for safe use."""
    # Remove trailing whitespace
    line = line.rstrip()
    # Escape special characters for template use
    line = line.replace("`", "\\`").replace("$", "\\$")
    return line


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def retry_operation(func, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry decorator for operations."""
    import functools
    import time

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_exception: Exception | None = None
        current_delay = delay
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(current_delay)
                    current_delay *= backoff
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry failed with no exception")
    return wrapper

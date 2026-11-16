from network_automation.utils import (
    chunk_list,
    cidr_to_netmask,
    expand_interface_range,
    get_broadcast_address,
    get_network_address,
    get_usable_range,
    get_vendor_from_sysobjectid,
    is_private_ip,
    is_valid_cidr,
    is_valid_ipv4,
    is_valid_ipv6,
    netmask_to_cidr,
    normalize_interface_name,
    parse_interface_name,
    parse_mac_address,
)


class TestInterfaceParsing:
    """Test interface name parsing and normalization."""

    def test_parse_cisco_interface(self):
        iface_type, slot, port = parse_interface_name("GigabitEthernet1/0")
        assert iface_type == "gigabitethernet"
        assert slot == "1"
        assert port == 0

    def test_parse_cisco_interface_three_part(self):
        iface_type, slot, port = parse_interface_name("TenGigabitEthernet1/0/1")
        assert iface_type == "tengigabitethernet"
        assert slot == "1/0"
        assert port == 1

    def test_parse_eltex_interface(self):
        iface_type, slot, port = parse_interface_name("gi1/0")
        assert iface_type == "gi"
        assert slot == "1"
        assert port == 0

    def test_parse_loopback(self):
        iface_type, slot, port = parse_interface_name("Loopback0")
        assert iface_type == "loopback"
        assert slot == "0"
        assert port is None

    def test_normalize_cisco(self):
        assert normalize_interface_name("gi1/0", "cisco") == "GigabitEthernet1/0"
        assert normalize_interface_name("te1/0/1", "cisco") == "TenGigabitEthernet1/0/1"
        assert normalize_interface_name("fa0/1", "cisco") == "FastEthernet0/1"

    def test_normalize_eltex(self):
        assert normalize_interface_name("GigabitEthernet1/0", "eltex") == "gi1/0"
        assert normalize_interface_name("TenGigabitEthernet1/0/1", "eltex") == "te1/0/1"


class TestIPValidation:
    """Test IP address validation and manipulation."""

    def test_valid_ipv4(self):
        assert is_valid_ipv4("192.168.1.1") is True
        assert is_valid_ipv4("10.0.0.1") is True
        assert is_valid_ipv4("255.255.255.255") is True
        assert is_valid_ipv4("0.0.0.0") is True

    def test_invalid_ipv4(self):
        assert is_valid_ipv4("256.1.1.1") is False
        assert is_valid_ipv4("192.168.1") is False
        assert is_valid_ipv4("not.an.ip") is False
        assert is_valid_ipv4("") is False

    def test_valid_ipv6(self):
        assert is_valid_ipv6("2001:db8::1") is True
        assert is_valid_ipv6("::1") is True
        assert is_valid_ipv6("fe80::1") is True

    def test_valid_cidr(self):
        assert is_valid_cidr("192.168.1.0/24") is True
        assert is_valid_cidr("10.0.0.0/8") is True
        assert is_valid_cidr("2001:db8::/32") is True

    def test_cidr_to_netmask(self):
        assert cidr_to_netmask(24) == "255.255.255.0"
        assert cidr_to_netmask("24") == "255.255.255.0"
        assert cidr_to_netmask("192.168.1.0/24") == "255.255.255.0"
        assert cidr_to_netmask(8) == "255.0.0.0"
        assert cidr_to_netmask(32) == "255.255.255.255"

    def test_netmask_to_cidr(self):
        assert netmask_to_cidr("255.255.255.0") == 24
        assert netmask_to_cidr("255.0.0.0") == 8
        assert netmask_to_cidr("255.255.255.255") == 32

    def test_get_network_address(self):
        assert get_network_address("192.168.1.100/24") == "192.168.1.0"
        assert get_network_address("10.5.6.7/16") == "10.5.0.0"

    def test_get_broadcast_address(self):
        assert get_broadcast_address("192.168.1.100/24") == "192.168.1.255"
        assert get_broadcast_address("10.5.6.7/16") == "10.5.255.255"

    def test_get_usable_range(self):
        first, last = get_usable_range("192.168.1.0/24")
        assert first == "192.168.1.1"
        assert last == "192.168.1.254"

    def test_is_private_ip(self):
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False


class TestInterfaceRange:
    """Test interface range expansion."""

    def test_simple_range(self):
        result = expand_interface_range("Gi1/0-3")
        assert result == ["Gi1/0", "Gi1/1", "Gi1/2", "Gi1/3"]

    def test_comma_separated(self):
        result = expand_interface_range("Gi1/0,Gi1/2")
        assert result == ["Gi1/0", "Gi1/2"]

    def test_mixed(self):
        result = expand_interface_range("Gi1/0-1,Gi1/3")
        assert result == ["Gi1/0", "Gi1/1", "Gi1/3"]


class TestMACAddress:
    """Test MAC address parsing."""

    def test_parse_colon_format(self):
        assert parse_mac_address("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"

    def test_parse_dot_format(self):
        assert parse_mac_address("aaaa.bbbb.cccc") == "aa:aa:bb:bb:cc:cc"

    def test_parse_dash_format(self):
        assert parse_mac_address("aa-bb-cc-dd-ee-ff") == "aa:bb:cc:dd:ee:ff"

    def test_parse_no_separator(self):
        assert parse_mac_address("aabbccddeeff") == "aa:bb:cc:dd:ee:ff"


class TestVendorOID:
    """Test vendor detection from SNMP OID."""

    def test_cisco_oid(self):
        assert get_vendor_from_sysobjectid("1.3.6.1.4.1.9.1.123") == "cisco"

    def test_eltex_oid(self):
        assert get_vendor_from_sysobjectid("1.3.6.1.4.1.89.1.1") == "eltex"

    def test_juniper_oid(self):
        assert get_vendor_from_sysobjectid("1.3.6.1.4.1.2636.1.1") == "juniper"

    def test_unknown_oid(self):
        assert get_vendor_from_sysobjectid("1.3.6.1.4.1.99999.1") is None


class TestChunkList:
    """Test list chunking."""

    def test_chunk_even(self):
        result = chunk_list([1, 2, 3, 4, 5, 6], 2)
        assert result == [[1, 2], [3, 4], [5, 6]]

    def test_chunk_uneven(self):
        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_chunk_larger_than_list(self):
        result = chunk_list([1, 2], 5)
        assert result == [[1, 2]]

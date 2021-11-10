# -*- coding: utf-*-
# utilities for network
import json
import netifaces
import nmap
import socket
import subprocess
import sh

HOSTNAME_KEY: str = 'hostname'
IP_V4_KEY: str = 'ipv4'
MAC_ADDRESS_KEY: str = 'mac'
VENDOR_KEY: str = 'vendor'
_ADDR_KEY: str = 'addr'
_NETMASK_KEY: str = 'netmask'


def is_dhcp_enabled(ipv4 : str) -> bool:
    """
    Return true if the address was given by a DHCP server.
    :return: true or false
    """
    try:
        out = subprocess.Popen("ip -4 -f inet -j address", shell=True, stdout=subprocess.PIPE).stdout.read().decode()
        ifaces: list = json.loads(out)
        for iface in ifaces:
            if 'addr_info' in iface:
                info: list =  iface['addr_info']
                if len(info) > 0 and 'local' in info[0]:
                    address : str =  info[0]['local']
                    if address == ipv4:
                        if 'dynamic' in info[0]:
                            return info[0]['dynamic']
                        return False
    except Exception:
        return None


def find_gateway() -> str:
    """
    Return the gateway address or None.
    :return: the gateway or None
    """
    try:
        return subprocess.Popen("route -ne|grep '^[0-9]'|grep '^0.'|head -1|while read c1 c2 c3; do echo $c2; done", shell=True, stdout=subprocess.PIPE).stdout.read().decode().strip()
    except Exception:
        return None


def find_wifi_ssid() -> str:
    """
    Return the SSID of the wifi active wifi connection or None.
    :return: the SSID of the wifi active wifi connection or None
    """
    try:
        output = subprocess.check_output(['sudo', 'iwgetid'])
        return str(output).split('"')[1]
    except Exception:
        return None


def find_all_ip_v4() -> list:
    """
    Return a list of all IP v4 addresses of the computer (local).
    :return: the list of all IP v4 addresses of the computer
    """
    results: list = list()
    for iface in netifaces.interfaces():
        try:
            inet_addresses = netifaces.ifaddresses(iface)[netifaces.AF_INET]
            for inet_address in inet_addresses:
                if _ADDR_KEY in inet_address and not inet_address[_ADDR_KEY].startswith('127'):
                    print('Found network interface: ' + inet_address[_ADDR_KEY])
                    results.append(inet_address[_ADDR_KEY])
        except KeyError:
            pass
    return results


def find_netmask(ip_v4: str) -> str:
    """
    Return the netmask associated to the given IP v4 address.
    :return: the netmask
    """
    for iface in netifaces.interfaces():
        try:
            inet_addresses = netifaces.ifaddresses(iface)[netifaces.AF_INET]
            for inet_address in inet_addresses:
                if _ADDR_KEY in inet_address and inet_address[_ADDR_KEY] == ip_v4:
                    print('Found network interface: ' + inet_address[_ADDR_KEY])
                    return inet_address[_NETMASK_KEY]
        except KeyError:
            pass
    return None


def find_local_mac_address(ip_v4: str) -> str:
    """
    Return the MAC address of the given IP v4 address of the computer (local).
    :param ip_v4: the IP v4 address
    :return: the MAC address
    """
    for iface in netifaces.interfaces():
        try:
            for inet_address in netifaces.ifaddresses(iface)[netifaces.AF_INET]:
                if _ADDR_KEY in inet_address and inet_address[_ADDR_KEY] == ip_v4:
                    for mac_address in netifaces.ifaddresses(iface)[netifaces.AF_LINK]:
                        if _ADDR_KEY in mac_address:
                            print('Found MAC address: ' + mac_address[_ADDR_KEY].upper() + ' for IPv4 address: ' + ip_v4)
                            return mac_address[_ADDR_KEY].upper()
        except KeyError:
            pass
    return None


def find_ip_v4() -> str:
    """
    Return the first not loopback IP v4 address of the computer (local).
    :return: the first not loopback IP v4 address
    """
    addresses: list = find_all_ip_v4()
    if len(addresses) > 0:
        return addresses[0]
    return '127.0.0.1'


def scan_network(ip_v4: str) -> list:
    """
    Return a list of dict associated to each computer found on the network associated to the given IP v4 address.
    The network is computed using the given IP v4 address and each dict contains the following entries : hostname, ipv4, mac, vendor.
    :param ip_v4: the IP v4 address used to identify network to scan
    :return: the list of dict associated to each computer found
    """
    nm: nmap.PortScanner = nmap.PortScanner()
    net: str = ip_v4.rsplit('.', 1)[0] + '.0/24'
    # print('Scanning network:', net)
    nm.scan(hosts=net, arguments='-sPn', sudo=True)
    hosts: list = nm.all_hosts()
    unique_results: dict = dict()
    local_ip: str = find_ip_v4()
    result: dict = dict()
    result[IP_V4_KEY] = local_ip
    result[MAC_ADDRESS_KEY] = find_local_mac_address(result[IP_V4_KEY])
    result[HOSTNAME_KEY] = socket.gethostbyaddr(result[IP_V4_KEY])[0]
    unique_results[local_ip] = result
    for host in hosts:
        data = nm[host]
        if data:
            addresses = data['addresses']
            hostnames = data['hostnames']
            vendor = data['vendor']
            if not addresses:
                continue
            ip: str = addresses['ipv4']
            result: dict = None
            if ip in unique_results:
                result = unique_results[ip]
            else:
                result = dict()
                result[IP_V4_KEY] = ip
            if 'mac' in addresses:
                result[MAC_ADDRESS_KEY] = addresses['mac'].upper()
                if vendor and result[MAC_ADDRESS_KEY] in vendor:
                    result[VENDOR_KEY] = vendor[result['mac']]
                elif VENDOR_KEY not in result:
                    result[VENDOR_KEY] = ''
            else:
                if MAC_ADDRESS_KEY not in result:
                    result[MAC_ADDRESS_KEY] = ''
                if VENDOR_KEY not in result:
                    result[VENDOR_KEY] = ''
            if hostnames and len(hostnames) > 0 and 'name' in hostnames[0]:
                result[HOSTNAME_KEY] = hostnames[0]['name']
            else:
                result[HOSTNAME_KEY] = ''
            unique_results[result[IP_V4_KEY]] = result
            print('Found host: ' + repr(result))
    results: list = list()
    for k in sorted(unique_results.keys()):
        results.append(unique_results[k])
    return results


def is_reachable(ip_v4: str, mac_addresses: list, scan_results: list = None) -> bool:
    """
    Check if given MAC addresses are reachable on the network of the given IP v4 address or in previous list of scan results.
    :param ip_v4: the IP v4 address used to identify network to scan, not used if given scan results is not None
    :param mac_addresses: the MAC addresses to search
    :param scan_results: the list of scan results, not used if IP v4 is not None
    :return: True if one of the MAC addresses was found on the network
    """
    results: list = scan_results
    if scan_results is None:
        results = scan_network(ip_v4)
    for data in results:
        if MAC_ADDRESS_KEY in data:
            if data[MAC_ADDRESS_KEY] in mac_addresses:
                return True
    return False

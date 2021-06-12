#! /usr/bin/python3
import json
import locale
import multiprocessing
import os
import signal
import socket
import subprocess
import sys
import threading
from datetime import datetime

import netifaces
import zeroconf

APPLICATION: str = 'MediaPlayer'
ADDR_KEY: str = 'addr'
NETMASK_KEY: str = 'netmask'
APPLICATION_TCP_PORT: int = 20060
# noinspection PyTypeChecker
service: zeroconf.Zeroconf = None
# noinspection PyTypeChecker
task: threading.Timer = None


def cleanup():
    """
    Close the resources.
    :return: None
    """
    global service, task
    if task:
        # noinspection PyBroadException
        try:
            task.cancel()
        except Exception:
            print('An error occurred while cancelling task')
    if service:
        # noinspection PyBroadException
        try:
            service.close()
        except Exception:
            print('An error occurred while closing service')


# noinspection PyUnusedLocal
def signal_handler(sig=None, frame=None):
    cleanup()
    print("Discovery service terminated")


def is_dhcp_enabled(ipv4: str) -> bool:
    """
    Return true if the address was given by a DHCP server.
    :return: true or false
    """
    # noinspection PyBroadException
    try:
        out = subprocess.Popen("ip -4 -f inet -j address", shell=True, stdout=subprocess.PIPE).stdout.read().decode()
        ifaces: list = json.loads(out)
        for iface in ifaces:
            if 'addr_info' in iface:
                info: list = iface['addr_info']
                if len(info) > 0 and 'local' in info[0]:
                    address: str = info[0]['local']
                    if address == ipv4:
                        if 'dynamic' in info[0]:
                            return info[0]['dynamic']
                        return False
    except Exception:
        return False


def find_interfaces() -> list:
    """
    Return a list of all interfaces.
    :return: the list of all interfaces
    """
    results: list = list()
    gateways: list = netifaces.gateways()[netifaces.AF_INET]
    for iface in netifaces.interfaces():
        try:
            for inet_address in netifaces.ifaddresses(iface)[netifaces.AF_INET]:
                if ADDR_KEY in inet_address and not inet_address[ADDR_KEY].startswith('127'):
                    result: dict = dict()
                    result['gateway'] = ''
                    result['mac'] = ''
                    for mac_address in netifaces.ifaddresses(iface)[netifaces.AF_LINK]:
                        if ADDR_KEY in mac_address:
                            result['mac'] = mac_address[ADDR_KEY].upper()
                            break
                    for gw in gateways:
                        if gw[1] == iface:
                            result['gateway'] = gw[0]
                    print('Found network interface: ' + inet_address[ADDR_KEY])
                    result['name'] = iface
                    result['dhcp'] = is_dhcp_enabled(inet_address[ADDR_KEY])
                    result[ADDR_KEY] = inet_address[ADDR_KEY]
                    result[NETMASK_KEY] = inet_address[NETMASK_KEY]
                    results.append(result)
        except KeyError:
            pass
    return results


def find_wifi_ssid() -> str:
    """
    Return the SSID of the wifi active wifi connection or None.
    :return: the SSID of the wifi active wifi connection or None
    """
    # noinspection PyBroadException
    try:
        output = subprocess.check_output(['iwgetid'])
        return str(output).split('"')[1]
    except Exception:
        return ''


def get_uptime() -> str:
    """
    Return the uptime as text.
    :return: the text
    """
    # noinspection PyBroadException
    try:
        output = subprocess.check_output(['awk', '{print $1}', '/proc/uptime'])
        return output.decode().strip()
    except Exception:
        return ''


def register_service():
    """
    Register the service.
    :return: None
    """
    global APPLICATION_TCP_PORT, service, active, task
    interfaces: list = find_interfaces()
    if not interfaces or len(interfaces) == 0:
        print("No network interface available, skipping")
        if active:
            task = threading.Timer(60, register_service)
            task.start()
        return
    uname = os.uname()
    now = datetime.now()
    addresses: list = list()
    for interface in interfaces:
        addresses.append(socket.inet_aton(interface[ADDR_KEY]))
    desc = {
        'application': APPLICATION,
        'hostname': socket.gethostname(),
        'version': '0.1',
        'info': uname.release + ',' + uname.version + ',' + str(multiprocessing.cpu_count()),
        'locale': ','.join(locale.getdefaultlocale()),
        'time': now.strftime("%H:%M:%S"),
        'uptime': get_uptime()
    }
    addresses: list = list()
    for interface in interfaces:
        address: str = interface[ADDR_KEY]
        if 'interfaces' in desc:
            desc['interfaces'] = desc['interfaces'] + ',' + address
        else:
            desc['interfaces'] = address
        desc['interface-' + interface['name']] = interface
        addresses.append(socket.inet_aton(address))
    info: zeroconf.ServiceInfo = zeroconf.ServiceInfo(name="Media Player Device._mediaplayer._tcp.local.",
                                                      type_="_mediaplayer._tcp.local.",
                                                      port=APPLICATION_TCP_PORT, weight=0, priority=0, properties=desc,
                                                      addresses=addresses)
    if service:
        print('Updating service on port: ' + str(APPLICATION_TCP_PORT))
        service.update_service(info)
    else:
        service = zeroconf.Zeroconf()
        print('Registering service on port: ' + str(APPLICATION_TCP_PORT))
        service.register_service(info)
    if active:
        task = threading.Timer(60, register_service)
        task.start()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    if not (sys.platform == "linux" or sys.platform == "linux2"):
        print('Platform is not supported: ' + sys.platform)
        sys.exit(1)
    active = True
    register_service()
    sys.exit(0)

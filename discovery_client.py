#! /usr/bin/python3
import signal
import zeroconf
import sys
import time

TIMEOUT: int = 2
# noinspection PyTypeChecker
client: zeroconf.Zeroconf = None


def cleanup():
    """
    Close the resources.
    :return: None
    """
    global client
    if client is not None:
        # noinspection PyBroadException
        try:
            client.close()
        except Exception:
            print('An error occurred while closing client')


# noinspection PyUnusedLocal
def signal_handler(sig=None, frame=None):
    cleanup()
    print("Client terminated")


class ListenerImpl(zeroconf.ServiceListener):

    def update_service(self, zc: zeroconf.Zeroconf, type: str, name: str) -> None:
        info = zc.get_service_info(type, name)
        print("Service %s changed, service info: %s" % (name, info))

    def remove_service(self, zc: zeroconf.Zeroconf, type: str, name: str):
        print("Service %s removed" % (name,))

    def add_service(self, zc: zeroconf.Zeroconf, type: str, name: str):
        info = zc.get_service_info(type, name)
        print("Service %s added, service info: %s" % (name, info))


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        client = zeroconf.Zeroconf()
        listener = ListenerImpl()
        browser = zeroconf.ServiceBrowser(client, "_mediaplayer._tcp.local.", listener)
        time.sleep(TIMEOUT)
    finally:
        client.close()
    sys.exit(0)

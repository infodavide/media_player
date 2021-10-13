#!/usr/bin/python
# -*- coding: utf-*-
# Media player HTTP server

import atexit
import logging
import signal
import socket
import socketserver
import sys
import threading
import time
import traceback

import media_api
from media_player_config import MediaPlayerConfig
from media_api import MediaPlayerController, ControllerListener, RemoteControlEvent

SENDING_MSG: str = 'Sending: '
EVENT_NOT_VALID: str = 'Event is not valid'
CHARSET: str = 'utf-8'


class _TcpHandler(socketserver.BaseRequestHandler):
    def __init__(self, request, client_address, server, controller, logger):
        self.__controller = controller
        self.__pending_data: bytearray = bytearray()
        self.__logger: logging.Logger = logger
        self.__logger.info('Initializing %s', self.__class__.__name__)
        super().__init__(request, client_address, server)

    def setup(self):
        self.__logger.debug('Setup')
        return socketserver.BaseRequestHandler.setup(self)

    def handle(self):
        self.request.settimeout(15)
        self.request.setblocking(True)
        while self.__controller.is_running():
            response: bytes = b''
            if self.__controller.is_running():
                try:
                    packet: bytearray = self.__pending_data + self.request.recv(512)
                    if not packet:
                        return
                    length: int = len(packet)
                    if length == 0:
                        return
                    data: bytearray = bytearray()
                    for i, val in enumerate(packet):
                        if val == 0x0A and i > 1 and packet[i - 1] == 0x0D:
                            data.extend(packet[0:i - 1])
                            self.__pending_data.clear()
                            self.__pending_data.extend(packet[i + 1:])
                            break
                    if len(data) == 0:
                        return
                    self.__logger.debug('Event received from {}: {}'.format(self.client_address[0], data))
                    code: int
                    event: RemoteControlEvent = RemoteControlEvent(data[0])
                    if len(data) > 1:
                        event.set_data(data[1:].decode('ascii'))
                    elif 0x20 <= data[0] <= 0x7E:  # A valid ASCII character
                        event.set_data(data.decode('ascii'))
                    self.__logger.debug('Dispatching event: %s', event)
                    if self.__controller.get_listener():
                        response = self.__controller.get_listener().on_control_event(event)
                    else:
                        self.__logger.warning('Event not processed')
                        response = media_api.RESPONSE_NACK
                except socket.timeout:
                    self.__logger.warning('Client connection timeout')
                    return
                except ConnectionResetError:
                    self.__logger.warning('Client connection closed')
                    return
                except Exception as ex:
                    self.__logger.error('Error: %s' % ex)
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
                    self.__logger.error(ex)
                    response = media_api.RESPONSE_NACK
                if not response and len(response) == 0:
                    response = media_api.RESPONSE_NACK
                self.__logger.debug('Sending response: %s', response)
                self.request.send(response)


class _TcpServer(socketserver.TCPServer):
    def __init__(self, server_address, controller, logger):
        self.__controller = controller
        self.__logger: logging.Logger = logger
        socketserver.TCPServer.allow_reuse_address = False
        socketserver.TCPServer.timeout = 2
        socketserver.TCPServer.request_queue_size = 5
        super().__init__(server_address, _TcpHandler)

    def finish_request(self, request, client_address):
        self.__logger.debug('Connection started with: %s', client_address[0])
        _TcpHandler(request, client_address, self, self.__controller, self.__logger)

    def handle_error(self, request, client_address):
        super().handle_error(request, client_address)
        self.__logger.warning('Error')


class MediaPlayerTcpController(MediaPlayerController):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, listener: ControllerListener):
        """
        Initialize the media player controller.
        :param parent_logger: the main logger
        :param config: the configuration object
        """
        super().__init__(config, listener)
        if not MediaPlayerTcpController.__logger:
            MediaPlayerTcpController.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                MediaPlayerTcpController.__logger.addHandler(handler)
            MediaPlayerTcpController.__logger.setLevel(parent_logger.level)
        MediaPlayerTcpController.__logger.info('Initializing %s', self.__class__.__name__)
        # Status flags
        self.__active: bool = False
        self.__shutdown_request = False
        # Locks
        self.__lock: threading.RLock = threading.RLock()
        self.__start_lock: threading.RLock = threading.RLock()
        self.__stop_lock: threading.RLock = threading.RLock()
        # Tasks
        # noinspection PyTypeChecker
        self.__main_task: threading.Timer = None
        # Hooks
        atexit.register(self.stop)
        signal.signal(signal.SIGINT, self.stop)
        # noinspection PyTypeChecker
        self.__server: _TcpServer = None

    def __main(self):
        MediaPlayerTcpController.__logger.info('Starting on port: %s', self._config.get_tcp_port())
        try:
            with _TcpServer(('0.0.0.0', self._config.get_tcp_port()), self, MediaPlayerTcpController.__logger) as server:
                self.__active = True
                self.__server = server
                while self.__active:
                    server.handle_request()
        except TypeError as ex:
            MediaPlayerTcpController.__logger.error('Error: %s' % ex)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            MediaPlayerTcpController.__logger.error(ex)
        finally:
            self.__server = None
            self.__active = False
            MediaPlayerTcpController.__logger.info('Stopped')

    def is_running(self) -> bool:
        return self.__active

    def start(self) -> None:
        with self.__lock:
            if self.__active:
                return
        with self.__start_lock:
            MediaPlayerTcpController.__logger.debug('Starting...')
            self.__active = True
            self.__shutdown_request = False
            self.__main_task = threading.Timer(1, self.__main)
            self.__main_task.start()
            MediaPlayerTcpController.__logger.debug('Started (%s)', self.__active)

    def stop(self) -> None:
        with self.__lock:
            if not self.__active:
                return
        with self.__stop_lock:
            MediaPlayerTcpController.__logger.debug('Stopping...')
            self.__active = False
            self.__shutdown_request = True
            try:
                if self.__server:
                    self.__server.server_close()
                self.__main_task = None
            except Exception as ex:
                MediaPlayerTcpController.__logger.error('Cannot stop main task: %s' % ex)
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
                MediaPlayerTcpController.__logger.error(ex)
            finally:
                if self._listener:
                    self._listener.on_controller_stop()

    def restart(self):
        self.stop()
        time.sleep(1)
        self.start()

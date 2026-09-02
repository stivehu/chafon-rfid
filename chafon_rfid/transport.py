#!/usr/bin/env python

import abc
import socket


class BaseTransport(object):
    __metaclass__ = abc.ABCMeta
    read_bytecount = 0x100

    def __init__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def read_bytes(self, length):
        raise NotImplementedError

    @abc.abstractmethod
    def write_bytes(self, byte_array):
        raise NotImplementedError

    def read(self):
        return self.read_bytes(self.read_bytecount)

    def read_frame(self):
        length_bytes = self.read_bytes(1)
        frame_length = length_bytes[0]
        data = length_bytes + self.read_bytes(frame_length)
        return bytearray(data)

    def write(self, byte_array):
        self.write_bytes(byte_array)


class TcpTransport(BaseTransport):

    buffer_size = 0xFF
    drain_timeout = 0.2

    def __init__(self, reader_addr, reader_port, timeout=5, auto_connect=False):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.settimeout(timeout)
        self.reader_addr = reader_addr
        self.reader_port = reader_port
        self.timeout = timeout
        if auto_connect:
            self.connect()

    def connect(self):
        self.socket.connect((self.reader_addr, self.reader_port))
        self._drain_stale_data()

    def _drain_stale_data(self):
        # A readeren egy korabbi (megszakadt) kapcsolat idejebol egy meg ki
        # nem olvasott valaszkeret varakozhat, ami az uj kapcsolaton az elso
        # parancsunk valasza ele keveredne -- csatlakozaskor ezert
        # kiuritjuk, ami mar a socketben var.
        self.socket.settimeout(self.drain_timeout)
        try:
            while self.socket.recv(self.buffer_size):
                pass
        except socket.timeout:
            pass
        finally:
            self.socket.settimeout(self.timeout)

    def reconnect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.settimeout(self.timeout)
        self.connect()

    def read_bytes(self, length):
        result = b''
        while len(result) < length:
            chunk = self.socket.recv(length - len(result))
            if not chunk:
                # Lezart TCP-kapcsolaton a recv() nem blokkol, hanem azonnal
                # ures bytes-szal ter vissza -- enelkul az ellenorzes nelkul a
                # ciklus vegtelenul, 100% CPU-t hasznalva probalna tovabb
                # olvasni egy soha meg nem erkezo adatra, kivetel es log
                # nelkul lefagyasztva a folyamatot.
                raise ConnectionError('A reader lezarta a TCP-kapcsolatot')
            result += chunk
        return result

    def write_bytes(self, byte_array):
        self.socket.sendall(byte_array)

    def close(self):
        self.socket.close()


class MockTransport(BaseTransport):

    def __init__(self, data):
        self.pointer = 0
        self.data = bytes(data)

    def read_bytes(self, length):
        data = self.data[self.pointer:self.pointer+length]
        self.pointer += length
        return data

    def write_bytes(self, byte_array):
        pass

    def close(self):
        pass

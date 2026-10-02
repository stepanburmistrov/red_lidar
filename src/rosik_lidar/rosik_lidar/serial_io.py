"""Serial reader used by both the standalone viewer and the ROS 2 node."""
from __future__ import annotations

import time
from typing import Iterator, Optional

import serial
from serial.tools import list_ports

from .protocol import MSG_SCAN, Packet, StreamParser


def available_ports() -> list[str]:
    return [p.device for p in list_ports.comports()]


class LidarSerial:
    def __init__(self, port: str, baud: int = 460800, timeout: float = 0.10) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self.parser = StreamParser()
        self.bytes_rx = 0
        self.packets_rx = 0

    def open(self) -> None:
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        self.ser.reset_input_buffer()

    def close(self) -> None:
        if self.ser is not None:
            self.ser.close()
            self.ser = None

    def read_packets(self) -> list[Packet]:
        if self.ser is None:
            raise RuntimeError("serial port is not open")
        waiting = self.ser.in_waiting
        data = self.ser.read(waiting if waiting else 1)
        self.bytes_rx += len(data)
        packets = self.parser.feed(data)
        self.packets_rx += len(packets)
        return packets

    def scans(self) -> Iterator[Packet]:
        while True:
            for packet in self.read_packets():
                if packet.msg_type == MSG_SCAN:
                    yield packet

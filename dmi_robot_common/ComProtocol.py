from __future__ import annotations
import os
import pathlib
import struct
import time
from enum import Enum
from typing import List, Tuple, Dict, Optional
from dmi_robot_common.UDPSocketManager import UDPSocketManager
from dmi_robot_common.Logger import logger

class ComProtocol:
    MAX_DATA_VALUES: int = 1019
    _MIN_MESSAGE_LENGTH: int = 4 #source_id, dest_id, length and crc
    def __init__(self, current_entity: Tuple[str, int, int], remote_entity: Tuple[str, int, int]) -> None:
        self._socket = UDPSocketManager((current_entity[0], current_entity[1]))
        self._source_id: int = current_entity[2]
        self._dest_id: int = remote_entity[2]
        self._remote_address: Tuple[str, int] = remote_entity[0], remote_entity[1]
        
    @staticmethod
    def _compute_crc(data: List[int]) -> int:
        crc: int = 0
        for b in data:
            crc ^= b & 0xFF
        return crc & 0xFF

    def put_data(self, payload: List[int]) -> bool:
        msg: List[int] = [
            self._source_id,
            self._dest_id,
            len(payload),
            *payload,
        ]
        crc: int = ComProtocol._compute_crc(msg)
        msg.append(crc)

        return self._socket.send(msg, self._remote_address)

    def get_data(self) -> List[int]:
        data: List[int] = self._socket.receive()
        ret: List[int] = []
        if data is not None and len(data) > ComProtocol._MIN_MESSAGE_LENGTH:
            source = data[0]
            dest = data[1]
            length = data[2]
            if len(data) == length + ComProtocol._MIN_MESSAGE_LENGTH:
                payload = data[3:-1]
                received_crc = data[-1]
                if received_crc == ComProtocol._compute_crc(data[:-1]):
                    if dest == self._source_id and source == self._dest_id:
                        ret = payload
                else:
                    logger.error("Wrong CRC")
            else:
                logger.error(f"Expected payload length: {length}, received payload length: {len(data) - ComProtocol._MIN_MESSAGE_LENGTH} ")
        return ret

    
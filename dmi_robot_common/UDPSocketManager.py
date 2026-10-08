import struct
import time
from typing import List, Tuple
from dmi_robot_common.YamlCfg import YamlCfg
import socket
from dmi_robot_common.Logger import logger

class UDPSocketManager:
    _SEND_SLEEP: float = 0.0
    def __init__(self, address):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(address)
        self._sock.setblocking(False)
    
    def send(self, msg: List[int], remote_address: Tuple[str, int]):
        try:
            header = struct.pack("!I", len(msg)) 
            body = b"".join(struct.pack("!i", x) for x in msg)  
            data = header + body
            logger.debug(f"Sending to {remote_address}: {msg}")
            sent = self._sock.sendto(data, remote_address)
            time.sleep(UDPSocketManager._SEND_SLEEP)
            return sent == len(data)
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
        

    def receive(self)-> List[int]:
        try:
            data, addr = self._sock.recvfrom(4096)
            if len(data) < 4:
                logger.error(f"Invalid packet from {addr}")
                return []
            count = struct.unpack("!I", data[:4])[0]
            if len(data) != 4 + count * 4:
                logger.error("Invalid packet length from %s", addr)
                return []
            msg = []
            for i in range(count):
                start = 4 + i * 4
                end = start + 4
                if end > len(data):
                    break
                value = struct.unpack("!i", data[start:end])[0]
                msg.append(value)
            logger.debug(f"Received from {addr}: {msg}")
            return msg
        except BlockingIOError:
            return []
        except OSError:
            logger.exception("UDP receive failed")
            raise

    def close(self) -> None:
        self._sock.close()

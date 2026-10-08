from __future__ import annotations
from enum import Enum
import os
import pathlib
import socket
import time
from typing import Any, List, Tuple
from dmi_robot_rasp.DmiRobot import DmiRobot
from dmi_robot_common.ComProtocol import ComProtocol
import struct
from dmi_robot_common.YamlCfg import YamlCfg
from dmi_robot_common.UDPSocketManager import UDPSocketManager
from dmi_robot_common.Logger import setup_logging, logger
from dmi_robot_common.DmiMessages import DmiMessages

class DmiControllerSlave:
      
    _PICTURES_SEND_SLEEP: float = 0.2
    def __init__(self, dmi_robot: DmiRobot, send_function, receive_function)->None:
        self._dmi_robot: DmiRobot = dmi_robot
        self._send_function = send_function
        self._receive_function = receive_function
        self._pictures: List[str] = []
        
        

    
    def _send(self, msg_type: DmiMessages, data: List[int])->bool:
        msg: List[int] = [msg_type.value]
        msg.extend(data)
        sent: bool = self._send_function(msg)
        if sent:
            logger.info(f"{msg_type.name} action sent with data length: {len(data)}")
            logger.debug(f"Data: {data}")
        else:
            logger.error(f"Error while sending {msg_type.name} action with data: {data}" )
        return sent
    
    def _send_pictures(self)->None:
        MAX_VALUES: int = ComProtocol.MAX_DATA_VALUES
        chunk_size: int = MAX_VALUES - 5
        total_images: int = len(self._pictures)
        if 0 <= total_images:
            img_bytes_list: List[List[int]] = [list(open(img, "rb").read()) for img in self._pictures]
            total_chunks_list: List[int] = [(len(img_bytes) + chunk_size - 1) // chunk_size for img_bytes in img_bytes_list]
            self._send(DmiMessages.PICTURE, total_chunks_list)
            for img_idx, img_bytes in enumerate(img_bytes_list):
                total_chunks: int = total_chunks_list[img_idx]
                for chunk_idx in range(total_chunks):
                    start: int = chunk_idx * chunk_size
                    end: int = min(start + chunk_size, len(img_bytes))
                    chunk: List[int] = img_bytes[start:end]

                    msg: List[int] = [total_images, img_idx, total_chunks, chunk_idx] + chunk

                    if not self._send(DmiMessages.PICTURE_DATA, msg):
                        self._send(DmiMessages.ERROR, [])
                    time.sleep(DmiControllerSlave._PICTURES_SEND_SLEEP)
        else:
            self._send(DmiMessages.ERROR, [])
        self._pictures = []
                

            
    def run(self)->None:
        data = self._receive_function()
        if data is not None and 0 != len(data):
            msg_type, args = DmiMessages.decode_message(data)
            try:
                if DmiMessages.MOVE_AND_CLICK == msg_type:
                    self._send(DmiMessages.DONE if self._dmi_robot.move_and_click(*args) else DmiMessages.ERROR, [])
                elif DmiMessages.TAKE_PICTURES == msg_type:
                    new_pictures: List[str] = self._dmi_robot.take_picture(*args)
                    self._pictures.extend(new_pictures)
                    self._send(DmiMessages.DONE if 0 != len(new_pictures) else DmiMessages.ERROR, [])
                elif DmiMessages.GET_PICTURES == msg_type:
                    self._send_pictures()
                elif DmiMessages.MOVE == msg_type:
                    self._send(DmiMessages.DONE if self._dmi_robot.move(*args) else DmiMessages.ERROR, [])
                elif DmiMessages.INITIALIZE == msg_type:
                    self._send(DmiMessages.DONE if self._dmi_robot.initialize_hardware() else DmiMessages.ERROR, [])
                elif DmiMessages.RETURN_TO_ZERO == msg_type:
                    self._send(DmiMessages.DONE if self._dmi_robot.return_to_zero() else DmiMessages.ERROR, [])
                elif DmiMessages.GET_CURRENT_POSITION == msg_type: 
                    self._send(DmiMessages.DONE, list(self._dmi_robot.current_x_y_position))
                elif DmiMessages.ACK == msg_type: 
                    self._send(DmiMessages.ACK, [])
                else:
                    raise Exception("Unknown message type received")
            except Exception as e:
                logger.error(f"Error: {e}")
                self._send(DmiMessages.ERROR, [])
            finally:
                pass #Keep receiving new messages
                    

        
        
if "__main__" == __name__:
    cfg_path: str = os.path.join(pathlib.Path(__file__).parent, "raspberry_cfg.yaml")
    cfg: YamlCfg = YamlCfg(cfg_path)
    setup_logging(cfg.log_level, pathlib.Path(__file__).stem)
    
            
    dmi_robot: DmiRobot = DmiRobot(cfg)
    

    com_protocol = ComProtocol(cfg.address, cfg.remote_address)
    
    
    dmi_controller: DmiControllerSlave = DmiControllerSlave(dmi_robot, com_protocol.put_data, com_protocol.get_data)
    while True:
        dmi_controller.run()
    
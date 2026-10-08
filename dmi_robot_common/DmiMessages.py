from __future__ import annotations
from enum import Enum
from typing import List, Tuple
from dmi_robot_common.Logger import logger

class DmiMessages(Enum):
        ERROR: int = 0
        MOVE_AND_CLICK: int = 1
        GET_PICTURES: int = 2
        MOVE: int = 3
        GET_CURRENT_POSITION: int = 4
        INITIALIZE: int = 5
        RETURN_TO_ZERO: int = 6
        DONE: int = 7
        PICTURE: int = 8
        PICTURE_DATA: int = 9
        TAKE_PICTURES: int = 10
        ACK: int = 11
        
        
        @staticmethod
        def get_wait_function_name(msg_type: DmiMessages)->str:
            return f"_wait_{msg_type.name}"
        
        @staticmethod
        def get_enum_from_function(func_name: str)->DmiMessages:
            return DmiMessages[func_name.replace("_wait_", "")]
        
        @staticmethod
        def decode_message(data: List[int])->Tuple[DmiMessages, List[int]]:
            msg_type: DmiMessages = DmiMessages.ERROR
            msg_data: List[int] = []
            if 0!= len(data):
                msg_type =  DmiMessages(data[0])
                if 1 <= len(data):
                    msg_data = data[1::]
            logger.info(f"Action {msg_type.name} received. Data length: {len(msg_data)}")
            logger.debug(f"Data: {msg_data}")
            return msg_type, msg_data
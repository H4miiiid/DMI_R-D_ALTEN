from __future__ import annotations
import inspect
import os
import pathlib
import time
from typing import Any, Dict, List, Tuple, Union
from dmi_robot_common.YamlCfg import YamlCfg
from dmi_robot_common.ComProtocol import ComProtocol
from enum import Enum
from dmi_robot_common.UDPSocketManager import UDPSocketManager
from dmi_robot_common.Logger import setup_logging, logger
from dmi_robot_common.DmiMessages import DmiMessages

class DmiControllerMaster:
    
    
    def __init__(self, send_function, receive_function)->None:
        self._send_function = send_function
        self._receive_function = receive_function
        
    def _start_timer(self)->None:
        self._start_time = time.time()
        
    def _timer_expired(self, v: float)->bool:
        return (time.time() - self._start_time) > v
    
    def send(self, msg_type: DmiMessages, *args: List[int])-> bool:
        msg: List[int]= [msg_type.value]
        msg.extend(*args)
        return self._send_function(msg)
    
    def _wait_response(self, msg_type: DmiMessages, timeout: float, sleep: float, expected_data_len: Union[int, None])-> Tuple[bool, list[int]]:
        func_name = DmiMessages.get_wait_function_name(msg_type)   
        func = getattr(self, func_name, None)
        ret: Tuple[bool, List[int]] = (False, [])
        if func is None:
            raise AttributeError(f"No implementation for {msg_type.name}")
        else:
            frame = inspect.currentframe()
            args, _, _, values = inspect.getargvalues(frame)
            args = [values[name] for name in args[2:]] 
            ret = func(*args)
        return ret
    
    def _wait_ACK(self, timeout: float, sleep: float, expected_data_len: Union[int, None]) -> Tuple[bool, list[int]]:
        return self._wait_single_message(DmiMessages.ACK, timeout, sleep, expected_data_len)
    
    def _wait_DONE(self, timeout: float, sleep: float, expected_data_len: Union[int, None]) -> Tuple[bool, list[int]]:
        return self._wait_single_message(DmiMessages.DONE, timeout, sleep, expected_data_len)
    
    def _wait_PICTURE(self, timeout: float, sleep: float, expected_data_len: Union[int, None]) -> Tuple[bool, list[int]]:
        ret: Tuple[bool, list[int]] = self._wait_single_message(DmiMessages.PICTURE, timeout, sleep, None)
        if ret[0]:
            total_chunks_list: List[int] = ret[1]
            images: List[List[int]] = [self._wait_n_messages(DmiMessages.PICTURE_DATA, timeout, sleep, None, chunk)[1] for chunk in total_chunks_list]
            paths: List[str] = self._save_images([elem for sublist in images for elem in sublist])
        return ret[0], paths
    
    def _wait_single_message(self, expected_msg_type: DmiMessages, timeout: float, sleep: float, expected_data_len: Union[int, None]) -> Tuple[bool, list[int]]:
        self._start_timer()
        while not self._timer_expired(timeout):
            data = self._receive_function()
            if data:
                msg_t, msg_data = self._decode_message(data)
                if msg_t == expected_msg_type:
                    if expected_data_len is None or len(msg_data) == expected_data_len:
                        logger.info(f"Expected {expected_msg_type.name} action with data length = {len(msg_data)} received")
                        logger.debug(f"Data: {msg_data}")
                        return True, msg_data
            time.sleep(sleep)
        logger.error(f"Timeout expired while waiting for {expected_msg_type.name} action" + ("" if expected_data_len is None else f" with data length = {expected_data_len}"))
        return False, []
    
    

    def _wait_n_messages(
        self,
        msg_type: DmiMessages,
        timeout: float,
        sleep: float,
        expected_data_len: Union[int, None],
        expected_n_msg: Union[int, None]
    ) -> Tuple[bool, List[List[int]]]:
  
        self._start_timer()
        all_msgs: List[List[int]] = []

        while not self._timer_expired(timeout):
            data = self._receive_function()
            if data:
                msg_t, msg_data = self._decode_message(data)

                if msg_t == msg_type:
                    if expected_data_len is None or len(msg_data) == expected_data_len:
                        all_msgs.append(msg_data)
                        logger.info(f"{msg_type.name} action received ({len(all_msgs)}). Data length: {len(msg_data)}")
                        logger.debug(f"Data: {msg_data}")

                        if expected_n_msg is not None and len(all_msgs) >= expected_n_msg:
                            logger.info(f"Received all {expected_n_msg} expected {msg_type.name} messages.")
                            return True, all_msgs

            time.sleep(sleep)

        logger.error(f"Timeout expired while waiting for {msg_type.name} messages"
            f"{'' if expected_data_len is None else f' with data length = {expected_data_len}'}"
            f"{'' if expected_n_msg is None else f' (expected {expected_n_msg}, received {len(all_msgs)})'}")

        return (len(all_msgs) > 0, all_msgs)

    

        
    def _decode_message(self, data: List[int])->Tuple[DmiMessages, List[int]]:
        msg_type: DmiMessages = DmiMessages.ERROR
        msg_data: List[int] = []
        if 0!= len(data):
            msg_type =  DmiMessages(data[0])
            if 1 <= len(data):
                msg_data = data[1::]
        return msg_type, msg_data

    def manage_action(self, action: DmiControllerMaster.Action)->Tuple[bool, List[List[Any]]]:
        ret: Tuple[bool, List[List[int]]] = (False, [])
        try:
            sent: bool = self.send(action.send_action, action.send_data)
            if not sent:
                logger.error(f"Error while sending action {action.send_action.name}. Data: {action.send_data}")
            else:
                logger.info(f"Action {action.send_action.name} sent. Data length: {len(action.send_data)}")
                logger.debug(f"Data: {action.send_data}")
                
                ret = self._wait_response(action.expected_response, action.timeout, action.receive_sleep, action.expected_data_len)
        except Exception as e:
            logger.error(f"Manage action error: {e}")
        return ret
    
    def _save_images(self, msgs: List[List[int]])->None:
    
        images: Dict[int, Dict[int, List[int]]] = {} 
        paths: List[str] = []
        for pkt in msgs:
            _, current_img, _, current_chunk, *data = pkt

            if current_img not in images:
                images[current_img] = {}

            images[current_img][current_chunk] = data

        folder = pathlib.Path(__file__).parent
        if 0 != len(images):
            for img_idx, pezzi in images.items():
                img_data = []
                for i in range(len(pezzi)):
                    img_data.extend(pezzi[i])

                file_path = os.path.join(folder, f"{img_idx}.jpg")
                with open(file_path, "wb") as f:
                    f.write(bytes(img_data))
                paths.append(file_path)
                logger.debug(f"Image {img_idx} saved in {file_path}")
        
        return paths
            
    class Action:
        _DEFAULT_TIMEOUT: float = 60 #s
        _DEFAULT_RCV_SLEEP: float = 0 #s
        def __init__(self, send_action: DmiMessages, send_data: List[int], expected_response: DmiMessages, expected_msg_len: Union[int, None] = None, timeout: float = _DEFAULT_TIMEOUT, receive_sleep: float = _DEFAULT_RCV_SLEEP):
            self._send_action: DmiMessages  = send_action
            self._send_data: List[int] = send_data
            self._expected_response: DmiMessages = expected_response
            self._timeout: float = timeout
            self._receive_sleep: float = receive_sleep
            self._expected_msg_len: Union[int, None] = expected_msg_len
            
        send_action: DmiMessages = property(lambda self: self._send_action , None, None)     
        send_data: List[int] = property(lambda self: self._send_data, None, None)
        expected_response: DmiMessages = property(lambda self: self._expected_response, None, None)
        timeout: float = property(lambda self: self._timeout, None, None)
        receive_sleep: float = property(lambda self: self._receive_sleep, None, None)
        expected_data_len: int = property(lambda self: self._expected_msg_len, None, None)
        expected_n_msg: int = property(lambda self: self._expected_n_msg, None, None)
        


if "__main__" == __name__:
    cfg_path: str = os.path.join(pathlib.Path(__file__).parent, "pc_cfg.yaml")
    cfg: YamlCfg = YamlCfg(cfg_path)
    
    setup_logging(cfg.log_level, pathlib.Path(__file__).stem)
    
    com_protocol = ComProtocol(cfg.address, cfg.remote_address)
    
    dmi_controller: DmiControllerMaster = DmiControllerMaster(com_protocol.put_data, com_protocol.get_data)
    
    while not dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.ACK, [], DmiMessages.ACK, 0, 1))[0]:
        time.sleep(0.5)
        
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.INITIALIZE, [], DmiMessages.DONE, 0)))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [100, 0, 0], DmiMessages.DONE, 0 )))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [100, 100, 0], DmiMessages.DONE, 0 )))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [200, 200, 50], DmiMessages.DONE, 0 )))    
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [0, 0, 0], DmiMessages.DONE, 0 )))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [100, 100, 50], DmiMessages.DONE, 0 )))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [0, 0, 0], DmiMessages.DONE, 0 )))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [100, 100, 500], DmiMessages.DONE, 0 )))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.INITIALIZE, [], DmiMessages.DONE, 0)))
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [30, 65, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [35, -50, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-35, 50, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [25, -15, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [110, -95, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-135, 125, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 1000], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [130, -120, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-150, 75, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-10, -35, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [30, 65, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [25, 0, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [100, -80, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 4000], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-275, -335, 0], DmiMessages.DONE, 0 )))
    #res = dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_CURRENT_POSITION, [], DmiMessages.DONE, 2 ))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-res[1][0], -res[1][1], 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_PICTURES, [], DmiMessages.PICTURE )))


    #input("")

    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [120, 350, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [150, 415, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [185, 365, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [150, 415, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [175, 400, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [285, 305, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [150, 430, 1000], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [280, 310, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [130, 385, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [120, 350, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [150, 415, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [175, 415, 500 ], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [275, 335, 4000], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 1000], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))

    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_PICTURES, [], DmiMessages.PICTURE )))
        
    #input("")
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [120, 80, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [30, 65, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [35, -50, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-35, 50, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [25, -15, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [110, -95, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-135, 125, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 1000], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [130, -120, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-150, 75, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-10, -35, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [30, 65, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [25, 0, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 500], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [100, -80, 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [ 0, 0, 4000], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-275, -65, 0], DmiMessages.DONE, 0 )))
    #res = dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_CURRENT_POSITION, [], DmiMessages.DONE, 2 ))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-res[1][0], -res[1][1], 0], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [0,1,1], DmiMessages.DONE, 0 )))
    
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_PICTURES, [], DmiMessages.PICTURE )))
    

    
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE_AND_CLICK, [1,2,3], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.MOVE, [-1,-2,-30], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_CURRENT_POSITION, [], DmiMessages.DONE, 2 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.INITIALIZE, [], DmiMessages.DONE, 0)))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.RETURN_TO_ZERO, [], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [-1,-2,-30], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.TAKE_PICTURES, [-1,-2,-30], DmiMessages.DONE, 0 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_CURRENT_POSITION, [], DmiMessages.DONE, 2 )))
    #print(dmi_controller.manage_action(DmiControllerMaster.Action(DmiMessages.GET_PICTURES, [1,2, 3], DmiMessages.PICTURE )))


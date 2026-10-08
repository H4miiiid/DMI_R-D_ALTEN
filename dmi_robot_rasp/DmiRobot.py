import os
import math
from time import sleep
from typing import List, Tuple, Union, Any
import subprocess
import numpy
from dmi_robot_rasp.Button import Button
from dmi_robot_rasp.InductionSensor import InductionSensor
from dmi_robot_rasp.Motor import Motor
import pathlib
from typing import Tuple, Union, Any
from dmi_robot_common.YamlCfg import YamlCfg
import functools
import cv2
from picamera2 import Picamera2

from dmi_robot_common.Logger import logger
  
class DmiRobot:
    _VELOCITY: float = 0.000000001
    _MIN_STEPS: int = 100
    _X: float = 380 #mm 6.13 * 6.25
    _Y: float = 470 #mm 6.13 * 7,75
    _X_OFFSET: float = 0 #mm TODO
    _Y_OFFSET: float = 0 #mm TODO
    _MAX_Z_STEPS: int = 9500
    _CAMERA_WIDTH: int = 1280
    _CAMERA_HEIGHT: int = 720
    _PICTURE_PATH = pathlib.Path(__file__).parent
    
    def __init__(self, pin_cfg: YamlCfg)-> None:
        self._button = Button(pin_cfg.button)  
        self._z_sensor = InductionSensor(pin_cfg.z_sensor, 10)
        self._x_sensor = InductionSensor(pin_cfg.x_sensor, 10)
        self._y_sensor = InductionSensor(pin_cfg.y_sensor, 10)
        self._r_motor = Motor(*pin_cfg.r_motor)  
        self._l_motor = Motor(*pin_cfg.l_motor)  
        self._z_motor = Motor(*pin_cfg.z_motor)       

        self._clockwise_dir: bool = False
        self._x_steps: int = 0
        self._y_steps: int = 0
        self._z_steps: int = 0
        self._x_total_steps: int = 0
        self._y_total_steps: int = 0
        self._autoscaling_done: bool = False
        self._x_left: bool = False
        self._cameras: List[Any] = [None] * 1

    current_x_y_position: Tuple[int, int] = property(lambda self: (self._x_steps_to_millimeters(self._x_steps), self._y_steps_to_millimeters(self._y_steps)), None, None)

    def log_call(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__qualname__

            arg_str: str = ", ".join(["self" if 0 == i and str(a) == "" else str(a) for i, a in enumerate(args)] + [f"{k}={v}" for k, v in kwargs.items()])

            logger.info(f"Called {func_name} ({arg_str})")

            result = func(*args, **kwargs)

            logger.info(f"Returned from {func_name}: {result}")
            return result
        return wrapper
    
    def __repr__(self):
        r: str = ""
        r +=(f"x: position = {self._x_steps}, sensor = {self._x_sensor.contact}\n")
        r +=(f"y: position = {self._y_steps}, sensor = {self._y_sensor.contact}\n")
        r+=(f"z: position = {self._z_steps}, sensor = {self._z_sensor.contact}\n")
        r+=f"x: 1 mm = {self._x_millimeters_to_steps(1)}\ny: 1 mm = {self._y_millimeters_to_steps(1)}"
        return r


    def _pulse_motor(self, motor: Motor, velocity: float) -> None:
        motor.write_pulse(1)
        sleep(velocity)
        motor.write_pulse(0)
        sleep(self._VELOCITY)

    def _set_lr_directions(self, l_steps: int, r_steps: int) -> None:
        self._l_motor.write_direction(not self._clockwise_dir if l_steps > 0 else self._clockwise_dir)
        self._r_motor.write_direction(not self._clockwise_dir if r_steps > 0 else self._clockwise_dir)

#    def _xy_linear_movement_steps(self, dx_steps: int, dy_steps: int, velocity: float) -> Tuple[int, int]:
#        """
#        Movimento lineare in XY da delta in steps (dx_steps, dy_steps) usando DDA/Bresenham sui motori L/R.
#        Ritorna (eff_dx_steps, eff_dy_steps) effettivamente eseguiti.
#        """
#        if not self._in_range():
#            return (0, 0)
#
#        # Protezioni minime: se stai andando verso finecorsa e sei già in contatto, fermati.
#        # (Non è homing: è solo safety)
#        if dx_steps < 0 and self._x_sensor.contact:
#            logger.warning("X sensor contact while moving negative X: stopping XY linear move")
#            return (0, 0)
#        if dy_steps < 0 and self._y_sensor.contact:
#            logger.warning("Y sensor contact while moving negative Y: stopping XY linear move")
#            return (0, 0)
#
#        # Trasformazione cartesiano -> motori
#        l_target = dx_steps - dy_steps
#        r_target = dx_steps + dy_steps
#
#        l_abs = abs(l_target)
#        r_abs = abs(r_target)
#        total = max(l_abs, r_abs)
#
#        if total == 0:
#            return (0, 0)
#
#        self._set_lr_directions(l_target, r_target)
#
#        # DDA: accumulatore per distribuire gli step in modo uniforme lungo il segmento
#        acc_l = 0
#        acc_r = 0
#
#        eff_l = 0
#        eff_r = 0
#
#        l_sign = 1 if l_target >= 0 else -1
#        r_sign = 1 if r_target >= 0 else -1
#
#        for _ in range(total):
#            # Safety range: se autoscaling è attivo, prova a non uscire
#            if self._autoscaling_done:
#                # stima del prossimo step cartesiano se facessimo un passo su L e/o R
#                # (non perfetta, ma evita di sfondare i limiti grossi)
#                next_l = eff_l + l_sign
#                next_r = eff_r + r_sign
#                next_x = (next_l + next_r) // 2
#                next_y = (next_l - next_r) // 2
#                # posizione stimata assoluta (in steps)
#                est_x = self._x_steps + next_x
#                est_y = self._y_steps + next_y
#                if est_x < 0 or est_y < 0:
#                    logger.error("Estimated negative XY range reached: stopping")
#                    break
#                if est_x > self._x_millimeters_to_steps(self._X) or est_y > self._y_millimeters_to_steps(self._Y):
#                    logger.error("Estimated XY max range reached: stopping")
#                    break
#
#            stepped_l = False
#            stepped_r = False
#
#            acc_l += l_abs
#            if acc_l >= total and l_abs > 0:
#                acc_l -= total
#                stepped_l = True
#
#            acc_r += r_abs
#            if acc_r >= total and r_abs > 0:
#                acc_r -= total
#                stepped_r = True
#
#            # Qui è cruciale: se devono steppare entrambi nello stesso “tick”, li pulsi assieme
#            if stepped_l and stepped_r:
#                self._l_motor.write_pulse(1)
#                self._r_motor.write_pulse(1)
#                sleep(velocity)
#                self._l_motor.write_pulse(0)
#                self._r_motor.write_pulse(0)
#                sleep(self._VELOCITY)
#                eff_l += l_sign
#                eff_r += r_sign
#            elif stepped_l:
#                self._pulse_motor(self._l_motor, velocity)
#                eff_l += l_sign
#            elif stepped_r:
#                self._pulse_motor(self._r_motor, velocity)
#                eff_r += r_sign
#            else:
#                # In teoria non dovrebbe succedere spesso, ma se succede mantieni il tempo
#                sleep(velocity)
#
#        # ritorno in cartesiano (delta)
#        eff_dx = (eff_l + eff_r) // 2
#        eff_dy = (eff_r - eff_l) // 2
#
#        self._x_steps += eff_dx
#        self._y_steps += eff_dy
#
#        logger.debug(f"x: position = {self._x_steps}, sensor = {self._x_sensor.contact}")
#        logger.debug(f"y: position = {self._y_steps}, sensor = {self._y_sensor.contact}")
#        logger.debug(f"z: position = {self._z_steps}, sensor = {self._z_sensor.contact}")
#
#        return (eff_dx, eff_dy)

    def _xy_linear_movement_steps(self, dx_steps: int, dy_steps: int, velocity: float) -> Tuple[int, int]:
        import math
        # Evitiamo calcoli inutili se non serve
        if dx_steps == 0 and dy_steps == 0: return (0, 0)
        if not self._in_range(): return (0, 0)

        l_target, r_target = dx_steps - dy_steps, dx_steps + dy_steps
        l_abs, r_abs = abs(l_target), abs(r_target)
        total = l_abs if l_abs > r_abs else r_abs
        
        self._set_lr_directions(l_target, r_target)

        # --- SETTAGGI VELOCITÀ AGGRESSIVI ---
        # Spingiamo la velocità di picco al 50% in più (0.5)
        target_delay = velocity * 0.5 
        # Partenza meno pigra per non perdere tempo
        start_delay = target_delay * 2.5
        # Rampa più corta ma intensa (500 passi)
        accel_steps = 500 if total > 1500 else total // 3

        # Cache delle costanti per risparmiare tempo nel loop
        diff_vel = start_delay - target_delay
        l_sign = 1 if l_target >= 0 else -1
        r_sign = 1 if r_target >= 0 else -1

        eff_l = eff_r = acc_l = acc_r = 0

        # Pre-referenziamo i metodi per guadagnare microsecondi
        write_l = self._l_motor.write_pulse
        write_r = self._r_motor.write_pulse

        for i in range(total):
            # RAMPA SEMPLIFICATA (Solo moltiplicazioni, niente potenze o coseni)
            if i < accel_steps:
                current_delay = start_delay - (diff_vel * (i / accel_steps))
            elif i > (total - accel_steps):
                current_delay = start_delay - (diff_vel * ((total - i) / accel_steps))
            else:
                current_delay = target_delay

            # LOGICA PASSO
            step_l = step_r = False
            acc_l += l_abs
            if acc_l >= total:
                acc_l -= total
                step_l = True
            acc_r += r_abs
            if acc_r >= total:
                acc_r -= total
                step_r = True

            # OUTPUT FISICO OTTIMIZZATO
            if step_l and step_r:
                write_l(1); write_r(1)
                sleep(current_delay)
                write_l(0); write_r(0)
                sleep(current_delay)
                eff_l += l_sign; eff_r += r_sign
            elif step_l:
                write_l(1); sleep(current_delay); write_l(0); sleep(current_delay)
                eff_l += l_sign
            elif step_r:
                write_r(1); sleep(current_delay); write_r(0); sleep(current_delay)
                eff_r += r_sign
            else:
                sleep(current_delay)

        self._x_steps += (eff_l + eff_r) // 2
        self._y_steps += (eff_r - eff_l) // 2
        return ((eff_l + eff_r) // 2, (eff_r - eff_l) // 2)

    @log_call
    def move_xy_diagonal_to(self, x_mm: int, y_mm: int, velocity: float = _VELOCITY) -> bool:
        """
        Movimento XY lineare (diagonale) verso una posizione ASSOLUTA (x_mm, y_mm) rispetto allo zero.
        """
        if not self._click_in_range(x_mm, y_mm):
            logger.error("Target XY out of range")
            return False

        target_x_steps = self._x_millimeters_to_steps(x_mm)
        target_y_steps = self._y_millimeters_to_steps(y_mm)

        dx = target_x_steps - self._x_steps
        dy = target_y_steps - self._y_steps

        self._xy_linear_movement_steps(dx, dy, velocity)
        return True


    def _y_movement (self, steps: Union[int, None], velocity: float) -> int:
        if self._in_range():
            self._r_motor.write_direction(not(self._clockwise_dir if steps > 0 else not self._clockwise_dir))
            self._l_motor.write_direction(not(not self._clockwise_dir if steps > 0 else self._clockwise_dir))
            eff_steps: int = 0
            while ((abs(steps) == numpy.inf) and (not self._y_sensor.contact)) or (abs(steps) != numpy.inf and abs(eff_steps) < abs(steps)):
                logger.debug(f"y contact: {self._y_sensor.contact}")
                self._l_motor.write_pulse(1)
                self._r_motor.write_pulse(1)
                sleep(velocity)
                self._l_motor.write_pulse(0)
                self._r_motor.write_pulse(0)
                sleep(self._VELOCITY)
                eff_steps += (1 if steps > 0 else -1)
            self._y_steps += eff_steps
            logger.debug(f"x: position = {self._x_steps}, sensor = {self._x_sensor.contact}")
            logger.debug(f"y: position = {self._y_steps}, sensor = {self._y_sensor.contact}")
            logger.debug(f"z: position = {self._z_steps}, sensor = {self._z_sensor.contact}")
        

    def _x_movement (self, steps: Union[int, float], velocity: float):
        if self._in_range():
            self._r_motor.write_direction(not self._clockwise_dir if steps > 0 else self._clockwise_dir)
            self._l_motor.write_direction(not self._clockwise_dir if steps > 0 else self._clockwise_dir)
            eff_steps: int = 0

            while (abs(eff_steps) < abs(steps)):
                logger.debug(f"x contact: {self._x_sensor.contact} - " + ("right" if self._x_left else "left"))
                if (abs(steps) == numpy.inf) and self._x_sensor.contact:
                    logger.debug(f"x contact: {self._x_sensor.contact} - " + ("right" if self._x_left else "left"))
                    if abs(eff_steps) < 500:
                        if (steps < 0 and self._x_left) or (steps > 0 and not self._x_left):
                            break
                    else:
                        self._x_left = not self._x_left
                        break

                self._l_motor.write_pulse(1)
                self._r_motor.write_pulse(1)
                sleep(velocity)
                self._l_motor.write_pulse(0)
                self._r_motor.write_pulse(0)
                sleep(self._VELOCITY)
                eff_steps += (1 if steps > 0 else -1)
            self._x_steps += eff_steps
            logger.debug(f"x: position = {self._x_steps}, sensor = {self._x_sensor.contact}")
            logger.debug(f"y: position = {self._y_steps}, sensor = {self._y_sensor.contact}")
            logger.debug(f"z: position = {self._z_steps}, sensor = {self._z_sensor.contact}")

            
    def _z_movement(self, steps: Union[int, None], velocity: float) -> bool:
        clicked: bool = self._button.pressed      #nel caso mi trovassi nella casistica in cui sto premendo, ma voglio fare un movimento indietro che è superiore al limite, la return notifica che il bottone è ancora premuto
        if self._in_range():
            self._z_motor.write_direction(not self._clockwise_dir if steps > 0 else self._clockwise_dir)
            eff_steps: int = 0
            while (abs(steps) != numpy.inf and abs(eff_steps) < abs(steps)) or (abs(steps) == numpy.inf):
                logger.debug(f"z contact: {self._z_sensor.contact}")
                if (self._z_sensor.contact) and (steps < 0):
                    logger.debug(f"z contact: {self._z_sensor.contact}")
                    break
                elif self._button.pressed and (steps > 0):
                    logger.info("Button pressed")
                    clicked = True
                    add_step = 200
                    for i in range(add_step):
                        i += 1
                        self._z_motor.write_pulse(1)
                        sleep(velocity*5)
                        self._z_motor.write_pulse(0)
                        sleep(self._VELOCITY)
                        eff_steps += add_step
                    break
                elif abs(eff_steps) >= self._MAX_Z_STEPS:
                    logger.warning("Button not clicked")
                    break
                self._z_motor.write_pulse(1)
                sleep(velocity)
                self._z_motor.write_pulse(0)
                sleep(self._VELOCITY)
                eff_steps += (1 if steps > 0 else -1)
            self._z_steps += eff_steps
            self._MAX_Z_STEPS = max(self._MAX_Z_STEPS, abs(self._z_steps))
            logger.debug(f"x: position = {self._x_steps}, sensor = {self._x_sensor.contact}")
            logger.debug(f"y: position = {self._y_steps}, sensor = {self._y_sensor.contact}")
            logger.debug(f"z: position = {self._z_steps}, sensor = {self._z_sensor.contact}")
            
        return clicked
            
    
    def _x_millimeters_to_steps(self, val: int)->int:
        return int((self._x_total_steps*val)/self._X) + self._X_OFFSET
        
    def _y_millimeters_to_steps(self, val: int)->int:
        return int((self._y_total_steps*val)/self._Y) + self._Y_OFFSET

    def _x_steps_to_millimeters(self, val: int)->int:
        return int((self._X*val)/self._x_total_steps) + self._X_OFFSET
        
    def _y_steps_to_millimeters(self, val: int)->int:
        return int((self._Y*val)/self._y_total_steps) + self._Y_OFFSET
    
    def _in_range(self)->bool:
        if not self._autoscaling_done:
            ret: bool = True
        else:
            ret: bool = ((self._x_steps <= self._x_millimeters_to_steps(self._X)) and \
                (self._y_steps <= self._y_millimeters_to_steps(self._Y)) and \
                (self._z_steps <= self._MAX_Z_STEPS))
            if not ret:
                logger.error(f"Error! motor out of range. Position in steps = ({self._x_steps}, {self._y_steps}, {self._z_steps}). Max = ({self._x_millimeters_to_steps(self._X)},{self._y_millimeters_to_steps(self._Y)},{self._MAX_Z_STEPS})")
        return ret


    
    def _z_click(self, time: float, velocity: float)->None:
        clicked = self._z_movement(numpy.inf, self._VELOCITY)
        if clicked:
            sleep(time)
        self._z_movement(-self._z_steps, self._VELOCITY)        
        

    def _click_in_range(self, x: int,y)->bool:
        return (x < self._X) and \
            (y < self._Y)
            
    @staticmethod
    def _make_picture_paths(path: str, n_pic: int) -> List[str]:
        i: int = 0
        while pathlib.Path(os.path.join(path, f"{i}.jpg")).exists():
            i += 1

        return [os.path.join(path, f"{i +  j}.jpg") for j in range(n_pic)]
    

    @log_call       
    def take_picture(self, n_camera: int, n_pic: int, total_time: int)->List[str]:
        total_time /= 1000 #ms
        if n_camera < len(self._cameras):
            pictures: List[str] = DmiRobot._make_picture_paths(DmiRobot._PICTURE_PATH, n_pic)
            for i in range(n_pic):
                self._cameras[n_camera].capture_file(pictures[i])
                logger.debug("Picture taken")
                time.sleep(total_time/n_pic)
        else:
            pictures: List[str] = []
        return pictures
              


    @log_call       
    def return_to_zero(self, velocity: float = _VELOCITY)-> bool:
        self._x_movement(-self._x_steps, velocity)
        self._y_movement(-self._y_steps, velocity)
        return True
    

    
#    @log_call       
#    def click(self, x: int,y: int, time: int, x_y_return_to_zero: bool = True, velocity: float = _VELOCITY)->bool:
#        time /= 1000 #ms
#        ret: bool = False
#        if self._click_in_range(x, y):
#            self._x_movement(self._x_millimeters_to_steps(x), velocity)
#            self._y_movement(self._y_millimeters_to_steps(y), velocity)
#            self._z_click(time, velocity)
#            ret = True
#            if x_y_return_to_zero:
#                self._x_movement(-self._x_millimeters_to_steps(x), velocity)
#                self._y_movement(-self._y_millimeters_to_steps(y), velocity)
#        else:
#            logger.error(f"Click out of range")
#        
#        return ret

    @log_call        
    def click(self, x: int, y: int, time_ms: int, x_y_return_to_zero: bool = False, velocity: float = _VELOCITY) -> bool:
        duration = time_ms / 1000.0 
        ret: bool = False

        if self._click_in_range(x, y):
            # 1. SICUREZZA: Assicuriamoci che la Z sia ritirata prima di partire
            if self._z_steps > 0:
                self._z_movement(-self._z_steps, velocity)

            # 2. MOVIMENTO ANDATA
            dx_steps = self._x_millimeters_to_steps(x) - self._x_steps
            dy_steps = self._y_millimeters_to_steps(y) - self._y_steps
            self._xy_linear_movement_steps(dx_steps, dy_steps, velocity)
            
            # 3. ESECUZIONE CLICK (z_click include già il ritorno della Z a 0)
            self._z_click(duration, velocity)
            ret = True
            
            # 4. MOVIMENTO RITORNO (Sempre con Z a zero grazie a z_click)
            if x_y_return_to_zero:
                back_dx = -self._x_steps
                back_dy = -self._y_steps
                self._xy_linear_movement_steps(back_dx, back_dy, velocity)
        else:
            logger.error(f"Click out of range: ({x}, {y})")
        
        return ret

#    @log_call       
#    def live_movement(self, x: int, y: int, z: int, velocity: float = _VELOCITY)->bool:
#        ret: bool = False
#        if self._click_in_range(x, y):
#            self._x_movement(self._x_millimeters_to_steps(x), velocity)
#            self._y_movement(self._y_millimeters_to_steps(y), velocity)
#            self._z_movement(self._y_millimeters_to_steps(z), velocity)
#            ret = True
#        else:
#            logger.error(f"Click out of range")
#        return ret

    @log_call        
    def live_movement(self, x: int, y: int, z: int, velocity: float = _VELOCITY) -> bool:
        ret: bool = False
        if self._click_in_range(x, y):
            # 1. SICUREZZA: Se la Z attuale non è a zero, la ritiriamo prima di muovere XY
            if self._z_steps > 0:
                logger.info("Safety: Retracting Z before XY movement")
                # Muoviamo la Z a 0 (negativo rispetto alla posizione attuale)
                self._z_movement(-self._z_steps, velocity)

            # 2. MOVIMENTO DIAGONALE COORDINATO
            dx_steps = self._x_millimeters_to_steps(x) - self._x_steps
            dy_steps = self._y_millimeters_to_steps(y) - self._y_steps
            self._xy_linear_movement_steps(dx_steps, dy_steps, velocity)

            # 3. MOVIMENTO ASSE Z ALLA POSIZIONE FINALE
            # Se il comando richiede una Z specifica (es. restare abbassati), lo facciamo ora
            target_z_steps = self._y_millimeters_to_steps(z) 
            dz_steps = target_z_steps - self._z_steps
            if dz_steps != 0:
                self._z_movement(dz_steps, velocity)

            ret = True
        else:
            logger.error(f"Click out of range: {x}, {y}")
        return ret
            
    @log_call       
    def initialize_hardware(self)->None:
        if not self._autoscaling_done:
            y_start: int = 20
            # Mi salvo le posizioni correnti ora per utilizzarle dopo ai fini del movimento verso il fine-corsa massimo
            self._y_movement(y_start, self._VELOCITY)
            self._z_movement(-numpy.inf, self._VELOCITY)
            self._x_movement(-numpy.inf, self._VELOCITY)
            self._x_steps = 0
            self._y_steps = y_start
            self._z_steps = 0

            self._y_movement(numpy.inf, self._VELOCITY)
            self._y_total_steps = self._y_steps
            
            self._x_movement(numpy.inf, self._VELOCITY)
            self._x_total_steps = self._x_steps  

            self._y_movement(-self._y_total_steps, self._VELOCITY)

            self._x_movement(-self._x_total_steps, self._VELOCITY)
            self._autoscaling_done = True
            #for i in range(len(self._cameras)):
            #    self._cameras[i] = Picamera2(camera_num=i)
            #    self._cameras[i].configure(self._cameras[i].create_still_configuration(main={"size": (self._CAMERA_WIDTH, self._CAMERA_HEIGHT)}))
            #    self._cameras[i].start()
            #Picamera2.set_logging(4)
        return True


            
import time
import socket
import struct

LIVE_MOVEMENT_MSG_OUT = 40    
CLICK_MSG_OUT = 50
PICTURE_MSG_OUT = 60
DONE_MSG_IN = 70

#def send_message(sock: socket.socket, ip, port, msg_type, *args):
    #msg = [msg_type]
    #msg.extend(list(args))
    #msg = bytes(msg)
    #sock.sendto(msg, (ip, port))
    #print(f"Sent: {msg}")"

#def receive_message(sock: socket.socket):
    #try:
        #data, addr = sock.recvfrom(1024)
        #data = list(data)
        #print(f"Received {addr}: {data}")
    #except:
        #data = []
    #return data

def send_message(sock, ip_dst, port_dst, msg_type, *args):
    args = list(args) + [0] * (3 - len(args))
    packed_data = struct.pack('>Bhhh', msg_type, *args[:3])
    sock.sendto(packed_data, (ip_dst, port_dst))
    print(f"Sent: msg_type={msg_type}, args={args[:3]}")

def receive_message(sock):
    try:
        data, addr = sock.recvfrom(1024)
        if not data:
            return []
        msg_type, x, y, z = struct.unpack('>Bhhh', data[:7])
        msg = [msg_type, x, y, z]
        print(f"Received {msg} from {addr}")
        return msg
    except BlockingIOError:
        return []
    except Exception as e:
        print(f"Receive error: {e}")
        return []
                  
def open_socket(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    sock.setblocking(False)
    return sock
            
if "__main__" == __name__:
    from dmi_robot_common.Logger import setup_logging, logger
    cfg_path: str = os.path.join(pathlib.Path(__file__).parent, "raspberry_cfg.yaml")
    cfg: YamlCfg = YamlCfg(cfg_path)
    setup_logging(cfg.log_level, pathlib.Path(__file__).stem)
    cfg_path: str = os.path.join(pathlib.Path(__file__).parent,"raspberry_cfg.yaml")
    cfg: YamlCfg = YamlCfg(cfg_path)
            
    #m: DmiRobot = DmiRobot(cfg)
    m = DmiRobot(cfg)
    #while 1:
    #    a = input("insert:\t")
    #    if a == "w":
    #        m._x_movement(3000, m._VELOCITY)
    #    elif a == "q":
    #        m._x_movement(-3000, m._VELOCITY)
    #    elif a == "e":
    #        m._y_movement(3000, m._VELOCITY)
    #    elif a == "d":
    #        m._y_movement(-3000, m._VELOCITY)
    #    elif a == "z":
    #        m._z_movement(3000, m._VELOCITY)
    #    elif a == "x":
    #        m._z_movement(-3000, m._VELOCITY)
    #    elif a == "p":
    #        m.initialize_hardware()
    #    elif a == "pd":
    #        m.click(0,0,1)
    #    elif a == "dm":
    #        dx = 2000
    #        dy = 2000
    #        m._xy_linear_movement_steps(dx, dy, m._VELOCITY)
    #
    #    logger.info(f"x: position = {m._x_steps}, sensor = {m._x_sensor.contact}")
    #    logger.info(f"y: position = {m._y_steps}, sensor = {m._y_sensor.contact}")
    #    logger.info(f"z: position = {m._z_steps}, sensor = {m._z_sensor.contact}")
    #
    #exit(0)
    #inp = input("a")
    #m.click()
    #exit(0)
    
    IP_SRC = "192.168.1.210"
    PORT_SRC = 2000
    IP_DST = "192.168.1.133"
    PORT_DST = 50
    sock = open_socket(IP_SRC, PORT_SRC)
    while True:
        msg = receive_message(sock)
        if len(msg) == 0:
            time.sleep(0.1)
            continue

        msg_type = msg[0]

        if msg_type == LIVE_MOVEMENT_MSG_OUT:
            x, y, z = msg[1:4]
            print(f"Live movement: x={x}, y={y}, z={z}")
            m.live_movement(x, y, z)
            send_message(sock, IP_DST, PORT_DST, DONE_MSG_IN)
        
        elif msg_type == CLICK_MSG_OUT:
            print(f"Click: {msg[1:4]}")
            m.click(*msg[1:4])
            send_message(sock, IP_DST, PORT_DST, DONE_MSG_IN)

        elif msg_type == PICTURE_MSG_OUT:
            print("Take picture")
            m.take_picture(os.path.join(pathlib.Path(__file__).parent,f"tmp{msg[1]}.jpg"), *msg[1::])
            time.sleep(0.1)
            send_message(sock, IP_DST, PORT_DST, DONE_MSG_IN)

        else:
            print(f"Unknown message type: {msg}")


            #if CLICK_MSG_OUT == msg[0]:
                #print(f"DMI click {msg}")
                #m.click(*msg[1:4])
                #send_message(sock, IP_DST, PORT_DST, DONE_MSG_IN)
            #elif PICTURE_MSG_OUT == msg[0]:
                #print(f"Take picture {msg}")
                #m.take_picture(os.path.join(pathlib.Path(__file__).parent,f"tmp{msg[1]}.jpg"), *msg[1::])
                #time.sleep(0.1)
                #send_message(sock, IP_DST, PORT_DST, DONE_MSG_IN)
            #elif LIVE_MOVEMENT_MSG_OUT == msg[0]:
                #print(f"DMI live movement {msg}")
                #m.live_movement(*msg[1:4])
                #send_message(sock, IP_DST, PORT_DST, DONE_MSG_IN)     
            #else:
                #print(f"Error, msg unknown type: {msg[0]}")
        #time.sleep(0.1)
    
    
    
    if "live" in inp:
        while True:
            movement = input("define movement coordinates -> x,y,z : ")
            movement.split(",")
            if len(movement) == 3:
                m.live_movement(movement[0] , movement[1], movement[2])
            
    m.click(200,400,0.1)
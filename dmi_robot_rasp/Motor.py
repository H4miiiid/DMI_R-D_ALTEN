from typing import Union, Any
from dmi_robot_rasp.GpioElement import GpioElement

class Motor(GpioElement):

    def __init__(self, enable: int, direction: int, pulse: int)->None:
        super().__init__()
        self._enable: int = enable
        self._direction: int = direction
        self._pulse: int = pulse
        self.configure_output(direction)
        self.configure_output(pulse)
        self.configure_output(enable)
        
    def write_direction(self, val: Any)->None:
        self.write(self._direction, val)
            
    def write_pulse(self, val: Any)->None:
        self.write(self._pulse, val)
        
    def write_enable(self, val:  Any)->None:
        self.write(self._enable, val)
        
    enable: Union[int, None] = property(lambda self: self._enable, None, None)
    direction: Union[int, None] = property(lambda self: self._direction, None, None)
    pulse: Union[int, None] = property(lambda self: self._pulse, None, None)
 
import lgpio
from typing import  Any


class GpioElement:
    _gpio_handle = None

    def __init__(self)->None:
        if GpioElement._gpio_handle is None:
            GpioElement._gpio_handle = lgpio.gpiochip_open(0)
        self._gpio_handle = GpioElement._gpio_handle
        
    def configure_output(self, pin: int)->None:
        lgpio.gpio_claim_output(self._gpio_handle, pin)
        
    def configure_input(self, pin: int)->None:
        lgpio.gpio_claim_input(self._gpio_handle, pin)
        
    def close(self)->None:
        lgpio.gpiochip_close(self._gpio_handle)
        
    def write(self, pin: int, val: Any)->None:
        lgpio.gpio_write(self._gpio_handle, pin, int(val))
        
    def read(self, pin: int)->int:
        return int(lgpio.gpio_read(self._gpio_handle, pin))

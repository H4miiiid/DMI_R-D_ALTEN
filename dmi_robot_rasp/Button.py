from dmi_robot_rasp.GpioElement import GpioElement



class Button(GpioElement):
    def __init__(self, pin: int)->None:
        super().__init__()
        self._pin: int = pin
        self.configure_input(pin)

    def _get_pressed(self)->bool:
        N: int = 15
        return all([self.read(self._pin) for _ in range(N)])
        
    pressed: bool = property(_get_pressed, None, None)   

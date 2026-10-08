from dmi_robot_rasp.GpioElement import GpioElement

        

class InductionSensor(GpioElement):
    
    def __init__(self, pin: int, n: int = 1)->None:
        if n < 1:
            raise Exception(f"Invalid n: {n}")
        super().__init__()
        self._pin: int = pin
        self.configure_input(pin)
        self._N: int = n

    
    def _get_contact(self)->bool:
        return (all([self.read(self._pin) for _ in range(self._N)])  if 1 == self.read(self._pin) else False)

    contact: bool = property(_get_contact, None, None)
    #contact: bool = property(lambda self: 1 == self.read(self._pin), None, None)





    

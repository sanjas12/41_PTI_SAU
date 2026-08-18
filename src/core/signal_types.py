from enum import Enum, auto


class SignalType(Enum):
    SINE = auto()
    SQUARE = auto()
    SAWTOOTH = auto()
    TRIANGLE = auto()
    RANDOM = auto()
    CUSTOM = auto()
    
    def __str__(self):
        return self.name.capitalize()
    
    @staticmethod
    def get_names():
        return [st.name.capitalize() for st in SignalType]
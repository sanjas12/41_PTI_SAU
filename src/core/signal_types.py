from enum import Enum, auto


class SignalType(Enum):
    """Типы сигналов"""

    # Аналоговые
    SINE = auto()
    SQUARE = auto()
    SAWTOOTH = auto()
    TRIANGLE = auto()
    RANDOM = auto()
    CUSTOM = auto()

    # Дискретные
    DISCRETE = auto()  # Простой дискретный (0/1)
    PULSE = auto()  # Импульсный
    PWM = auto()  # ШИМ (с изменяемой скважностью)
    STEP = auto()  # Ступенчатый
    TOGGLE = auto()  # Переключающийся

    def __str__(self):
        names = {
            "SINE": "Синус",
            "SQUARE": "Меандр",
            "SAWTOOTH": "Пилообразный",
            "TRIANGLE": "Треугольный",
            "RANDOM": "Случайный",
            "CUSTOM": "Пользовательский",
            "DISCRETE": "Дискретный (0/1)",
            "PULSE": "Импульсный",
            "PWM": "ШИМ",
            "STEP": "Ступенчатый",
            "TOGGLE": "Переключающийся",
        }
        return names.get(self.name, self.name.capitalize())

    def is_analog(self) -> bool:
        """Проверить, является ли сигнал аналоговым"""
        return self in [
            SignalType.SINE,
            SignalType.SQUARE,
            SignalType.SAWTOOTH,
            SignalType.TRIANGLE,
            SignalType.RANDOM,
            SignalType.CUSTOM,
        ]

    def is_discrete(self) -> bool:
        """Проверить, является ли сигнал дискретным"""
        return self in [
            SignalType.DISCRETE,
            SignalType.PULSE,
            SignalType.PWM,
            SignalType.STEP,
            SignalType.TOGGLE,
        ]

    @staticmethod
    def get_analog_types():
        """Получить список аналоговых типов"""
        return [
            SignalType.SINE,
            SignalType.SQUARE,
            SignalType.SAWTOOTH,
            SignalType.TRIANGLE,
            SignalType.RANDOM,
            SignalType.CUSTOM,
        ]

    @staticmethod
    def get_discrete_types():
        """Получить список дискретных типов"""
        return [
            SignalType.DISCRETE,
            SignalType.PULSE,
            SignalType.PWM,
            SignalType.STEP,
            SignalType.TOGGLE,
        ]

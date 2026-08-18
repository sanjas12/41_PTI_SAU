import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ScenarioStep:
    """Шаг сценария"""
    channel_id: int
    signal_type: str  # Название типа сигнала
    amplitude: float = 50.0
    frequency: float = 1.0
    offset: float = 0.0
    duration: float = 5.0  # Длительность в секундах
    ramp_up: float = 0.0    # Время нарастания (сек)
    ramp_down: float = 0.0  # Время затухания (сек)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'channel_id': self.channel_id,
            'signal_type': self.signal_type,
            'amplitude': self.amplitude,
            'frequency': self.frequency,
            'offset': self.offset,
            'duration': self.duration,
            'ramp_up': self.ramp_up,
            'ramp_down': self.ramp_down
        }
    
    @classmethod
    def from_dict(cls, data: Dict[Any, Any]) -> 'ScenarioStep':
        return cls(
            channel_id=data['channel_id'],
            signal_type=data['signal_type'],
            amplitude=data.get('amplitude', 50.0),
            frequency=data.get('frequency', 1.0),
            offset=data.get('offset', 0.0),
            duration=data.get('duration', 5.0),
            ramp_up=data.get('ramp_up', 0.0),
            ramp_down=data.get('ramp_down', 0.0)
        )


@dataclass
class Scenario:
    """Сценарий проигрывания сигналов"""
    name: str = "Новый сценарий"
    steps: List[ScenarioStep] = field(default_factory=list)
    loop: bool = False
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'version': self.version,
            'loop': self.loop,
            'steps': [step.to_dict() for step in self.steps]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[Any, Any]) -> 'Scenario':
        steps = [ScenarioStep.from_dict(s) for s in data.get('steps', [])]
        return cls(
            name=data.get('name', 'Новый сценарий'),
            steps=steps,
            loop=data.get('loop', False),
            version=data.get('version', '1.0')
        )
    
    def get_total_duration(self) -> float:
        """Получить общую длительность сценария"""
        return sum(step.duration for step in self.steps)
    
    def save_to_file(self, filepath: str):
        """Сохранить сценарий в JSON файл"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'Scenario':
        """Загрузить сценарий из JSON файла"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
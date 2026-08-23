import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

TRIGGER_ANY = "any"
TRIGGER_ALL = "all"
TRIGGER_SPECIFIC = "specific"
VALID_TRIGGER_MODES = {TRIGGER_ANY, TRIGGER_ALL, TRIGGER_SPECIFIC}


@dataclass
class ScenarioStep:
    """Операция сценария и её расположение на графическом поле."""

    channel_id: int
    signal_type: str
    amplitude: float = 50.0
    frequency: float = 1.0
    offset: float = 0.0
    duration: float = 5.0
    ramp_up: float = 0.0
    ramp_down: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    position_x: float = 0.0
    position_y: float = 0.0
    trigger_mode: str = TRIGGER_ALL
    trigger_step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "signal_type": self.signal_type,
            "amplitude": self.amplitude,
            "frequency": self.frequency,
            "offset": self.offset,
            "duration": self.duration,
            "ramp_up": self.ramp_up,
            "ramp_down": self.ramp_down,
            "position": [self.position_x, self.position_y],
            "trigger_mode": self.trigger_mode,
            "trigger_step_id": self.trigger_step_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[Any, Any]) -> "ScenarioStep":
        position = data.get("position", [0.0, 0.0])
        trigger_mode = data.get("trigger_mode", TRIGGER_ALL)
        if trigger_mode not in VALID_TRIGGER_MODES:
            trigger_mode = TRIGGER_ALL
        return cls(
            id=str(data.get("id") or uuid4().hex),
            channel_id=int(data["channel_id"]),
            signal_type=str(data["signal_type"]),
            amplitude=float(data.get("amplitude", 50.0)),
            frequency=float(data.get("frequency", 1.0)),
            offset=float(data.get("offset", 0.0)),
            duration=float(data.get("duration", 5.0)),
            ramp_up=float(data.get("ramp_up", 0.0)),
            ramp_down=float(data.get("ramp_down", 0.0)),
            position_x=float(position[0]),
            position_y=float(position[1]),
            trigger_mode=trigger_mode,
            trigger_step_id=data.get("trigger_step_id"),
        )


@dataclass(frozen=True)
class ScenarioConnection:
    """Направленная связь: target запускается после source."""

    source_id: str
    target_id: str

    def to_dict(self) -> Dict[str, str]:
        return {"source_id": self.source_id, "target_id": self.target_id}

    @classmethod
    def from_dict(cls, data: Dict[Any, Any]) -> "ScenarioConnection":
        return cls(source_id=str(data["source_id"]), target_id=str(data["target_id"]))


@dataclass
class Scenario:
    """Ориентированный граф операций сценария."""

    name: str = "Новый сценарий"
    steps: List[ScenarioStep] = field(default_factory=list)
    connections: List[ScenarioConnection] = field(default_factory=list)
    loop: bool = False
    version: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "loop": self.loop,
            "steps": [step.to_dict() for step in self.steps],
            "connections": [connection.to_dict() for connection in self.connections],
        }

    @classmethod
    def from_dict(cls, data: Dict[Any, Any]) -> "Scenario":
        steps = [ScenarioStep.from_dict(item) for item in data.get("steps", [])]
        raw_connections = data.get("connections")
        if raw_connections is None:
            connections = [
                ScenarioConnection(previous.id, current.id)
                for previous, current in zip(steps, steps[1:])
            ]
            for index, step in enumerate(steps):
                step.position_x = float(index * 240)
                step.position_y = 40.0
        else:
            connections = [
                ScenarioConnection.from_dict(item) for item in raw_connections
            ]
            known_ids = {step.id for step in steps}
            connections = [
                connection
                for connection in connections
                if connection.source_id in known_ids
                and connection.target_id in known_ids
            ]
        return cls(
            name=data.get("name", "Новый сценарий"),
            steps=steps,
            connections=connections,
            loop=bool(data.get("loop", False)),
            version="2.0",
        )

    def incoming_ids(self, step_id: str) -> Set[str]:
        return {
            connection.source_id
            for connection in self.connections
            if connection.target_id == step_id
        }

    def add_connection(self, source_id: str, target_id: str) -> None:
        connection = ScenarioConnection(source_id, target_id)
        known_ids = {step.id for step in self.steps}
        if source_id not in known_ids or target_id not in known_ids:
            raise ValueError("Связь ссылается на отсутствующий шаг")
        if source_id == target_id:
            raise ValueError("Шаг нельзя соединить с самим собой")
        if connection in self.connections:
            return
        if self._has_path(target_id, source_id):
            raise ValueError("Связь создаёт цикл")
        self.connections.append(connection)

    def remove_step(self, step_id: str) -> None:
        self.steps = [step for step in self.steps if step.id != step_id]
        self.connections = [
            connection
            for connection in self.connections
            if step_id not in (connection.source_id, connection.target_id)
        ]

    def _has_path(self, source_id: str, target_id: str) -> bool:
        pending = [source_id]
        visited: Set[str] = set()
        while pending:
            current = pending.pop()
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(
                connection.target_id
                for connection in self.connections
                if connection.source_id == current
            )
        return False

    def get_total_duration(self) -> float:
        """Оценить длительность; точное значение зависит от условий ветвления."""
        return sum(step.duration for step in self.steps)

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> "Scenario":
        with open(filepath, encoding="utf-8") as file:
            data = json.load(file)
        return cls.from_dict(data)

from typing import Iterator

import pytest
from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from scenario.scenario_model import ScenarioStep
from scenario.scenario_widget import StepEditDialog


@pytest.fixture
def app() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


@pytest.mark.parametrize(
    "device,address", [("owen", 3004), ("plc", 6), ("simulator", 0)]
)
def test_new_step_inherits_channel_assignment(
    app: QApplication, device: str, address: int
) -> None:
    channel = AnalogChannel(
        id=0,
        name="channel",
        output_device=device,
        output_address=address,
        mu210_module=2,
    )
    dialog = StepEditDialog(SignalGenerator([channel]))
    try:
        step = dialog.get_step()
        assert (step.output_device, step.output_address) == (device, address)
        if device == "owen":
            assert (step.mu210_module, step.mu210_register) == (2, address)
    finally:
        dialog.close()


def test_switching_channel_updates_assignment(app: QApplication) -> None:
    generator = SignalGenerator(
        [
            AnalogChannel(id=0, name="first"),
            AnalogChannel(id=1, name="second", output_device="plc", output_address=8),
        ]
    )
    dialog = StepEditDialog(generator)
    try:
        dialog.channel_combo.setCurrentIndex(1)
        step = dialog.get_step()
        assert (step.channel_id, step.output_device, step.output_address) == (
            1,
            "plc",
            8,
        )
        assert dialog.mu210_module_spin.isHidden()
    finally:
        dialog.close()


@pytest.mark.parametrize("signal_type", ["Sine", "Pwm"])
def test_existing_step_preserves_assignment_and_metadata(
    app: QApplication, signal_type: str
) -> None:
    original = ScenarioStep(
        channel_id=0,
        signal_type=signal_type,
        output_device="plc",
        output_address=6,
        position_x=123.0,
    )
    dialog = StepEditDialog(
        SignalGenerator([AnalogChannel(id=0, name="channel")]), step=original
    )
    try:
        edited = dialog.get_step()
        assert edited.output_device == original.output_device
        assert edited.output_address == original.output_address
        assert edited.id == original.id
        assert edited.position_x == original.position_x
        assert ScenarioStep.from_dict(edited.to_dict()).output_address == 6
    finally:
        dialog.close()


def test_device_switch_and_discrete_visibility(app: QApplication) -> None:
    dialog = StepEditDialog(SignalGenerator([AnalogChannel(id=0, name="channel")]))
    try:
        dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("plc"))
        assert dialog.output_address_combo.count() == 20
        assert dialog.mu210_module_spin.isHidden()
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("Pwm"))
        assert not dialog.device_combo.isHidden()
        assert not dialog.device_label.isHidden()
        assert not dialog.discrete_group.isHidden()
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("Sine"))
        assert not dialog.device_combo.isHidden()
        assert dialog.discrete_group.isHidden()
        dialog.device_combo.setCurrentIndex(dialog.device_combo.findData("owen"))
        dialog.output_address_combo.setCurrentIndex(7)
        step = dialog.get_step()
        assert step.output_address == step.mu210_register == 3007
        assert SignalType[step.signal_type.upper()].is_analog()
    finally:
        dialog.close()

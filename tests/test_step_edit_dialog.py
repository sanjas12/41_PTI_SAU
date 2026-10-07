from typing import Iterator

import pytest
from PyQt5.QtWidgets import QApplication

from core.channel import AnalogChannel
from core.signal_generator import SignalGenerator
from core.signal_types import SignalType
from scenario.scenario_engine import ScenarioEngine
from scenario.scenario_model import Scenario, ScenarioStep
from scenario.scenario_widget import StepEditDialog
from ui.channel_widget import ChannelSettingsDialog


@pytest.fixture
def app() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


def test_constant_channel_settings_offer_fixed_value(app: QApplication) -> None:
    channel = AnalogChannel(
        id=0, name="constant", signal_type=SignalType.CUSTOM, constant_value=27.5
    )
    dialog = ChannelSettingsDialog(channel)
    try:
        assert dialog.type_combo.currentText() == "Постоянный"
        assert not dialog.constant_spin.isHidden()
        assert dialog.freq_spin.isHidden()
        assert dialog.amp_spin.isHidden()
        assert dialog.offset_spin.isHidden()
        dialog.constant_spin.setValue(42.0)
        assert dialog.get_settings()["constant_value"] == 42.0
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("SINE"))
        assert dialog.constant_spin.isHidden()
        assert not dialog.freq_spin.isHidden()
    finally:
        dialog.close()


@pytest.mark.parametrize("graph", [False, True])
def test_constant_step_roundtrip_and_restore(app: QApplication, graph: bool) -> None:
    channel = AnalogChannel(id=0, name="channel", constant_value=12.0)
    generator = SignalGenerator([channel])
    step = ScenarioStep(channel_id=0, signal_type="Custom", constant_value=42.0)
    dialog = StepEditDialog(generator, step=step)
    try:
        assert dialog.type_combo.currentText() == "Постоянный"
        assert not dialog.constant_spin.isHidden()
        assert dialog.freq_spin.isHidden()
        edited = ScenarioStep.from_dict(dialog.get_step().to_dict())
        assert edited.constant_value == 42.0
        engine = ScenarioEngine(generator)
        engine.scenario = Scenario(name="constant", steps=[edited])
        engine._save_channel_configs()
        if graph:
            engine._apply_graph_step(edited)
        else:
            engine._apply_step(0)
        assert channel.constant_value == 42.0
        engine._restore_channel_configs()
        assert channel.constant_value == 12.0
    finally:
        dialog.close()


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

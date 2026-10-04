from pathlib import Path

import pytest
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QApplication

from ui.connection_dialog import ConnectionDialog
from ui.connection_panel import ConnectionPanel
from ui.themes import build_stylesheet


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("large", [False, True])
def test_connection_dialog_actions_fit_and_use_shared_theme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, theme: str, large: bool
) -> None:
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet()
    monkeypatch.setattr(
        ConnectionPanel,
        "_get_config_path",
        lambda self: str(tmp_path / "connections.json"),
    )
    app.setStyleSheet(build_stylesheet(theme, large=large))
    dialog = ConnectionDialog()
    try:
        dialog.show()
        app.processEvents()
        panel = dialog.connection_panel
        buttons = [
            panel.connect_btn,
            panel.disconnect_btn,
            panel.save_btn,
            panel.delete_btn,
            dialog.close_btn,
        ]
        rectangles = []
        for button in buttons:
            assert button.isVisible()
            assert button.width() >= button.minimumSizeHint().width()
            assert button.height() >= button.minimumSizeHint().height()
            assert not button.styleSheet()
            rect = button.rect()
            rect.moveTopLeft(button.mapTo(dialog, QPoint(0, 0)))
            assert dialog.rect().contains(rect)
            assert all(not rect.intersects(other) for other in rectangles)
            rectangles.append(rect)
        assert not panel.styleSheet()
        assert not panel.isCheckable()
        assert panel.connect_btn.isEnabled()
        assert not panel.disconnect_btn.isEnabled()
        dialog.set_connection_status(True)
        assert not panel.connect_btn.isEnabled()
        assert panel.disconnect_btn.isEnabled()
        dialog.set_connection_status(False)
        assert panel.connect_btn.isEnabled()
        assert not panel.disconnect_btn.isEnabled()
    finally:
        dialog.close()
        app.setStyleSheet(previous_style)
        app.processEvents()

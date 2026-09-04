from PyQt5.QtWidgets import QApplication

from ui.connection_panel import ConnectionPanel


def test_connection_panel_offers_all_supported_device_types(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    config_path = tmp_path / "connections.json"
    monkeypatch.setattr(
        ConnectionPanel, "_get_config_path", lambda _self: str(config_path)
    )

    panel = ConnectionPanel()

    device_types = [
        panel.device_combo.itemData(index)
        for index in range(panel.device_combo.count())
    ]
    assert device_types == ["plc", "simulator", "owen"]

    panel.device_combo.setCurrentIndex(panel.device_combo.findData("simulator"))
    params = panel.get_connection_params()
    assert params["device_type"] == "simulator"
    assert params["host"] == "127.0.0.1"

    panel.device_combo.setCurrentIndex(panel.device_combo.findData("owen"))
    panel.ip_edit.setText("192.168.1.99, 192.168.1.100")
    assert panel.get_connection_params()["host"] == ("192.168.1.99, 192.168.1.100")

    panel.close()
    app.processEvents()

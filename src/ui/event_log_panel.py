"""Встроенная панель журнала событий главного окна."""

import html
from datetime import datetime
from typing import Dict, List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class EventLogPanel(QGroupBox):
    """Компактный потокобезопасный журнал, встроенный в главное окно."""

    log_requested = pyqtSignal(str, str)
    MAX_ENTRIES = 2000

    LEVEL_NAMES = {
        "Все": None,
        "Информация": "info",
        "Успех": "success",
        "Предупреждение": "warning",
        "Ошибка": "error",
        "Отладка": "debug",
    }
    LEVEL_COLORS = {
        "info": "#34495e",
        "success": "#2f7d4a",
        "warning": "#a56616",
        "error": "#b23a3a",
        "debug": "#66727d",
    }
    LEVEL_PREFIXES = {
        "info": "INFO",
        "success": "OK",
        "warning": "WARN",
        "error": "ERROR",
        "debug": "DEBUG",
    }

    def __init__(self, parent=None):
        super().__init__("Журнал событий", parent)
        self._entries: List[Dict[str, str]] = []
        self._setup_ui()
        self.log_requested.connect(self._append_entry)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.LEVEL_NAMES.keys())
        self.filter_combo.currentTextChanged.connect(self._refresh)
        toolbar.addWidget(self.filter_combo)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_button)

        toolbar.addStretch()
        self.count_label = QLabel("0 сообщений")
        self.count_label.setObjectName("secondaryText")
        toolbar.addWidget(self.count_label)
        layout.addLayout(toolbar)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("eventLog")
        self.text_edit.setPlaceholderText("События приложения появятся здесь")
        layout.addWidget(self.text_edit, 1)

    def log(self, message: str, level: str = "info") -> None:
        """Добавить сообщение через Qt-сигнал, безопасный для фоновых задач."""
        self.log_requested.emit(str(message), level)

    def clear(self) -> None:
        self._entries.clear()
        self._refresh()

    def _append_entry(self, message: str, level: str) -> None:
        normalized_level = level if level in self.LEVEL_COLORS else "info"
        self._entries.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": normalized_level,
                "message": message,
            }
        )
        if len(self._entries) > self.MAX_ENTRIES:
            del self._entries[: len(self._entries) - self.MAX_ENTRIES]
        self._refresh()

    def _refresh(self) -> None:
        selected_level = self.LEVEL_NAMES.get(self.filter_combo.currentText())
        visible_entries = [
            entry
            for entry in self._entries
            if selected_level is None or entry["level"] == selected_level
        ]

        rows = []
        for entry in visible_entries:
            level = entry["level"]
            color = self.LEVEL_COLORS[level]
            prefix = self.LEVEL_PREFIXES[level]
            rows.append(
                f'<span style="color:#7b8791">{entry["time"]}</span> '
                f'<span style="color:{color};font-weight:600">[{prefix}]</span> '
                f'<span style="color:{color}">{html.escape(entry["message"])}</span>'
            )

        self.text_edit.setHtml("<br>".join(rows))
        self.text_edit.moveCursor(QTextCursor.End)
        self.count_label.setText(f"{len(self._entries)} сообщений")

"""Единая светлая промышленная тема приложения."""

import config.config as cfg

COLORS = {
    "canvas": "#eef1f4",
    "surface": "#ffffff",
    "surface_alt": "#f7f8fa",
    "border": "#c7ced6",
    "border_strong": "#9da8b3",
    "text": "#1f2933",
    "muted": "#66727d",
    "primary": "#246b8f",
    "primary_hover": "#1d5a78",
    "primary_soft": "#e5f1f7",
    "success": "#2f7d4a",
    "warning": "#a56616",
    "danger": "#b23a3a",
    "disabled": "#aab2ba",
}


def app_stylesheet() -> str:
    """Вернуть глобальную QSS-тему для компактного инженерного интерфейса."""
    color = COLORS
    return f"""
        * {{
            font-family: {cfg.FONT_FAMILY};
            font-size: {cfg.FONT_SIZE}pt;
            color: {color["text"]};
        }}
        QMainWindow, QDialog {{ background-color: {color["canvas"]}; }}
        QWidget {{
            selection-background-color: {color["primary"]};
            selection-color: white;
        }}
        QLabel {{ background-color: transparent; }}
        QGroupBox {{
            background-color: {color["surface"]};
            border: 1px solid {color["border"]};
            border-radius: 3px;
            font-weight: 600;
            margin-top: 10px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {color["text"]};
            background-color: {color["surface"]};
        }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            min-height: 24px;
            padding: 2px 6px;
            background-color: {color["surface"]};
            border: 1px solid {color["border_strong"]};
            border-radius: 2px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
        QDoubleSpinBox:focus {{ border-color: {color["primary"]}; }}
        QPushButton {{
            min-height: 26px;
            padding: 3px 10px;
            background-color: {color["surface_alt"]};
            border: 1px solid {color["border_strong"]};
            border-radius: 2px;
        }}
        QPushButton:hover {{
            background-color: {color["primary_soft"]};
            border-color: {color["primary"]};
        }}
        QPushButton:pressed {{ background-color: #d7e8f1; }}
        QPushButton:disabled {{
            color: {color["disabled"]};
            background-color: #eceff1;
            border-color: #d7dce1;
        }}
        QPushButton#modeButton {{
            min-width: 110px;
            border-radius: 0;
            font-weight: 600;
            color: {color["primary"]};
        }}
        QPushButton#modeButton:checked {{
            color: white;
            background-color: {color["primary"]};
            border-color: {color["primary"]};
        }}
        QFrame#channelCard {{
            background-color: {color["surface"]};
            border: 1px solid {color["border"]};
            border-radius: 3px;
        }}
        QFrame#channelCard:hover {{
            background-color: {color["primary_soft"]};
            border-color: {color["primary"]};
        }}
        QLabel#channelName, QLabel#channelValue {{
            color: {color["primary"]};
            font-weight: 600;
        }}
        QLabel#channelBound, QLabel#secondaryText {{ color: {color["muted"]}; }}
        QPushButton#iconButton {{
            min-width: 24px;
            max-width: 24px;
            min-height: 24px;
            max-height: 24px;
            padding: 0;
        }}
        QScrollArea {{
            background-color: {color["canvas"]};
            border: none;
        }}
        QScrollBar:vertical {{
            width: 11px;
            background: {color["canvas"]};
        }}
        QScrollBar::handle:vertical {{
            min-height: 24px;
            background: {color["border_strong"]};
            border-radius: 2px;
        }}
        QSplitter::handle {{ background-color: {color["border"]}; width: 2px; }}
        QProgressBar {{
            min-height: 16px;
            border: 1px solid {color["border"]};
            border-radius: 2px;
            background-color: {color["surface_alt"]};
            text-align: center;
        }}
        QProgressBar::chunk {{ background-color: {color["primary"]}; }}
        QToolTip {{
            color: {color["text"]};
            background-color: {color["surface"]};
            border: 1px solid {color["border_strong"]};
        }}
    """


MENU_BAR_STYLE: str = f"""
    QMenuBar {{
        background-color: {COLORS["surface"]};
        border-bottom: 1px solid {COLORS["border"]};
    }}
    QMenuBar::item:selected {{ background-color: {COLORS["primary_soft"]}; }}
"""

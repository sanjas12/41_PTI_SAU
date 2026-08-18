from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QLabel,
                             QGroupBox, QVBoxLayout, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal

from .collapsible_groupbox import CollapsibleGroupBox


class ControlPanel(CollapsibleGroupBox):
    """Панель управления с кнопками"""
    
    # Сигналы для внешнего использования.
    # Play/Stop/Пауза — общие кнопки: что именно они запускают (ручную
    # генерацию или сценарий) решает MainWindow, глядя на то, какая
    # вкладка (Ручной/Сценарий) сейчас выбрана.
    play_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    plot_clicked = pyqtSignal()
    logger_clicked = pyqtSignal()
    plc_clicked = pyqtSignal()
    save_channels_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Управление", parent, collapsed=False)
        self.setup_ui()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        # Создаем контейнер для содержимого
        content_widget = QWidget()
        layout = QHBoxLayout()
        content_widget.setLayout(layout)
        
        # Play / Stop / Пауза — общие кнопки для ручного режима и сценария
        self.play_btn = QPushButton("▶ Старт")
        self.play_btn.clicked.connect(self.play_clicked.emit)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #a5d6a7; color: #eeeeee; }
        """)
        layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹ Стоп")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover { background-color: #da190b; }
            QPushButton:disabled { background-color: #ef9a9a; color: #eeeeee; }
        """)
        layout.addWidget(self.stop_btn)
        
        self.pause_btn = QPushButton("⏸ Пауза")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_clicked.emit)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #ffcc80; color: #eeeeee; }
        """)
        layout.addWidget(self.pause_btn)
        
        # Индикатор выполнения — актуален для сценария (ход выполнения
        # шагов); в ручном режиме скрыт (MainWindow управляет видимостью).
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(100)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Кнопка Сброс
        self.reset_btn = QPushButton("↺ Сброс")
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        layout.addWidget(self.reset_btn)
        
        # Кнопка Графики
        self.plot_btn = QPushButton("📊 Графики")
        self.plot_btn.clicked.connect(self.plot_clicked.emit)
        self.plot_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        layout.addWidget(self.plot_btn)
        
        # Кнопка Журнал
        self.logger_btn = QPushButton("📋 Журнал")
        self.logger_btn.clicked.connect(self.logger_clicked.emit)
        self.logger_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        layout.addWidget(self.logger_btn)
        
        # Кнопка PLC Регистры
        self.plc_btn = QPushButton("📋 PLC Регистры")
        self.plc_btn.clicked.connect(self.plc_clicked.emit)
        self.plc_btn.setStyleSheet("""
            QPushButton {
                background-color: #795548;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #5D4037; }
        """)
        layout.addWidget(self.plc_btn)
        
        # Кнопка Сохранить каналы
        self.save_channels_btn = QPushButton("💾 Сохранить каналы")
        self.save_channels_btn.clicked.connect(self.save_channels_clicked.emit)
        self.save_channels_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        layout.addWidget(self.save_channels_btn)
        
        layout.addStretch()
        
        # FPS метка
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.fps_label)
        
        # Устанавливаем layout для GroupBox (содержимое content_widget)
        self.setLayout(layout)
        
        # СОХРАНЯЕМ ВСЕ ВИДЖЕТЫ ДЛЯ СВОРАЧИВАНИЯ
        # ВАЖНО: собираем детей self, а не content_widget — после
        # self.setLayout(layout) Qt переносит все виджеты layout'а на self
        # (см. QWidget::setLayout -> reparentChildWidgets), и content_widget
        # остаётся пустым, отсоединённым от иерархии виджетом.
        self._content_widgets = [
            child for child in self.findChildren(QWidget) if child is not self
        ]
        
        # Стили
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #fafafa;
            }
            QGroupBox::indicator {
                width: 18px;
                height: 18px;
            }
            QGroupBox::indicator:checked {
                image: none;
            }
            QGroupBox::indicator:unchecked {
                image: none;
            }
        """)
        
    def set_running_state(self, is_running: bool):
        """Play/Stop: включить нужную пару в зависимости от того,
        идёт ли сейчас генерация/выполнение (ручное или сценарий)."""
        self.play_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)
        
    def set_pause_enabled(self, enabled: bool):
        """В ручном режиме паузы нет — кнопка гасится."""
        self.pause_btn.setEnabled(enabled)
        if not enabled:
            self.set_pause_icon(paused=False)
            
    def set_pause_icon(self, paused: bool):
        """Переключить иконку между 'Пауза' и 'Возобновить'."""
        if paused:
            self.pause_btn.setText("▶ Возобновить")
            self.pause_btn.setToolTip("Возобновить")
        else:
            self.pause_btn.setText("⏸ Пауза")
            self.pause_btn.setToolTip("Пауза")
            
    def set_progress(self, value: int):
        """Обновить индикатор выполнения (0-100)."""
        self.progress_bar.setValue(value)
        
    def set_progress_visible(self, visible: bool):
        """Индикатор актуален только для сценария — в ручном режиме прячем."""
        self.progress_bar.setVisible(visible)
            
    def update_fps(self, fps: int):
        """Обновить FPS"""
        self.fps_label.setText(f"FPS: {fps}")
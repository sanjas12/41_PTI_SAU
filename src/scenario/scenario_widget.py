import json
import os

from PyQt5.QtCore import QMimeData, QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QDrag, QFont, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.signal_generator import SignalGenerator
from core.signal_types import SignalType

from .scenario_engine import ScenarioEngine, ScenarioMode
from .scenario_model import Scenario, ScenarioStep


class StepWidget(QFrame):
    """Виджет для отображения шага сценария (drag&drop)"""
    
    def __init__(self, step_index: int, step: ScenarioStep, parent=None):
        super().__init__(parent)
        self.step_index = step_index
        self.step = step
        self.setup_ui()
        self.setAcceptDrops(True)
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px;
                margin: 2px;
            }
            QFrame:hover {
                background-color: #e8f5e9;
                border: 2px solid #4CAF50;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Номер шага
        self.number_label = QLabel(f"#{self.step_index + 1}")
        self.number_label.setStyleSheet("font-weight: bold; color: #666; min-width: 30px;")
        layout.addWidget(self.number_label)
        
        # Информация о канале
        channel_info = f"Канал {self.step.channel_id + 1}"
        self.channel_label = QLabel(channel_info)
        self.channel_label.setStyleSheet("font-weight: bold; min-width: 60px;")
        layout.addWidget(self.channel_label)
        
        # Тип сигнала
        type_color = {
            'Sine': '#2196F3',
            'Square': '#f44336',
            'Sawtooth': '#FF9800',
            'Triangle': '#4CAF50',
            'Random': '#9C27B0',
            'Custom': '#795548'
        }.get(self.step.signal_type, '#666666')
        
        self.type_label = QLabel(self.step.signal_type)
        self.type_label.setStyleSheet(f"color: {type_color}; font-weight: bold; min-width: 60px;")
        layout.addWidget(self.type_label)
        
        # Параметры
        params = f"{self.step.amplitude:.0f}% | {self.step.frequency:.1f}Гц"
        self.params_label = QLabel(params)
        self.params_label.setStyleSheet("color: #666; min-width: 80px;")
        layout.addWidget(self.params_label)
        
        # Длительность
        duration = f"{self.step.duration:.1f}с"
        self.duration_label = QLabel(duration)
        self.duration_label.setStyleSheet("color: #666; min-width: 50px;")
        layout.addWidget(self.duration_label)
        
        # Рампа
        if self.step.ramp_up > 0 or self.step.ramp_down > 0:
            ramp_text = f"▲{self.step.ramp_up:.1f}▼{self.step.ramp_down:.1f}"
            self.ramp_label = QLabel(ramp_text)
            self.ramp_label.setStyleSheet("color: #FF9800; min-width: 50px;")
            layout.addWidget(self.ramp_label)
        
        layout.addStretch()
        
        # Кнопка удаления
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(20, 20)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        layout.addWidget(self.delete_btn)
        
        self.setLayout(layout)
        self.setMinimumHeight(35)
        self.setMaximumHeight(45)
        
    def mousePressEvent(self, event):
        """Начало перетаскивания"""
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.step_index))
            drag.setMimeData(mime_data)
            
            # Создаем иконку для перетаскивания
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            
            drag.exec_(Qt.MoveAction)
            
    def contextMenuEvent(self, event):
        """Контекстное меню для шага"""
        menu = QMenu()
        
        edit_action = QAction("✏️ Редактировать", self)
        edit_action.triggered.connect(self.edit_step)
        menu.addAction(edit_action)
        
        delete_action = QAction("🗑 Удалить", self)
        delete_action.triggered.connect(self.delete_step)
        menu.addAction(delete_action)
        
        menu.addSeparator()
        
        move_up = QAction("⬆ Переместить вверх", self)
        move_up.triggered.connect(self.move_up)
        menu.addAction(move_up)
        
        move_down = QAction("⬇ Переместить вниз", self)
        move_down.triggered.connect(self.move_down)
        menu.addAction(move_down)
        
        menu.exec_(event.globalPos())
        
    def edit_step(self):
        """Редактировать шаг"""
        # Сигнал будет обрабатываться в родительском виджете
        self.parent().edit_step(self.step_index)
        
    def delete_step(self):
        """Удалить шаг"""
        self.parent().delete_step(self.step_index)
        
    def move_up(self):
        """Переместить вверх"""
        self.parent().move_step(self.step_index, -1)
        
    def move_down(self):
        """Переместить вниз"""
        self.parent().move_step(self.step_index, 1)


class ScenarioWidget(QWidget):
    """Виджет конструктора сценариев"""
    
    # Сигналы
    scenario_changed = pyqtSignal(object)  # Сценарий изменен
    scenario_saved = pyqtSignal(str)  # Сценарий сохранен
    
    def __init__(self, generator: SignalGenerator, engine: ScenarioEngine, parent=None):
        super().__init__(parent)
        self.generator = generator
        self.engine = engine
        self.scenario = Scenario()
        self.current_file = None
        
        # Подключаем сигналы двигателя
        self.engine.scenario_started.connect(self.on_scenario_started)
        self.engine.scenario_stopped.connect(self.on_scenario_stopped)
        self.engine.scenario_finished.connect(self.on_scenario_finished)
        self.engine.step_changed.connect(self.on_step_changed)
        self.engine.progress_changed.connect(self.on_progress_changed)
        self.engine.mode_changed.connect(self.on_mode_changed)
        
        self.setup_ui()
        self.update_step_list()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)
        self.setLayout(layout)
        
        # Устанавливаем максимальную высоту для компактности
        self.setMaximumHeight(250)
        
        # Заголовок
        title_layout = QHBoxLayout()
        title = QLabel("🎬 Конструктор сценариев")
        title.setStyleSheet("font-size: 11px; font-weight: bold;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # Кнопка добавления шага (компактная)
        self.add_step_btn = QPushButton("➕")
        self.add_step_btn.setFixedSize(25, 25)
        self.add_step_btn.setToolTip("Добавить шаг")
        self.add_step_btn.clicked.connect(self.add_step)
        self.add_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        title_layout.addWidget(self.add_step_btn)
        
        layout.addLayout(title_layout)
        
        # Список шагов (компактный)
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout()
        self.steps_layout.setSpacing(2)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_container.setLayout(self.steps_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(120)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: 1px solid #ddd; 
                border-radius: 3px; 
                background-color: white;
            }
        """)
        scroll.setWidget(self.steps_container)
        layout.addWidget(scroll)
        
        # Нижняя панель управления (компактная)
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(3)
        
        # Кнопки управления сценарием (компактные)
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(30, 25)
        self.play_btn.setToolTip("Запустить сценарий")
        self.play_btn.clicked.connect(self.play_scenario)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        bottom_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(30, 25)
        self.stop_btn.setToolTip("Остановить сценарий")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scenario)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        bottom_layout.addWidget(self.stop_btn)
        
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setFixedSize(30, 25)
        self.pause_btn.setToolTip("Пауза/Возобновить")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_scenario)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        bottom_layout.addWidget(self.pause_btn)
        
        bottom_layout.addStretch()
        
        # Прогресс (компактный)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(100)
        self.progress_bar.setMaximumHeight(15)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                height: 15px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        bottom_layout.addWidget(self.progress_bar)
        
        # Кнопки сохранения/загрузки (компактные)
        self.save_btn = QPushButton("💾")
        self.save_btn.setFixedSize(25, 25)
        self.save_btn.setToolTip("Сохранить сценарий")
        self.save_btn.clicked.connect(self.save_scenario)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        bottom_layout.addWidget(self.save_btn)
        
        self.load_btn = QPushButton("📂")
        self.load_btn.setFixedSize(25, 25)
        self.load_btn.setToolTip("Загрузить сценарий")
        self.load_btn.clicked.connect(self.load_scenario)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        bottom_layout.addWidget(self.load_btn)
        
        layout.addLayout(bottom_layout)
        
        # Статус (компактный)
        status_layout = QHBoxLayout()
        status_layout.setSpacing(5)
        
        self.steps_count_label = QLabel("0 шагов")
        self.steps_count_label.setStyleSheet("color: #666; font-size: 8px;")
        status_layout.addWidget(self.steps_count_label)
        
        status_layout.addStretch()
        
        self.status_label = QLabel("Режим: Ручной")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 8px;")
        status_layout.addWidget(self.status_label)
        
        layout.addLayout(status_layout)
            
    def _create_steps_panel(self):
        """Создать панель со списком шагов"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Заголовок
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("📋 Шаги сценария"))
        header_layout.addStretch()
        
        self.steps_count_label = QLabel("0 шагов")
        self.steps_count_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.steps_count_label)
        layout.addLayout(header_layout)
        
        # Контейнер для шагов (с поддержкой drag&drop)
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout()
        self.steps_layout.setSpacing(2)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_container.setLayout(self.steps_layout)
        
        # Скролл для шагов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #ddd; border-radius: 4px; }")
        scroll.setWidget(self.steps_container)
        
        layout.addWidget(scroll)
        
        # Кнопки управления шагами
        buttons_layout = QHBoxLayout()
        
        self.add_step_btn = QPushButton("➕ Добавить шаг")
        self.add_step_btn.clicked.connect(self.add_step)
        self.add_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        buttons_layout.addWidget(self.add_step_btn)
        
        self.clear_steps_btn = QPushButton("🗑 Очистить все")
        self.clear_steps_btn.clicked.connect(self.clear_steps)
        self.clear_steps_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        buttons_layout.addWidget(self.clear_steps_btn)
        
        layout.addLayout(buttons_layout)
        
        return widget
        
    def _create_control_panel(self):
        """Создать панель управления"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Информация о сценарии
        info_group = QGroupBox("📊 Информация")
        info_layout = QVBoxLayout()
        info_group.setLayout(info_layout)
        
        self.name_label = QLabel("Имя: Новый сценарий")
        info_layout.addWidget(self.name_label)
        
        self.duration_label = QLabel("Длительность: 0.0 с")
        info_layout.addWidget(self.duration_label)
        
        self.steps_info_label = QLabel("Шагов: 0")
        info_layout.addWidget(self.steps_info_label)
        
        self.loop_check = QCheckBox("Зациклить")
        self.loop_check.toggled.connect(self.on_loop_toggled)
        info_layout.addWidget(self.loop_check)
        
        layout.addWidget(info_group)
        
        # Прогресс
        progress_group = QGroupBox("📈 Прогресс")
        progress_layout = QVBoxLayout()
        progress_group.setLayout(progress_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Режим: Ручной")
        self.status_label.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.status_label)
        
        self.time_label = QLabel("Время: 0.0 с")
        self.time_label.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.time_label)
        
        layout.addWidget(progress_group)
        
        # Кнопки управления сценарием
        control_group = QGroupBox("🎮 Управление")
        control_layout = QVBoxLayout()
        control_group.setLayout(control_layout)
        
        play_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("▶ Запустить")
        self.play_btn.clicked.connect(self.play_scenario)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        play_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.clicked.connect(self.stop_scenario)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        play_layout.addWidget(self.stop_btn)
        
        self.pause_btn = QPushButton("⏸ Пауза")
        self.pause_btn.clicked.connect(self.pause_scenario)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        play_layout.addWidget(self.pause_btn)
        
        control_layout.addLayout(play_layout)
        
        layout.addWidget(control_group)
        
        # Кнопки сохранения/загрузки
        file_group = QGroupBox("💾 Файл")
        file_layout = QHBoxLayout()
        file_group.setLayout(file_layout)
        
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.clicked.connect(self.save_scenario)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        file_layout.addWidget(self.save_btn)
        
        self.load_btn = QPushButton("📂 Загрузить")
        self.load_btn.clicked.connect(self.load_scenario)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        file_layout.addWidget(self.load_btn)
        
        layout.addWidget(file_group)
        
        return widget
        
    def _create_scenario_controls(self):
        """Создать нижнюю панель управления"""
        layout = QHBoxLayout()
        
        self.mode_switch_btn = QPushButton("🔄 Переключить режим")
        self.mode_switch_btn.clicked.connect(self.switch_mode)
        self.mode_switch_btn.setStyleSheet("""
            QPushButton {
                background-color: #795548;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5D4037; }
        """)
        layout.addWidget(self.mode_switch_btn)
        
        layout.addStretch()
        
        self.mode_indicator = QLabel("Режим: Ручной")
        self.mode_indicator.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.mode_indicator)
        
        return layout
        
    def update_step_list(self):
        """Обновить список шагов"""
        # Очищаем контейнер
        for i in reversed(range(self.steps_layout.count())):
            widget = self.steps_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Добавляем шаги
        for i, step in enumerate(self.scenario.steps):
            step_widget = StepWidget(i, step, self)
            step_widget.delete_btn.clicked.connect(lambda checked, idx=i: self.delete_step(idx))
            self.steps_layout.addWidget(step_widget)
        
        # Обновляем информацию
        self.steps_count_label.setText(f"{len(self.scenario.steps)} шагов")
        self.steps_info_label.setText(f"Шагов: {len(self.scenario.steps)}")
        self.duration_label.setText(f"Длительность: {self.scenario.get_total_duration():.1f} с")
        
        # Отправляем сигнал об изменении
        self.scenario_changed.emit(self.scenario)
        
    def add_step(self):
        """Добавить новый шаг"""
        dialog = StepEditDialog(self.generator, self)
        if dialog.exec_() == QDialog.Accepted:
            step = dialog.get_step()
            if step:
                self.scenario.steps.append(step)
                self.update_step_list()
                
    def edit_step(self, index: int):
        """Редактировать шаг"""
        if 0 <= index < len(self.scenario.steps):
            dialog = StepEditDialog(self.generator, self, self.scenario.steps[index])
            if dialog.exec_() == QDialog.Accepted:
                step = dialog.get_step()
                if step:
                    self.scenario.steps[index] = step
                    self.update_step_list()
                    
    def delete_step(self, index: int):
        """Удалить шаг"""
        if 0 <= index < len(self.scenario.steps):
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Удалить шаг #{index + 1}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self.scenario.steps[index]
                self.update_step_list()
                
    def clear_steps(self):
        """Очистить все шаги"""
        if not self.scenario.steps:
            return
            
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Очистить все шаги?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.scenario.steps.clear()
            self.update_step_list()
            
    def move_step(self, index: int, direction: int):
        """Переместить шаг"""
        new_index = index + direction
        if 0 <= new_index < len(self.scenario.steps):
            self.scenario.steps[index], self.scenario.steps[new_index] = \
                self.scenario.steps[new_index], self.scenario.steps[index]
            self.update_step_list()
            
    def on_loop_toggled(self, checked: bool):
        """Изменен флаг зацикливания"""
        self.scenario.loop = checked
        
    def play_scenario(self):
        """Запустить сценарий"""
        if not self.scenario.steps:
            QMessageBox.warning(self, "Предупреждение", "Сценарий пуст!")
            return
            
        self.engine.load_scenario(self.scenario)
        self.engine.start_scenario()
        
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        
    def stop_scenario(self):
        """Остановить сценарий"""
        self.engine.stop_scenario()
        
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
    def pause_scenario(self):
        """Пауза сценария"""
        if self.engine.mode == ScenarioMode.SCENARIO:
            self.engine.pause_scenario()
            self.pause_btn.setText("▶ Возобновить")
        else:
            self.engine.resume_scenario()
            self.pause_btn.setText("⏸ Пауза")
            
    def switch_mode(self):
        """Переключить режим"""
        if self.engine.mode == ScenarioMode.MANUAL:
            self.engine.start_scenario()
        else:
            self.engine.set_manual_mode()
            
    def on_scenario_started(self, name: str):
        """Сценарий запущен"""
        self.status_label.setText(f"Выполняется: {name}")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.mode_indicator.setText("Режим: Сценарий")
        self.mode_indicator.setStyleSheet("color: #FF9800; font-weight: bold;")
        
    def on_scenario_stopped(self):
        """Сценарий остановлен"""
        self.status_label.setText("Остановлен")
        self.status_label.setStyleSheet("color: #f44336;")
        self.mode_indicator.setText("Режим: Ручной")
        self.mode_indicator.setStyleSheet("color: #4CAF50; font-weight: bold;")
        
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸ Пауза")
        
    def on_scenario_finished(self):
        """Сценарий завершен"""
        self.status_label.setText("Завершен")
        self.status_label.setStyleSheet("color: #4CAF50;")
        
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸ Пауза")
        
    def on_step_changed(self, current: int, total: int):
        """Изменен текущий шаг"""
        self.steps_info_label.setText(f"Шаг: {current}/{total}")
        
    def on_progress_changed(self, progress: float):
        """Обновлен прогресс"""
        self.progress_bar.setValue(int(progress))
        
    def on_mode_changed(self, mode: str):
        """Изменен режим"""
        if mode == "manual":
            self.mode_indicator.setText("Режим: Ручной")
            self.mode_indicator.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif mode == "scenario":
            self.mode_indicator.setText("Режим: Сценарий")
            self.mode_indicator.setStyleSheet("color: #FF9800; font-weight: bold;")
        elif mode == "paused":
            self.mode_indicator.setText("Режим: Пауза")
            self.mode_indicator.setStyleSheet("color: #2196F3; font-weight: bold;")
            
    def save_scenario(self):
        """Сохранить сценарий"""
        if not self.scenario.steps:
            QMessageBox.warning(self, "Предупреждение", "Сценарий пуст!")
            return
            
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить сценарий",
            f"{self.scenario.name}.json",
            "JSON files (*.json)"
        )
        
        if filepath:
            self.scenario.save_to_file(filepath)
            self.current_file = filepath
            self.scenario_saved.emit(filepath)
            QMessageBox.information(self, "Успех", f"Сценарий сохранен в:\n{filepath}")
            
    def load_scenario(self):
        """Загрузить сценарий"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузить сценарий",
            "",
            "JSON files (*.json)"
        )
        
        if filepath:
            try:
                self.scenario = Scenario.load_from_file(filepath)
                self.current_file = filepath
                self.name_label.setText(f"Имя: {self.scenario.name}")
                self.loop_check.setChecked(self.scenario.loop)
                self.update_step_list()
                QMessageBox.information(self, "Успех", f"Сценарий загружен:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить сценарий:\n{str(e)}")


class StepEditDialog(QDialog):
    """Диалог редактирования шага"""
    
    def __init__(self, generator: SignalGenerator, parent=None, step: ScenarioStep = None):
        super().__init__(parent)
        self.generator = generator
        self.step = step or ScenarioStep(channel_id=0, signal_type="Sine")
        self.setWindowTitle("Редактирование шага" if step else "Добавление шага")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        form_layout = QFormLayout()
        
        # Канал
        self.channel_combo = QComboBox()
        for channel in self.generator.channels:
            self.channel_combo.addItem(
                f"Канал {channel.id + 1}: {channel.name}",
                channel.id
            )
        if self.step:
            index = self.channel_combo.findData(self.step.channel_id)
            if index >= 0:
                self.channel_combo.setCurrentIndex(index)
        form_layout.addRow("Канал:", self.channel_combo)
        
        # Тип сигнала
        self.type_combo = QComboBox()
        self.type_combo.addItems([st.name.capitalize() for st in SignalType])
        if self.step:
            index = self.type_combo.findText(self.step.signal_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        form_layout.addRow("Тип сигнала:", self.type_combo)
        
        # Амплитуда
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0, 100)
        self.amp_spin.setValue(self.step.amplitude)
        self.amp_spin.setSuffix(" %")
        form_layout.addRow("Амплитуда:", self.amp_spin)
        
        # Частота
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.01, 100)
        self.freq_spin.setValue(self.step.frequency)
        self.freq_spin.setSuffix(" Гц")
        form_layout.addRow("Частота:", self.freq_spin)
        
        # Смещение
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-100, 100)
        self.offset_spin.setValue(self.step.offset)
        self.offset_spin.setSuffix(" %")
        form_layout.addRow("Смещение:", self.offset_spin)
        
        # Длительность
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 3600)
        self.duration_spin.setValue(self.step.duration)
        self.duration_spin.setSuffix(" с")
        form_layout.addRow("Длительность:", self.duration_spin)
        
        # Нарастание
        self.ramp_up_spin = QDoubleSpinBox()
        self.ramp_up_spin.setRange(0, 60)
        self.ramp_up_spin.setValue(self.step.ramp_up)
        self.ramp_up_spin.setSuffix(" с")
        form_layout.addRow("Нарастание:", self.ramp_up_spin)
        
        # Затухание
        self.ramp_down_spin = QDoubleSpinBox()
        self.ramp_down_spin.setRange(0, 60)
        self.ramp_down_spin.setValue(self.step.ramp_down)
        self.ramp_down_spin.setSuffix(" с")
        form_layout.addRow("Затухание:", self.ramp_down_spin)
        
        layout.addLayout(form_layout)
        
        # Кнопки OK/Cancel
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setMinimumWidth(350)
        
    def get_step(self) -> ScenarioStep:
        """Получить настроенный шаг"""
        return ScenarioStep(
            channel_id=self.channel_combo.currentData(),
            signal_type=self.type_combo.currentText(),
            amplitude=self.amp_spin.value(),
            frequency=self.freq_spin.value(),
            offset=self.offset_spin.value(),
            duration=self.duration_spin.value(),
            ramp_up=self.ramp_up_spin.value(),
            ramp_down=self.ramp_down_spin.value()
        )
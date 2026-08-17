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
                padding: 2px;
                margin: 1px;
            }
            QFrame:hover {
                background-color: #e8f5e9;
                border: 2px solid #4CAF50;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(3)
        
        # Номер шага
        self.number_label = QLabel(f"#{self.step_index + 1}")
        self.number_label.setStyleSheet("font-weight: bold; color: #666; min-width: 25px; font-size: 8px;")
        layout.addWidget(self.number_label)
        
        # Информация о канале
        channel_info = f"Ch{self.step.channel_id + 1}"
        self.channel_label = QLabel(channel_info)
        self.channel_label.setStyleSheet("font-weight: bold; min-width: 25px; font-size: 8px;")
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
        
        self.type_label = QLabel(self.step.signal_type[:4])
        self.type_label.setStyleSheet(f"color: {type_color}; font-weight: bold; min-width: 30px; font-size: 8px;")
        layout.addWidget(self.type_label)
        
        # Длительность
        duration = f"{self.step.duration:.0f}с"
        self.duration_label = QLabel(duration)
        self.duration_label.setStyleSheet("color: #666; min-width: 25px; font-size: 8px;")
        layout.addWidget(self.duration_label)
        
        layout.addStretch()
        
        # Кнопка удаления
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(16, 16)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 8px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        layout.addWidget(self.delete_btn)
        
        self.setLayout(layout)
        self.setMinimumHeight(25)
        self.setMaximumHeight(30)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.step_index))
            drag.setMimeData(mime_data)
            
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            
            drag.exec_(Qt.MoveAction)
            
    def contextMenuEvent(self, event):
        menu = QMenu()
        
        edit_action = QAction("✏️ Редактировать", self)
        edit_action.triggered.connect(self.edit_step)
        menu.addAction(edit_action)
        
        delete_action = QAction("🗑 Удалить", self)
        delete_action.triggered.connect(self.delete_step)
        menu.addAction(delete_action)
        
        menu.addSeparator()
        
        move_up = QAction("⬆ Вверх", self)
        move_up.triggered.connect(self.move_up)
        menu.addAction(move_up)
        
        move_down = QAction("⬇ Вниз", self)
        move_down.triggered.connect(self.move_down)
        menu.addAction(move_down)
        
        menu.exec_(event.globalPos())
        
    def edit_step(self):
        self.parent().edit_step(self.step_index)
        
    def delete_step(self):
        self.parent().delete_step(self.step_index)
        
    def move_up(self):
        self.parent().move_step(self.step_index, -1)
        
    def move_down(self):
        self.parent().move_step(self.step_index, 1)


class ScenarioWidget(QWidget):
    """Виджет конструктора сценариев"""
    
    scenario_changed = pyqtSignal(object)
    scenario_saved = pyqtSignal(str)
    
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
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)
        
        # Устанавливаем максимальную высоту для компактности
        self.setMaximumHeight(180)
        
        # Заголовок
        title_layout = QHBoxLayout()
        title_layout.setSpacing(3)
        
        title = QLabel("🎬 Сценарии")
        title.setStyleSheet("font-size: 10px; font-weight: bold;")
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        # Кнопка добавления шага
        self.add_step_btn = QPushButton("➕")
        self.add_step_btn.setFixedSize(20, 20)
        self.add_step_btn.setToolTip("Добавить шаг")
        self.add_step_btn.clicked.connect(self.add_step)
        self.add_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        title_layout.addWidget(self.add_step_btn)
        
        layout.addLayout(title_layout)
        
        # Список шагов
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout()
        self.steps_layout.setSpacing(1)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_container.setLayout(self.steps_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(100)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: 1px solid #ddd; 
                border-radius: 3px; 
                background-color: white;
            }
        """)
        scroll.setWidget(self.steps_container)
        layout.addWidget(scroll)
        
        # Нижняя панель
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(3)
        
        # Кнопки управления
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(25, 22)
        self.play_btn.setToolTip("Запустить сценарий")
        self.play_btn.clicked.connect(self.play_scenario)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        bottom_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(25, 22)
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
                font-size: 10px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        bottom_layout.addWidget(self.stop_btn)
        
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setFixedSize(25, 22)
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
                font-size: 10px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        bottom_layout.addWidget(self.pause_btn)
        
        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(80)
        self.progress_bar.setMaximumHeight(14)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                height: 14px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        bottom_layout.addWidget(self.progress_bar)
        
        bottom_layout.addStretch()
        
        # Кнопки сохранения/загрузки
        self.save_btn = QPushButton("💾")
        self.save_btn.setFixedSize(22, 22)
        self.save_btn.setToolTip("Сохранить сценарий")
        self.save_btn.clicked.connect(self.save_scenario)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        bottom_layout.addWidget(self.save_btn)
        
        self.load_btn = QPushButton("📂")
        self.load_btn.setFixedSize(22, 22)
        self.load_btn.setToolTip("Загрузить сценарий")
        self.load_btn.clicked.connect(self.load_scenario)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        bottom_layout.addWidget(self.load_btn)
        
        layout.addLayout(bottom_layout)
        
        # Статус
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
            self.pause_btn.setText("▶")
            self.pause_btn.setToolTip("Возобновить")
        else:
            self.engine.resume_scenario()
            self.pause_btn.setText("⏸")
            self.pause_btn.setToolTip("Пауза")
            
    def switch_mode(self):
        """Переключить режим"""
        if self.engine.mode == ScenarioMode.MANUAL:
            self.engine.start_scenario()
        else:
            self.engine.set_manual_mode()
            
    def on_scenario_started(self, name: str):
        self.status_label.setText(f"Выполняется: {name[:15]}")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 8px;")
        
    def on_scenario_stopped(self):
        self.status_label.setText("Остановлен")
        self.status_label.setStyleSheet("color: #f44336; font-size: 8px;")
        
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸")
        self.pause_btn.setToolTip("Пауза")
        
    def on_scenario_finished(self):
        self.status_label.setText("Завершен")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 8px;")
        
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸")
        self.pause_btn.setToolTip("Пауза")
        
    def on_step_changed(self, current: int, total: int):
        pass
        
    def on_progress_changed(self, progress: float):
        self.progress_bar.setValue(int(progress))
        
    def on_mode_changed(self, mode: str):
        if mode == "manual":
            self.status_label.setText("Режим: Ручной")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 8px;")
        elif mode == "scenario":
            self.status_label.setText("Режим: Сценарий")
            self.status_label.setStyleSheet("color: #FF9800; font-size: 8px;")
        elif mode == "paused":
            self.status_label.setText("Режим: Пауза")
            self.status_label.setStyleSheet("color: #2196F3; font-size: 8px;")
            
    def save_scenario(self):
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
        form_layout.setSpacing(5)
        
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
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setMinimumWidth(300)
        
    def get_step(self) -> ScenarioStep:
        return ScenarioStep(
            channel_id=self.channel_combo.currentData(),
            signal_type=self.type_combo.currentText(),
            amplitude=self.amp_spin.value(),
            frequency=self.freq_spin.value(),
            offset=0.0,
            duration=self.duration_spin.value(),
            ramp_up=self.ramp_up_spin.value(),
            ramp_down=self.ramp_down_spin.value()
        )
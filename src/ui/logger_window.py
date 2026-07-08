from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QLabel, QCheckBox,
                             QSpinBox, QGroupBox, QFileDialog, QMessageBox,
                             QComboBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QTextCursor
import datetime
import os
import re


class LoggerWindow(QMainWindow):
    """Отдельное окно для отображения журнала событий"""
    
    # Сигнал для записи сообщения из других окон
    log_signal = pyqtSignal(str, str)  # message, level
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Журнал событий")
        self.setGeometry(200, 200, 800, 600)
        
        self.log_buffer = []
        self.max_logs = 10000
        self.auto_scroll = True
        self.log_file = None
        self.filter_level = None
        
        self.setup_ui()
        self.setup_connections()
        
        # Подключаем сигнал для потокобезопасного логирования
        self.log_signal.connect(self._append_log)
        
    def setup_ui(self):
        """Настройка интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Панель управления
        control_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("🗑 Очистить")
        self.clear_btn.clicked.connect(self.clear_log)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        control_layout.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.clicked.connect(self.save_log)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        control_layout.addWidget(self.save_btn)
        
        self.auto_scroll_cb = QCheckBox("Авто-прокрутка")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(self.set_auto_scroll)
        control_layout.addWidget(self.auto_scroll_cb)
        
        control_layout.addStretch()
        
        self.count_label = QLabel("Сообщений: 0")
        self.count_label.setStyleSheet("color: #666666;")
        control_layout.addWidget(self.count_label)
        
        layout.addLayout(control_layout)
        
        # Текстовое поле для логов - используем QTextEdit (поддерживает HTML)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                font-family: Consolas;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.log_text)
        
        # Нижняя панель
        info_layout = QHBoxLayout()
        
        self.filter_label = QLabel("Фильтр:")
        self.filter_label.setStyleSheet("color: #666666;")
        info_layout.addWidget(self.filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все", "Информация", "Успех", "Ошибка", "Предупреждение"])
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        self.filter_combo.setStyleSheet("""
            QComboBox {
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)
        info_layout.addWidget(self.filter_combo)
        
        info_layout.addStretch()
        
        self.timestamp_label = QLabel("Время: " + datetime.datetime.now().strftime("%H:%M:%S"))
        self.timestamp_label.setStyleSheet("color: #666666;")
        info_layout.addWidget(self.timestamp_label)
        
        layout.addLayout(info_layout)
        
        # Стили
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
    def setup_connections(self):
        """Настройка соединений"""
        # Таймер обновления времени
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timestamp)
        self.timer.start(1000)
        
    def update_timestamp(self):
        """Обновить метку времени"""
        self.timestamp_label.setText("Время: " + datetime.datetime.now().strftime("%H:%M:%S"))
        
    def log(self, message: str, level: str = "info"):
        """Добавить сообщение в журнал (потокобезопасно)"""
        self.log_signal.emit(message, level)
        
    def _append_log(self, message: str, level: str = "info"):
        """Внутренний метод для добавления сообщения"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Цвета для разных уровней
        colors = {
            "info": "#d4d4d4",
            "success": "#4CAF50",
            "error": "#f44336",
            "warning": "#FF9800",
            "debug": "#9C27B0"
        }
        
        # Префиксы для уровней
        prefixes = {
            "info": "[INFO]",
            "success": "[OK]",
            "error": "[ERROR]",
            "warning": "[WARN]",
            "debug": "[DEBUG]"
        }
        
        color = colors.get(level, "#d4d4d4")
        prefix = prefixes.get(level, "[INFO]")
        
        # Формируем HTML строку
        html = f'<span style="color: #888888;">{timestamp}</span> ' \
               f'<span style="color: {color}; font-weight: bold;">{prefix}</span> ' \
               f'<span style="color: {color};">{message}</span>'
        
        # Добавляем в буфер
        self.log_buffer.append((html, level))
        
        # Ограничиваем буфер
        if len(self.log_buffer) > self.max_logs:
            self.log_buffer = self.log_buffer[-self.max_logs:]
        
        # Обновляем отображение
        self._update_display()
        
        # Обновляем счетчик
        self.count_label.setText(f"Сообщений: {len(self.log_buffer)}")
        
    def _update_display(self):
        """Обновить отображение с учетом фильтра"""
        filter_text = self.filter_combo.currentText()
        
        # Определяем уровень для фильтра
        filter_level = None
        if filter_text != "Все":
            filter_map = {
                "Информация": "info",
                "Успех": "success",
                "Ошибка": "error",
                "Предупреждение": "warning"
            }
            filter_level = filter_map.get(filter_text)
        
        # Фильтруем сообщения
        filtered = []
        for html, level in self.log_buffer:
            if filter_level is None or level == filter_level:
                filtered.append(html)
        
        # Собираем HTML
        if filtered:
            display_text = "<br>".join(filtered)
        else:
            display_text = "<span style='color: #666666;'>Нет сообщений для отображения</span>"
        
        # Устанавливаем HTML (QTextEdit поддерживает setHtml)
        self.log_text.setHtml(display_text)
        
        # Автопрокрутка
        if self.auto_scroll:
            self.log_text.moveCursor(QTextCursor.End)
            
    def apply_filter(self):
        """Применить фильтр"""
        self._update_display()
        
    def set_auto_scroll(self, enabled: bool):
        """Установить авто-прокрутку"""
        self.auto_scroll = enabled
        
    def clear_log(self):
        """Очистить журнал"""
        self.log_buffer.clear()
        self.log_text.clear()
        self.count_label.setText("Сообщений: 0")
        
    def save_log(self):
        """Сохранить журнал в файл"""
        if not self.log_buffer:
            QMessageBox.information(self, "Информация", "Журнал пуст")
            return
            
        # Выбираем файл для сохранения
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить журнал",
            f"log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "HTML Files (*.html);;Text Files (*.txt)"
        )
        
        if not filename:
            return
            
        try:
            if filename.endswith('.html'):
                # Сохраняем как HTML
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("<!DOCTYPE html>\n")
                    f.write("<html><head><meta charset='utf-8'>\n")
                    f.write("""
                    <style>
                        body { 
                            font-family: Consolas; 
                            background: #1e1e1e; 
                            color: #d4d4d4; 
                            padding: 20px;
                        }
                        .timestamp { color: #888888; }
                        .prefix { font-weight: bold; }
                        .info { color: #d4d4d4; }
                        .success { color: #4CAF50; }
                        .error { color: #f44336; }
                        .warning { color: #FF9800; }
                        .debug { color: #9C27B0; }
                    </style>
                    </head><body>\n")
                    for html, _ in self.log_buffer:
                        f.write(html + "<br>\n")
                    f.write("</body></html>"
                    """)
            else:
                # Сохраняем как текстовый файл
                with open(filename, 'w', encoding='utf-8') as f:
                    for html, level in self.log_buffer:
                        # Извлекаем текст из HTML
                        text = re.sub(r'<[^>]+>', '', html)
                        f.write(f"[{level.upper()}] {text}\n")
                        
            QMessageBox.information(self, "Успех", f"Журнал сохранен в {filename}")
            self.log("Журнал сохранен в файл", "success")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить журнал: {e}")
            
    def showEvent(self, event):
        """При показе окна обновляем отображение"""
        self._update_display()
        super().showEvent(event)
        
    def closeEvent(self, event):
        """При закрытии окна не закрываем приложение"""
        self.hide()
        event.ignore()
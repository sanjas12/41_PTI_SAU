import struct
import threading
import time
from typing import List, Optional

from PyQt5.QtCore import QObject, QThreadPool, QTimer, pyqtSignal

from core.signal_generator import SignalGenerator
from modbus.modbus_client import ModbusClientWrapper
from modbus.worker import Runnable


class PLCInterface(QObject):
    """Интерфейс для связи с PLC Modicon Premium через Modbus TCP"""
    
    # Сигналы для обновления UI
    data_updated = pyqtSignal(dict)  # Обновлены данные
    connection_status = pyqtSignal(bool)  # Статус подключения
    error_occurred = pyqtSignal(str)  # Ошибка
    debug_data = pyqtSignal(dict)  # Дебаг данные
    write_completed = pyqtSignal(bool)  # Сигнал о завершении записи
    
    def __init__(self, generator: SignalGenerator, parent=None, debug: bool = False):
        super().__init__(parent)
        self.generator = generator
        self.debug = debug
        
        # Инициализируем modbus
        self.modbus = ModbusClientWrapper()
        
        # Адреса регистров (начиная с %MW0)
        self.registers = {
            'analog_signals': {
                'start_address': 0,
                'count': 20,
                'type': 'float'
            },
            'control': {
                'start_address': 40,
                'count': 10,
                'type': 'int'
            },
            'status': {
                'start_address': 50,
                'count': 10,
                'type': 'int'
            }
        }
        
        # Кэш данных для записи
        self.write_cache = {}
        self.last_write_time = 0
        self.write_interval = 0.2  # 200ms
        
        # Состояние
        self._lock = threading.Lock()
        self._connected = False
        self._is_configured = False
        self._write_pending = False
        
        # Пул потоков для асинхронных операций
        self.thread_pool = QThreadPool.globalInstance()
        
        # Для отладки - сохраняем последние записанные данные
        self.last_written_data = {}
        self.write_count = 0
        
        # Таймер для периодического обновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plc_data)
        
        if self.debug:
            print("[PLC_DEBUG] PLCInterface инициализирован")
        
    def configure(self, host: str, port: int, unit_id: int = 1):
        """Настройка подключения к PLC"""
        try:
            self.modbus.configure(host, port, unit_id)
            self._is_configured = True
            self._connected = False
            self.connection_status.emit(False)
            
            if self.debug:
                print(f"[PLC_DEBUG] Настроен Modbus: {host}:{port} (Unit ID: {unit_id})")
            
            return True
        except Exception as e:
            error_msg = f"Ошибка настройки PLC: {e}"
            self.error_occurred.emit(error_msg)
            self._is_configured = False
            self._connected = False
            self.connection_status.emit(False)
            
            if self.debug:
                print(f"[PLC_DEBUG] ❌ {error_msg}")
            
            return False
            
    def connect(self) -> bool:
        """Подключиться к PLC"""
        if not self._is_configured:
            self.error_occurred.emit("PLC не настроен")
            return False
            
        try:
            result = self.modbus.open()
            if result:
                self._connected = True
                self.connection_status.emit(True)
                self.write_count = 0
                self._write_pending = False
                
                # Запускаем таймер обновления
                self.update_timer.start(200)
                
                if self.debug:
                    print("[PLC_DEBUG] ✅ Подключение к PLC установлено")
                
                return True
            else:
                self._connected = False
                self.connection_status.emit(False)
                
                if self.debug:
                    print("[PLC_DEBUG] ❌ Не удалось подключиться к PLC")
                
                return False
        except Exception as e:
            error_msg = f"Ошибка подключения к PLC: {e}"
            self.error_occurred.emit(error_msg)
            self._connected = False
            self.connection_status.emit(False)
            
            if self.debug:
                print(f"[PLC_DEBUG] ❌ {error_msg}")
            
            return False
            
    def disconnect(self):
        """Отключиться от PLC"""
        self._connected = False
        self._write_pending = False
        self.update_timer.stop()
        
        try:
            self.modbus.close()
            if self.debug:
                print("[PLC_DEBUG] 🔌 Отключено от PLC")
        except Exception as e:
            if self.debug:
                print(f"[PLC_DEBUG] Ошибка при отключении: {e}")
            
        self.connection_status.emit(False)
        
    def is_connected(self) -> bool:
        """Проверить статус подключения"""
        return self._connected and self._is_configured
        
    def _prepare_write_data(self):
        """Подготовить данные для записи"""
        if not self._connected or not self._is_configured:
            return None
            
        with self._lock:
            try:
                # Получаем значения каналов
                values = self.generator.get_values()
                
                # Собираем данные для записи
                write_data = {
                    'registers': [],
                    'channels': [],
                    'timestamp': time.time()
                }
                
                # 1. Аналоговые сигналы (каналы 1-20) - REAL
                start_addr = self.registers['analog_signals']['start_address']
                for i, value in enumerate(values):
                    if i >= 20:
                        break
                    try:
                        val = max(-1000.0, min(1000.0, float(value)))
                        float_bytes = struct.pack('<f', val)
                        reg1, reg2 = struct.unpack('<HH', float_bytes)
                        
                        if 0 <= reg1 <= 65535 and 0 <= reg2 <= 65535:
                            addr = start_addr + i * 2
                            write_data['registers'].append((addr, reg1))
                            write_data['registers'].append((addr + 1, reg2))
                            
                            # Сохраняем для дебага
                            write_data['channels'].append({
                                'index': i,
                                'value': val,
                                'address': addr,
                                'reg1': reg1,
                                'reg2': reg2
                            })
                    except Exception as e:
                        self.error_occurred.emit(f"Ошибка подготовки канала {i+1}: {e}")
                    
                # 2. Управляющие параметры
                ctrl_addr = self.registers['control']['start_address']
                status_word = 0
                for i, channel in enumerate(self.generator.channels):
                    if i >= 20:
                        break
                    if channel.enabled:
                        status_word |= (1 << i)
                
                if 0 <= status_word <= 65535:
                    write_data['registers'].append((ctrl_addr, status_word))
                
                # 3. Статусная информация
                status_addr = self.registers['status']['start_address']
                active_count = sum(1 for ch in self.generator.channels[:20] if ch.enabled)
                if 0 <= active_count <= 65535:
                    write_data['registers'].append((status_addr, active_count))
                
                # Heartbeat (сигнал жизни)
                heartbeat_addr = status_addr + 1
                heartbeat_value = int(time.time() % 32000)
                write_data['registers'].append((heartbeat_addr, heartbeat_value))
                
                return write_data
                
            except Exception as e:
                self.error_occurred.emit(f"Ошибка подготовки данных: {e}")
                return None
                
    def _write_data_to_plc(self, write_data: dict):
        """Выполнить запись данных в PLC (выполняется в отдельном потоке)"""
        if not self._connected or not self._is_configured:
            return
            
        if not write_data:
            return
            
        try:
            # Записываем все регистры
            for addr, value in write_data['registers']:
                self.modbus.write_single_register(addr, value)
            
            # Обновляем счетчик
            self.write_count += 1
            
            # Отправляем сигнал об успешной записи
            self.write_completed.emit(True)
            
            # Отправляем дебаг данные ТОЛЬКО через сигнал (убрали прямой вывод)
            if self.debug and self.write_count % 10 == 0:  # Каждые 10 записей
                debug_info = {
                    'write_count': self.write_count,
                    'timestamp': write_data['timestamp'],
                    'channels': write_data.get('channels', []),
                    'registers': write_data.get('registers', [])
                }
                self.debug_data.emit(debug_info)
                # УБРАЛИ self._print_debug_info(debug_info) ← дублирование
                
        except Exception as e:
            if self._connected:
                self.error_occurred.emit(f"Ошибка записи данных: {e}")
                self.write_completed.emit(False)
                    
    def update_plc_data(self):
        """Обновить данные в PLC (вызывается по таймеру)"""
        if not self._connected or not self._is_configured:
            return
            
        # Подготавливаем данные
        write_data = self._prepare_write_data()
        if not write_data:
            return
            
        # Отправляем на запись в отдельном потоке
        task = Runnable(self._write_data_to_plc, write_data)
        task.signals.error.connect(lambda e: self.error_occurred.emit(f"Ошибка записи: {e}"))
        self.thread_pool.start(task)
            
    def read_plc_data(self, address: int, count: int) -> Optional[List[int]]:
        """Прочитать данные из PLC"""
        if not self._connected or not self._is_configured:
            return None
            
        try:
            return self.modbus.read_holding(address, count)
        except Exception as e:
            if self._connected:
                self.error_occurred.emit(f"Ошибка чтения из PLC: {e}")
            return None
            
    def read_float(self, address: int) -> Optional[float]:
        """Прочитать REAL значение из PLC (2 регистра)"""
        if not self._connected or not self._is_configured:
            return None
            
        try:
            data = self.modbus.read_holding(address, 2)
            if data and len(data) == 2:
                float_bytes = struct.pack('<HH', data[0], data[1])
                return struct.unpack('<f', float_bytes)[0]
            return None
        except Exception as e:
            if self._connected:
                self.error_occurred.emit(f"Ошибка чтения float из PLC: {e}")
            return None
            
    def write_float(self, address: int, value: float) -> bool:
        """Записать REAL значение в PLC (2 регистра)"""
        if not self._connected or not self._is_configured:
            return False
            
        try:
            val = max(-1000.0, min(1000.0, value))
            float_bytes = struct.pack('<f', val)
            reg1, reg2 = struct.unpack('<HH', float_bytes)
            
            if 0 <= reg1 <= 65535 and 0 <= reg2 <= 65535:
                result1 = self.modbus.write_single_register(address, reg1)
                result2 = self.modbus.write_single_register(address + 1, reg2)
                return result1 and result2
            return False
        except Exception as e:
            if self._connected:
                self.error_occurred.emit(f"Ошибка записи float в PLC: {e}")
            return False
            
    def get_register_map(self) -> dict:
        """Получить карту регистров для отображения"""
        return {
            'analog_signals': {
                'start': self.registers['analog_signals']['start_address'],
                'end': self.registers['analog_signals']['start_address'] + 
                       self.registers['analog_signals']['count'] * 2 - 1,
                'description': 'Аналоговые сигналы (REAL)',
                'channels': [f'Канал {i+1}' for i in range(self.registers['analog_signals']['count'])]
            },
            'control': {
                'start': self.registers['control']['start_address'],
                'end': self.registers['control']['start_address'] + 
                       self.registers['control']['count'] - 1,
                'description': 'Управляющие параметры (INT)'
            },
            'status': {
                'start': self.registers['status']['start_address'],
                'end': self.registers['status']['start_address'] + 
                       self.registers['status']['count'] - 1,
                'description': 'Статусная информация (INT)'
            }
        }
        
    def get_last_written_data(self) -> dict:
        """Получить последние записанные данные для отладки"""
        return self.last_written_data
        
    def set_debug(self, enabled: bool):
        """Включить/выключить режим отладки"""
        self.debug = enabled
        if enabled:
            print("[PLC_DEBUG] Режим отладки ВКЛЮЧЕН")
        else:
            print("[PLC_DEBUG] Режим отладки ВЫКЛЮЧЕН")

    def set_write_interval(self, interval: float):
        """Установить интервал записи в PLC"""
        self.write_interval = max(0.01, min(10.0, interval))
        
        # Перезапускаем таймер с новым интервалом
        self.update_timer.stop()
        interval_ms = int(self.write_interval * 1000)
        self.update_timer.start(max(10, interval_ms))
        
        if self.debug:
            print(f"[PLC_DEBUG] Интервал записи изменен: {self.write_interval:.3f} с "
                f"({1.0/self.write_interval:.1f} Гц)")
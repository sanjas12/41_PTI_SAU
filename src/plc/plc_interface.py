import struct
import time
import threading
from typing import List, Optional, Tuple
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from modbus.modbus_client import ModbusClientWrapper
from core.signal_generator import SignalGenerator


class PLCInterface(QObject):
    """Интерфейс для связи с PLC Modicon Premium через Modbus TCP"""
    
    # Сигналы для обновления UI
    data_updated = pyqtSignal(dict)  # Обновлены данные
    connection_status = pyqtSignal(bool)  # Статус подключения
    error_occurred = pyqtSignal(str)  # Ошибка
    
    def __init__(self, generator: SignalGenerator, parent=None):
        super().__init__(parent)
        self.generator = generator
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
        self.write_interval = 0.1
        
        # Поток для фоновой записи
        self.running = False
        self.write_thread = None
        self._lock = threading.Lock()
        self._connected = False  # ← ДОБАВЛЕНО
        
        # Таймер для периодического обновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plc_data)
        # Не запускаем таймер до подключения
        
    def configure(self, host: str, port: int, unit_id: int = 1):
        """Настройка подключения к PLC"""
        try:
            self.modbus.configure(host, port, unit_id)
            self._connected = True
            self.connection_status.emit(True)
            return True
        except Exception as e:
            self.error_occurred.emit(f"Ошибка настройки PLC: {e}")
            self._connected = False
            self.connection_status.emit(False)
            return False
            
    def connect(self) -> bool:
        """Подключиться к PLC"""
        try:
            result = self.modbus.open()
            if result:
                self._connected = True
                self.connection_status.emit(True)
                self.running = True
                # Запускаем поток записи
                self.start_write_thread()
                # Запускаем таймер обновления
                self.update_timer.start(100)
            else:
                self._connected = False
                self.connection_status.emit(False)
            return result
        except Exception as e:
            self.error_occurred.emit(f"Ошибка подключения к PLC: {e}")
            self._connected = False
            self.connection_status.emit(False)
            return False
            
    def disconnect(self):
        """Отключиться от PLC"""
        self.running = False
        self._connected = False
        self.update_timer.stop()
        if self.write_thread and self.write_thread.is_alive():
            self.write_thread.join(timeout=1.0)
        self.modbus.close()
        self.connection_status.emit(False)
        
    def is_connected(self) -> bool:
        """Проверить статус подключения"""
        return self._connected and self.modbus.is_connected()
        
    def start_write_thread(self):
        """Запустить поток для фоновой записи"""
        if self.write_thread and self.write_thread.is_alive():
            return
            
        self.running = True
        self.write_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.write_thread.start()
        
    def _write_loop(self):
        """Цикл фоновой записи данных в PLC"""
        while self.running and self._connected:
            try:
                current_time = time.time()
                if current_time - self.last_write_time >= self.write_interval:
                    self._write_all_data()
                    self.last_write_time = current_time
                time.sleep(0.01)
            except Exception as e:
                self.error_occurred.emit(f"Ошибка в цикле записи: {e}")
                time.sleep(0.1)
                
    def _write_all_data(self):
        """Записать все данные в PLC"""
        if not self._connected:
            return
            
        with self._lock:
            try:
                # Получаем значения каналов
                values = self.generator.get_values()
                
                # Подготавливаем данные для записи
                write_data = []
                
                # 1. Аналоговые сигналы (каналы 1-20) - REAL
                start_addr = self.registers['analog_signals']['start_address']
                for i, value in enumerate(values):
                    if i >= 20:
                        break
                    # Преобразуем float в 2 регистра (32-bit)
                    float_bytes = struct.pack('<f', float(value))
                    reg1, reg2 = struct.unpack('<HH', float_bytes)
                    write_data.append((start_addr + i * 2, reg1))
                    write_data.append((start_addr + i * 2 + 1, reg2))
                    
                # 2. Управляющие параметры
                ctrl_addr = self.registers['control']['start_address']
                status_word = 0
                for i, channel in enumerate(self.generator.channels):
                    if i >= 20:
                        break
                    if channel.enabled:
                        status_word |= (1 << i)
                write_data.append((ctrl_addr, status_word))
                
                # 3. Статусная информация
                status_addr = self.registers['status']['start_address']
                active_count = sum(1 for ch in self.generator.channels[:20] if ch.enabled)
                write_data.append((status_addr, active_count))
                
                # Выполняем запись
                for addr, value in write_data:
                    self.modbus.write_single_register(addr, value)
                    
            except Exception as e:
                self.error_occurred.emit(f"Ошибка записи данных: {e}")
                    
    def update_plc_data(self):
        """Обновить данные в PLC (вызывается по таймеру)"""
        if not self._connected:
            return
            
        try:
            self._write_all_data()
            self.data_updated.emit({
                'timestamp': time.time(),
                'channels': self.generator.get_values()
            })
        except Exception as e:
            self.error_occurred.emit(f"Ошибка обновления данных PLC: {e}")
            
    def read_plc_data(self, address: int, count: int) -> Optional[List[int]]:
        """Прочитать данные из PLC"""
        if not self._connected:
            return None
        try:
            return self.modbus.read_holding(address, count)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка чтения из PLC: {e}")
            return None
            
    def read_float(self, address: int) -> Optional[float]:
        """Прочитать REAL значение из PLC (2 регистра)"""
        if not self._connected:
            return None
        try:
            data = self.modbus.read_holding(address, 2)
            if data and len(data) == 2:
                float_bytes = struct.pack('<HH', data[0], data[1])
                return struct.unpack('<f', float_bytes)[0]
            return None
        except Exception as e:
            self.error_occurred.emit(f"Ошибка чтения float из PLC: {e}")
            return None
            
    def write_float(self, address: int, value: float) -> bool:
        """Записать REAL значение в PLC (2 регистра)"""
        if not self._connected:
            return False
        try:
            float_bytes = struct.pack('<f', value)
            reg1, reg2 = struct.unpack('<HH', float_bytes)
            result1 = self.modbus.write_single_register(address, reg1)
            result2 = self.modbus.write_single_register(address + 1, reg2)
            return result1 and result2
        except Exception as e:
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


class PLCDataConverter:
    """Класс для преобразования данных между Python и PLC"""
    
    @staticmethod
    def float_to_registers(value: float) -> Tuple[int, int]:
        """Преобразовать float в 2 регистра (16-bit)"""
        float_bytes = struct.pack('<f', value)
        reg1, reg2 = struct.unpack('<HH', float_bytes)
        return reg1, reg2
        
    @staticmethod
    def registers_to_float(reg1: int, reg2: int) -> float:
        """Преобразовать 2 регистра в float"""
        float_bytes = struct.pack('<HH', reg1, reg2)
        return struct.unpack('<f', float_bytes)[0]
        
    @staticmethod
    def int_to_registers(value: int) -> Tuple[int, int]:
        """Преобразовать int в 2 регистра (32-bit)"""
        int_bytes = struct.pack('<I', value)
        reg1, reg2 = struct.unpack('<HH', int_bytes)
        return reg1, reg2
        
    @staticmethod
    def registers_to_int(reg1: int, reg2: int) -> int:
        """Преобразовать 2 регистра в int"""
        int_bytes = struct.pack('<HH', reg1, reg2)
        return struct.unpack('<I', int_bytes)[0]
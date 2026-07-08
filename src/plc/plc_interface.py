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
    debug_data = pyqtSignal(dict)  # Дебаг данные
    
    def __init__(self, generator: SignalGenerator, parent=None, debug: bool = False):
        super().__init__(parent)  # ← ВАЖНО: вызываем конструктор QObject
        self.generator = generator
        self.debug = debug
        
        # ИНИЦИАЛИЗИРУЕМ modbus ПЕРВЫМ ДЕЛОМ
        self.modbus = ModbusClientWrapper()  # ← ОБЯЗАТЕЛЬНО
        
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
        self.write_interval = 0.1  # 100ms
        
        # Поток для фоновой записи
        self.running = False
        self.write_thread = None
        self._lock = threading.Lock()
        self._connected = False
        self._is_configured = False
        
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
            if not hasattr(self, 'modbus'):
                self.modbus = ModbusClientWrapper()
                
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
            
            if self.debug:
                print("[PLC_DEBUG] ❌ PLC не настроен")
            
            return False
            
        try:
            if not hasattr(self, 'modbus'):
                self.modbus = ModbusClientWrapper()
                
            result = self.modbus.open()
            if result:
                self._connected = True
                self.connection_status.emit(True)
                self.running = True
                self.write_count = 0
                self.start_write_thread()
                self.update_timer.start(100)
                
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
        self.running = False
        self._connected = False
        self.update_timer.stop()
        
        if self.write_thread and self.write_thread.is_alive():
            self.write_thread.join(timeout=1.0)
            
        try:
            if hasattr(self, 'modbus') and self.modbus:
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
        
    def start_write_thread(self):
        """Запустить поток для фоновой записи"""
        if self.write_thread and self.write_thread.is_alive():
            return
            
        self.running = True
        self.write_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.write_thread.start()
        
        if self.debug:
            print("[PLC_DEBUG] Поток записи запущен")
        
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
                if self._connected:
                    self.error_occurred.emit(f"Ошибка в цикле записи: {e}")
                time.sleep(0.1)
                
    def _write_all_data(self):
        """Записать все данные в PLC"""
        if not self._connected or not self._is_configured:
            return
            
        if not hasattr(self, 'modbus') or not self.modbus:
            self.error_occurred.emit("Modbus клиент не инициализирован")
            return
            
        with self._lock:
            try:
                # Получаем значения каналов
                values = self.generator.get_values()
                
                # Собираем данные для отладки
                debug_info = {
                    'timestamp': time.time(),
                    'channels': [],
                    'registers': [],
                    'write_count': self.write_count + 1
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
                            
                            # Записываем
                            self.modbus.write_single_register(addr, reg1)
                            self.modbus.write_single_register(addr + 1, reg2)
                            
                            # Сохраняем для дебага
                            debug_info['channels'].append({
                                'index': i,
                                'value': val,
                                'address': addr,
                                'reg1': reg1,
                                'reg2': reg2
                            })
                            
                            debug_info['registers'].append({
                                'address': addr,
                                'name': f'Analog_Ch{i+1}_LOW',
                                'value': reg1,
                                'hex': f'0x{reg1:04X}'
                            })
                            debug_info['registers'].append({
                                'address': addr + 1,
                                'name': f'Analog_Ch{i+1}_HIGH',
                                'value': reg2,
                                'hex': f'0x{reg2:04X}'
                            })
                            
                    except Exception as e:
                        self.error_occurred.emit(f"Ошибка записи канала {i+1}: {e}")
                    
                # 2. Управляющие параметры
                ctrl_addr = self.registers['control']['start_address']
                status_word = 0
                for i, channel in enumerate(self.generator.channels):
                    if i >= 20:
                        break
                    if channel.enabled:
                        status_word |= (1 << i)
                
                if 0 <= status_word <= 65535:
                    self.modbus.write_single_register(ctrl_addr, status_word)
                    
                    debug_info['registers'].append({
                        'address': ctrl_addr,
                        'name': 'Channel_Status',
                        'value': status_word,
                        'hex': f'0x{status_word:04X}',
                        'binary': f'{status_word:016b}'
                    })
                
                # 3. Статусная информация
                status_addr = self.registers['status']['start_address']
                active_count = sum(1 for ch in self.generator.channels[:20] if ch.enabled)
                if 0 <= active_count <= 65535:
                    self.modbus.write_single_register(status_addr, active_count)
                    
                    debug_info['registers'].append({
                        'address': status_addr,
                        'name': 'Active_Channels',
                        'value': active_count,
                        'hex': f'0x{active_count:04X}'
                    })
                
                # Heartbeat (сигнал жизни)
                heartbeat_addr = status_addr + 1
                heartbeat_value = int(time.time() % 32000)
                self.modbus.write_single_register(heartbeat_addr, heartbeat_value)
                
                debug_info['registers'].append({
                    'address': heartbeat_addr,
                    'name': 'Heartbeat',
                    'value': heartbeat_value,
                    'hex': f'0x{heartbeat_value:04X}'
                })
                
                # Сохраняем последние данные для дебага
                self.last_written_data = debug_info
                self.write_count += 1
                
                # Отправляем сигнал дебага
                if self.debug:
                    self.debug_data.emit(debug_info)
                    self._print_debug_info(debug_info)
                
            except Exception as e:
                if self._connected:
                    self.error_occurred.emit(f"Ошибка записи данных: {e}")
                    
    def _print_debug_info(self, debug_info: dict):
        """Вывести отладочную информацию в консоль"""
        print("\n" + "=" * 80)
        print(f"📊 ПЕРЕДАЧА ДАННЫХ В PLC #{debug_info['write_count']}")
        print(f"⏰ Время: {time.strftime('%H:%M:%S', time.localtime(debug_info['timestamp']))}")
        print("=" * 80)
        
        # Аналоговые каналы
        if debug_info['channels']:
            print("\n📈 АНАЛОГОВЫЕ СИГНАЛЫ (REAL):")
            for ch in debug_info['channels']:
                print(f"  Канал {ch['index']+1:2d}: {ch['value']:8.2f} → "
                      f"%MW{ch['address']:3d} (0x{ch['reg1']:04X}) "
                      f"%MW{ch['address']+1:3d} (0x{ch['reg2']:04X})")
        else:
            print("\n📈 Нет аналоговых сигналов")
        
        # Регистры
        if debug_info['registers']:
            print("\n📝 ЗАПИСАННЫЕ РЕГИСТРЫ:")
            for reg in debug_info['registers']:
                if 'binary' in reg:
                    print(f"  %MW{reg['address']:3d} {reg['name']:16s} = "
                          f"{reg['value']:5d} {reg['hex']:6s} ({reg['binary']})")
                else:
                    print(f"  %MW{reg['address']:3d} {reg['name']:16s} = "
                          f"{reg['value']:5d} {reg['hex']:6s}")
        else:
            print("\n📝 Нет записанных регистров")
        
        print("=" * 80)
        print(f"✅ Всего записей: {len(debug_info.get('registers', []))}")
        print("=" * 80 + "\n")
                    
    def update_plc_data(self):
        """Обновить данные в PLC (вызывается по таймеру)"""
        if not self._connected or not self._is_configured:
            return
            
        if not hasattr(self, 'modbus') or not self.modbus:
            return
            
        try:
            self._write_all_data()
            self.data_updated.emit({
                'timestamp': time.time(),
                'channels': self.generator.get_values()
            })
        except Exception as e:
            if self._connected:
                self.error_occurred.emit(f"Ошибка обновления данных PLC: {e}")
            
    def read_plc_data(self, address: int, count: int) -> Optional[List[int]]:
        """Прочитать данные из PLC"""
        if not self._connected or not self._is_configured:
            return None
            
        if not hasattr(self, 'modbus') or not self.modbus:
            self.error_occurred.emit("Modbus клиент не инициализирован")
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
            
        if not hasattr(self, 'modbus') or not self.modbus:
            self.error_occurred.emit("Modbus клиент не инициализирован")
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
            
        if not hasattr(self, 'modbus') or not self.modbus:
            self.error_occurred.emit("Modbus клиент не инициализирован")
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
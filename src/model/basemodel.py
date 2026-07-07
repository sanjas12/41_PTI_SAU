from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd


@dataclass
class Model:
    """Класс модели данных для хранения состояния приложения."""
    # Параметры файла
    encoding: Optional[str] = None
    delimiter: Optional[str] = None
    decimal: Optional[str] = None
    first_filename: Optional[str] = None
    filenames: List[str] = field(default_factory=list)
    selected_filter_file: Optional[str] = None
    
    # Флаги состояния
    is_kol_1_2: bool = False
    is_time: bool = False
    is_ms: bool = False
    ready_plot: bool = False
    ready_to_analysis: bool = False
    
    # Данные
    df: Optional[pd.DataFrame] = None
    dict_all_signals: Dict[str, int] = field(default_factory=dict)
    dict_base_signals: Dict[str, int] = field(default_factory=dict)
    dict_secondary_signals: Dict[str, int] = field(default_factory=dict)
    time_signal: Optional[str] = None

    # Отображение графиков 
    step: Optional[int] = None      # выборка

    def clear_state(self) -> None:
        """Сбрасывает состояние модели к начальным значениям."""
        # self.encoding = None
        # self.delimiter = None
        # self.decimal = None
        # self.first_filename = None
        # self.filenames = []
        # self.is_kol_1_2 = False
        # self.is_time = False
        # self.is_ms = False
        self.df = None
        self.dict_all_signals.clear()
        self.dict_base_signals.clear()
        self.dict_secondary_signals.clear()
        # self.time_signal = None
        self.ready_plot = False
        self.step = None
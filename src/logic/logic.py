import logging
import os
import gzip
from pathlib import Path
import sys
import chardet
import pandas as pd
from typing import List, Dict, Union
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config.config as cfg
from model.basemodel import Model
from ui.main_window import MainWindowUI


class MainLogic:
    """Основной класс логики приложения"""

    def __init__(self, ui: MainWindowUI):
        self.model = Model()
        self.ui = ui

        self._setup_connections()

    def _setup_connections(self) -> None:
        """Настраивает соединения сигналов и слотов"""
        # кнопка Open files
        self.ui.gb_signals.btn_first.clicked.connect(
            self.load_and_prepare_data
        )
        
        # кнопка Построить графики
        self.ui.button_graph.clicked.connect(
            self.plot_graph
        )
        
        for group_box, dict_signal in zip(
            (self.ui.gb_base_axe, self.ui.gb_secondary_axe),
            (self.model.dict_base_signals, self.model.dict_secondary_signals),
        ):
            group_box.btn_first.clicked.connect(
                lambda _, gb=group_box, ds=dict_signal: self.add_signal(gb, ds)
            )
            group_box.btn_second.clicked.connect(
                lambda _, gb=group_box, ds=dict_signal: self.remove_signal(gb, ds)
            )

 


def test_MainLogic():

    app = QApplication(sys.argv)

    main_window = MainWindowUI("Тест Main Logic")
    MainLogic(main_window)

    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":

    # --- Тест FileHandler класса ---
    # test_FileHandker()

    # --- Тест MainLogic класса ---
    test_MainLogic()

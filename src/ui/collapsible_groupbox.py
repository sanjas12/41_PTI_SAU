from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtCore import Qt


class CollapsibleGroupBox(QGroupBox):
    """GroupBox с возможностью сворачивания/разворачивания"""
    
    def __init__(self, title, parent=None, collapsed=False):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(not collapsed)
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
        self.toggled.connect(self.on_toggled)
        self._collapsed = collapsed
        self._content_widgets = []
        
    def add_content_widget(self, widget):
        """Добавить виджет в содержимое GroupBox"""
        self._content_widgets.append(widget)
        
    def on_toggled(self, checked):
        """Обработчик изменения состояния"""
        self._collapsed = not checked
        self.update_content_visibility(checked)
        
    def update_content_visibility(self, visible):
        """Обновить видимость содержимого"""
        for widget in self._content_widgets:
            widget.setVisible(visible)
            
    def set_collapsed(self, collapsed):
        """Установить состояние свернуто/развернуто"""
        self.setChecked(not collapsed)
        self._collapsed = collapsed
        self.update_content_visibility(not collapsed)
        
    def is_collapsed(self):
        """Проверить, свернут ли GroupBox"""
        return self._collapsed
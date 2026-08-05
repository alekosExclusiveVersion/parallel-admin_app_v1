"""
gui/styles.py

Общий QSS-стиль для всего приложения.
Используется MainWindow, LoginDialog и другими виджетами.
"""

from __future__ import annotations

SHARED_STYLESHEET = """
QWidget#MainWindow{
    background:#f4f6f8;
}

QFrame{
    background:white;
    border:1px solid #e3e8ef;
    border-radius:10px;
}

QLabel{
    color:#0f172a;
    background:transparent;
    border:none;
}

QLabel#SectionTitle{
    font-size:13px;
    font-weight:600;
    color:#334155;
    border:none;
    background:transparent;
}


/* --- Status bar (full-bleed) --- */
QFrame#StatusBar{
    background:#0f172a;
    border:none;
    border-radius:0;
}

QFrame#StatusBar QLabel{
    border:none;
    background:transparent;
}

QFrame#StatusBar QProgressBar{
    background:rgba(255,255,255,0.12);
    border:none;
    border-radius:4px;
    min-height:6px;
    max-height:6px;
    text-align:center;
}

QFrame#StatusBar QProgressBar::chunk{
    background:#3b82f6;
    border-radius:4px;
}

/* --- Inputs --- */
QTreeWidget,
QTextEdit,
QPlainTextEdit,
QTableWidget,
QLineEdit,
QComboBox,
QAbstractSpinBox{
    background:white;
    border:1px solid #e3e8ef;
    border-radius:6px;
    color:#0f172a;
    font-size:13px;
    padding:4px;
    selection-background-color:#eff6ff;
    selection-color:#0f172a;
}

QTreeWidget::item{
    padding:3px 2px;
    border-radius:4px;
}

QTreeWidget::item:selected{
    background:#eff6ff;
    color:#0f172a;
}

QTreeWidget::item:hover{
    background:#f8fafc;
}

QTreeWidget:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QLineEdit:focus,
QComboBox:focus{
    border:1px solid #2563eb;
}

QComboBox{
    padding:4px 28px 4px 10px;
}

QComboBox QAbstractItemView{
    background:white;
    border:1px solid #e3e8ef;
    border-radius:8px;
    outline:none;
    padding:6px;
    selection-background-color:#eff6ff;
    selection-color:#0f172a;
}

QComboBox QAbstractItemView::item{
    border:none;
    border-radius:6px;
}

QComboBox QAbstractItemView::item:hover{
    background:#f1f5f9;
}

QComboBox QFrame{
    background:white;
    border:none;
    border-radius:0;
}

/* --- Toolbar --- */
QToolBar{
    background:white;
    border:1px solid #e3e8ef;
    border-radius:10px;
    padding:4px;
    spacing:4px;
}

QToolBar::separator{
    width:1px;
    background:#e2e8f0;
    margin:4px 2px;
}

QToolBar QToolButton{
    border:none;
    border-radius:6px;
    background:transparent;
    padding:6px;
    color:#64748b;
}

QToolBar QToolButton:hover{
    background:#f1f5f9;
    color:#0f172a;
}

QToolBar QToolButton:pressed{
    background:#e2e8f0;
}

QToolBar QToolButton:disabled{
    color:#cbd5e1;
}

/* --- Icon buttons --- */
QToolButton#btn_icon{
    border:none;
    border-radius:6px;
    background:transparent;
    padding:4px 6px;
    color:#475569;
}

QToolButton#btn_icon:hover{
    background:#eff6ff;
    color:#2563eb;
}

QToolButton#btn_icon:disabled{
    background:transparent;
    color:#cbd5e1;
}

/* --- Buttons --- */
QPushButton{
    min-height:28px;
    border:1px solid #2563eb;
    border-radius:6px;
    background:white;
    color:#2563eb;
    font-weight:600;
    font-size:13px;
    text-align:center;
    padding:0 12px;
}

QPushButton:hover{
    background:#eff6ff;
    border-color:#1d4ed8;
    color:#1d4ed8;
}

QPushButton:pressed{
    background:#dbeafe;
    border-color:#1e40af;
    color:#1e40af;
}

QPushButton:disabled{
    background:#f1f5f9;
    border-color:#cbd5e1;
    color:#94a3b8;
}

QPushButton:focus{
    border:1px solid #2563eb;
}

QPushButton#btn_primary{
    background:#2563eb;
    border:1px solid #2563eb;
    color:white;
    font-weight:600;
}

QPushButton#btn_primary:hover{
    background:#1d4ed8;
    border-color:#1d4ed8;
    color:white;
}

QPushButton#btn_primary:pressed{
    background:#1e40af;
    color:white;
}

QPushButton#btn_primary:disabled{
    background:#f1f5f9;
    border-color:#cbd5e1;
    color:#94a3b8;
}

QPushButton#btn_danger{
    background:white;
    border:1px solid #dc2626;
    color:#dc2626;
    font-weight:600;
}

QPushButton#btn_danger:hover{
    background:#fef2f2;
    border-color:#b91c1c;
    color:#b91c1c;
}

QPushButton#btn_danger:pressed{
    background:#fee2e2;
    border-color:#991b1b;
    color:#991b1b;
}

QPushButton#btn_danger:disabled{
    background:#f1f5f9;
    border-color:#cbd5e1;
    color:#94a3b8;
}

/* --- Checkbox --- */
QCheckBox{
    font-size:13px;
    color:#0f172a;
    margin:0 6px;
}

QCheckBox::indicator{
    width:16px;
    height:16px;
    border:1px solid #cbd5e1;
    border-radius:4px;
    background:white;
}

QCheckBox::indicator:hover{
    border-color:#2563eb;
}

QCheckBox::indicator:checked{
    background:#2563eb;
    border-color:#2563eb;
}

/* --- Table headers --- */
QHeaderView::section{
    background:#f8fafc;
    border:none;
    border-bottom:1px solid #e2e8f0;
    border-right:1px solid #eef2f7;
    padding:6px 8px;
    font-size:12px;
    font-weight:600;
    color:#475569;
}

QHeaderView::section:hover{
    background:#eef2f7;
}

/* --- Tabs --- */
QTabWidget::pane{
    border:none;
    border-radius:0;
    background:white;
}

QStackedWidget{
    border:none;
    border-radius:0;
    background:white;
}

QFrame#TabPage{
    border:none;
    border-radius:0;
}

QTabBar::tab{
    background:transparent;
    padding:7px 16px;
    color:#64748b;
    border:none;
    border-bottom:2px solid transparent;
    font-size:13px;
}

QTabBar::tab:first{
    margin-left:6px;
}

QTabBar::tab:top{
    margin-top:4px;
}

QTabBar::tab:selected{
    color:#2563eb;
    border-bottom:2px solid #2563eb;
    font-weight:600;
}

QTabBar::tab:hover:!selected{
    color:#0f172a;
}

/* --- Progress (default) --- */
QProgressBar{
    border:1px solid #e3e8ef;
    border-radius:5px;
    background:white;
    text-align:center;
    min-height:20px;
}

QProgressBar::chunk{
    background:#2563eb;
    border-radius:4px;
}

/* --- Menu --- */
QMenu{
    background:white;
    border:1px solid #e3e8ef;
    border-radius:8px;
    padding:6px;
}

QMenu::item{
    padding:6px 22px;
    border-radius:6px;
    color:#0f172a;
}

QMenu::item:selected{
    background:#eff6ff;
    color:#1d4ed8;
}

QMenu::separator{
    height:1px;
    background:#eef2f7;
    margin:4px 8px;
}

/* --- Scrollbars --- */
QScrollBar:vertical{
    background:transparent;
    width:10px;
    margin:2px;
}

QScrollBar::handle:vertical{
    background:#cbd5e1;
    border-radius:4px;
    min-height:30px;
}

QScrollBar::handle:vertical:hover{
    background:#94a3b8;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical{
    height:0;
}

QScrollBar:horizontal{
    background:transparent;
    height:10px;
    margin:2px;
}

QScrollBar::handle:horizontal{
    background:#cbd5e1;
    border-radius:4px;
    min-width:30px;
}

QScrollBar::handle:horizontal:hover{
    background:#94a3b8;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal{
    width:0;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal{
    background:transparent;
}
"""

# Стиль для LoginDialog — переопределяет только специфичные для диалога части,
# остальное берётся из SHARED_STYLESHEET.
LOGIN_DIALOG_STYLESHEET = (
    SHARED_STYLESHEET
    + """
QDialog{
    background:#f4f6f8;
}

QLabel#DialogTitle{
    font-size:14px;
    font-weight:700;
    color:#0f172a;
}
"""
)

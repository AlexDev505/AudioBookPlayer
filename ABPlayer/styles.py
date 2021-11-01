import os
import typing as ty

__all__ = ["get_style_sheet", "DEFAULT_STYLESHEET"]

DEFAULT_STYLESHEET = """QWidget {
    color: rgb(215, 214, 217);
}

QFrame {
    border: none;
}

/*  BUTTONS */
QPushButton {
    background-color: rgba(0, 0, 0, 0);
    color: rgb(142, 146, 151);
    border-radius: 5px;
    border: none;
}
QPushButton:hover {
    background-color: rgb(52, 55, 60);
    border-radius: 5px;
}
QPushButton:pressed {
    background-color: rgb(55, 57, 63);
}

/* LINE EDIT */
QLineEdit {
    background-color: rgb(64, 68, 75);
    border-radius: 5px;
    padding-left:3px;
    border: none;
}

/* COMBOBOX */
QComboBox {
    background-color: rgb(64, 68, 75);
    border-radius: 5px;
    border: none;
}
QComboBox QAbstractItemView {
    selection-background-color: rgb(50, 53, 59);
}
QComboBox::drop-down {
    border: none;
}
QComboBox::down-arrow {
    image: url(:/other/angle_down.svg);
    border: none;
    width: 35px;
    height: 35px;
    padding-right: 20px;
}

/*  TOOLTIP */
QToolTip {
    background-color: rgb(29, 30, 34);
    color: rgb(142, 146, 151);
    border: none;
    border-left: 2px solid rgb(142, 146, 151);
    text-align: left;
    padding: 4px;
}

/* SLIDER */
QSlider {
    background-color: rgb(41, 43, 47);
}
QSlider::groove:horizontal {
    background: rgb(64, 68, 75);
    border-radius: 1px;
}
QSlider::sub-page:horizontal {
    background: rgb(142, 146, 151);
    border-radius: 1px;
    height: 40px;
}
QSlider::add-page:horizontal {
    background: rgb(64, 68, 75);
    border-radius: 1px;
    height: 40px;
}
QSlider::handle:horizontal {
    background: rgb(142, 146, 151);
    border: 0px;
    width: 5px;
    margin-top: 0px;
    margin-bottom: 0px;
    border-radius: 1px;
}

/* TAB WIDGET */
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: rgba(0, 0, 0, 0);
    padding: 10px;
    font-weight: normal;
    border: none;
}
QTabBar::tab:selected {
    background: rgba(0, 0, 0, 0);
    border-top: 2px solid rgb(255, 255, 255);
    font-weight: bold;
    margin-bottom: -1px;
}

/*SCROLLBAR */
QScrollArea {
    border: none;
}
/* VERTICAL SCROLLBAR */
QScrollBar:vertical {
    border: none;
    width: 8px;
    margin: 15px 0px 15px 0px;
}
/* HANDLE BAR VERTICAL */
QScrollBar::handle:vertical {
    background-color: rgb(32, 34, 37);
    min-height: 30px;
    border-radius: 4px;
}
/* BTN TOP */
QScrollBar::sub-line:vertical {
    height: 0px;
}
/* BTN BOTTOM */
QScrollBar::add-line:vertical {
    height: 0px;
}
/* RESET ARROW */
QScrollBar::up-arrow:vertical
QScrollBar::down-arrow:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: rgb(46, 51, 56);
    border-radius: 4px;
}

/* PROGRESS BAR */
QProgressBar {
    background-color: rgb(64, 68, 75);
    border: none;
    border-radius: 5px;
    color: black;
}
QProgressBar::chunk {
    background-color: rgb(142, 146, 151);
    border-radius :5px;
}

/* LINE */
Line {
    background-color: rgb(45, 47, 50);
}


/* INPUT FIELD */
#searchField QLineEdit,
#searchField_2 QLineEdit {
    border-radius: 0px;
    border-top-left-radius: 5px;
    border-bottom-left-radius: 5px;
}
#searchField QPushButton,
#searchField_2 QPushButton,
#sortAuthorFrame QPushButton,
#sortByFrame QPushButton {
    background-color: rgb(64, 68, 75);
    border-radius: 0px;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    border-left: 1px solid rgb(142, 146, 151);
    padding-left: 2px;
    padding-right: 2px;
}
#searchField QPushButton:hover,
#searchField_2 QPushButton:hover,
#sortAuthorFrame QPushButton:hover,
#sortByFrame QPushButton:hover {
    background-color: rgb(50, 53, 59);
}
#searchField QPushButton:pressed,
#searchField_2 QPushButton:pressed,
#sortAuthorFrame QPushButton:pressed,
#sortByFrame QPushButton:pressed {
    margin-bottom: -1px;
}
#sortAuthorFrame QComboBox,
#sortByFrame QComboBox {
    border-radius: 0px;
    border-top-left-radius: 5px;
    border-bottom-left-radius: 5px;
}

/* TOP FRAME */
#topFrame {
    background-color: rgb(32, 34, 37);
}
#logo {
    color: rgb(142, 146, 151);
}

/*  MENU */
#menuFrame {
    background-color: rgb(32, 34, 37);
}
#menuFrame * {
    text-align: left;
}
#menuFrame QPushButton {
    padding: 6px 10px 6px 10px;
}

/*  CONTENT */
#content,
#stackedWidget,
#libraryPage,
#bookPage,
#addBookPage,
#infoPage,
#settingsPage {
    background-color: rgb(32, 34, 37);
}
#libraryPageContent,
#bookPageContent,
#addBookPageContent,
#infoPageContent,
#settingsPageContent {
    background-color: rgb(54, 57, 63);
    border-top-left-radius: 15px;
}
/* BUTTONS */
#infoPageContent QPushButton, #needDownloadingPage QPushButton {
    padding: 10px;
    background-color: rgb(47, 49, 54);
    border: 1px solid rgb(41, 43, 47);
    border-radius: 5px;
}
/* LIBRARY PAGE CONTENT */
#libraryPageContent QTabWidget * {
    background-color: rgb(54, 57, 63);
}
/* BOOK PAGE CONTENT */
#bookItems {
    border: 2px solid rgb(64, 68, 75);
    border-radius: 3px;
}
#bookPageContent,
#description,
#bookItems * {
    background-color: rgb(54, 57, 63);
}
#bookPageContent QPushButton:hover {
    background-color: rgb(50, 53, 59);
}
#bookPageContent QPushButton:pressed {
    margin-bottom: -1px;
}

/* LIBRARY */
#libraryFrame {
    border-top: 2px solid rgb(41, 43, 47);
    border-radius: 2px;
}
#allBooksLayout QWidget,
#inProgressBooksLayout QWidget,
#listenedBooksLayout QWidget {
    background-color: rgba(255, 255, 255, 0);
    color: rgb(215, 214, 217);
}

#allBooksLayout #frame,
#inProgressBooksLayout #frame,
#listenedBooksLayout #frame {
    background-color: rgb(47, 49, 54);
    border-radius:10px;
}

#allBooksLayout QPushButton,
#inProgressBooksLayout QPushButton,
#listenedBooksLayout QPushButton {
    background-color: rgba(0, 0, 0, 0);
    color: rgb(142, 146, 151);
    border-radius: 5px;
    border: none;
}
#allBooksLayout QPushButton:hover,
#inProgressBooksLayout QPushButton:hover,
#listenedBooksLayout QPushButton:hover {
    background-color: rgb(52, 55, 60);
    border-radius: 5px;
}
#allBooksLayout QPushButton:pressed,
#inProgressBooksLayout QPushButton:pressed,
#listenedBooksLayout QPushButton:pressed {
    background-color: rgb(55, 57, 63);
}
/* FILTERS PANEL */
#libraryFiltersPanel {
    background-color: rgb(47, 49, 54);
    border-top-left-radius: 15px;
}
#libraryFiltersPanel QFrame {
    background-color: rgb(47, 49, 54);
}
#toggleBooksFilterPanelBtn {
    background-color: rgb(54, 57, 63);
    border-radius: 0px;
    border-top-left-radius: 15px;
}
#toggleBooksFilterPanelBtn:hover {
    background-color: rgb(50, 53, 59);
}

/* PLAYER */
/* PLAYER BTNS */
#playerBtns QPushButton {
    background-color: rgb(64, 68, 75);
    padding: 5px 3px 5px 3px;
}
#playerBtns QPushButton:hover {
    background-color: rgb(58, 62, 68);
}
/* PAGES */
#playerPage QScrollBar:vertical {
    margin: 0px;
 }
#playerContent,
#playerPage,
#needDownloadingPage,
#downloadingPage {
    background-color: rgb(54, 57, 63);
}
#needDownloadingPage,
#downloadingPage{
    border: 2px solid rgb(64, 68, 75);
    border-radius: 3px;
}
/* ITEMS */
#bookItems QSlider {
    border-bottom: 2px solid rgb(64, 68, 75);
}
#playerPage QSlider::handle:horizontal {
    background-color: rgba(64, 68, 75, 0);
}
#bookItems QSlider::sub-page:horizontal {
    background: rgb(142, 146, 151);
}
#bookItems QSlider::add-page:horizontal {
    background: rgb(54, 57, 63);
}

/*  CONTROL PANEL */
#controlPanel,
#controlPanel QFrame {
    background-color: rgb(41, 43, 47);
}
"""

styles: ty.Dict[str, str] = {}
for root, _, files in os.walk(os.path.join(os.environ["APP_DIR"], "styles")):
    for file in files:
        if file.endswith(".qss"):
            styles[file.split(".qss")[0]] = os.path.join(root, file)


def get_style_sheet(name: str) -> ty.Union[str, None]:
    file_path = styles.get(name)
    if file_path:
        with open(file_path, encoding="utf-8") as f:
            return f.read()

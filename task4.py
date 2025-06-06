import random
import time
import json
import os

from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

LEVELS = (
    (8, 10),
    (16, 40),
    (24, 99),
)

CELL_SIZES = {
    0: 32,
    1: 24,
    2: 20
}

RECORDS_FILE = "./files/records.json"

IMG_BOMB = QImage("./images/bomb.png")
IMG_CLOCK = QImage("./images/clock.png")
IMG_START = QImage("./images/rocket.png")
IMG_FLAG = QImage("./images/flag.png")

STATUS_READY = 0
STATUS_PLAY = 1
STATUS_FAILED = 2
STATUS_SUCCESS = 3

STATUS_ICONS = {
    STATUS_READY: "./images/plus.png",
    STATUS_PLAY: "./images/smiley.png",
    STATUS_FAILED: "./images/cross.png",
    STATUS_SUCCESS: "./images/smiley-lol.png"
}

class Cell(QWidget):
    expandable = pyqtSignal(int, int)
    clicked = pyqtSignal()
    game_over = pyqtSignal()
    flagged = pyqtSignal(bool)
    chorded = pyqtSignal(int, int)

    def __init__(self, x, y):
        super().__init__()
        self.setFixedSize(20, 20)

        self.x = x
        self.y = y

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = event.rect()

        if self.is_end:
            inner = Qt.GlobalColor.black
        elif self.is_revealed:
            inner = self.palette().color(QPalette.ColorRole.NColorRoles.Window)
        else:
            inner = Qt.GlobalColor.lightGray
        outer = Qt.GlobalColor.gray
        p.fillRect(r, QBrush(inner))
        pen = QPen(outer)
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRect(r)

        if self.is_revealed:
            if self.is_mine:
                pixmap_bomb = QPixmap.fromImage(IMG_BOMB).scaled(
                    self.width(), self.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                p.drawPixmap(r, pixmap_bomb)
            elif self.is_start:
                pixmap_start = QPixmap.fromImage(IMG_START).scaled(
                    self.width(), self.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                p.drawPixmap(r, pixmap_start)
            elif self.mines_around > 0:
                color_map = {
                    1: Qt.GlobalColor.blue,
                    2: Qt.GlobalColor.darkRed,
                    3: Qt.GlobalColor.darkMagenta,
                    4: Qt.GlobalColor.darkGreen,
                    5: Qt.GlobalColor.red,
                    6: Qt.GlobalColor.darkCyan,
                    7: Qt.GlobalColor.gray,
                    8: Qt.GlobalColor.black
                }
                pen = QPen(color_map.get(self.mines_around, Qt.GlobalColor.black))
                p.setPen(pen)
                f = p.font()
                f.setBold(True)
                p.setFont(f)
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(self.mines_around))
        elif self.is_flagged:
            pixmap_flag = QPixmap.fromImage(IMG_FLAG).scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            p.drawPixmap(r, pixmap_flag)

    def reset(self):
        self.is_start = False
        self.is_end = False
        self.is_mine = False
        self.mines_around = 0
        self.is_revealed = False
        self.is_flagged = False
        self.first_click_done = False
        self.update()

    def click(self):
        if not self.is_revealed and not self.is_flagged:
            self.reveal()

    def reveal(self):
        if not self.is_revealed:
            self.reveal_self()
            if self.mines_around == 0:
                self.expandable.emit(self.x, self.y)
            if self.is_mine:
                self.is_end = True
                self.game_over.emit()

    def reveal_self(self):
        self.is_revealed = True
        self.update()

    def mouseReleaseEvent(self, event):
        self.clicked.emit()
        if event.button() == Qt.MouseButton.LeftButton:
            self.click()
        elif event.button() == Qt.MouseButton.RightButton:
            if not self.is_revealed:
                self.toggle_flag()
            else:
                self.chorded.emit(self.x, self.y)
        self.clicked.emit()

    def toggle_flag(self):
        self.is_flagged = not self.is_flagged
        self.update()
        self.flagged.emit(self.is_flagged)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.level = 0
        self.board_size, self.mines_count = LEVELS[self.level]

        self.records = self.load_records()
        self.best_time_label = QLabel("Best: ---")
        font = self.best_time_label.font()
        font.setPointSize(12)
        self.best_time_label.setFont(font)
        self.best_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setWindowTitle("Minesweeper")
        self.setFixedSize(300, 300)
        self.initUI()
        self.init_grid()
        self.update_status(STATUS_READY)
        self.first_click_done = False
        self._timer = QTimer()
        self._timer.timeout.connect(self.update_timer)
        self._timer.start(1000)
        self.reset()
        self.setFixedSize(self.sizeHint())
        self.show()

    def initUI(self):
        central_widget = QWidget()

        self.level_selector = QGroupBox("Level")
        level_layout = QHBoxLayout()

        self.radio_buttons = []
        level_names = ["Easy", "Medium", "Hard"]
        for i, name in enumerate(level_names):
            rb = QRadioButton(name)
            rb.toggled.connect(self.on_level_changed)
            level_layout.addWidget(rb)
            self.radio_buttons.append(rb)

        self.radio_buttons[self.level].setChecked(True)
        self.level_selector.setLayout(level_layout)

        toolbar = QHBoxLayout()
        self.mines = QLabel(str(self.mines_count))
        self.mines.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clock = QLabel("000")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = self.mines.font()
        font.setPointSize(24)
        font.setWeight(75)
        self.mines.setFont(font)
        self.clock.setFont(font)

        self.button = QPushButton()
        self.button.setFixedSize(32, 32)
        self.button.setIconSize(QSize(32, 32))
        self.button.setIcon(QIcon(STATUS_ICONS[STATUS_PLAY]))
        self.button.setFlat(True)
        self.button.pressed.connect(self.button_pressed)

        l = QLabel()
        l.setPixmap(QPixmap.fromImage(IMG_BOMB))
        l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(l)
        toolbar.addWidget(self.mines)
        toolbar.addWidget(self.button)
        toolbar.addWidget(self.clock)

        l = QLabel()
        l.setPixmap(QPixmap.fromImage(IMG_CLOCK))
        l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(l)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.level_selector)
        main_layout.addLayout(toolbar)

        self.grid = QGridLayout()
        self.grid.setSpacing(5)
        main_layout.addLayout(self.grid)

        self.best_time_label = QLabel("Best: ---")
        font = self.best_time_label.font()
        font.setPointSize(12)
        self.best_time_label.setFont(font)
        self.best_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.best_time_label)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def init_grid(self):
        cell_size = CELL_SIZES[self.level]
        for x in range(self.board_size):
            for y in range(self.board_size):
                cell = Cell(x, y)
                cell.setFixedSize(cell_size, cell_size)
                self.grid.addWidget(cell, x, y)
                cell.expandable.connect(self.expand_reveal)
                cell.clicked.connect(self.handle_click)
                cell.game_over.connect(self.game_over)
                cell.flagged.connect(self.handle_flag)
                cell.chorded.connect(self.handle_chord)

    def reset(self):
        self.mines_count = LEVELS[self.level][1]
        self.mines.setText(f"{self.mines_count:03d}")
        self.clock.setText("000")

        level_key = self.get_level_key()
        best_time = self.records.get(level_key)
        self.best_time_label.setText(f"Best: {best_time if best_time else '---'}")

        for _, _, cell in self.get_all_cells():
            cell.reset()

        mine_positions = self.set_mines()
        self.calc_mines_around()
        # self.set_start()

    def get_cell(self, x, y):
        return self.grid.itemAtPosition(x, y).widget()

    def get_all_cells(self):
        for x in range(self.board_size):
            for y in range(self.board_size):
                yield (x, y, self.get_cell(x, y))

    def set_mines(self):
        positions = []
        while len(positions) < self.mines_count:
            x = random.randint(0, self.board_size - 1)
            y = random.randint(0, self.board_size - 1)
            if (x, y) not in positions:
                self.get_cell(x, y).is_mine = True
                positions.append((x, y))
        return positions
    
    def calc_mines_around(self):
        for x, y, cell in self.get_all_cells():
            cell.mines_around = self.get_mines_around(x, y)

    def get_mines_around(self, x, y):
        cells = [cell for _, _, cell in self.get_around_cells(x, y)]
        return sum(1 if cell.is_mine else 0 for cell in cells)
    
    def get_around_cells(self, x, y):
        positions = []
        for xi in range(max(0, x - 1), min(x + 2, self.board_size)):
            for yi in range(max(0, y - 1), min(y + 2, self.board_size)):
                positions.append((xi, yi, self.get_cell(xi, yi)))
        return positions
    
    def set_start(self):
        empty_cells = [
            cell
            for x, y, cell in self.get_all_cells()
            if not cell.is_mine and cell.mines_around == 0
        ]
        start_cell = random.choice(empty_cells)
        start_cell.is_start = True

        for _, _, cell in self.get_around_cells(start_cell.x, start_cell.y):
            if not cell.is_mine:
                cell.click()

    def expand_reveal(self, x, y):
        for _, _, cell in self.get_revealable_cells(x, y):
            cell.reveal()
    
    def get_revealable_cells(self, x, y, force=False):
        for xi, yi, cell in self.get_around_cells(x, y):
            if (force or not cell.is_mine and not cell.is_flagged and not cell.is_revealed):
                yield (xi, yi, cell)

    def update_status(self, status):
        self.status = status
        self.button.setIcon(QIcon(STATUS_ICONS[self.status]))

    def handle_click(self):
        sender = self.sender()
        x, y = sender.x, sender.y

        if self.status == STATUS_READY:
            self.update_status(STATUS_PLAY)
            self._timer_start = int(time.time())
        
        if not self.first_click_done:
            self.place_mines_after_first_click(x, y)
            self.first_click_done = True

        self.check_win()

    def update_timer(self):
        if self.status == STATUS_PLAY:
            n_seconds = int(time.time()) - self._timer_start
            self.clock.setText(f"{n_seconds:03d}")

    def game_over(self):
        self.update_status(STATUS_FAILED)
        self.reveal_grid()

    def reveal_grid(self):
        for _, _, cell in self.get_all_cells():
            if not (cell.is_flagged and cell.is_mine):
                cell.reveal_self()

    def handle_flag(self, flagged):
        self.mines_count += -1 if flagged else +1
        self.mines.setText(f"{self.mines_count:03d}")

    def check_win(self):
        if self.mines_count == 0:
            if all(cell.is_revealed or cell.is_flagged for _, _, cell in self.get_all_cells()):
                self.finish_game()
        else:
            unrevealed = []
            for _, _, cell in self.get_all_cells():
                if not cell.is_revealed and not cell.is_flagged:
                    unrevealed.append(cell)
                    if len(unrevealed) > self.mines_count or not cell.is_mine:
                        return
            if len(unrevealed) == self.mines_count:
                if all(cell.is_flagged == cell.is_mine or cell in unrevealed for _, _, cell in self.get_all_cells()):
                    for cell in unrevealed:
                        cell.toggle_flag()
                    self.finish_game()

    def finish_game(self):
        self.update_status(STATUS_SUCCESS)
        elapsed = int(time.time()) - self._timer_start
        level_key = self.get_level_key()
        best = self.records.get(level_key)
        if best is None or elapsed < best:
            self.records[level_key] = elapsed
            self.best_time_label.setText(f"Best: {elapsed}")
            self.save_records()

    def button_pressed(self):
        if self.status == STATUS_PLAY:
            self.update_status(STATUS_FAILED)
            self.reveal_grid()
        elif self.status in (STATUS_FAILED, STATUS_SUCCESS):
            self.update_status(STATUS_READY)
            self.reset()

    def handle_chord(self, x, y):
        to_reveal = []
        self.determine_to_safe_reveal(x, y, to_reveal)
        for _, _, cell in to_reveal:
            cell.reveal()

    def determine_to_safe_reveal(self, x, y, to_reveal):
        flagged_count = sum(int(cell.is_flagged) for _, _, cell in self.get_around_cells(x, y))
        base_cell = self.get_cell(x, y)
        if flagged_count == base_cell.mines_around:
            for xi, yi, cell in self.get_revealable_cells(x, y, True):
                if (xi, yi) not in ((xq, yq) for xq, yq, _ in to_reveal):
                    to_reveal.append((xi, yi, cell))
                    self.determine_to_safe_reveal(xi, yi, to_reveal)

    def load_records(self):
        if os.path.exists(RECORDS_FILE):
            with open(RECORDS_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_records(self):
        with open(RECORDS_FILE, "w") as f:
            json.dump(self.records, f)

    def get_level_key(self):
        size, mines = LEVELS[self.level]
        return f"{size}x{size}_{mines}mines"
    
    def on_level_changed(self):
        for i, rb in enumerate(self.radio_buttons):
            if rb.isChecked():
                if i != self.level:
                    self.level = i
                    self.board_size, self.mines_count = LEVELS[self.level]
                    self.clear_grid()
                    self.init_grid()
                    self.update_status(STATUS_READY)
                    self.reset()
                break

    def clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def place_mines_after_first_click(self, safe_x, safe_y):
        positions = []
        forbidden = {(safe_x, safe_y)}
        for xi in range(max(0, safe_x-1), min(safe_x+2, self.board_size)):
            for yi in range(max(0, safe_y-1), min(safe_y+2, self.board_size)):
                forbidden.add((xi, yi))

        while len(positions) < self.mines_count:
            x = random.randint(0, self.board_size - 1)
            y = random.randint(0, self.board_size - 1)
            if (x, y) not in positions and (x, y) not in forbidden:
                self.get_cell(x, y).is_mine = True
                positions.append((x, y))

        self.calc_mines_around()

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    app.exec()
import sys
import json
import random
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
from PyQt5 import QtCore, QtGui, QtWidgets

GRID_SIZE = 16


# ---------------------------------------------------------
#  Built-in word lists
# ---------------------------------------------------------

CLOCK_WORDS = [

    "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX",
    "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE",
    "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX",
    "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE",
    "THIRTEEN", "FOURTEEN", "FIFTEEN",
    "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN",
    "TWENTY","THIRTY", "FORTY", "FIFTY",

    # Natural-language minute words
    "QUARTER", "HALF",
    "QUARTER", "HALF",

    # Modifiers
    "PAST", "TO", "OCLOCK",
    "PAST", "TO", "OCLOCK",

    # Digital-style support
    "ZERO",  "OH",

    # Status
    "CONNECTED","OFFLINE","SETUP",    
]

WEATHER_WORDS = [
    # Core conditions
    "SUN", "SUNNY",
    "RAIN", "WET", "DRY",
    "SNOW", "ICY", "HAIL",
    "WIND", 
    "CLOUD", 
    "STORM",
    "FOG", 

    # Temperature / feel
    "COLD", "WARM", "HOT",
    "FREEZE", "MILD", "CHILL",

    # Time-related
    "MORNING","AFTERNOON","EVENING",
    "TOMORROW",
    "NOW", "LATER", "THIS",

    # Strength
    "LIGHT", "HEAVY", "STRONG",

    # Directions
    "NORTH", "SOUTH", "EAST", "WEST",

    # Alerts
    "ALERT", "WARNING",

]

WEATHER_WORDS = []


# 16-colour palette for per-word highlighting
HIGHLIGHT_PALETTE = [
    QtGui.QColor("#FF5555"),  # red
    QtGui.QColor("#FFAA00"),  # orange
    QtGui.QColor("#FFFF55"),  # yellow
    QtGui.QColor("#AAFF00"),  # lime
    QtGui.QColor("#55FF55"),  # green
    QtGui.QColor("#00FFAA"),  # aquamarine
    QtGui.QColor("#55FFFF"),  # cyan
    QtGui.QColor("#00AAFF"),  # sky blue
    QtGui.QColor("#5555FF"),  # blue
    QtGui.QColor("#AA00FF"),  # purple
    QtGui.QColor("#FF55FF"),  # magenta
    QtGui.QColor("#FF00AA"),  # pink
    QtGui.QColor("#FFFFFF"),  # white
    QtGui.QColor("#AAAAAA"),  # light grey
    QtGui.QColor("#555555"),  # dark grey
    QtGui.QColor("#FFDDAA"),  # warm cream
]


# ---------------------------------------------------------
#  Data model
# ---------------------------------------------------------

@dataclass
class PlacedWord:
    word: str
    category: str
    direction: str
    cells: list  # list of {"row": int, "col": int}
    color: Tuple[int, int, int]  # (r, g, b)


class WordsearchModel:
    def __init__(self, rows: int = GRID_SIZE, cols: int = GRID_SIZE):
        self.rows = rows
        self.cols = cols
        self.grid: List[List[str]] = [[" " for _ in range(self.cols)] for _ in range(self.rows)]

        # editable categories (user)
        self.categories: Dict[str, List[str]] = {
            "names": [],
            "activities": [],
            "linking": [],
            "extras": [],
        }

        # built-in categories (read-only)
        self.builtin_categories: Dict[str, List[str]] = {
            "clock": CLOCK_WORDS,
            "weather": WEATHER_WORDS,
        }

        # which categories are currently enabled for placement
        self.enabled_categories: Dict[str, bool] = {
            "clock": True,
            "weather": True,
            "names": True,
            "activities": True,
            "linking": True,
            "extras": True,
        }

        # condensed direction flags
        self.allow_backwards: bool = True
        self.allow_diagonals: bool = True

        self.placed_words: List[PlacedWord] = []

    # --- grid ops -----------------------------------------------------------

    def clear_grid(self):
        self.grid = [[" " for _ in range(self.cols)] for _ in range(self.rows)]
        self.placed_words.clear()

    def random_fill_empty(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == " ":
                    self.grid[r][c] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    # --- category ops -------------------------------------------------------

    def update_category(self, cat: str, text: str):
        """Replace a user category's words with contents of textarea (one word per line)."""
        words: List[str] = []
        for line in text.splitlines():
            w = line.strip().upper()
            if w:
                words.append(w)
        self.categories[cat] = words

    def all_words_with_categories(self) -> List[Tuple[str, str]]:
        """Return list of (category, word) pairs for placement.

        Built-in categories first, then user categories, filtered by enabled_categories.
        """
        out: List[Tuple[str, str]] = []

        # built-in categories
        for cat, words in self.builtin_categories.items():
            if self.enabled_categories.get(cat, False):
                for w in words:
                    out.append((cat, w))

        # user categories
        for cat in ["names", "activities", "linking", "extras"]:
            if self.enabled_categories.get(cat, False):
                for w in self.categories.get(cat, []):
                    out.append((cat, w))

        return out

    # --- direction ops ------------------------------------------------------

    def get_enabled_directions(self) -> List[Tuple[int, int, str]]:
        """
        Build direction list based on allow_backwards + allow_diagonals.
        Mode B for diagonals:
          - diagonals ON, backwards OFF => SE, NE
          - diagonals ON, backwards ON  => NE, NW, SE, SW
        """
        dirs = []

        # Always forward cardinal directions
        dirs.append((0, 1, "E"))   # east
        dirs.append((1, 0, "S"))   # south

        # Backwards cardinals
        if self.allow_backwards:
            dirs.append((0, -1, "W"))  # west
            dirs.append((-1, 0, "N"))  # north

        if self.allow_diagonals:
            # Forward-ish diagonals: SE & NE
            dirs.append((1, 1, "SE"))
            dirs.append((-1, 1, "NE"))

            # If backwards allowed, also NW & SW
            if self.allow_backwards:
                dirs.append((-1, -1, "NW"))
                dirs.append((1, -1, "SW"))

        return dirs

    # --- JSON serialisation -------------------------------------------------

    def to_json(self) -> dict:
        rows = ["".join(r) for r in self.grid]
        return {
            "name": "Family Noticeboard",
            "version": 1,
            "grid": {
                "rows": self.rows,
                "cols": self.cols,
                "letters": rows,
            },
            "categories": self.categories,          # user categories only
            "builtin_categories": {
                "clock": CLOCK_WORDS,
                "weather": WEATHER_WORDS,
            },
            "enabled_categories": self.enabled_categories,
            "allow_backwards": self.allow_backwards,
            "allow_diagonals": self.allow_diagonals,
            "words": [asdict(w) for w in self.placed_words],
            "style": {
                "letter_pitch_mm": 10,
                "panel_gap_mm": 0,
            },
        }

    def from_json(self, data: dict):
        grid = data["grid"]
        self.rows = grid["rows"]
        self.cols = grid["cols"]
        self.grid = [list(r) for r in grid["letters"]]

        # user categories from file; fall back to existing default structure
        self.categories = data.get("categories", self.categories)

        # built-in categories remain from constants; ignore file overrides
        self.builtin_categories = {
            "clock": CLOCK_WORDS,
            "weather": WEATHER_WORDS,
        }

        self.enabled_categories = data.get(
            "enabled_categories",
            {
                "clock": True,
                "weather": True,
                "names": True,
                "activities": True,
                "linking": True,
                "extras": True,
            },
        )

        self.allow_backwards = data.get("allow_backwards", True)
        self.allow_diagonals = data.get("allow_diagonals", True)

        self.placed_words.clear()
        for w in data.get("words", []):
            color_tuple = tuple(w.get("color", (255, 255, 255)))
            self.placed_words.append(
                PlacedWord(
                    word=w["word"],
                    category=w.get("category", "extras"),
                    direction=w.get("direction", "E"),
                    cells=w.get("cells", []),
                    color=color_tuple,
                )
            )


# ---------------------------------------------------------
#  Word placer with overlap-first + exhaustive retries
# ---------------------------------------------------------

class WordPlacer:
    def __init__(self, model: WordsearchModel):
        self.model = model

    def _can_place(self, word: str, row: int, col: int, dr: int, dc: int) -> bool:
        for i, ch in enumerate(word):
            r = row + dr * i
            c = col + dc * i
            if r < 0 or r >= self.model.rows or c < 0 or c >= self.model.cols:
                return False
            existing = self.model.grid[r][c]
            if existing != " " and existing != ch:
                return False
        return True

    def _do_place(self, word: str, category: str, row: int, col: int, dr: int, dc: int, dir_name: str):
        cells = []
        for i, ch in enumerate(word):
            r = row + dr * i
            c = col + dc * i
            self.model.grid[r][c] = ch
            cells.append({"row": r, "col": c})

        col = random.choice(HIGHLIGHT_PALETTE)
        color_tuple = (col.red(), col.green(), col.blue())

        self.model.placed_words.append(
            PlacedWord(word=word, category=category, direction=dir_name, cells=cells, color=color_tuple)
        )

    def _try_overlap_placement(
        self,
        word: str,
        category: str,
        directions: List[Tuple[int, int, str]],
    ) -> bool:
        """
        Phase 1: try to place 'word' by hooking into existing letters on the grid.
        Returns True if placed, False otherwise.
        """
        rows, cols = self.model.rows, self.model.cols

        # For each letter in the word, try to match an existing cell
        for i, ch in enumerate(word):
            for r in range(rows):
                for c in range(cols):
                    if self.model.grid[r][c] != ch:
                        continue
                    # We have a potential anchor at (r, c) for word[i]
                    for dr, dc, dir_name in directions:
                        start_r = r - dr * i
                        start_c = c - dc * i
                        if self._can_place(word, start_r, start_c, dr, dc):
                            self._do_place(word, category, start_r, start_c, dr, dc, dir_name)
                            return True
        return False

    def _try_place_all_once(self, max_tries_per_word: int = 200) -> List[Tuple[str, str]]:
        """Attempt to place all words once, returning list of unplaced (category, word).

        Placement phases:
          1. Try to overlap with existing letters
          2. Fallback to random starts
        """

        self.model.clear_grid()
        words = self.model.all_words_with_categories()

        # Place longer words first, randomised order for equal-length words
        random.shuffle(words)
        words.sort(key=lambda wc: len(wc[1]), reverse=True)

        unplaced: List[Tuple[str, str]] = []
        rows, cols = self.model.rows, self.model.cols
        directions = self.model.get_enabled_directions()

        for category, word in words:
            w = word.upper().strip()
            if not w:
                continue

            placed = False
            length = len(w)

            # Phase 1: try overlap-based placement
            # Do not use overlapped placement for clock words

            if category != "clock": 
                if self._try_overlap_placement(w, category, directions):
                    placed = True
            else:
                # Phase 2: fallback to random starting positions
                for _ in range(max_tries_per_word):
                    dr, dc, dir_name = random.choice(directions)

                    # vertical (rows)
                    if dr == 0:
                        start_r_min = 0
                        start_r_max = rows - 1
                    elif dr > 0:
                        start_r_min = 0
                        start_r_max = rows - length
                    else:  # dr < 0
                        start_r_min = length - 1
                        start_r_max = rows - 1

                    # horizontal (cols)
                    if dc == 0:
                        start_c_min = 0
                        start_c_max = cols - 1
                    elif dc > 0:
                        start_c_min = 0
                        start_c_max = cols - length
                    else:  # dc < 0
                        start_c_min = length - 1
                        start_c_max = cols - 1

                    if start_r_min > start_r_max or start_c_min > start_c_max:
                        continue

                    row = random.randint(start_r_min, start_r_max)
                    col = random.randint(start_c_min, start_c_max)

                    if self._can_place(w, row, col, dr, dc):
                        self._do_place(w, category, row, col, dr, dc, dir_name)
                        placed = True
                        break

            if not placed:
                unplaced.append((category, w))

        return unplaced

    def place_all_words_exhaustive(self, max_global_tries: int = 200, max_tries_per_word: int = 200):
        """Retry placement until all words have been placed or global attempts exhausted."""
        last_unplaced: List[Tuple[str, str]] = []

        for attempt in range(1, max_global_tries + 1):
            last_unplaced = self._try_place_all_once(max_tries_per_word=max_tries_per_word)
            if not last_unplaced:
                return True, attempt, last_unplaced

        # if we get here, last attempt still has unplaced words
        return False, max_global_tries, last_unplaced


# ---------------------------------------------------------
#  UI: Category panel (text areas + checkboxes + direction flags)
# ---------------------------------------------------------

class CategoryPanel(QtWidgets.QWidget):
    def __init__(self, model: WordsearchModel):
        super().__init__()
        self.model = model

        layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self.text_widgets: Dict[str, QtWidgets.QPlainTextEdit] = {}

        # Editable categories as text areas
        for cat in ["names", "activities", "linking", "extras"]:
            edit = QtWidgets.QPlainTextEdit()
            self.text_widgets[cat] = edit
            tab = QtWidgets.QWidget()
            tl = QtWidgets.QVBoxLayout(tab)
            tl.addWidget(edit)
            self.tabs.addTab(tab, cat.capitalize())

        # Built-in clock (read-only)
        clock_edit = QtWidgets.QPlainTextEdit()
        clock_edit.setReadOnly(True)
        clock_edit.setPlainText("\n".join(self.model.builtin_categories["clock"]))
        clock_tab = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(clock_tab)
        cl.addWidget(clock_edit)
        self.tabs.addTab(clock_tab, "Clock")

        # Built-in weather (read-only)
        weather_edit = QtWidgets.QPlainTextEdit()
        weather_edit.setReadOnly(True)
        weather_edit.setPlainText("\n".join(self.model.builtin_categories["weather"]))
        weather_tab = QtWidgets.QWidget()
        wl = QtWidgets.QVBoxLayout(weather_tab)
        wl.addWidget(weather_edit)
        self.tabs.addTab(weather_tab, "Weather")

        # Category enable/disable checkboxes
        gb_cat = QtWidgets.QGroupBox("Categories to place")
        gb_cat_layout = QtWidgets.QVBoxLayout(gb_cat)
        self.checkbox_widgets: Dict[str, QtWidgets.QCheckBox] = {}

        def add_cat_checkbox(cat_key: str, label: str):
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(self.model.enabled_categories.get(cat_key, True))
            cb.stateChanged.connect(lambda state, k=cat_key: self.on_category_toggled(k, state))
            self.checkbox_widgets[cat_key] = cb
            gb_cat_layout.addWidget(cb)

        add_cat_checkbox("clock", "Clock (built-in)")
        add_cat_checkbox("weather", "Weather (built-in)")
        add_cat_checkbox("names", "Names")
        add_cat_checkbox("activities", "Activities")
        add_cat_checkbox("linking", "Linking")
        add_cat_checkbox("extras", "Extras")

        layout.addWidget(gb_cat)

        # Direction options
        gb_dir = QtWidgets.QGroupBox("Placement directions")
        dir_layout = QtWidgets.QVBoxLayout(gb_dir)

        self.cb_backwards = QtWidgets.QCheckBox("Allow backwards (W, N and backward diagonals)")
        self.cb_backwards.setChecked(self.model.allow_backwards)
        self.cb_backwards.stateChanged.connect(self.on_backwards_toggled)
        dir_layout.addWidget(self.cb_backwards)

        self.cb_diagonals = QtWidgets.QCheckBox("Allow diagonals (SE/NE and, if backwards, NW/SW)")
        self.cb_diagonals.setChecked(self.model.allow_diagonals)
        self.cb_diagonals.stateChanged.connect(self.on_diagonals_toggled)
        dir_layout.addWidget(self.cb_diagonals)

        layout.addWidget(gb_dir)

        # Update button (only affects editable categories)
        update_btn = QtWidgets.QPushButton("Update user categories from text areas")
        update_btn.clicked.connect(self.update_model_from_text)
        layout.addWidget(update_btn)

        self.refresh_from_model()

    def refresh_from_model(self):
        # text areas
        for cat, edit in self.text_widgets.items():
            lines = "\n".join(self.model.categories.get(cat, []))
            edit.setPlainText(lines)

        # category checkboxes from model.enabled_categories
        for cat, cb in self.checkbox_widgets.items():
            cb.blockSignals(True)
            cb.setChecked(self.model.enabled_categories.get(cat, True))
            cb.blockSignals(False)

        # direction checkboxes
        self.cb_backwards.blockSignals(True)
        self.cb_backwards.setChecked(self.model.allow_backwards)
        self.cb_backwards.blockSignals(False)

        self.cb_diagonals.blockSignals(True)
        self.cb_diagonals.setChecked(self.model.allow_diagonals)
        self.cb_diagonals.blockSignals(False)

    def update_model_from_text(self):
        for cat, edit in self.text_widgets.items():
            self.model.update_category(cat, edit.toPlainText())

    def on_category_toggled(self, cat_key: str, state: int):
        self.model.enabled_categories[cat_key] = (state == QtCore.Qt.Checked)

    def on_backwards_toggled(self, state: int):
        self.model.allow_backwards = (state == QtCore.Qt.Checked)

    def on_diagonals_toggled(self, state: int):
        self.model.allow_diagonals = (state == QtCore.Qt.Checked)


# ---------------------------------------------------------
#  Unified preview: letters + word highlighting, start/stop
# ---------------------------------------------------------

class WordsearchPreview(QtWidgets.QWidget):
    def __init__(self, model: WordsearchModel):
        super().__init__()
        self.model = model
        self.word_index = 0

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(800)  # ms: show each word for ~0.8s

    def reset_word_index(self):
        self.word_index = 0

    def _tick(self):
        words = self.model.placed_words
        if words:
            self.word_index = (self.word_index + 1) % len(words)
        self.update()

    def start_preview(self):
        if not self.timer.isActive():
            self.timer.start(800)

    def stop_preview(self):
        if self.timer.isActive():
            self.timer.stop()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        qp.fillRect(self.rect(), QtCore.Qt.black)

        if self.model.cols == 0 or self.model.rows == 0:
            return

        cell_w = self.width() / self.model.cols
        cell_h = self.height() / self.model.rows
        cell = min(cell_w, cell_h)

        # Determine which cells are lit for the current word
        lit_cells = set()
        current_color = QtGui.QColor(255, 255, 255)

        words = self.model.placed_words
        if words:
            current = words[self.word_index]
            for cell_info in current.cells:
                lit_cells.add((cell_info["row"], cell_info["col"]))
            r, g, b = current.color
            current_color = QtGui.QColor(r, g, b)

        # draw grid
        qp.setRenderHint(QtGui.QPainter.Antialiasing, False)
        font = QtGui.QFont("Courier", 14, QtGui.QFont.Bold)
        qp.setFont(font)

        for r in range(self.model.rows):
            for c in range(self.model.cols):
                x = c * cell
                y = r * cell
                rect = QtCore.QRectF(x, y, cell, cell)

                if (r, c) in lit_cells:
                    qp.setBrush(current_color)
                else:
                    qp.setBrush(QtGui.QColor(30, 30, 30))

                qp.setPen(QtCore.Qt.NoPen)
                qp.drawRect(rect)

                # draw letter
                letter = self.model.grid[r][c]
                if letter.strip():
                    # Use high contrast letter colour
                    qp.setPen(QtCore.Qt.black if (r, c) in lit_cells else QtCore.Qt.white)
                    qp.drawText(rect, QtCore.Qt.AlignCenter, letter)


# ---------------------------------------------------------
#  Main window
# ---------------------------------------------------------

class WordsearchEditor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Family Wordsearch Editor")

        self.model = WordsearchModel()
        self.placer = WordPlacer(self.model)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        self.cat_panel = CategoryPanel(self.model)
        self.preview = WordsearchPreview(self.model)

        layout.addWidget(self.cat_panel, 3)
        layout.addWidget(self.preview, 5)

        self._build_toolbar()
        self.statusBar().showMessage("Ready")

    def _build_toolbar(self):
        tb = self.addToolBar("Main")

        act_place = QtWidgets.QAction("Place Words (exhaustive)", self)
        act_place.triggered.connect(self.on_place_words)
        tb.addAction(act_place)

        act_fill = QtWidgets.QAction("Random Fill Empty", self)
        act_fill.triggered.connect(self.on_random_fill)
        tb.addAction(act_fill)

        tb.addSeparator()

        act_save = QtWidgets.QAction("Save JSON", self)
        act_save.triggered.connect(self.on_save)
        tb.addAction(act_save)

        act_load = QtWidgets.QAction("Load JSON", self)
        act_load.triggered.connect(self.on_load)
        tb.addAction(act_load)

        tb.addSeparator()

        act_start = QtWidgets.QAction("Start Preview", self)
        act_start.triggered.connect(self.on_start_preview)
        tb.addAction(act_start)

        act_stop = QtWidgets.QAction("Stop Preview", self)
        act_stop.triggered.connect(self.on_stop_preview)
        tb.addAction(act_stop)

    # --- actions ------------------------------------------------------------

    def on_place_words(self):
        # sync user categories from text areas
        self.cat_panel.update_model_from_text()

        success, attempts, unplaced = self.placer.place_all_words_exhaustive()
        self.model.random_fill_empty()
        self.preview.reset_word_index()
        self.preview.update()

        if success:
            self.statusBar().showMessage(f"All words placed after {attempts} attempt(s)")
        else:
            msg = ", ".join(f"{c}:{w}" for c, w in unplaced)
            self.statusBar().showMessage(
                f"Could not place all words after {attempts} attempts. Unplaced: {msg}"
            )

    def on_random_fill(self):
        self.model.random_fill_empty()
        self.preview.update()
        self.statusBar().showMessage("Randomly filled empty cells")

    def on_save(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save wordsearch",
            "",
            "Wordsearch JSON (*.json)",
        )
        if not path:
            return
        self.cat_panel.update_model_from_text()
        data = self.model.to_json()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.statusBar().showMessage(f"Saved to {path}")

    def on_load(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load wordsearch",
            "",
            "Wordsearch JSON (*.json)",
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.model.from_json(data)
        self.cat_panel.refresh_from_model()
        self.preview.reset_word_index()
        self.preview.update()
        self.statusBar().showMessage(f"Loaded from {path}")

    def on_start_preview(self):
        self.preview.start_preview()
        self.statusBar().showMessage("Preview running")

    def on_stop_preview(self):
        self.preview.stop_preview()
        self.statusBar().showMessage("Preview stopped")


# ---------------------------------------------------------
#  Entry point
# ---------------------------------------------------------

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = WordsearchEditor()
    w.resize(1400, 800)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

"""deck.ui.groups_dialog — ręczna edycja zakładek docka.

Kolejność na tej liście jest kolejnością zakładek w docku, a odznaczenie chowa
zakładkę bez utraty jej ustawień. Przeciąganie zmienia kolejność, dwuklik —
nazwę.

Okno celowo nie ma rodzica: dock jest oknem bez prawa do focusu
(WS_EX_NOACTIVATE), więc dialog podpięty pod niego nie dałby się obsłużyć
klawiaturą.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox,
                               QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout)

from deck.profiles import Group


class GroupsDialog(QDialog):
    """Zwraca nową kolejność grup, ich widoczność i nazwy."""

    def __init__(self, groups: list[Group], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Grupy")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(420, 520)

        self.list = QListWidget(self)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemDoubleClicked.connect(self._rename_item)
        for g in groups:
            item = QListWidgetItem(g.title)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Unchecked if g.hidden else Qt.Checked)
            item.setData(Qt.UserRole, g.gid)
            self.list.addItem(item)

        up = QPushButton("▲", self)
        down = QPushButton("▼", self)
        rename = QPushButton("Zmień nazwę…", self)
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        rename.clicked.connect(lambda: self._rename_item(self.list.currentItem()))

        all_on = QPushButton("Wszystkie", self)
        all_off = QPushButton("Żadna", self)
        all_on.clicked.connect(lambda: self._check_all(True))
        all_off.clicked.connect(lambda: self._check_all(False))

        side = QVBoxLayout()
        side.addWidget(up)
        side.addWidget(down)
        side.addSpacing(12)
        side.addWidget(rename)
        side.addSpacing(12)
        side.addWidget(all_on)
        side.addWidget(all_off)
        side.addStretch(1)

        middle = QHBoxLayout()
        middle.addWidget(self.list, 1)
        middle.addLayout(side)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Przeciągnij, by zmienić kolejność zakładek. "
                             "Ptaszek = zakładka widoczna w docku.", self))
        lay.addLayout(middle, 1)
        lay.addWidget(buttons)

    # ── operacje na liście ────────────────────────────────────────────────
    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        new = row + delta
        if row < 0 or not 0 <= new < self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(new, item)
        self.list.setCurrentRow(new)

    def _check_all(self, on: bool) -> None:
        """Hurtowe włączenie albo wyłączenie widoczności — przy kilkunastu
        zakładkach szybciej jest odznaczyć wszystkie i wybrać kilka."""
        state = Qt.Checked if on else Qt.Unchecked
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def _rename_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        text, ok = QInputDialog.getText(self, "Nazwa grupy", "Nazwa:",
                                        text=item.text())
        if ok and text.strip():
            item.setText(text.strip())

    # ── wynik ─────────────────────────────────────────────────────────────
    def result_order(self) -> list[tuple[str, str, bool]]:
        """[(gid, tytuł, ukryta)] w kolejności ustawionej przez użytkownika."""
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            out.append((str(it.data(Qt.UserRole)), it.text(),
                        it.checkState() != Qt.Checked))
        return out

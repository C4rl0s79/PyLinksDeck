"""deck.ui.tiles — siatka kafli: model, rysowanie, widok.

Siatkę rysuje QListView w trybie ikon: dostajemy wirtualizację (663 kafle nie
mogą być 663 widgetami), zaznaczanie wielokrotne i obsługę klawiatury za darmo.
Rozmiar kafla to zwykła liczba pikseli — bez trybów „małe/średnie/duże" i bez
sufitu 256 px, który ogranicza ikony powłoki.
"""

from __future__ import annotations

import os

from PySide6.QtCore import (QAbstractAnimation, QAbstractListModel,
                            QEasingCurve, QModelIndex,
                            QPropertyAnimation, QRect, QSize, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QListView, QStyle,
                               QStyledItemDelegate)

from deck.library import Item
from deck.thumbs import MAX_PX, MIN_PX, STEP, ThumbCache

LABEL_H = 30
PAD = 8


class TileModel(QAbstractListModel):
    """Pozycje jednej grupy; grafika dociągana leniwie z ThumbCache."""

    def __init__(self, cache: ThumbCache, parent=None) -> None:
        super().__init__(parent)
        self._items: list[Item] = []
        self._cache = cache
        self.tile_w = 128
        self.tile_h = 192
        self.dpr = 1.0
        self.defer = False          # True w trakcie skalowania kółkiem
        self.fit_mode = "auto"      # auto | cover | contain
        self.spine_ok = False       # grzbiet platformy dla ROM-ów

    def _fit_for(self, it: Item) -> str:
        """Sposób renderowania kafla dla tej pozycji.

        W trybie automatycznym kafel jest zawsze wypełniony, bo siatka ma być
        równa: okładki bywają 1:1, 0,71:1 czy 3:4 i wpisane w ramkę zostawiały
        pasy przy pojedynczych grach (te, którym w PyLinksWeb ustawiono `pad`).
        Kadr, czyli *która część* obrazu zostaje, nadal pochodzi z PyLinksWeb.
        Wierne odwzorowanie jego ikon daje `contain`, a dla ROM-ów — grzbiet.
        """
        if self.spine_ok and it.is_rom:
            return "spine"
        if self.fit_mode == "contain":
            return ""              # "" = fit i offset dokładnie jak w PyLinksWeb
        return "crop"

    def set_items(self, items: list[Item]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item_at(self, row: int) -> Item | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        it = self.item_at(index.row())
        if it is None:
            return None
        if role == Qt.DisplayRole:
            return it.name
        if role == Qt.DecorationRole:
            return self._cache.get(it, self.tile_w, self.tile_h, self.dpr,
                                   self.defer, self._fit_for(it))
        if role == Qt.ToolTipRole:
            extra = f" · {', '.join(it.collections)}" if it.collections else ""
            return f"{it.name}\n{it.platform}{extra}"
        if role == Qt.UserRole:
            return it
        return None


class TileDelegate(QStyledItemDelegate):
    """Rysuje kafel: okładka, podpis, stany zaznaczenia i najechania."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tile_w = 128
        self.tile_h = 192
        self.show_labels = True

    def sizeHint(self, option, index) -> QSize:
        h = self.tile_h + (LABEL_H if self.show_labels else 0)
        return QSize(self.tile_w + PAD, h + PAD)

    def paint(self, p: QPainter, option, index) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        r = option.rect
        tile = QRect(r.x() + PAD // 2, r.y() + PAD // 2, self.tile_w, self.tile_h)

        state = option.state
        if state & QStyle.State_Selected:
            p.setBrush(QColor(255, 255, 255, 38))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)
        elif state & QStyle.State_MouseOver:
            p.setBrush(QColor(255, 255, 255, 18))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)

        pm = index.data(Qt.DecorationRole)
        if pm is not None and not pm.isNull():
            dpr = max(1.0, pm.devicePixelRatio())
            w, h = pm.width() / dpr, pm.height() / dpr
            scale = min(self.tile_w / max(1.0, w), self.tile_h / max(1.0, h))
            dw, dh = int(w * scale), int(h * scale)
            # Do dołu ramki, nie do środka: okładki o różnych proporcjach stoją
            # wtedy na wspólnej linii, a podpis nie odkleja się od obrazka.
            p.drawPixmap(tile.x() + (self.tile_w - dw) // 2,
                         tile.bottom() - dh, dw, dh, pm)
        else:
            p.setBrush(QColor(255, 255, 255, 14))       # kafel jeszcze się liczy
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(tile, 6, 6)

        if self.show_labels:
            f = QFont(option.font)
            f.setPixelSize(max(9, min(15, int(self.tile_w * 0.11))))
            p.setFont(f)
            fm = QFontMetrics(f)
            text = fm.elidedText(index.data(Qt.DisplayRole) or "",
                                 Qt.ElideRight, r.width() - PAD)
            box = QRect(r.x(), tile.bottom() + 3, r.width(), LABEL_H - 6)
            p.setPen(QPen(QColor(12, 12, 14, 190), 3))   # obrys pod czytelność
            p.drawText(box, Qt.AlignHCenter | Qt.AlignTop, text)
            p.setPen(QColor(240, 240, 245))
            p.drawText(box, Qt.AlignHCenter | Qt.AlignTop, text)
        p.restore()


class TileView(QListView):
    """Siatka kafli. Ctrl+kółko skaluje płynnie, bez pokazywania kroków pośrednich."""

    zoom_ended = Signal()

    def __init__(self, cache: ThumbCache, parent=None) -> None:
        super().__init__(parent)
        self.model_ = TileModel(cache, self)
        self.delegate = TileDelegate(self)
        self.setModel(self.model_)
        self.setItemDelegate(self.delegate)

        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.viewport().setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.doubleClicked.connect(self._launch)
        self.setStyleSheet("""
            QListView { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,70);
                                          border-radius: 5px; min-height: 28px; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
            QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
        """)

        # Po zatrzymaniu kółka zlecamy render docelowego rozmiaru. W trakcie
        # kręcenia rysujemy rozciągnięty kafel z cache — użytkownik nie ogląda
        # kolejno wszystkich rozmiarów, przez które przejechał.
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(220)
        self._settle.timeout.connect(self._end_zoom)

        # Przewijanie: zamiast skoku o kilka wierszy animujemy pasek do celu.
        # Kolejne obroty kółka dokładają się do bieżącego celu, więc szybkie
        # kręcenie nadal przewija daleko, tylko gładko.
        self._scroll_anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._scroll_anim.setDuration(260)
        self._scroll_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._scroll_target: int | None = None
        self.scroll_speed = 0.7
        self._margin = -1

        # Kafle wracają z wątków paczkami — jedno odświeżenie na 60 ms.
        self._repaint = QTimer(self)
        self._repaint.setSingleShot(True)
        self._repaint.setInterval(60)
        self._repaint.timeout.connect(self.viewport().update)
        cache.ready.connect(lambda *_: self._repaint.start())

    # ── rozmiar kafla ─────────────────────────────────────────────────────
    def set_tile(self, width: int, height: int, show_labels: bool, dpr: float) -> None:
        self.model_.tile_w, self.model_.tile_h, self.model_.dpr = width, height, dpr
        self.delegate.tile_w, self.delegate.tile_h = width, height
        self.delegate.show_labels = show_labels
        self.setGridSize(QSize(width + PAD,
                               height + PAD + (LABEL_H if show_labels else 0)))
        self.setIconSize(QSize(width, height))
        self._center_grid()
        self.viewport().update()

    def _center_grid(self) -> None:
        """Wyśrodkowuje siatkę: przy dużych kaflach reszta po podziale potrafiła
        zostawić kilkaset pikseli pustki przy jednej krawędzi."""
        cell = self.gridSize().width()
        if cell <= 0:
            return
        avail = self.width() - 14                    # zapas na pasek przewijania
        cols = max(1, avail // cell)
        margin = max(0, int((avail - cols * cell) / 2))
        if margin != self._margin:
            self._margin = margin
            self.setViewportMargins(margin, 0, margin, 0)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._center_grid()

    def _end_zoom(self) -> None:
        self.model_.defer = False
        self.viewport().update()
        self.zoom_ended.emit()

    def wheelEvent(self, ev) -> None:
        if ev.modifiers() & Qt.ControlModifier:
            self.model_.defer = True
            self._settle.start()
            self.zoom_step(1 if ev.angleDelta().y() > 0 else -1)
            ev.accept()
            return
        self._smooth_scroll(ev.angleDelta().y())
        ev.accept()

    def _smooth_scroll(self, delta_y: int) -> None:
        bar = self.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        # Uwaga: state() zwraca obiekt enum, który jest prawdziwy także dla
        # Stopped — porównujemy wprost z Running, inaczej bierzemy nieustawiony cel.
        running = self._scroll_anim.state() == QAbstractAnimation.Running
        base = (self._scroll_target if running and self._scroll_target is not None
                else bar.value())
        # Krok to ułamek widocznego obszaru, nie wysokość kafla: przy dużych
        # ikonach jeden obrót kółka przeskakiwał niemal cały ekran.
        step = max(48, int(self.viewport().height() * 0.4 * max(0.1, self.scroll_speed)))
        target = max(0, min(bar.maximum(),
                            int(base - delta_y / 120.0 * step)))
        self._scroll_target = target
        self._scroll_anim.stop()
        self._scroll_anim.setStartValue(bar.value())
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()

    # Podmieniane przez panel — tu tylko sygnalizujemy zamiar.
    def zoom_step(self, step: int) -> None:
        pass

    def _launch(self, index: QModelIndex) -> None:
        it = self.model_.item_at(index.row())
        if it is None:
            return
        try:
            os.startfile(str(it.lnk))     # skrót niesie cel, argumenty i katalog
        except OSError:
            pass

    def selected_items(self) -> list[Item]:
        rows = self.selectionModel().selectedIndexes()
        return [it for it in (self.model_.item_at(i.row()) for i in rows) if it]


def clamp_tile(px: int) -> int:
    return max(MIN_PX, min(MAX_PX, px))


def step_tile(px: int, step: int) -> int:
    return clamp_tile(px + step * STEP)

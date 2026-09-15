"""deck.ui.tiles — siatka kafli: model, rysowanie, widok.

Siatkę rysuje QListView w trybie ikon: dostajemy wirtualizację (663 kafle nie
mogą być 663 widgetami), zaznaczanie wielokrotne i obsługę klawiatury za darmo.
Rozmiar kafla to zwykła liczba pikseli — bez trybów „małe/średnie/duże" i bez
sufitu 256 px, który ogranicza ikony powłoki.
"""

from __future__ import annotations

from PySide6.QtCore import (QAbstractAnimation, QAbstractListModel,
                            QEasingCurve, QModelIndex, QPoint,
                            QPropertyAnimation, QRect, QSize, Qt, QTimer,
                            Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPen,
                           QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QListView, QStyle,
                               QStyledItemDelegate)

from deck import launcher
from deck.library import Item
from deck.thumbs import MAX_PX, MIN_PX, STEP, ThumbCache

LABEL_H = 30       # najmniejsza wysokość podpisu (jedna linia)
LABEL_GAP = 3      # odstęp obrazka od podpisu
PAD = 8
GAP = 8            # stały odstęp między kaflami (piksele logiczne — skaluje się z DPI)
SCROLLBAR_W = 14   # miejsce na pasek przewijania


def label_font(base: QFont, tile_w: int) -> QFont:
    """Czcionka podpisu — rośnie z kaflem, w granicach czytelności."""
    f = QFont(base)
    f.setPixelSize(max(9, min(15, int(tile_w * 0.11))))
    return f


def label_width(tile_w: int) -> int:
    """Szerokość, w której zawija się podpis (komórka minus margines)."""
    return max(1, tile_w + GAP - PAD)


_LABEL_FLAGS = Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap


def label_height(fm: QFontMetrics, text: str, width: int) -> int:
    """Wysokość podpisu zawiniętego do `width` — całego, bez wielokropka."""
    h = fm.boundingRect(QRect(0, 0, width, 10000), _LABEL_FLAGS, text or "").height()
    return max(LABEL_H, LABEL_GAP + h + 6)


def row_label_heights(names: list, cols: int, fm: QFontMetrics, width: int) -> list:
    """Wysokość podpisu dla każdego WIERSZA siatki = najwyższy podpis w wierszu.

    Cały wiersz ma jedną wysokość, więc obrazki i początki podpisów stoją na
    wspólnej linii, a kolejny wiersz nie nachodzi na zawinięty tytuł.
    """
    cols = max(1, cols)
    cache: dict = {}
    out = []
    for start in range(0, len(names), cols):
        row = 0
        for n in names[start:start + cols]:
            if n not in cache:
                cache[n] = label_height(fm, n, width)
            row = max(row, cache[n])
        out.append(row)
    return out


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

        Domyślnie plakat jest rozciągany do ramki: kafel wychodzi pełny, nic
        z plakatu nie znika i nic nie zostaje dołożone — kosztem proporcji.
        `cover` wypełnia kadrowaniem (wycinek wg `offset` z PyLinksWeb),
        `contain` odwzorowuje ikonę PyLinksWeb wiernie, a ROM-y mogą zamiast
        tego dostać grzbiet platformy.
        """
        if self.spine_ok and it.is_rom:
            return "spine"
        if self.fit_mode == "contain":
            return ""              # "" = fit i offset dokładnie jak w PyLinksWeb
        if self.fit_mode == "cover":
            return "crop"          # wypełnia kadrując, wycinek wg offsetu
        return "stretch"           # pełny kafel bez ucinania i bez podkładek

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
        self.row_labels: list[int] = []   # wysokość podpisu per wiersz (liczy widok)
        self.cols = 1

    def label_h(self, row: int) -> int:
        if not self.show_labels:
            return 0
        r = row // max(1, self.cols)
        return self.row_labels[r] if 0 <= r < len(self.row_labels) else LABEL_H

    def sizeHint(self, option, index) -> QSize:
        # Z podpisami siatka nie ma stałego kroku — wysokość wiersza zależy od
        # najdłuższego tytułu w nim, więc komórka ma dokładnie rozmiar kroku.
        return QSize(self.tile_w + GAP, self.tile_h + GAP + self.label_h(index.row()))

    def paint(self, p: QPainter, option, index) -> None:
        p.save()
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        r = option.rect
        tile = QRect(r.x() + (r.width() - self.tile_w) // 2,
                     r.y() + PAD // 2, self.tile_w, self.tile_h)

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
            # Pełny tytuł zawinięty w wiersze — wysokość komórki policzył już
            # widok (row_label_heights), więc tekst się mieści.
            p.setFont(label_font(option.font, self.tile_w))
            text = index.data(Qt.DisplayRole) or ""
            w = label_width(self.tile_w)
            box = QRect(r.x() + (r.width() - w) // 2, tile.bottom() + LABEL_GAP,
                        w, max(1, r.bottom() - tile.bottom() - LABEL_GAP))
            p.setPen(QPen(QColor(12, 12, 14, 190), 3))   # obrys pod czytelność
            p.drawText(box, _LABEL_FLAGS, text)
            p.setPen(QColor(240, 240, 245))
            p.drawText(box, _LABEL_FLAGS, text)
        p.restore()


class TileView(QListView):
    """Siatka kafli. Ctrl+kółko skaluje płynnie, bez pokazywania kroków pośrednich."""

    zoom_ended = Signal()
    launched = Signal(object, QRect, QPixmap)   # pozycja i wygląd kafla do animacji
    context_requested = Signal(object, QPoint)  # prawy klik: gra, pozycja globalna

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
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context)
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
        self.cols = 8               # ile kafli w wierszu (z ustawień)
        self.ratio = 1.5            # proporcja kafla (2:3 albo 1:1)

        # Kafle wracają z wątków paczkami — jedno odświeżenie na 60 ms.
        self._repaint = QTimer(self)
        self._repaint.setSingleShot(True)
        self._repaint.setInterval(60)
        self._repaint.timeout.connect(self.viewport().update)
        cache.ready.connect(lambda *_: self._repaint.start())
        self.model_.modelReset.connect(self._fit_columns)

    # ── rozmiar kafla ─────────────────────────────────────────────────────
    def set_tile(self, cols: int, ratio: float, show_labels: bool,
                 dpr: float) -> None:
        """`cols` to liczba kafli w wierszu — niezmiennik układu między ekranami."""
        self.cols = max(1, int(cols))
        self.ratio = ratio
        self.model_.dpr = dpr
        self.delegate.show_labels = show_labels
        self._fit_columns()
        self.viewport().update()

    def metrics(self, width: int | None = None) -> tuple[int, int, int]:
        """(kolumny, szerokość kafla, wysokość kafla) dla danej szerokości widoku.

        Odstęp jest stały, a to kafel dopasowuje się do szerokości: liczba kolumn
        wynika z rozmiaru *preferowanego* (tego z profilu, zmienianego kółkiem),
        a potem kafle rozciągają się tak, by wypełnić wiersz co do piksela.
        Dzięki temu układ wygląda tak samo przy każdej rozdzielczości i każdym
        skalowaniu ekranu — wszystkie wymiary są logiczne, a fizyczne piksele
        dokłada dopiero render (px × devicePixelRatio).
        """
        w = self.width() if width is None else width
        # Qt rezerwuje odstęp przy KAŻDEJ komórce siatki, nie tylko między nimi:
        # wiersz zajmuje cols × (kafel + odstęp).
        avail = max(MIN_PX + GAP, w - SCROLLBAR_W - 2 * GAP)
        cols = max(1, min(self.cols, int(avail // (MIN_PX + GAP))))
        cell_w = max(MIN_PX + GAP, int(avail // cols))
        tile_w = max(MIN_PX, cell_w - GAP)
        tile_h = max(MIN_PX, int(round(tile_w * self.ratio)))
        return cols, tile_w, tile_h

    def row_heights(self, width: int | None = None) -> list[int]:
        """Wysokość kolejnych wierszy siatki (kafel + odstęp + podpis)."""
        cols, tile_w, tile_h = self.metrics(width)
        n = self.model_.rowCount()
        if not self.delegate.show_labels:
            return [tile_h + GAP] * (-(-n // cols))
        names = [self.model_.item_at(i).name for i in range(n)]
        fm = QFontMetrics(label_font(self.font(), tile_w))
        return [tile_h + GAP + h
                for h in row_label_heights(names, cols, fm, label_width(tile_w))]

    def _fit_columns(self) -> None:
        """Przelicza rozmiar kafla pod bieżącą szerokość widoku."""
        cols, tile_w, tile_h = self.metrics()
        labels = self.delegate.show_labels
        self.delegate.tile_w, self.delegate.tile_h = tile_w, tile_h
        self.delegate.cols = cols
        self.model_.tile_w, self.model_.tile_h = tile_w, tile_h
        self.setIconSize(QSize(tile_w, tile_h))
        if labels:
            # Bez stałej siatki: Qt układa komórki z sizeHint, a wiersz ma
            # wysokość najdłuższego tytułu w nim.
            rows = [h - tile_h - GAP for h in self.row_heights()]
            changed = (rows != self.delegate.row_labels or self.gridSize().isValid()
                       or self.uniformItemSizes())
            self.delegate.row_labels = rows
            if self.gridSize().isValid():
                self.setGridSize(QSize())
            self.setUniformItemSizes(False)
            self.setSpacing(0)
            if changed:
                self.scheduleDelayedItemsLayout()
        else:
            self.delegate.row_labels = []
            self.setUniformItemSizes(True)
            # szerokość komórki liczona z tego samego wzoru co kolumny
            grid = QSize(tile_w + GAP, tile_h + GAP)
            if self.gridSize() != grid:
                self.setGridSize(grid)
        # Reszta po podziale to najwyżej kilka pikseli — rozdzielamy ją równo na
        # boki, żeby siatka była wyśrodkowana, a nie dosunięta do lewej.
        cols, _, _ = self.metrics()
        avail = max(0, self.width() - SCROLLBAR_W - 2 * GAP)
        margin = GAP + max(0, (avail - cols * (tile_w + GAP)) // 2)
        if self._margin != margin:
            self._margin = margin
            self.setViewportMargins(margin, 0, margin, 0)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._fit_columns()

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
        # Miejsce samego obrazka (bez podpisu) w układzie ekranu — stąd startuje
        # animacja uruchomienia.
        cell = self.visualRect(index)
        top_left = self.viewport().mapToGlobal(
            cell.topLeft() + QPoint((cell.width() - self.delegate.tile_w) // 2,
                                    PAD // 2))
        rect = QRect(top_left, QSize(self.delegate.tile_w, self.delegate.tile_h))
        pm = self.model_.data(index, Qt.DecorationRole)
        self.launched.emit(it, rect, pm if pm is not None else QPixmap())
        ok, err = launcher.launch_item(it)
        if not ok:
            print(f"[deck] nie udało się uruchomić {it.name}: {err}", flush=True)

    def _context(self, pos: QPoint) -> None:
        idx = self.indexAt(pos)
        item = self.model_.item_at(idx.row()) if idx.isValid() else None
        if item is not None:
            self.context_requested.emit(item, self.viewport().mapToGlobal(pos))

    def selected_items(self) -> list[Item]:
        rows = self.selectionModel().selectedIndexes()
        return [it for it in (self.model_.item_at(i.row()) for i in rows) if it]

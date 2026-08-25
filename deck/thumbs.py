"""deck.thumbs — kafle w dowolnym rozmiarze, bez sufitu 256 px.

Sedno całej apki: kafel powstaje z *surowej* okładki (często 600×900 i więcej),
a nie z .ico. Dzięki temu suwak rozmiaru nie ma górnej granicy poza rozdzielczością
źródła, a przy ekranie 4K kafel jest ostry, bo renderujemy w pikselach
fizycznych (px × devicePixelRatio), nie logicznych.

Kafel nie musi być kwadratem — okładki gier są pionowe (2:3), więc kwadrat
zjadałby jedną trzecią powierzchni na puste marginesy.

Renderowanie idzie w wątkach roboczych — 663 kafle po 512 px to zbyt dużo, by
liczyć je synchronicznie. Wątek zwraca QImage (QPixmap wolno tworzyć wyłącznie
w wątku GUI), a cache dyskowy sprawia, że drugie uruchomienie jest natychmiastowe.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter,
                           QPixmap)

from deck import paths as P
from deck import spine as _spine
from deck.library import Item, safe_key

try:
    from PIL import Image
    PIL_OK = True
except Exception:                                    # pragma: no cover
    PIL_OK = False

# Rozmiar zaokrąglamy do wielokrotności, żeby ciągnięcie suwaka nie zasypało
# cache setką wariantów różniących się o piksel.
STEP = 16
MIN_PX = 48
MAX_PX = 1408

# Proporcje kafla: okładka pionowa albo kwadrat (ikony, logotypy, MAME).
ASPECTS = {"portrait": 1.5, "square": 1.0}


def quantize(px: int) -> int:
    return max(MIN_PX, min(MAX_PX, int(round(px / STEP)) * STEP))


def tile_size(width: int, aspect: str = "portrait") -> tuple[int, int]:
    """Szerokość kafla → (szerokość, wysokość) dla danej proporcji."""
    ratio = ASPECTS.get(aspect, 1.5)
    return width, max(MIN_PX, int(round(width * ratio)))


def _cache_file(key: str, w: int, h: int, src: Path | None, fit: str,
                offset: float) -> Path:
    """Nazwa w cache obejmuje wszystko, co wpływa na wygląd kafla.

    Poza plikiem źródłowym liczy się też kadr: zmiana `offset` w PyLinksWeb daje
    inny wycinek przy tym samym trybie, więc bez niego w kluczu wracałby stary
    obrazek mimo poprawnie odczytanych ustawień.
    """
    stamp = ""
    if src is not None:
        try:
            st = src.stat()
            stamp = f"{int(st.st_mtime)}{st.st_size}"
        except OSError:
            pass
    h10 = hashlib.md5(f"{src}|{stamp}|{fit}|{offset:.4f}".encode()).hexdigest()[:10]
    return P.thumbs_dir() / f"{safe_key(key)}_{w}x{h}{fit[:1]}_{h10}.png"


# ── rysowanie ──────────────────────────────────────────────────────────────
def _render_cover(src: Path, w: int, h: int, fit: str, offset: float) -> QImage | None:
    """Skaluje okładkę do w×h, kadrując jak podgląd w PyLinksWeb."""
    if not PIL_OK:
        img = QImage(str(src))
        return None if img.isNull() else img.scaled(
            w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    try:
        with Image.open(src) as im:
            im.load()
            im = im.convert("RGBA")
            if fit == "crop":
                sw, sh = im.size
                want = w / h
                if sw / sh > want:                 # źródło szersze — tniemy boki
                    nw = int(sh * want)
                    left = int(max(0, min(sw - nw, (sw - nw) * offset)))
                    im = im.crop((left, 0, left + nw, sh))
                else:                              # źródło wyższe — tniemy górę/dół
                    nh = int(sw / want)
                    top = int(max(0, min(sh - nh, (sh - nh) * offset)))
                    im = im.crop((0, top, sw, top + nh))
                im = im.resize((w, h), Image.LANCZOS)
            else:                                  # wpisanie w ramkę, bez obcinania
                im.thumbnail((w, h), Image.LANCZOS)
                canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2), im)
                im = canvas
            data = im.tobytes("raw", "RGBA")
            img = QImage(data, im.width, im.height, QImage.Format_RGBA8888)
            return img.copy()                      # odczep od bufora Pythona
    except Exception:
        return None


def _pil_to_qimage(im) -> QImage:
    data = im.tobytes("raw", "RGBA")
    return QImage(data, im.width, im.height, QImage.Format_RGBA8888).copy()


# Ustawienia grzbietu i wyszukiwarka logotypów — wstrzykiwane przez aplikację,
# bo wątek roboczy nie ma dostępu do stanu UI.
SPINE = _spine.SpineSettings()
LOGO_FOR = None            # callable(platforma) -> Path | None


def _render_spine(item: Item, size: int) -> QImage | None:
    """Kwadratowa ikona ROM-a z grzbietem platformy (jak w PyLinksWeb)."""
    if not SPINE.usable or LOGO_FOR is None or item.cover is None:
        return None
    logo = LOGO_FOR(item.platform)
    if logo is None:
        return None
    im = _spine.compose(item.cover, logo, size, SPINE.side, SPINE.frac,
                        SPINE.logo_scale)
    return _pil_to_qimage(im) if im is not None else None


def placeholder(name: str, w: int, h: int) -> QImage:
    """Zastępczy kafel dla gry bez okładki — inicjał na gradiencie."""
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    seed = int(hashlib.md5(name.encode("utf-8", "ignore")).hexdigest()[:6], 16)
    hue = seed % 360
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor.fromHsv(hue, 90, 120))
    grad.setColorAt(1.0, QColor.fromHsv((hue + 40) % 360, 110, 60))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    radius = min(w, h) * 0.08
    p.drawRoundedRect(0, 0, w, h, radius, radius)

    initials = "".join(word[0] for word in name.split()[:2] if word).upper() or "?"
    f = QFont()
    f.setPixelSize(max(12, int(min(w, h) * 0.34)))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 210))
    p.drawText(img.rect(), Qt.AlignCenter, initials)
    p.end()
    return img


# ── asynchroniczne renderowanie ────────────────────────────────────────────
class _Signals(QObject):
    done = Signal(str, int, int, str, QImage)       # key, w, h, tryb kadru, obraz


class _Job(QRunnable):
    def __init__(self, item: Item, w: int, h: int, fit: str, sig: _Signals) -> None:
        super().__init__()
        self.item, self.w, self.h, self.fit, self.sig = item, w, h, fit, sig
        self.setAutoDelete(True)

    def run(self) -> None:                          # wątek roboczy
        it, w, h, fit = self.item, self.w, self.h, self.fit
        cache = _cache_file(it.key, w, h, it.cover, fit, it.offset)
        img: QImage | None = None
        if cache.is_file():
            cand = QImage(str(cache))
            img = None if cand.isNull() else cand
        if img is None:
            if fit == "spine" and it.cover is not None:
                img = _render_spine(it, w)
            if img is None and it.cover is not None:
                img = _render_cover(it.cover, w, h, fit, it.offset)
            if img is None:
                img = placeholder(it.name, w, h)
            try:
                img.save(str(cache), "PNG")
            except Exception:
                pass
        self.sig.done.emit(it.key, w, h, fit, img)


class ThumbCache(QObject):
    """Pamięciowy cache kafli z leniwym dociąganiem w tle.

    `get` nigdy nie blokuje: albo oddaje gotowy kafel, albo zleca render i
    zwraca None, a widok przerysuje się po sygnale `ready`.
    """

    ready = Signal(str)                             # key

    def __init__(self, max_items: int = 900, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mem: OrderedDict[tuple[str, int, int, str], QPixmap] = OrderedDict()
        self._pending: set[tuple[str, int, int, str]] = set()
        # (klucz gry, tryb kadru) → gotowe rozmiary
        self._sizes: dict[tuple[str, str], set[tuple[int, int]]] = {}
        self._max = max_items
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(
            max(2, (QThreadPool.globalInstance().maxThreadCount() or 4) - 1))
        self._sig = _Signals()
        self._sig.done.connect(self._on_done)

    def clear(self) -> None:
        self._mem.clear()
        self._sizes.clear()

    def get(self, item: Item, w: int, h: int, dpr: float = 1.0,
            defer: bool = False, fit: str = "") -> QPixmap | None:
        """Kafel w żądanym rozmiarze albo najbliższy już policzony.

        `defer=True` mówi: nie zlecaj teraz nowego renderu. Używamy tego w trakcie
        skalowania kółkiem — inaczej każdy krok pośredni trafiałby do kolejki i
        użytkownik oglądałby po kolei wszystkie rozmiary, przez które przejechał.
        Zamiast tego pokazujemy istniejący kafel rozciągnięty do nowej ramki, a
        render właściwego rozmiaru rusza dopiero, gdy skalowanie się zatrzyma.
        """
        scale = max(1.0, dpr)
        fit_eff = fit or item.fit or "pad"       # pusty = kadrowanie z PyLinksWeb
        rw, rh = self._render_size(w, h, scale)
        tag = (item.key, rw, rh, fit_eff)
        hit = self._mem.get(tag)
        if hit is not None:
            self._mem.move_to_end(tag)
            if abs(hit.devicePixelRatio() - scale) > 0.01:
                hit.setDevicePixelRatio(scale)
            return hit
        if not defer and tag not in self._pending:
            self._pending.add(tag)
            self._pool.start(_Job(item, rw, rh, fit_eff, self._sig))
        return self._nearest(item.key, fit_eff, rw, scale)

    @staticmethod
    def _render_size(w: int, h: int, scale: float) -> tuple[int, int]:
        """Rozmiar renderu zachowujący proporcje ramki kafla.

        Kwantyzowanie obu boków osobno psuło proporcje (a przy dużych kaflach
        górny limit ścinał samą wysokość — kafel 2:3 renderował się jako 1:1,16,
        więc kadr zjadał górę i dół, a w ramce zostawały puste pasy). Dlatego
        zaokrąglamy tylko szerokość, wysokość liczymy z proporcji, a limit
        rozmiaru zmniejsza *oba* boki naraz.
        """
        ratio = (h / w) if w else 1.5
        rw = quantize(int(w * scale))
        rh = max(MIN_PX, int(round(rw * ratio)))
        if rh > MAX_PX:                       # zejdź proporcjonalnie, nie tnij
            rw = quantize(max(MIN_PX, int(rw * MAX_PX / rh)))
            rh = max(MIN_PX, int(round(rw * ratio)))
        return rw, rh

    def _nearest(self, key: str, fit: str, want_w: int,
                 scale: float) -> QPixmap | None:
        """Najbliższy rozmiarowo gotowy kafel tej gry — zaślepka na czas renderu."""
        sizes = self._sizes.get((key, fit))
        if not sizes:
            return None
        best = min(sizes, key=lambda s: abs(s[0] - want_w))
        pm = self._mem.get((key, best[0], best[1], fit))
        if pm is not None and abs(pm.devicePixelRatio() - scale) > 0.01:
            pm.setDevicePixelRatio(scale)
        return pm

    def _on_done(self, key: str, w: int, h: int, fit: str, img: QImage) -> None:
        tag = (key, w, h, fit)
        self._pending.discard(tag)
        self._mem[tag] = QPixmap.fromImage(img)
        self._mem.move_to_end(tag)
        self._sizes.setdefault((key, fit), set()).add((w, h))
        while len(self._mem) > self._max:
            (k, ow, oh, of), _ = self._mem.popitem(last=False)
            known = self._sizes.get((k, of))
            if known is not None:
                known.discard((ow, oh))
                if not known:
                    self._sizes.pop((k, of), None)
        self.ready.emit(key)

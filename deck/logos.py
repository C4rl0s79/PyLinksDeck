"""deck.logos — logotypy platform do zakładek docka.

Grafiki bierzemy z tego samego katalogu, którego używa PyLinksWeb do grzbietów
okładek (`platform_logo_dir` w jego config.json), łącznie z wariantami
kolorystycznymi w podkatalogu `_variants`. Dzięki temu zakładka „PS2" wygląda
tak samo jak grzbiet na ikonie tej samej platformy.

Gdy logotypu nie ma (kolekcje, MAME, własne grupy), zakładka po prostu pokazuje
nazwę — brak grafiki nigdy nie może wywalić docka.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from deck import paths as P

# Nazwy platform w LINKS bywają inne niż nazwy plików logotypów.
ALIASES = {
    "PS1": ("PSX", "PS1", "PLAYSTATION"),
    "PS2": ("PS2",),
    "PS3": ("PS3",),
    "PSP": ("PSP",),
    "GCN": ("GC", "GCN", "GAMECUBE", "NGC"),
    "MD": ("MD", "GENESIS", "MEGADRIVE"),
    "SEGACD": ("SEGACD", "MEGACD"),
    "SNESMSU1": ("SNES",),
    "NAOMI2": ("NAOMI",),
    "MAME": ("ARCADE", "MAME"),
    "PC": ("PC", "WINDOWS"),
}

EXTS = (".png", ".webp", ".jpg")


def logo_root(pylinks_dir: Path | None = None) -> Path | None:
    """Katalog logotypów wskazany w konfiguracji PyLinksWeb."""
    base = pylinks_dir or P.pylinks_dir()
    try:
        cfg = json.loads(P.pylinks_config(base).read_text("utf-8-sig"))
    except Exception:
        return None
    d = cfg.get("platform_logo_dir") or ""
    p = Path(d)
    return p if d and p.is_dir() else None

def _is_dark(img: QImage) -> bool:
    """Czy logotyp jest ciemny (czarne litery na przezroczystym tle).

    Katalog PyLinksWeb miesza wersje jasne i ciemne — ta druga na czarnym docku
    jest po prostu niewidoczna, więc dostaje jasny podkład. Liczymy średnią
    jasność pikseli nieprzezroczystych na miniaturze, bo pełny obraz ma 1920 px.
    """
    small = img.scaled(28, 28, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    total = weight = 0.0
    for y in range(small.height()):
        for x in range(small.width()):
            c = small.pixelColor(x, y)
            a = c.alphaF()
            if a < 0.25:
                continue
            total += a * (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
            weight += a
    return weight > 0 and (total / weight) < 96


class LogoSet:
    """Odnajduje i skaluje logotypy; trzyma cache wg (platforma, wysokość)."""

    def __init__(self, pylinks_dir: Path | None = None, style: str = "default") -> None:
        self.root = logo_root(pylinks_dir)
        self.style = style
        self._paths: dict[str, Path | None] = {}
        self._cache: dict[tuple[str, int], QPixmap] = {}
        self._dark: dict[str, bool] = {}

    def refresh(self) -> None:
        """Zapomina wczytane logotypy — po podmianie pliku w katalogu PyLinksWeb
        inaczej trzymalibyśmy stary obrazek do restartu."""
        self._paths.clear()
        self._cache.clear()
        self._dark.clear()

    def is_dark(self, platform: str) -> bool:
        """Czy logotyp wymaga jasnego podkładu (barwy zostawiamy nietknięte —
        odwracanie kolorów robiło z czerwonego SNES-a cyjanowy)."""
        return self._dark.get((platform or "").upper(), False)

    def set_style(self, style: str) -> None:
        if style != self.style:
            self.style = style
            self._paths.clear()
            self._cache.clear()
            self._dark.clear()

    def _dirs(self) -> list[Path]:
        if self.root is None:
            return []
        dirs = []
        if self.style and self.style != "default":
            cand = self.root / "_variants" / self.style
            if cand.is_dir():
                dirs.append(cand)
        dirs.append(self.root)
        return dirs

    def path_for(self, platform: str) -> Path | None:
        """Ścieżka logotypu dla platformy albo None."""
        key = (platform or "").upper()
        if key in self._paths:
            return self._paths[key]
        found: Path | None = None
        names = (key,) + ALIASES.get(key, ())
        for d in self._dirs():
            for name in names:
                for ext in EXTS:
                    cand = d / f"{name}{ext}"
                    if cand.is_file():
                        found = cand
                        break
                if found:
                    break
            if found:
                break
        self._paths[key] = found
        return found

    def fitted(self, platform: str, max_w: int, max_h: int,
               dpr: float = 1.0) -> QPixmap | None:
        """Logotyp wpisany w ramkę max_w × max_h (piksele logiczne).

        Logotypy platform są bardzo szerokie — od 3:1 do niemal 9:1 — więc
        skalowanie wyłącznie do wysokości zakładki dawało obrazek szerszy niż
        sama zakładka. Dopasowujemy w obu wymiarach naraz.
        """
        src = self.path_for(platform)
        if src is None or max_w < 8 or max_h < 6:
            return None
        scale = max(1.0, dpr)
        tw, th = int(max_w * scale), int(max_h * scale)
        tag = (str(src), tw * 10000 + th)
        hit = self._cache.get(tag)
        if hit is not None:
            return hit
        img = QImage(str(src))
        if img.isNull():
            self._paths[(platform or "").upper()] = None
            return None
        self._dark[(platform or "").upper()] = _is_dark(img)
        pm = QPixmap.fromImage(img)
        pm = pm.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(scale)
        self._cache[tag] = pm
        return pm

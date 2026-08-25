r"""deck.paths — gdzie leżą dane PyLinksWeb i gdzie Deck trzyma swoje.

Deck jest wyłącznie czytelnikiem biblioteki PyLinksWeb: nie zapisuje niczego
w jego katalogu. Własny stan (układy grup, profile monitorów, cache kafli)
idzie do %LOCALAPPDATA%\PyLinksDeck.
"""

from __future__ import annotations

import os
from pathlib import Path

# Kandydaci na katalog danych PyLinksWeb, w kolejności prawdopodobieństwa.
# Wersja spakowana (PyLinksWeb.exe) trzyma dane obok siebie i to zwykle ona jest
# tą używaną na co dzień — katalog z kodem źródłowym bywa nieaktualny.
CANDIDATES = (Path(r"D:\Links"), Path(r"D:\py\PyLinksWeb"))


def is_data_dir(p: Path) -> bool:
    """Czy katalog wygląda na dane PyLinksWeb (config plus skróty)."""
    return p.is_dir() and (p / "config.json").is_file() and (p / "LINKS").is_dir()


def _freshness(p: Path) -> float:
    try:
        return (p / "config.json").stat().st_mtime
    except OSError:
        return 0.0


def pylinks_dir(override: str = "") -> Path:
    """Katalog danych: wskazany ręcznie, ze zmiennej, albo najświeższy znaleziony."""
    for cand in (override, os.environ.get("PYLINKS_DIR", "")):
        if cand and Path(cand).is_dir():
            return Path(cand)
    found = [c for c in CANDIDATES if is_data_dir(c)]
    if found:
        return max(found, key=_freshness)
    return CANDIDATES[-1]


def links_root(base: Path) -> Path:
    return base / "LINKS"


def cache_dir(base: Path) -> Path:
    return base / "Cache"


def covers_dir(base: Path, mode: str = "icon") -> Path:
    return cache_dir(base) / "covers" / mode


def pylinks_db(base: Path) -> Path:
    return cache_dir(base) / "pylinks.db"


def pylinks_config(base: Path) -> Path:
    return base / "config.json"


def app_dir() -> Path:
    """Katalog stanu Decka; tworzony przy pierwszym zapisie."""
    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(root) / "PyLinksDeck"
    d.mkdir(parents=True, exist_ok=True)
    return d


def thumbs_dir() -> Path:
    d = app_dir() / "thumbs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def layouts_path() -> Path:
    return app_dir() / "layouts.json"


def settings_path() -> Path:
    return app_dir() / "settings.json"

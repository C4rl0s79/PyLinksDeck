"""deck.library — biblioteka gier czytana z eksportu PyLinksWeb.

Źródłem prawdy o *uruchamianiu* są skróty w LINKS/<PLATFORMA>/*.lnk (cel plus
argumenty), a źródłem prawdy o *grafice* — surowe okładki w Cache/covers/icon.
Celowo NIE używamy .ico ani powłoki: .ico ma sufit 256 px i to on odpowiada za
„ikony przestają rosnąć, rośnie tylko odstęp". Okładka w pełnej rozdzielczości
skaluje się do dowolnego rozmiaru kafla.

Klucz gry odtwarzamy tak samo, jak liczy go PyLinksWeb (api._game_key), żeby
trafić w tę samą nazwę pliku okładki i w ten sam wpis kadrowania w bazie.
Gdy klucz nie trafia (klon MAME, tytuł zsanityzowany przy tworzeniu .lnk),
schodzimy po kolejnych zapasowych indeksach zamiast zostawiać kafel bez grafiki.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from deck import paths as P

# Steam eksportuje skróty w dwóch wariantach: protokołem i przez -applaunch.
_STEAM_ID = re.compile(r"steam://rungameid/(\d+)|-applaunch\s+(\d+)", re.I)
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_NORM = re.compile(r"[^a-z0-9]+")

# Prefiksy źródeł używane przez PyLinksWeb w nazwach plików okładek.
_SOURCES = ("rom", "steam", "mame", "extra", "gog", "epic", "pc")
_KINDS = ("name", "app", "gog", "epic")


def safe_key(key: str) -> str:
    """Nazwa pliku okładki dla klucza gry (jak art._safe_key)."""
    return _SAFE.sub("_", key)[:180]


def norm(text: str) -> str:
    """Nazwa zredukowana do porównywania (bez interpunkcji i wielkości liter)."""
    return _NORM.sub("", (text or "").lower())


@dataclass
class Item:
    """Jedna pozycja biblioteki — to, co Deck rysuje i uruchamia."""

    key: str
    name: str
    platform: str
    lnk: Path
    target: str = ""
    args: str = ""
    workdir: str = ""
    cover: Path | None = None
    fit: str = "pad"
    offset: float = 0.5
    collections: list[str] = field(default_factory=list)
    franchise: str = ""        # seria z PyLinksWeb (IGDB); pusta = gra luźna
    order_ts: int = 0          # data do układania w serii (remake = oryginał)
    release_ts: int = 0        # data wydania TEJ wersji — rozstrzyga remisy

    @property
    def sort_name(self) -> str:
        return norm(self.name)

    @property
    def is_rom(self) -> bool:
        """Grzbiet platformy PyLinksWeb dokłada wyłącznie ROM-om (export.py:309)."""
        return self.key.startswith("rom::")


# ── odczyt skrótów ─────────────────────────────────────────────────────────
class _ShortcutReader:
    """Czyta .lnk przez COM, z cache na dysku (COM na 700 plikach jest wolny)."""

    def __init__(self) -> None:
        self._path = P.app_dir() / "lnk_cache.json"
        self._cache: dict = {}
        self._dirty = False
        self._shell = None
        try:
            self._cache = json.loads(self._path.read_text("utf-8"))
        except Exception:
            self._cache = {}

    def _com(self):
        if self._shell is None:
            import win32com.client  # type: ignore

            self._shell = win32com.client.Dispatch("WScript.Shell")
        return self._shell

    def read(self, lnk: Path) -> tuple[str, str, str]:
        try:
            st = lnk.stat()
            stamp = f"{int(st.st_mtime)}:{st.st_size}"
        except OSError:
            return "", "", ""
        hit = self._cache.get(str(lnk))
        if hit and hit.get("stamp") == stamp:
            return hit.get("target", ""), hit.get("args", ""), hit.get("cwd", "")
        try:
            sc = self._com().CreateShortCut(str(lnk))
            rec = {"stamp": stamp, "target": sc.TargetPath or "",
                   "args": sc.Arguments or "", "cwd": sc.WorkingDirectory or ""}
        except Exception:
            rec = {"stamp": stamp, "target": "", "args": "", "cwd": ""}
        self._cache[str(lnk)] = rec
        self._dirty = True
        return rec["target"], rec["args"], rec["cwd"]

    def flush(self) -> None:
        if not self._dirty:
            return
        try:
            self._path.write_text(json.dumps(self._cache), "utf-8")
            self._dirty = False
        except OSError:
            pass


# ── indeks okładek ─────────────────────────────────────────────────────────
class _Covers:
    """Trzy indeksy okładek: po kluczu, po (platforma, tytuł) i po tytule.

    Nazwa pliku ma postać <źródło>_[rodzaj|platforma]_<ogon>, gdzie ogon to
    znormalizowany tytuł (albo set MAME). Rozbicie tego z powrotem daje zapasowe
    drogi dojścia, gdy sam klucz nie wystarcza — a nie wystarcza wtedy, gdy
    tworzenie .lnk zsanityzowało tytuł (apostrof → podkreślenie).
    """

    def __init__(self, base: Path) -> None:
        self.exact: dict[str, Path] = {}
        self.by_plat: dict[tuple[str, str], Path] = {}
        self.by_name: dict[str, Path] = {}
        d = P.covers_dir(base, "icon")
        if not d.is_dir():
            return
        for f in d.iterdir():
            if not f.is_file():
                continue
            self.exact[f.stem] = f
            parts = f.stem.split("_")
            src = parts[0] if parts else ""
            plat = ""
            if src in _SOURCES:
                parts = parts[1:]
                if parts and parts[0] in _KINDS:
                    parts = parts[1:]
                elif src == "rom" and parts:
                    plat, parts = parts[0].upper(), parts[1:]
            tail = norm("_".join(parts))
            if not tail:
                continue
            if plat:
                self.by_plat.setdefault((plat, tail), f)
            self.by_name.setdefault(tail, f)

    def find(self, key: str, platform: str, name: str,
             mame_parent: str = "") -> Path | None:
        hit = self.exact.get(safe_key(key))
        if hit:
            return hit
        if mame_parent:
            hit = self.exact.get(safe_key(f"mame::{mame_parent}"))
            if hit:
                return hit
        return (self.by_plat.get((platform.upper(), norm(name)))
                or self.by_name.get(norm(name)))


# ── baza PyLinksWeb (tylko odczyt) ─────────────────────────────────────────
def _db(base: Path) -> sqlite3.Connection | None:
    p = P.pylinks_db(base)
    if not p.is_file():
        return None
    try:
        # URI sqlite nie znosi backslashy z Windows — stąd as_posix().
        return sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    except Exception:
        return None


class _Crops:
    """Kadry z PyLinksWeb, wyszukiwane także po samym tytule.

    Klucz kadru zawiera oryginalny tytuł gry, a my odtwarzamy go z nazwy pliku
    `.lnk` — a ta jest zsanityzowana (apostrof w „Assassin's Creed Odyssey"
    staje się podkreśleniem). Dokładne dopasowanie gubiłoby więc kadr każdej gry
    ze znakiem specjalnym w tytule, dlatego trzymamy też indeks po
    znormalizowanym tytule.
    """

    def __init__(self, con: sqlite3.Connection | None, default_fit: str) -> None:
        self.default = (default_fit, 0.5)
        self.exact: dict[str, tuple[str, float]] = {}
        self.by_plat: dict[tuple[str, str], tuple[str, float]] = {}
        self.by_name: dict[str, tuple[str, float]] = {}
        if con is None:
            return
        try:
            rows = list(con.execute("SELECT key,fit,coff FROM crops"))
        except Exception:
            return
        for key, fit, off in rows:
            val = (fit or "pad", float(off))
            self.exact[key] = val
            parts = str(key).split("::")
            if len(parts) != 3:
                continue
            src, mid, tail = parts
            if src == "rom":
                self.by_plat.setdefault((mid.upper(), norm(tail)), val)
            elif mid == "name":
                self.by_name.setdefault(norm(tail), val)

    def get(self, key: str, platform: str, name: str) -> tuple[str, float]:
        hit = self.exact.get(key)
        if hit is None:
            hit = self.by_plat.get((platform.upper(), norm(name)))
        if hit is None:
            hit = self.by_name.get(norm(name))
        return hit or self.default


def _mame_parents(con: sqlite3.Connection | None) -> dict[str, str]:
    """set klonu → set rodzica; okładka bywa zapisana tylko pod rodzicem."""
    if con is None:
        return {}
    try:
        return {n: p for n, p in con.execute(
            "SELECT name,parent FROM mame_sets WHERE parent<>''")}
    except Exception:
        return {}


def _default_fit(base: Path) -> str:
    """Globalny tryb kadrowania z PyLinksWeb.

    Wpisy w tabeli `crops` są tylko nadpisaniami dla pojedynczych gier; reszta
    bierze `icon_fit_mode` z config.json (tak samo robi export._fit_for w PyLinksWeb).
    """
    try:
        cfg = json.loads(P.pylinks_config(base).read_text("utf-8-sig"))
    except Exception:
        return "pad"
    return str(cfg.get("icon_fit_mode") or "pad")


def _collections(base: Path) -> dict[str, list[str]]:
    """Kolekcje z config.json → mapa 'PLATFORMA\\x00tytuł' → [kolekcje]."""
    out: dict[str, list[str]] = {}
    try:
        cfg = json.loads(P.pylinks_config(base).read_text("utf-8-sig"))
    except Exception:
        return out
    for coll, entries in (cfg.get("collections") or {}).items():
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            tag = f"{(e.get('platform') or '').upper()}\x00{norm(e.get('name'))}"
            out.setdefault(tag, []).append(coll)
    return out


# ── budowa klucza ──────────────────────────────────────────────────────────
def _mame_set(args: str) -> str:
    """Nazwa setu z argumentów mame.exe — ostatni token bez myślnika."""
    toks = [t for t in args.replace('"', " ").split() if not t.startswith("-")]
    return toks[-1].lower() if toks else ""


class _Series:
    """Serie gier rozpoznane przez PyLinksWeb (tabela `game_series`).

    Jak przy kadrach: klucz odtworzony z nazwy pliku skrótu bywa inny niż
    oryginalny (dwukropek w tytule staje się podkreślnikiem), więc obok
    dopasowania dokładnego trzymamy indeks (platforma, znormalizowana nazwa).
    Brak tabeli — np. seria jeszcze nierozpoznana — nie może niczego wywalić.
    """

    def __init__(self, con: sqlite3.Connection | None) -> None:
        self.exact: dict[str, tuple[str, int, int]] = {}
        self.by_name: dict[tuple[str, str], tuple[str, int, int]] = {}
        if con is None:
            return
        try:
            rows = con.execute(
                "SELECT key, name, COALESCE(franchise, collection), order_ts, release_ts "
                "FROM game_series WHERE COALESCE(franchise, collection) IS NOT NULL"
            ).fetchall()
        except sqlite3.Error:
            return                      # PyLinksWeb nie rozpoznawał jeszcze serii
        for key, name, fr, ts, rel in rows:
            val = (fr or "", int(ts or 0), int(rel or 0))
            self.exact[key] = val
            self.by_name[(self._plat(key), norm(name))] = val

    @staticmethod
    def _plat(key: str) -> str:
        if key.startswith("rom::"):
            return key.split("::")[1].upper()
        if key.startswith("mame::"):
            return "MAME"
        return "PC"

    def get(self, key: str, platform: str, name: str) -> tuple[str, int, int]:
        return (self.exact.get(key)
                or self.by_name.get((platform.upper(), norm(name)))
                or ("", 0, 0))


def _key_for(platform: str, name: str, target: str, args: str) -> str:
    """Odtwarza klucz PyLinksWeb na podstawie tego, co widać w skrócie."""
    m = _STEAM_ID.search(f"{target} {args}")
    if m:
        return f"steam::app::{m.group(1) or m.group(2)}"
    if platform.upper() == "MAME":
        st = _mame_set(args)
        if st:
            return f"mame::{st}"
    if platform.upper() == "PC":
        return f"extra::name::{name.strip().lower()}"
    return f"rom::{platform.lower()}::{name.strip().lower()}"


def load(base: Path | None = None) -> list[Item]:
    """Wczytuje całą bibliotekę. Bez efektów ubocznych w katalogu PyLinksWeb."""
    base = base or P.pylinks_dir()
    root = P.links_root(base)
    if not root.is_dir():
        return []

    fit_default = _default_fit(base)
    con = _db(base)
    try:
        crops = _Crops(con, fit_default)
        parents = _mame_parents(con)
        series = _Series(con)
    finally:
        if con is not None:
            con.close()
    covers = _Covers(base)
    colls = _collections(base)
    reader = _ShortcutReader()
    items: list[Item] = []

    for plat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        platform = plat_dir.name
        # LINKS/Kolekcje/<nazwa>/*.lnk to te same gry co w katalogach platform,
        # tyle że pogrupowane. Przynależność do kolekcji bierzemy z config.json,
        # więc taki katalog pomijamy — inaczej każda gra byłaby dwa razy.
        if not any(plat_dir.glob("*.lnk")):
            continue
        for lnk in sorted(plat_dir.glob("*.lnk")):
            name = lnk.stem.strip()
            target, args, cwd = reader.read(lnk)
            key = _key_for(platform, name, target, args)
            parent = parents.get(_mame_set(args), "") if platform.upper() == "MAME" else ""
            fit, off = crops.get(key, platform, name)
            franchise, order_ts, release_ts = series.get(key, platform, name)
            items.append(Item(
                key=key, name=name, platform=platform, lnk=lnk,
                target=target, args=args, workdir=cwd,
                cover=covers.find(key, platform, name, parent),
                fit=fit, offset=off,
                collections=colls.get(f"{platform.upper()}\x00{norm(name)}", []),
                franchise=franchise, order_ts=order_ts, release_ts=release_ts,
            ))
    reader.flush()
    return items

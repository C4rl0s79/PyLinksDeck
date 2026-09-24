"""deck.profiles — ustawienia wspólne i to, co naprawdę zależy od ekranu.

Podział wynika z bolesnej lekcji: profil „wszystko per zestaw monitorów" sprawiał,
że podłączenie projektora zaczynało konfigurację od zera — inne ukryte zakładki,
inny wygląd, inne rozmiary. Dlatego:

* **wspólne** (`Settings`) są zakładki: ich kolejność, widoczność, nazwy i wygląd,
  a także zachowanie panelu. To *ustawienia użytkownika* i nie mają powodu
  zmieniać się z rozdzielczością;
* **per ekran** (`ScreenLayout`) zostają wyłącznie wymiary docka i panelu, i to
  wyrażone ułamkiem ekranu, więc nawet one przenoszą się sensownie.

Rozmiar kafla jest liczbą **kolumn**, nie pikseli. Piksel na 1080p i na 4K to
zupełnie inna część ekranu, a liczba kolumn wygląda tak samo wszędzie — to ona
jest niezmiennikiem układu.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from typing import Iterable

from deck import paths as P

SCHEMA = 4
MIN_COLS = 1
MAX_COLS = 24


@dataclass
class Group:
    """Jedna zakładka docka wraz z regułą doboru gier."""

    gid: str
    title: str
    rule: dict = field(default_factory=lambda: {"kind": "all"})
    cols: int = 8              # ile kafli w wierszu — niezależne od rozdzielczości
    aspect: str = "portrait"   # portrait = okładka 2:3, square = kwadrat
    hidden: bool = False
    sort: str = "name"
    logo: str = ""             # nazwa logotypu; puste = dobierz po platformie
    fit_mode: str = "auto"     # auto (rozciągnij) | cover (kadruj) | contain
    spine: str = "auto"        # auto = jak PyLinksWeb, on, off

    def matches(self, item) -> bool:
        kind = self.rule.get("kind", "all")
        if kind == "platform":
            return item.platform.upper() == str(self.rule.get("value", "")).upper()
        if kind == "collection":
            return self.rule.get("value") in item.collections
        if kind == "manual":
            return item.key in set(self.rule.get("keys") or [])
        return kind == "all"

    @property
    def platform(self) -> str:
        if self.rule.get("kind") == "platform":
            return str(self.rule.get("value", ""))
        return ""


@dataclass
class ScreenLayout:
    """Wymiary docka i panelu — jedyne, co wolno różnić się między ekranami."""

    label: str = ""
    dock_width: float = 0.86       # ułamek szerokości ekranu
    dock_height: int = 46          # px logiczne (skalują się z DPI)
    dock_offset: int = 0
    panel_width: float = 0.94
    panel_height: float = 0.80


@dataclass
class Settings:
    """Ustawienia użytkownika — te same na każdym ekranie."""

    groups: list[Group] = field(default_factory=list)
    active_gid: str = ""
    show_labels: bool = True
    show_logos: bool = True
    logo_style: str = "default"
    scroll_speed: float = 0.7
    animations: bool = True
    auto_hide: bool = True
    opacity: float = 0.96
    screens: dict[str, ScreenLayout] = field(default_factory=dict)
    # ręczna kolejność gier w serii: {nazwa serii: [klucze gier]} — tam, gdzie
    # data wydania nie oddaje kolejności fabularnej (Yakuza 0 przed Kiwami)
    series_order: dict[str, list[str]] = field(default_factory=dict)

    # ── zakładki ──────────────────────────────────────────────────────────
    def visible_groups(self) -> list[Group]:
        return [g for g in self.groups if not g.hidden]

    def active(self) -> Group | None:
        vis = self.visible_groups()
        if not vis:
            return None
        for g in vis:
            if g.gid == self.active_gid:
                return g
        return vis[0]

    # ── wymiary bieżącego ekranu ──────────────────────────────────────────
    def layout(self, sig: str, label: str = "") -> ScreenLayout:
        if not sig:                      # przed rozpoznaniem ekranu — wartości
            return ScreenLayout()        # tymczasowe, nie zapisujemy pustego klucza
        lay = self.screens.get(sig)
        if lay is None:
            lay = ScreenLayout(label=label)
            self.screens[sig] = lay
        elif label:
            lay.label = label
        return lay

    # ── zapis i odczyt ────────────────────────────────────────────────────
    def to_json(self) -> dict:
        d = asdict(self)
        d["groups"] = [asdict(g) for g in self.groups]
        d["screens"] = {k: asdict(v) for k, v in self.screens.items()}
        return d

    @staticmethod
    def from_json(d: dict) -> "Settings":
        gkeys = {f.name for f in fields(Group)}
        lkeys = {f.name for f in fields(ScreenLayout)}
        skeys = {f.name for f in fields(Settings)} - {"groups", "screens"}
        groups = [Group(**{k: v for k, v in g.items() if k in gkeys})
                  for g in (d.get("groups") or [])]
        screens = {sig: ScreenLayout(**{k: v for k, v in lay.items() if k in lkeys})
                   for sig, lay in (d.get("screens") or {}).items()}
        kwargs = {k: v for k, v in d.items() if k in skeys}
        return Settings(groups=groups, screens=screens, **kwargs)


# ── sygnatura ekranu ───────────────────────────────────────────────────────
def screen_key(screen) -> tuple[str, str]:
    """(klucz, czytelna etykieta) dla JEDNEGO ekranu — rozmiar i skalowanie.

    Liczy się wyłącznie ekran, na którym Deck stoi (główny): to jego szerokość
    dzieli dock i panel. Nazwa monitora do klucza NIE wchodzi — Windows nadaje
    ją zależnie od tego, które ekrany są w danej chwili włączone i który jest
    główny, więc ten sam laptop bywał raz jednym, raz drugim urządzeniem i
    dostawał za każdym razem nowy, pusty profil.
    """
    g = screen.geometry()
    dpr = round(float(screen.devicePixelRatio()), 2)
    key = f"{g.width()}x{g.height()}@{dpr:g}"
    label = f"{g.width()}×{g.height()}" + (f" ×{dpr:g}" if abs(dpr - 1.0) > 0.01 else "")
    return key, label


def signature(screens: Iterable, primary=None) -> tuple[str, str]:
    """(klucz, etykieta) dla bieżącego ustawienia — wg ekranu głównego."""
    scr = primary
    if scr is None:
        scr = next(iter(screens), None)
    if scr is None:
        return "none", ""
    return screen_key(scr)


def _key_from_label(label: str) -> str:
    """Klucz ekranu odtworzony z etykiety starego profilu („2048×1280 ×1.25")."""
    text = str(label or "").strip()
    if not text or "+" in text:          # profil wielu ekranów — nie wiadomo,
        return ""                        # który był główny, nie ma czego przenosić
    m = re.match(r"^(\d+)×(\d+)(?:\s*×([\d.,]+))?$", text)
    if not m:
        return ""
    dpr = float((m.group(3) or "1").replace(",", "."))
    return f"{m.group(1)}x{m.group(2)}@{round(dpr, 2):g}"


def _merge_screens(entries: Iterable) -> dict:
    """Stare profile (klucz = hash z nazwą monitora) na klucze wg rozmiaru.

    Ten sam ekran miewał po kilka wpisów. Zostawiamy ten, w którym użytkownik
    coś zmienił — domyślne wartości nic nie wnoszą — a przy kilku zmienionych
    ten wpisany najpóźniej.
    """
    base = ScreenLayout()
    out: dict = {}
    for lay in entries:
        key = _key_from_label(lay.label)
        if not key:
            continue
        touched = any(getattr(lay, f.name) != getattr(base, f.name)
                      for f in fields(ScreenLayout) if f.name != "label")
        old = out.get(key)
        if old is None or touched:
            out[key] = lay
    return out


def clamp_cols(value: int) -> int:
    return max(MIN_COLS, min(MAX_COLS, int(value)))


# ── pierwsze uruchomienie ──────────────────────────────────────────────────
def default_settings(items) -> Settings:
    """Zakładki: najpierw kolekcje z PyLinksWeb, potem platformy wg liczebności."""
    plats: dict[str, int] = {}
    colls: dict[str, int] = {}
    for it in items:
        plats[it.platform] = plats.get(it.platform, 0) + 1
        for c in it.collections:
            colls[c] = colls.get(c, 0) + 1

    groups: list[Group] = []
    for name in sorted(colls, key=lambda c: -colls[c]):
        groups.append(Group(gid=f"coll::{name}", title=name.title(),
                            rule={"kind": "collection", "value": name}))
    for name in sorted(plats, key=lambda p: (-plats[p], p)):
        groups.append(Group(gid=f"plat::{name}", title=name,
                            rule={"kind": "platform", "value": name}))
    s = Settings(groups=groups)
    s.active_gid = groups[0].gid if groups else ""
    return s


# ── trwałość i migracja ────────────────────────────────────────────────────
def _from_schema2(raw: dict) -> Settings | None:
    """Przenosi stary układ (profil per ekran) na wspólne ustawienia.

    Bierzemy najbogatszy profil jako źródło zakładek — ustawienia użytkownika
    przepadłyby, gdyby po prostu zacząć od zera. Rozmiar kafla w pikselach
    przeliczamy na liczbę kolumn wg typowej szerokości panelu.
    """
    profiles = raw.get("profiles") or {}
    if not profiles:
        return None
    best = max(profiles.values(), key=lambda p: len(p.get("groups") or []))
    groups = []
    for g in best.get("groups") or []:
        tile = int(g.get("tile", 128) or 128)
        groups.append(Group(
            gid=g.get("gid", ""), title=g.get("title", ""),
            rule=g.get("rule") or {"kind": "all"},
            cols=clamp_cols(1900 // max(32, tile + 8)),
            aspect=g.get("aspect", "portrait"), hidden=bool(g.get("hidden", False)),
            sort=g.get("sort", "name"), logo=g.get("logo", ""),
            fit_mode=g.get("fit_mode", "auto"), spine=g.get("spine", "auto"),
        ))
    s = Settings(
        groups=groups, active_gid=best.get("active_gid", ""),
        show_labels=bool(best.get("show_labels", True)),
        show_logos=bool(best.get("show_logos", True)),
        logo_style=best.get("logo_style", "default"),
        scroll_speed=float(best.get("scroll_speed", 0.7)),
        animations=bool(best.get("animations", True)),
        auto_hide=bool(best.get("auto_hide", True)),
        opacity=float(best.get("opacity", 0.96)),
    )
    olds = []
    for sig, prof in profiles.items():
        olds.append(ScreenLayout(
            label=prof.get("label", ""),
            dock_width=float(prof.get("dock_width", 0.86)),
            dock_height=int(prof.get("dock_height", 46)),
            dock_offset=int(prof.get("dock_offset", 0)),
            panel_width=float(prof.get("panel_width", 0.94)),
            panel_height=float(prof.get("panel_height", 0.80)),
        ))
    s.screens = _merge_screens(olds)
    return s


def load() -> Settings | None:
    try:
        raw = json.loads(P.layouts_path().read_text("utf-8"))
    except Exception:
        return None
    schema = int(raw.get("schema", 0))
    if schema == SCHEMA:
        try:
            cfg = Settings.from_json(raw.get("settings") or {})
        except Exception:
            return None
        cfg.screens.pop("", None)        # ślad po starym, pustym kluczu
        return cfg
    if schema < SCHEMA:
        _backup(schema)
    if schema == 3:
        try:
            cfg = Settings.from_json(raw.get("settings") or {})
        except Exception:
            return None
        cfg.screens = _merge_screens(cfg.screens.values())
        return cfg
    if schema == 2:
        try:
            return _from_schema2(raw)
        except Exception:
            return None
    return None


def _backup(schema: int) -> None:
    """Kopia pliku przed migracją — z konfiguracją zbieraną miesiącami nie ma
    żartów, a migracja zmienia klucze ekranów nieodwracalnie."""
    src = P.layouts_path()
    dst = src.with_name(src.name + f".pre-v{schema + 1}-backup")
    try:
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
    except OSError:
        pass


def save(settings: Settings) -> None:
    data = {"schema": SCHEMA, "settings": settings.to_json()}
    tmp = P.layouts_path().with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(P.layouts_path())
    except OSError:
        pass

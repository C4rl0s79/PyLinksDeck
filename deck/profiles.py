"""deck.profiles — grupy i profile per zestaw monitorów.

Deck nie rozstawia ramek po pulpicie (to robi Fences i jego Folder Portal).
Grupy są **zakładkami w docku**: lista grup to kolejność zakładek, a szerokość
każdej zakładki wynika z szerokości docka podzielonej przez liczbę widocznych
grup. Dlatego w profilu nie ma współrzędnych grup — jest kolejność.

Profil jest osobny dla każdego zestawu monitorów, rozpoznawanego po sygnaturze
(nazwy ekranów + rozdzielczości + skalowanie). Przepięcie laptopa na projektor
albo 4K przełącza cały wygląd — rozmiar kafli włącznie — zamiast go rozjeżdżać.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from typing import Iterable

from deck import paths as P

# 2 = układ dokowy; profile w starym formacie (ramki) są odrzucane przy wczytaniu.
SCHEMA = 2


@dataclass
class Group:
    """Jedna zakładka docka wraz z regułą doboru gier."""

    gid: str
    title: str
    rule: dict = field(default_factory=lambda: {"kind": "all"})
    tile: int = 128            # szerokość kafla w px logicznych
    aspect: str = "portrait"   # portrait = okładka 2:3, square = kwadrat
    hidden: bool = False
    sort: str = "name"
    logo: str = ""             # nazwa logotypu; puste = dobierz po platformie
    fit_mode: str = "auto"     # auto | cover (wypełnij) | contain (wpisz)
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
        """Platforma grupy, jeśli grupa jest platformowa — do doboru logotypu."""
        if self.rule.get("kind") == "platform":
            return str(self.rule.get("value", ""))
        return ""


@dataclass
class Profile:
    """Wygląd Decka dla jednego zestawu monitorów."""

    sig: str
    label: str = ""
    groups: list[Group] = field(default_factory=list)

    dock_width: float = 0.86       # ułamek szerokości ekranu
    dock_height: int = 46          # px logiczne
    dock_offset: int = 0           # odsunięcie od górnej krawędzi
    panel_width: float = 0.94      # ułamek szerokości ekranu
    panel_height: float = 0.80     # ułamek wysokości obszaru roboczego

    scroll_speed: float = 0.7      # 1.0 = 40 % widoku na obrót kółka
    show_labels: bool = True       # podpisy pod kaflami
    show_logos: bool = True        # logotypy zamiast nazw w zakładkach
    logo_style: str = "Light_Color"
    opacity: float = 0.96
    active_gid: str = ""
    auto_hide: bool = True         # panel chowa się po zjechaniu myszą
    screen: str = ""

    def to_json(self) -> dict:
        d = asdict(self)
        d["groups"] = [asdict(g) for g in self.groups]
        return d

    @staticmethod
    def from_json(d: dict) -> "Profile":
        gkeys = {f.name for f in fields(Group)}
        pkeys = {f.name for f in fields(Profile)} - {"groups"}
        groups = [Group(**{k: v for k, v in g.items() if k in gkeys})
                  for g in (d.get("groups") or [])]
        kwargs = {k: v for k, v in d.items() if k in pkeys}
        kwargs.setdefault("sig", "")
        return Profile(groups=groups, **kwargs)

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


# ── sygnatura zestawu monitorów ────────────────────────────────────────────
def signature(screens: Iterable) -> tuple[str, str]:
    """(sygnatura, czytelna etykieta) dla aktualnie podłączonych ekranów."""
    parts, labels = [], []
    for s in sorted(screens, key=lambda s: (s.name(), s.geometry().x())):
        g = s.geometry()
        dpr = round(float(s.devicePixelRatio()), 2)
        parts.append(f"{s.name()}|{g.width()}x{g.height()}@{dpr}")
        labels.append(f"{g.width()}×{g.height()}"
                      + (f" ×{dpr:g}" if abs(dpr - 1.0) > 0.01 else ""))
    sig = hashlib.sha1("||".join(parts).encode()).hexdigest()[:12] if parts else "none"
    return sig, " + ".join(labels)


def suggest_tile(screens: Iterable) -> int:
    """Szerokość kafla proporcjonalna do ekranu: 1080p → 112, 1600p → 160, 4K → 224."""
    heights = [s.geometry().height() for s in screens] or [1080]
    return max(64, min(384, int(round(max(heights) * 0.104 / 16)) * 16))


def suggest_dock_height(screens: Iterable) -> int:
    heights = [s.geometry().height() for s in screens] or [1080]
    return max(32, min(88, int(round(max(heights) * 0.03))))


# ── domyślny profil ────────────────────────────────────────────────────────
def default_profile(sig: str, label: str, items, screens=()) -> Profile:
    """Zakładki: najpierw kolekcje z PyLinksWeb, potem platformy wg liczebności."""
    tile = suggest_tile(screens) if screens else 128
    plats: dict[str, int] = {}
    colls: dict[str, int] = {}
    for it in items:
        plats[it.platform] = plats.get(it.platform, 0) + 1
        for c in it.collections:
            colls[c] = colls.get(c, 0) + 1

    groups: list[Group] = []
    for name in sorted(colls, key=lambda c: -colls[c]):
        groups.append(Group(gid=f"coll::{name}", title=name.title(),
                            rule={"kind": "collection", "value": name}, tile=tile))
    for name in sorted(plats, key=lambda p: (-plats[p], p)):
        groups.append(Group(gid=f"plat::{name}", title=name,
                            rule={"kind": "platform", "value": name}, tile=tile))

    prof = Profile(sig=sig, label=label, groups=groups)
    if screens:
        prof.dock_height = suggest_dock_height(screens)
    prof.active_gid = groups[0].gid if groups else ""
    return prof


# ── trwałość ───────────────────────────────────────────────────────────────
def load_all() -> dict[str, Profile]:
    try:
        raw = json.loads(P.layouts_path().read_text("utf-8"))
    except Exception:
        return {}
    if int(raw.get("schema", 0)) != SCHEMA:
        return {}                       # inny układ świata — zaczynamy od nowa
    out: dict[str, Profile] = {}
    for sig, d in (raw.get("profiles") or {}).items():
        try:
            out[sig] = Profile.from_json(d)
        except Exception:
            continue
    return out


def save_all(profiles: dict[str, Profile]) -> None:
    data = {"schema": SCHEMA,
            "profiles": {sig: p.to_json() for sig, p in profiles.items()}}
    tmp = P.layouts_path().with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(P.layouts_path())
    except OSError:
        pass

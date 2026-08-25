"""deck.spine — kwadratowa ikona ROM-a: grzbiet platformy plus okładka.

Wierny port `pylinks.core.spine.add_platform_spine`. Gdy w PyLinksWeb włączony
jest `icon_platform_spine`, ikona ROM-a nie jest zwykłą okładką: to kwadrat
złożony z pionowego grzbietu z logotypem platformy i okładki rozciągniętej na
resztę pola. Dlatego takie ikony nie mają pustych pasów po bokach — i dlatego
`fit`/`offset` w ogóle nie wchodzą tu w grę (PyLinksWeb też ich nie używa,
gdy składa grzbiet).

Różnica wobec oryginału: tam kompozycja powstaje zawsze w 512 px, bo trafia do
`.ico`. Tutaj renderujemy wprost w docelowym rozmiarze kafla, więc grzbiet jest
ostry także przy 512 czy 1024 px.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from deck import paths as P

try:
    from PIL import Image, ImageDraw
    PIL_OK = True
except Exception:                                    # pragma: no cover
    PIL_OK = False


@dataclass(frozen=True)
class SpineSettings:
    """Ustawienia grzbietu przepisane z config.json PyLinksWeb."""

    enabled: bool = False
    side: str = "left"
    frac: float = 0.22
    logo_scale: float = 0.85
    logo_dir: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.enabled and self.logo_dir and PIL_OK)


def load_settings(base: Path | None = None) -> SpineSettings:
    try:
        cfg = json.loads(P.pylinks_config(base or P.pylinks_dir()).read_text("utf-8-sig"))
    except Exception:
        return SpineSettings()
    return SpineSettings(
        enabled=bool(cfg.get("icon_platform_spine", False)),
        side=str(cfg.get("icon_spine_side", "left") or "left"),
        frac=float(cfg.get("icon_spine_frac", 0.22) or 0.22),
        logo_scale=float(cfg.get("spine_logo_scale", 0.85) or 0.85),
        logo_dir=str(cfg.get("platform_logo_dir", "") or ""),
    )


def _rgba(hexc: str, alpha: int = 255):
    h = hexc.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def ensure_contrast(logo):
    """Ciemny jednobarwny wordmark → jasny (czytelny na ciemnym grzbiecie)."""
    try:
        small = logo.convert("RGBA")
        small.thumbnail((64, 64))
        lum = sat = cnt = 0
        for r, g, b, a in small.getdata():
            if a < 40:
                continue
            mx, mn = max(r, g, b), min(r, g, b)
            lum += 0.299 * r + 0.587 * g + 0.114 * b
            sat += 0 if mx == 0 else (mx - mn) / mx
            cnt += 1
        if cnt and (lum / cnt) < 125 and (sat / cnt) < 0.30:
            alpha = logo.convert("RGBA").split()[3]
            light = Image.new("RGBA", logo.size, (238, 238, 238, 0))
            light.putalpha(alpha)
            return light
        return logo
    except Exception:
        return logo


_READY: dict = {}


def _logo(path: Path):
    """Logo gotowe do nałożenia (wczytane + poprawiony kontrast), z cache."""
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        key = (str(path), 0)
    hit = _READY.get(key)
    if hit is not None:
        return hit
    try:
        img = ensure_contrast(Image.open(path).convert("RGBA"))
    except Exception:
        return None
    if len(_READY) > 64:
        _READY.clear()
    _READY[key] = img
    return img


def compose(src: Path, logo_path: Path, size: int, side: str = "left",
            frac: float = 0.22, logo_scale: float = 0.85):
    """Kwadrat size×size: grzbiet z logotypem + okładka wypełniająca resztę."""
    if not PIL_OK:
        return None
    logo = _logo(logo_path)
    if logo is None:
        return None
    try:
        with Image.open(src) as raw:
            raw.load()
            base = raw.convert("RGBA")
    except Exception:
        return None
    try:
        W0, H0 = base.size
        if min(W0, H0) < 24:
            return None
        r = size / max(W0, H0)
        base = base.resize((max(1, round(W0 * r)), max(1, round(H0 * r))),
                           Image.LANCZOS)
        W, H = base.size
        S = size
        sw = max(14, int(round(S * frac)))        # grzbiet ma stałą szerokość

        spine = Image.new("RGBA", (sw, S), _rgba("#141414"))
        d = ImageDraw.Draw(spine)
        if side == "left":
            d.rectangle([sw - 2, 0, sw - 1, S - 1], fill=_rgba("#000000", 120))
            d.line([(1, 0), (1, S)], fill=_rgba("#ffffff", 55))
        else:
            d.rectangle([0, 0, 1, S - 1], fill=_rgba("#000000", 120))
            d.line([(sw - 2, 0), (sw - 2, S)], fill=_rgba("#ffffff", 55))

        lg = logo.rotate(90 if side == "left" else -90, expand=True)
        ls = max(0.30, min(1.0, float(logo_scale or 0.85)))
        scale = max(1, int(sw * min(0.98, ls))) / max(1, lg.width)
        hcap = min(0.98, ls * 1.10 + 0.03)
        if lg.height * scale > S * hcap:
            scale = (S * hcap) / max(1, lg.height)
        lg = lg.resize((max(1, int(lg.width * scale)), max(1, int(lg.height * scale))),
                       Image.LANCZOS)
        spine.alpha_composite(lg, ((sw - lg.width) // 2, (S - lg.height) // 2))

        out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        aw = S - sw
        area_aspect = aw / S
        src_aspect = W / H
        if abs(src_aspect - area_aspect) / area_aspect <= 0.20:
            # plakat o zbliżonych proporcjach → poszerz do pełnego wypełnienia
            art = base.resize((aw, S), Image.LANCZOS)
            out.alpha_composite(art, (sw if side == "left" else 0, 0))
        else:
            # duża różnica (np. kwadrat) → wpisz w całości, bez zniekształceń
            sc = min(aw / W, S / H)
            nw, nh = max(1, round(W * sc)), max(1, round(H * sc))
            art = base.resize((nw, nh), Image.LANCZOS)
            ax = sw + (aw - nw) // 2 if side == "left" else (aw - nw) // 2
            out.alpha_composite(art, (ax, (S - nh) // 2))
        out.alpha_composite(spine, (0, 0) if side == "left" else (S - sw, 0))
        return out
    except Exception:
        return None

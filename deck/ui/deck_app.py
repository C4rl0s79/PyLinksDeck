"""deck.ui.deck_app — spina wszystko: dock, panel, profile, zasobnik, opcje.

Model interakcji: na pulpicie leży wyłącznie belka zakładek. Najechanie na nią
rozwija panel z kaflami wybranej grupy, kliknięcie zakładki przełącza grupę,
zjechanie myszą panel chowa. Prawy przycisk na docku otwiera pełne opcje —
z rozmiarem kafli, logotypami platform i autostartem włącznie.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import (QAction, QColor, QCursor, QGuiApplication, QIcon,
                           QPainter, QPixmap)
from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog, QMenu,
                               QMessageBox, QSystemTrayIcon)

from deck import (autostart, library, logos as L, paths as P,
                  profiles as PR, spine as SP, winshell)
from deck import thumbs as TH
from deck.thumbs import MAX_PX, MIN_PX, ThumbCache
from deck.ui.dock import DockBar
from deck.ui.groups_dialog import GroupsDialog
from deck.ui.panel import PanelWindow

TILE_PRESETS = (64, 96, 128, 160, 192, 256, 320, 384, 512)
DOCK_WIDTHS = ((0.5, "połowa"), (0.7, "70 %"), (0.86, "86 %"), (1.0, "cała szerokość"))
DOCK_HEIGHTS = (36, 46, 56, 72, 96)
PANEL_HEIGHTS = ((0.5, "50 %"), (0.65, "65 %"), (0.8, "80 %"), (0.92, "92 %"))
PANEL_WIDTHS = ((0.7, "70 %"), (0.84, "84 %"), (0.94, "94 %"), (1.0, "100 %"))


def _tray_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor(58, 122, 216))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setPen(QColor(255, 255, 255))
    f = p.font()
    f.setPixelSize(34)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "D")
    p.end()
    return QIcon(pm)


class DeckApp:
    """Cała aplikacja bez własnego okna głównego — dock i panel są osobnymi oknami."""

    def __init__(self) -> None:
        self.settings = self._load_settings()
        self.base = P.pylinks_dir(self.settings.get("pylinks_dir", ""))
        self.cache = ThumbCache()
        self.items: list[library.Item] = []
        self.profiles = PR.load_all()
        self.profile: PR.Profile | None = None

        self.logos = L.LogoSet(self.base)
        self._apply_spine_settings()
        self.dock = DockBar(self.logos)
        self.panel = PanelWindow(self.cache)

        self.dock.activated.connect(self._on_tab)
        self.dock.hovered.connect(lambda _: self._show_panel())
        self.dock.exited.connect(self._schedule_hide)
        self.dock.options_requested.connect(self._menu)
        self.panel.entered.connect(self._cancel_hide)
        self.panel.exited.connect(self._schedule_hide)
        self.panel.tile_changed.connect(self._on_tile_changed)
        self.panel.height_changed.connect(self._on_panel_resized)

        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(450)
        self._hide_timer.timeout.connect(self._hide_panel)

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._save)

        self._screen_timer = QTimer()
        self._screen_timer.setSingleShot(True)
        self._screen_timer.setInterval(400)
        self._screen_timer.timeout.connect(self._apply_profile)

        # Explorer bywa podnoszony nad nas (kliknięcie w tapetę, „Pokaż pulpit"),
        # a wtedy dock znika z oczu bez żadnego zdarzenia do przechwycenia.
        self._guard = QTimer()
        self._guard.setInterval(3000)
        self._guard.timeout.connect(self._guard_layer)
        self._guard.start()

        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda *_: self._screen_timer.start())
        app.screenRemoved.connect(lambda *_: self._screen_timer.start())
        app.primaryScreenChanged.connect(lambda *_: self._screen_timer.start())
        for s in app.screens():
            s.geometryChanged.connect(lambda *_: self._screen_timer.start())
            s.logicalDotsPerInchChanged.connect(lambda *_: self._screen_timer.start())

        autostart.refresh_if_enabled()
        self._build_tray()
        self.reload_library()
        self._apply_profile()

    # ── ustawienia i biblioteka ───────────────────────────────────────────
    @staticmethod
    def _load_settings() -> dict:
        try:
            return json.loads(P.settings_path().read_text("utf-8"))
        except Exception:
            return {}

    def _apply_spine_settings(self) -> None:
        """Wątki renderujące nie mają dostępu do UI — podajemy im ustawienia
        grzbietu i wyszukiwarkę logotypów wprost."""
        TH.SPINE = SP.load_settings(self.base)
        TH.LOGO_FOR = self.logos.path_for

    def spine_for(self, g: PR.Group) -> bool:
        """Czy ta grupa ma rysować grzbiet platformy."""
        if g.aspect != "square" or not TH.SPINE.usable:
            return False
        return g.spine == "on" or (g.spine == "auto" and TH.SPINE.enabled)

    def reload_library(self) -> None:
        self.items = library.load(self.base)
        if self.profile:
            self._sync_groups()
            self._refresh_panel()

    def _sync_groups(self) -> None:
        """Dostraja zakładki do tego, co faktycznie jest w bibliotece.

        Dokłada platformy i kolekcje, których profil jeszcze nie zna, i chowa te,
        w których nie ma już ani jednej gry — bez tego zmiana katalogu danych
        zostawiałaby puste zakładki po poprzedniej bibliotece.
        """
        prof = self.profile
        if prof is None:
            return
        known = {g.gid for g in prof.groups}
        tile = PR.suggest_tile(QGuiApplication.instance().screens())
        plats: dict[str, int] = {}
        colls: dict[str, int] = {}
        for it in self.items:
            plats[it.platform] = plats.get(it.platform, 0) + 1
            for c in it.collections:
                colls[c] = colls.get(c, 0) + 1

        for name in sorted(colls, key=lambda c: -colls[c]):
            gid = f"coll::{name}"
            if gid not in known:
                prof.groups.append(PR.Group(gid=gid, title=name.title(),
                                            rule={"kind": "collection", "value": name},
                                            tile=tile))
        for name in sorted(plats, key=lambda p: (-plats[p], p)):
            gid = f"plat::{name}"
            if gid not in known:
                prof.groups.append(PR.Group(gid=gid, title=name,
                                            rule={"kind": "platform", "value": name},
                                            tile=tile))

        for g in prof.groups:                    # puste zakładki znikają z docka
            if not any(g.matches(it) for it in self.items):
                g.hidden = True
        if prof.active() is None and prof.visible_groups():
            prof.active_gid = prof.visible_groups()[0].gid
        self.dock.set_groups(prof.visible_groups(),
                             prof.active().gid if prof.active() else "")
        self._save_soon()

    # ── profil ────────────────────────────────────────────────────────────
    def _apply_profile(self) -> None:
        app = QGuiApplication.instance()
        sig, label = PR.signature(app.screens())
        prof = self.profiles.get(sig)
        if prof is None:
            prof = PR.default_profile(sig, label, self.items, app.screens())
            self.profiles[sig] = prof
        prof.label = label
        self.profile = prof
        self.logos.set_style(prof.logo_style)
        self._layout_windows()
        self.dock.set_show_logos(prof.show_logos)
        self.dock.set_groups(prof.visible_groups(),
                             (prof.active().gid if prof.active() else ""))
        self.dock.show()
        self._pin(self.dock)
        self._refresh_panel()
        self._save()

    def _screen(self):
        return QGuiApplication.primaryScreen()      # Deck żyje na ekranie głównym

    def _layout_windows(self) -> None:
        prof, scr = self.profile, self._screen()
        if prof is None or scr is None:
            return
        ar = scr.availableGeometry()
        prof.screen = scr.name()

        dw = max(240, int(ar.width() * prof.dock_width))
        dh = max(28, int(prof.dock_height))
        dx = ar.x() + (ar.width() - dw) // 2
        dy = ar.y() + max(0, prof.dock_offset)
        self.dock.setGeometry(dx, dy, dw, dh)
        self.dock.setWindowOpacity(prof.opacity)

        pw = max(320, int(ar.width() * prof.panel_width))
        ph = max(200, int(ar.height() * prof.panel_height))
        px = ar.x() + (ar.width() - pw) // 2
        py = dy + dh + 8
        ph = min(ph, ar.y() + ar.height() - py - 8)
        self.panel.setGeometry(px, py, pw, ph)
        self.panel.setWindowOpacity(prof.opacity)

    def _refresh_panel(self) -> None:
        prof = self.profile
        if prof is None:
            return
        g = prof.active()
        if g is None:
            self.panel.hide()
            return
        scr = self._screen()
        dpr = float(scr.devicePixelRatio()) if scr else 1.0
        picked = [it for it in self.items if g.matches(it)]
        picked.sort(key=lambda i: (i.platform, i.sort_name) if g.sort == "platform"
                    else (i.sort_name,))
        self.panel.set_scroll_speed(prof.scroll_speed)
        self.panel.set_group(g, picked, dpr, prof.show_labels,
                             self.spine_for(g))
        self._fit_panel()

    def _fit_panel(self) -> None:
        """Panel jest tak wysoki, jak trzeba — nie wyżej niż pozwala profil."""
        prof, scr = self.profile, self._screen()
        if prof is None or scr is None:
            return
        ar = scr.availableGeometry()
        pw = max(320, int(ar.width() * prof.panel_width))
        top = self.dock.geometry().bottom() + 8
        limit = min(int(ar.height() * prof.panel_height),
                    ar.y() + ar.height() - top - 8)
        ph = max(160, min(limit, self.panel.content_height(pw)))
        self.panel.setGeometry(ar.x() + (ar.width() - pw) // 2, top, pw, ph)

    # ── zakładki i panel ──────────────────────────────────────────────────
    def _on_tab(self, gid: str) -> None:
        if not self.profile:
            return
        self.profile.active_gid = gid
        self.dock.set_active(gid)
        self._refresh_panel()
        self._show_panel()
        self._save_soon()

    def _on_tile_changed(self, *_args) -> None:
        self._fit_panel()
        self._save_soon()

    def _on_panel_resized(self, px: int) -> None:
        """Przeciągnięcie dolnej krawędzi ustala, jak daleko sięgają ikony.

        Zapisujemy ułamek wysokości ekranu, nie piksele — inaczej zasięg
        rozjechałby się po przepięciu na inny monitor.
        """
        prof, scr = self.profile, self._screen()
        if prof is None or scr is None:
            return
        ar = scr.availableGeometry()
        prof.panel_height = max(0.15, min(1.0, px / max(1, ar.height())))
        self._save_soon()

    def _show_panel(self) -> None:
        self._cancel_hide()
        if self.profile is None or self.profile.active() is None:
            return
        if not self.panel.isVisible():
            self.panel.show()
            self._pin(self.panel)

    def _schedule_hide(self) -> None:
        if self.profile and self.profile.auto_hide:
            self._hide_timer.start()

    def _cancel_hide(self) -> None:
        self._hide_timer.stop()

    def _hide_panel(self) -> None:
        """Chowa panel, chyba że kursor zdążył wrócić na dock albo na panel.

        Między dockiem a panelem jest kilka pikseli przerwy; bez tego sprawdzenia
        przejechanie przez nią zamykałoby panel w pół ruchu.
        """
        pos = QCursor.pos()
        if self.dock.isVisible() and self.dock.geometry().contains(pos):
            return
        if self.panel.isVisible() and self.panel.geometry().contains(pos):
            return
        self.panel.hide()

    # ── warstwa pulpitu ───────────────────────────────────────────────────
    def _pin(self, w) -> None:
        hwnd = int(w.winId())
        winshell.make_unobtrusive(hwnd)
        if self.profile and self.profile_always_on_top():
            winshell.set_topmost(hwnd, True)
            return
        winshell.set_topmost(hwnd, False)
        winshell.pin_above_desktop(hwnd)

    def profile_always_on_top(self) -> bool:
        return bool(self.settings.get("always_on_top", False))

    def _guard_layer(self) -> None:
        if self.profile_always_on_top():
            return
        for w in (self.dock, self.panel):
            if w.isVisible() and winshell.is_below_desktop(int(w.winId())):
                self._pin(w)

    # ── zapis ─────────────────────────────────────────────────────────────
    def _save_soon(self) -> None:
        self._save_timer.start()

    def _save(self) -> None:
        PR.save_all(self.profiles)

    def _save_settings(self) -> None:
        try:
            P.settings_path().write_text(
                json.dumps(self.settings, ensure_ascii=False, indent=1), "utf-8")
        except OSError:
            pass

    # ── opcje ─────────────────────────────────────────────────────────────
    def _menu(self, pos: QPoint) -> None:
        prof = self.profile
        if prof is None:
            return
        m = QMenu()

        m.addAction("Grupy…", self._manage_groups)

        g = prof.active()
        if g is not None:
            look = m.addMenu(f"Wygląd grupy: {g.title}")

            shape = look.addMenu("Kształt kafla")
            for label, val in (("Okładka 2:3", "portrait"), ("Kwadrat", "square")):
                a = QAction(label, shape, checkable=True)
                a.setChecked(g.aspect == val)
                a.triggered.connect(lambda _=False, v=val: self._set_group(aspect=v))
                shape.addAction(a)

            sizes = look.addMenu("Rozmiar kafla")
            for px in TILE_PRESETS:
                a = QAction(f"{px} px", sizes, checkable=True)
                a.setChecked(g.tile == px)
                a.triggered.connect(lambda _=False, v=px: self._set_group(tile=v))
                sizes.addAction(a)
            sizes.addSeparator()
            sizes.addAction("Ctrl + kółko w panelu").setEnabled(False)

            fitm = look.addMenu("Dopasowanie okładki")
            for label, val in (("Automatycznie", "auto"),
                               ("Wypełnij kafel (równa siatka)", "cover"),
                               ("Wpisz w całości — jak PyLinksWeb", "contain")):
                a = QAction(label, fitm, checkable=True)
                a.setChecked(g.fit_mode == val)
                a.triggered.connect(lambda _=False, v=val: self._set_group(fit_mode=v))
                fitm.addAction(a)

            spn = look.addMenu("Grzbiet platformy")
            for label, val in (("Jak w PyLinksWeb", "auto"), ("Zawsze", "on"),
                               ("Nigdy", "off")):
                a = QAction(label, spn, checkable=True)
                a.setChecked(g.spine == val)
                a.triggered.connect(lambda _=False, v=val: self._set_group(spine=v))
                spn.addAction(a)
            spn.addSeparator()
            if not TH.SPINE.usable:
                spn.addAction("PyLinksWeb nie ma włączonego grzbietu").setEnabled(False)
            else:
                spn.addAction("dotyczy ROM-ów i kafla kwadratowego").setEnabled(False)

            look.addSeparator()
            look.addAction("Zastosuj ten wygląd do wszystkich grup",
                           self._apply_look_to_all)

        scroll = m.addMenu("Przewijanie")
        for label, val in (("Bardzo wolne", 0.3), ("Wolne", 0.5),
                           ("Zwykłe", 0.7), ("Szybkie", 1.2)):
            a = QAction(label, scroll, checkable=True)
            a.setChecked(abs(prof.scroll_speed - val) < 0.05)
            a.triggered.connect(lambda _=False, v=val: self._set_scroll_speed(v))
            scroll.addAction(a)

        a_lbl = QAction("Podpisy pod kaflami", m, checkable=True)
        a_lbl.setChecked(prof.show_labels)
        a_lbl.triggered.connect(self._toggle_labels)
        m.addAction(a_lbl)

        m.addAction("Przezroczystość…", self._set_opacity)
        a_top = QAction("Zawsze na wierzchu", m, checkable=True)
        a_top.setChecked(self.profile_always_on_top())
        a_top.triggered.connect(self._toggle_on_top)
        m.addAction(a_top)

        m.addSeparator()
        a_start = QAction("Uruchamiaj przy starcie Windows", m, checkable=True)
        a_start.setChecked(autostart.is_enabled())
        a_start.triggered.connect(self._toggle_autostart)
        m.addAction(a_start)
        m.addAction("Katalog PyLinksWeb…", self._choose_dir)
        m.addAction("Odśwież bibliotekę", self.reload_library)
        m.addAction("Ustaw wszystko od nowa", self._reset_profile)
        info = m.addAction(f"Profil: {prof.label}")
        info.setEnabled(False)
        m.addSeparator()
        m.addAction("Zamknij Deck", QApplication.quit)
        m.exec(pos)

    # ── akcje opcji ───────────────────────────────────────────────────────
    def _manage_groups(self) -> None:
        prof = self.profile
        if prof is None:
            return
        dlg = GroupsDialog(prof.groups)
        if dlg.exec() != GroupsDialog.Accepted:
            return
        by_gid = {g.gid: g for g in prof.groups}
        ordered, seen = [], set()
        for gid, title, hidden in dlg.result_order():
            g = by_gid.get(gid)
            if g is None or gid in seen:
                continue
            g.title, g.hidden = title, hidden
            ordered.append(g)
            seen.add(gid)
        for g in prof.groups:
            if g.gid not in seen:
                ordered.append(g)
        prof.groups = ordered
        if prof.active() is None and prof.visible_groups():
            prof.active_gid = prof.visible_groups()[0].gid
        self.dock.set_groups(prof.visible_groups(),
                             prof.active().gid if prof.active() else "")
        self._refresh_panel()
        self._save()

    def _set_group(self, **changes) -> None:
        """Zmienia wygląd aktywnej grupy — każda zakładka ma własne ustawienia."""
        g = self.profile.active() if self.profile else None
        if g is None:
            return
        for name, value in changes.items():
            setattr(g, name, value)
        self._refresh_panel()
        self._save()

    def _apply_look_to_all(self) -> None:
        """Kopiuje wygląd aktywnej grupy na pozostałe zakładki."""
        prof = self.profile
        src = prof.active() if prof else None
        if src is None:
            return
        for g in prof.groups:
            g.aspect, g.tile = src.aspect, src.tile
            g.fit_mode, g.spine = src.fit_mode, src.spine
        self._refresh_panel()
        self._save()

    def _set_scroll_speed(self, value: float) -> None:
        if self.profile:
            self.profile.scroll_speed = value
            self.panel.set_scroll_speed(value)
            self._save()

    def _toggle_labels(self, on: bool) -> None:
        if self.profile:
            self.profile.show_labels = on
            self._refresh_panel()
            self._save()

    def _toggle_logos(self, on: bool) -> None:
        if self.profile:
            self.profile.show_logos = on
            self.dock.set_show_logos(on)
            self._save()

    def _set_logo_style(self, style: str) -> None:
        if self.profile:
            self.profile.logo_style = style
            self.logos.set_style(style)
            self.dock.update()
            self._save()

    def _set_dock_width(self, val: float) -> None:
        if self.profile:
            self.profile.dock_width = val
            self._layout_windows()
            self._save()

    def _set_dock_height(self, val: int) -> None:
        if self.profile:
            self.profile.dock_height = val
            self._layout_windows()
            self._save()

    def _set_panel_height(self, val: float) -> None:
        if self.profile:
            self.profile.panel_height = val
            self._layout_windows()
            self._save()

    def _set_panel_width(self, val: float) -> None:
        if self.profile:
            self.profile.panel_width = val
            self._layout_windows()
            self._save()

    def _toggle_auto_hide(self, on: bool) -> None:
        if self.profile:
            self.profile.auto_hide = on
            self._save()

    def _toggle_on_top(self, on: bool) -> None:
        self.settings["always_on_top"] = bool(on)
        self._save_settings()
        self._pin(self.dock)
        if self.panel.isVisible():
            self._pin(self.panel)

    def _set_opacity(self) -> None:
        if not self.profile:
            return
        val, ok = QInputDialog.getInt(None, "Przezroczystość", "Krycie (%):",
                                      int(self.profile.opacity * 100), 40, 100, 5)
        if ok:
            self.profile.opacity = val / 100.0
            self._layout_windows()
            self._save()

    def _reset_profile(self) -> None:
        if not self.profile:
            return
        if QMessageBox.question(None, "Ustawienia od nowa",
                                "Odtworzyć zakładki i ustawienia dla tego ekranu?") \
                != QMessageBox.Yes:
            return
        self.profiles.pop(self.profile.sig, None)
        self._apply_profile()

    def _choose_dir(self) -> None:
        """Wskazanie katalogu danych PyLinksWeb (tego z config.json i LINKS)."""
        path = QFileDialog.getExistingDirectory(
            None, "Katalog PyLinksWeb (z config.json i LINKS)", str(self.base))
        if not path:
            return
        cand = Path(path)
        if not P.is_data_dir(cand):
            QMessageBox.warning(
                None, "Katalog PyLinksWeb",
                "W tym katalogu nie ma config.json ani LINKS. Wskaż ten, w którym leży PyLinksWeb.exe.")
            return
        self.settings["pylinks_dir"] = str(cand)
        self._save_settings()
        self.base = cand
        self.logos = L.LogoSet(self.base, self.profile.logo_style
                               if self.profile else "default")
        self.dock.logos = self.logos
        self._apply_spine_settings()
        self.reload_library()
        self._refresh_panel()

    def _toggle_autostart(self, on: bool) -> None:
        if not autostart.set_enabled(on):
            QMessageBox.warning(None, "Autostart",
                                "Nie udało się zapisać wpisu w rejestrze użytkownika.")

    # ── zasobnik ──────────────────────────────────────────────────────────
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(_tray_icon())
        self.tray.setToolTip("PyLinks Deck")
        menu = QMenu()
        menu.addAction("Pokaż / ukryj dock", self._toggle_dock)
        menu.addAction("Grupy…", self._manage_groups)
        menu.addAction("Opcje…", lambda: self._menu(self.dock.mapToGlobal(
            QPoint(self.dock.width() // 2, self.dock.height()))))
        menu.addAction("Odśwież bibliotekę", self.reload_library)
        menu.addSeparator()
        menu.addAction("Zamknij", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self._toggle_dock() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def _toggle_dock(self) -> None:
        if self.dock.isVisible():
            self.panel.hide()
            self.dock.hide()
        else:
            self.dock.show()
            self._pin(self.dock)

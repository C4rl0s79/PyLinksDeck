"""deck.ui.deck_app — spina wszystko: dock, panel, ustawienia, zasobnik, opcje.

Model interakcji: na pulpicie leży wyłącznie belka zakładek. Najechanie na nią
rozwija panel z kaflami wybranej grupy, kliknięcie zakładki przełącza grupę,
zjechanie myszą panel chowa. Prawy przycisk na docku otwiera pełne opcje.

Ustawienia zakładek są **wspólne dla wszystkich ekranów** — przepięcie monitora
nie może zmieniać tego, co ukryte ani jak wygląda siatka. Od rozdzielczości
zależą wyłącznie wymiary docka i panelu, i te trzymamy osobno per zestaw ekranów.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import (QAction, QColor, QCursor, QGuiApplication, QIcon,
                           QPainter, QPixmap)
from PySide6.QtWidgets import (QApplication, QFileDialog, QInputDialog, QMenu,
                               QMessageBox, QSystemTrayIcon)

from deck import (autostart, library, logos as L, paths as P,
                  profiles as PR, spine as SP, winshell)
from deck import thumbs as TH
from deck.thumbs import ThumbCache
from deck.ui.dock import DockBar
from deck.ui.groups_dialog import GroupsDialog
from deck.ui.launch_fx import flash
from deck.ui.panel import PanelWindow

COL_PRESETS = (3, 4, 5, 6, 8, 10, 12, 16)
DOCK_WIDTHS = ((0.5, "połowa"), (0.7, "70 %"), (0.86, "86 %"), (1.0, "cała szerokość"))
DOCK_HEIGHTS = (36, 46, 56, 72, 96)
PANEL_HEIGHTS = ((0.5, "50 %"), (0.65, "65 %"), (0.8, "80 %"), (0.92, "92 %"))
PANEL_WIDTHS = ((0.7, "70 %"), (0.84, "84 %"), (0.94, "94 %"), (1.0, "100 %"))
SCROLL_SPEEDS = (("Bardzo wolne", 0.3), ("Wolne", 0.5), ("Zwykłe", 0.7),
                 ("Szybkie", 1.2))


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
        self.cfg = PR.load() or PR.Settings()
        self.sig, self.sig_label = "", ""

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
        self.panel.cols_changed.connect(self._on_cols_changed)
        self.panel.height_changed.connect(self._on_panel_resized)
        self.panel.launched.connect(self._on_launched)
        self._flash = None          # referencja, żeby okno efektu przeżyło

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
        self._screen_timer.timeout.connect(self._apply_screen)

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
        self._apply_screen()

    # ── ustawienia programu (niezależne od profilu wyglądu) ───────────────
    @staticmethod
    def _load_settings() -> dict:
        try:
            return json.loads(P.settings_path().read_text("utf-8"))
        except Exception:
            return {}

    def _save_settings(self) -> None:
        try:
            P.settings_path().write_text(
                json.dumps(self.settings, ensure_ascii=False, indent=1), "utf-8")
        except OSError:
            pass

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

    # ── biblioteka ────────────────────────────────────────────────────────
    def reload_library(self) -> None:
        """Przeładowuje bibliotekę **wraz z grafiką**.

        Sama lista gier to za mało: kafle siedzą w cache pamięciowym pod kluczem
        (gra, rozmiar, tryb), a znacznik pliku źródłowego jest tylko w nazwie
        pliku na dysku. Bez wyczyszczenia pamięci podmieniona w PyLinksWeb
        okładka pokazywałaby się dopiero po restarcie.
        """
        self.items = library.load(self.base)
        self.cache.clear()
        self.logos.refresh()
        self._apply_spine_settings()
        if not self.cfg.groups:
            self.cfg = PR.default_settings(self.items)
        self._sync_groups()
        self._refresh_panel()
        self.dock.update()

    def _sync_groups(self) -> None:
        """Dostraja zakładki do zawartości biblioteki, nie ruszając ustawień.

        Dokłada platformy i kolekcje, których jeszcze nie znamy, i chowa te bez
        ani jednej gry. Widoczność, kolejność i wygląd istniejących zakładek
        zostają nietknięte — to wybór użytkownika, nie coś do przeliczenia.
        """
        known = {g.gid for g in self.cfg.groups}
        plats: dict[str, int] = {}
        colls: dict[str, int] = {}
        for it in self.items:
            plats[it.platform] = plats.get(it.platform, 0) + 1
            for c in it.collections:
                colls[c] = colls.get(c, 0) + 1

        for name in sorted(colls, key=lambda c: -colls[c]):
            gid = f"coll::{name}"
            if gid not in known:
                self.cfg.groups.append(PR.Group(
                    gid=gid, title=name.title(),
                    rule={"kind": "collection", "value": name}))
        for name in sorted(plats, key=lambda p: (-plats[p], p)):
            gid = f"plat::{name}"
            if gid not in known:
                self.cfg.groups.append(PR.Group(
                    gid=gid, title=name, rule={"kind": "platform", "value": name}))

        for g in self.cfg.groups:
            if not any(g.matches(it) for it in self.items):
                g.hidden = True
        if self.cfg.active() is None and self.cfg.visible_groups():
            self.cfg.active_gid = self.cfg.visible_groups()[0].gid
        self.dock.set_show_logos(self.cfg.show_logos)
        self.dock.set_groups(self.cfg.visible_groups(),
                             self.cfg.active().gid if self.cfg.active() else "")
        self._save_soon()

    # ── ekran ─────────────────────────────────────────────────────────────
    def _screen(self):
        return QGuiApplication.primaryScreen()      # Deck żyje na ekranie głównym

    @property
    def layout(self) -> PR.ScreenLayout:
        return self.cfg.layout(self.sig, self.sig_label)

    def _apply_screen(self) -> None:
        """Reaguje na zmianę monitorów: przelicza wymiary, nie ustawienia.

        Zakładki, ich widoczność i wygląd są wspólne — przepięcie ekranu ma
        zmienić tylko to, ile miejsca zajmuje dock i panel.
        """
        app = QGuiApplication.instance()
        self.sig, self.sig_label = PR.signature(app.screens())
        self.logos.set_style(self.cfg.logo_style)
        self._layout_windows()
        self.dock.set_show_logos(self.cfg.show_logos)
        self.dock.set_groups(self.cfg.visible_groups(),
                             self.cfg.active().gid if self.cfg.active() else "")
        self.dock.show()
        self._pin(self.dock)
        self._refresh_panel()
        self._save()

    def _layout_windows(self) -> None:
        scr = self._screen()
        if scr is None:
            return
        lay = self.layout
        ar = scr.availableGeometry()
        dw = max(240, int(ar.width() * lay.dock_width))
        dh = max(28, int(lay.dock_height))
        dx = ar.x() + (ar.width() - dw) // 2
        dy = ar.y() + max(0, lay.dock_offset)
        self.dock.setGeometry(dx, dy, dw, dh)
        self.dock.setWindowOpacity(self.cfg.opacity)
        self.panel.setWindowOpacity(self.cfg.opacity)
        if self.panel.isVisible():
            self.panel.reveal(self._panel_rect(), False)

    def _panel_rect(self) -> QRect:
        """Docelowa geometria panelu: tak wysoki, jak trzeba, nie wyżej niż profil."""
        scr = self._screen()
        if scr is None:
            return QRect()
        lay = self.layout
        ar = scr.availableGeometry()
        pw = max(320, int(ar.width() * lay.panel_width))
        top = self.dock.geometry().bottom() + 8
        limit = min(int(ar.height() * lay.panel_height),
                    ar.y() + ar.height() - top - 8)
        ph = max(160, min(limit, self.panel.content_height(pw)))
        return QRect(ar.x() + (ar.width() - pw) // 2, top, pw, ph)

    def _refresh_panel(self) -> None:
        g = self.cfg.active()
        if g is None:
            self.panel.hide()
            return
        scr = self._screen()
        dpr = float(scr.devicePixelRatio()) if scr else 1.0
        picked = [it for it in self.items if g.matches(it)]
        picked.sort(key=lambda i: (i.platform, i.sort_name) if g.sort == "platform"
                    else (i.sort_name,))
        self.panel.set_scroll_speed(self.cfg.scroll_speed)
        self.panel.set_group(g, picked, dpr, self.cfg.show_labels, self.spine_for(g))
        self._fit_panel()

    def _fit_panel(self) -> None:
        rect = self._panel_rect()
        if rect.isNull():
            return
        if self.panel.isVisible():
            self.panel.reveal(rect, False)
        else:
            self.panel._target = rect

    # ── zakładki i panel ──────────────────────────────────────────────────
    def _on_tab(self, gid: str) -> None:
        self.cfg.active_gid = gid
        self.dock.set_active(gid)
        self._refresh_panel()
        self._show_panel()
        self._save_soon()

    def _show_panel(self) -> None:
        self._cancel_hide()
        if self.cfg.active() is None:
            return
        was_hidden = not self.panel.isVisible()
        self.panel.reveal(self._panel_rect(), self.cfg.animations)
        if was_hidden:
            self._pin(self.panel)

    def _schedule_hide(self) -> None:
        if self.cfg.auto_hide:
            self._hide_timer.start()

    def _cancel_hide(self) -> None:
        self._hide_timer.stop()

    def _hide_panel(self) -> None:
        """Chowa panel, chyba że kursor zdążył wrócić na dock albo na panel."""
        pos = QCursor.pos()
        if self.dock.isVisible() and self.dock.geometry().contains(pos):
            return
        if self.panel.isVisible() and self.panel.geometry().contains(pos):
            return
        self.panel.dismiss(self.cfg.animations)

    def _on_cols_changed(self, gid: str, cols: int) -> None:
        self._fit_panel()
        self._save_soon()

    def _on_panel_resized(self, px: int) -> None:
        """Przeciągnięcie dolnej krawędzi ustala zasięg ikon — zapisujemy ułamek
        wysokości ekranu, żeby przeniósł się na inne rozdzielczości."""
        scr = self._screen()
        if scr is None:
            return
        ar = scr.availableGeometry()
        self.layout.panel_height = max(0.15, min(1.0, px / max(1, ar.height())))
        self._save_soon()

    def _on_launched(self, item, rect: QRect, pixmap) -> None:
        """Kafel wystrzeliwuje na pełny ekran, panel zwija się za nim."""
        if self.cfg.animations:
            scr = self._screen()
            if scr is not None:
                self._flash = flash(pixmap, rect, scr.geometry())
        self.panel.dismiss(self.cfg.animations)

    # ── warstwa pulpitu ───────────────────────────────────────────────────
    def _pin(self, w) -> None:
        hwnd = int(w.winId())
        winshell.make_unobtrusive(hwnd)
        if self.settings.get("always_on_top", False):
            winshell.set_topmost(hwnd, True)
            return
        winshell.set_topmost(hwnd, False)
        winshell.pin_above_desktop(hwnd)

    def _guard_layer(self) -> None:
        if self.settings.get("always_on_top", False):
            return
        for w in (self.dock, self.panel):
            if w.isVisible() and winshell.is_below_desktop(int(w.winId())):
                self._pin(w)

    # ── zapis ─────────────────────────────────────────────────────────────
    def _save_soon(self) -> None:
        self._save_timer.start()

    def _save(self) -> None:
        PR.save(self.cfg)

    # ── opcje ─────────────────────────────────────────────────────────────
    def _menu(self, pos: QPoint) -> None:
        m = QMenu()
        m.addAction("Grupy…", self._manage_groups)

        g = self.cfg.active()
        if g is not None:
            look = m.addMenu(f"Wygląd grupy: {g.title}")

            shape = look.addMenu("Kształt kafla")
            for label, val in (("Okładka 2:3", "portrait"), ("Kwadrat", "square")):
                a = QAction(label, shape, checkable=True)
                a.setChecked(g.aspect == val)
                a.triggered.connect(lambda _=False, v=val: self._set_group(aspect=v))
                shape.addAction(a)

            cols = look.addMenu("Kafli w wierszu")
            for n in COL_PRESETS:
                a = QAction(str(n), cols, checkable=True)
                a.setChecked(g.cols == n)
                a.triggered.connect(lambda _=False, v=n: self._set_group(cols=v))
                cols.addAction(a)
            cols.addSeparator()
            cols.addAction("Ctrl + kółko w panelu").setEnabled(False)

            fitm = look.addMenu("Dopasowanie okładki")
            for label, val in (("Rozciągnij do kafla (nic nie ucina)", "auto"),
                               ("Wypełnij kadrując (ucina brzegi)", "cover"),
                               ("Wpisz w całości — jak PyLinksWeb", "contain")):
                a = QAction(label, fitm, checkable=True)
                a.setChecked(g.fit_mode == val or
                             (val == "auto" and g.fit_mode not in ("cover", "contain")))
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
            spn.addAction("dotyczy ROM-ów i kafla kwadratowego").setEnabled(False)

            look.addSeparator()
            look.addAction("Zastosuj ten wygląd do wszystkich grup",
                           self._apply_look_to_all)

        scroll = m.addMenu("Przewijanie")
        for label, val in SCROLL_SPEEDS:
            a = QAction(label, scroll, checkable=True)
            a.setChecked(abs(self.cfg.scroll_speed - val) < 0.05)
            a.triggered.connect(lambda _=False, v=val: self._set_scroll_speed(v))
            scroll.addAction(a)

        a_anim = QAction("Animacje", m, checkable=True)
        a_anim.setChecked(self.cfg.animations)
        a_anim.triggered.connect(self._toggle_animations)
        m.addAction(a_anim)

        a_lbl = QAction("Podpisy pod kaflami", m, checkable=True)
        a_lbl.setChecked(self.cfg.show_labels)
        a_lbl.triggered.connect(self._toggle_labels)
        m.addAction(a_lbl)

        m.addSeparator()
        logo_menu = m.addMenu("Logotypy platform")
        a_logo = QAction("Pokazuj zamiast nazw", logo_menu, checkable=True)
        a_logo.setChecked(self.cfg.show_logos)
        a_logo.triggered.connect(self._toggle_logos)
        logo_menu.addAction(a_logo)
        if self.logos.root is None:
            logo_menu.addAction("brak katalogu logotypów w PyLinksWeb").setEnabled(False)
        else:
            logo_menu.addSeparator()
            logo_menu.addAction(f"katalog: {self.logos.root}").setEnabled(False)

        lay = self.layout
        dock_menu = m.addMenu("Dock")
        wsub = dock_menu.addMenu("Szerokość")
        for val, label in DOCK_WIDTHS:
            a = QAction(label, wsub, checkable=True)
            a.setChecked(abs(lay.dock_width - val) < 0.01)
            a.triggered.connect(lambda _=False, v=val: self._set_dock(dock_width=v))
            wsub.addAction(a)
        hsub = dock_menu.addMenu("Wysokość")
        for val in DOCK_HEIGHTS:
            a = QAction(f"{val} px", hsub, checkable=True)
            a.setChecked(lay.dock_height == val)
            a.triggered.connect(lambda _=False, v=val: self._set_dock(dock_height=v))
            hsub.addAction(a)

        panel_menu = m.addMenu("Panel")
        psub = panel_menu.addMenu("Wysokość")
        for val, label in PANEL_HEIGHTS:
            a = QAction(label, psub, checkable=True)
            a.setChecked(abs(lay.panel_height - val) < 0.01)
            a.triggered.connect(lambda _=False, v=val: self._set_dock(panel_height=v))
            psub.addAction(a)
        wsub2 = panel_menu.addMenu("Szerokość")
        for val, label in PANEL_WIDTHS:
            a = QAction(label, wsub2, checkable=True)
            a.setChecked(abs(lay.panel_width - val) < 0.01)
            a.triggered.connect(lambda _=False, v=val: self._set_dock(panel_width=v))
            wsub2.addAction(a)
        a_auto = QAction("Chowaj po zjechaniu myszą", panel_menu, checkable=True)
        a_auto.setChecked(self.cfg.auto_hide)
        a_auto.triggered.connect(self._toggle_auto_hide)
        panel_menu.addAction(a_auto)

        m.addAction("Przezroczystość…", self._set_opacity)
        a_top = QAction("Zawsze na wierzchu", m, checkable=True)
        a_top.setChecked(bool(self.settings.get("always_on_top", False)))
        a_top.triggered.connect(self._toggle_on_top)
        m.addAction(a_top)

        m.addSeparator()
        a_start = QAction("Uruchamiaj przy starcie Windows", m, checkable=True)
        a_start.setChecked(autostart.is_enabled())
        a_start.triggered.connect(self._toggle_autostart)
        m.addAction(a_start)
        m.addAction("Katalog PyLinksWeb…", self._choose_dir)
        m.addAction("Wyczyść cache miniatur", self._clear_thumbs)
        m.addAction("Odśwież bibliotekę", self.reload_library)
        m.addAction("Ustaw wszystko od nowa", self._reset_settings)
        info = m.addAction(f"Ekran: {self.sig_label}")
        info.setEnabled(False)
        m.addSeparator()
        m.addAction("Zamknij Deck", QApplication.quit)
        m.exec(pos)

    # ── akcje ─────────────────────────────────────────────────────────────
    def _set_group(self, **changes) -> None:
        """Zmienia wygląd aktywnej grupy — każda zakładka ma własne ustawienia."""
        g = self.cfg.active()
        if g is None:
            return
        for name, value in changes.items():
            setattr(g, name, PR.clamp_cols(value) if name == "cols" else value)
        self._refresh_panel()
        self._save()

    def _apply_look_to_all(self) -> None:
        src = self.cfg.active()
        if src is None:
            return
        for g in self.cfg.groups:
            g.aspect, g.cols = src.aspect, src.cols
            g.fit_mode, g.spine = src.fit_mode, src.spine
        self._refresh_panel()
        self._save()

    def _set_dock(self, **changes) -> None:
        """Wymiary docka i panelu — jedyne ustawienia zależne od ekranu."""
        lay = self.layout
        for name, value in changes.items():
            setattr(lay, name, value)
        self._layout_windows()
        self._fit_panel()
        self._save()

    def _set_scroll_speed(self, value: float) -> None:
        self.cfg.scroll_speed = value
        self.panel.set_scroll_speed(value)
        self._save()

    def _toggle_animations(self, on: bool) -> None:
        self.cfg.animations = on
        self._save()

    def _toggle_labels(self, on: bool) -> None:
        self.cfg.show_labels = on
        self._refresh_panel()
        self._save()

    def _toggle_logos(self, on: bool) -> None:
        self.cfg.show_logos = on
        self.dock.set_show_logos(on)
        self._save()

    def _toggle_auto_hide(self, on: bool) -> None:
        self.cfg.auto_hide = on
        self._save()

    def _toggle_on_top(self, on: bool) -> None:
        self.settings["always_on_top"] = bool(on)
        self._save_settings()
        self._pin(self.dock)
        if self.panel.isVisible():
            self._pin(self.panel)

    def _set_opacity(self) -> None:
        val, ok = QInputDialog.getInt(None, "Przezroczystość", "Krycie (%):",
                                      int(self.cfg.opacity * 100), 40, 100, 5)
        if ok:
            self.cfg.opacity = val / 100.0
            self._layout_windows()
            self._save()

    def _manage_groups(self) -> None:
        dlg = GroupsDialog(self.cfg.groups)
        if dlg.exec() != GroupsDialog.Accepted:
            return
        by_gid = {g.gid: g for g in self.cfg.groups}
        ordered, seen = [], set()
        for gid, title, hidden in dlg.result_order():
            g = by_gid.get(gid)
            if g is None or gid in seen:
                continue
            g.title, g.hidden = title, hidden
            ordered.append(g)
            seen.add(gid)
        for g in self.cfg.groups:
            if g.gid not in seen:
                ordered.append(g)
        self.cfg.groups = ordered
        if self.cfg.active() is None and self.cfg.visible_groups():
            self.cfg.active_gid = self.cfg.visible_groups()[0].gid
        self.dock.set_groups(self.cfg.visible_groups(),
                             self.cfg.active().gid if self.cfg.active() else "")
        self._refresh_panel()
        self._save()

    def _reset_settings(self) -> None:
        if QMessageBox.question(None, "Ustawienia od nowa",
                                "Odtworzyć zakładki i wygląd od zera?") \
                != QMessageBox.Yes:
            return
        screens = self.cfg.screens          # wymiary ekranów zostawiamy
        self.cfg = PR.default_settings(self.items)
        self.cfg.screens = screens
        self._sync_groups()
        self._apply_screen()

    def _clear_thumbs(self) -> None:
        """Kasuje wyrenderowane kafle z dysku i buduje je od nowa."""
        removed = 0
        for f in P.thumbs_dir().glob("*.png"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        self.reload_library()
        QMessageBox.information(None, "Cache miniatur",
                                f"Usunięto {removed} plików. Kafle liczą się od nowa.")

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
                "W tym katalogu nie ma config.json ani LINKS. Wskaż ten, w którym "
                "leży PyLinksWeb.exe.")
            return
        self.settings["pylinks_dir"] = str(cand)
        self._save_settings()
        self.base = cand
        self.logos = L.LogoSet(self.base, self.cfg.logo_style)
        self.dock.logos = self.logos
        self._apply_spine_settings()
        self.reload_library()

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

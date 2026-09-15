"""deck.series_order — układanie gier jednej serii obok siebie.

Przynależność do serii i daty przychodzą z PyLinksWeb (tabela `game_series`,
rozpoznawana w IGDB). Z samej nazwy nie da się jej wyczytać: „Yakuza 0",
„Yakuza Kiwami" i „Like a Dragon: Infinite Wealth" to jedna seria mimo zmiany
nazwy, a trylogia Legend of Heroes na PSP ma numerację inną niż kolejność wydań.

Zasady:
* seria stoi w miejscu, w którym alfabetycznie wypada JEJ nazwa (przedimek
  „The" pomijany — „The Legend of Heroes" trafia pod L),
* w obrębie serii — ręczna kolejność użytkownika, jeśli ją ustawił, a potem
  data wydania oryginału (remake i port mają już datę oryginału, patrz PyLinksWeb),
* przy tej samej dacie oryginału — data wydania TEJ wersji: automat Tekkena
  (1994-12) przed portem na PS1 (1995-03), choć oba wskazują ten sam oryginał,
* gry bez rozpoznanej serii układają się po nazwie, dokładnie jak wcześniej.

IGDB zna tylko daty. Kolejności fabularnej (Yakuza 0 przed Kiwami) nie ma
w żadnym źródle, dlatego istnieje ręczne przesuwanie.
"""

from __future__ import annotations

import re

_NORM = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    return _NORM.sub("", (text or "").lower())


def series_sort_name(franchise: str) -> str:
    """Nazwa serii do sortowania — bez wiodącego przedimka „The"."""
    t = (franchise or "").strip()
    if t.lower().startswith("the "):
        t = t[4:]
    return _norm(t)


def make_sort_key(manual: dict):
    """Klucz sortowania z uwzględnieniem ręcznej kolejności `{seria: [klucze]}`.

    Wszystkie krotki mają ten sam kształt (str, int, int, int, int, int, str), żeby
    porównanie gry z serii i gry luźnej nigdy nie trafiło na różne typy.
    """
    manual = manual or {}

    def key(it) -> tuple:
        fr = getattr(it, "franchise", "") or ""
        name = getattr(it, "sort_name", "") or ""
        if not fr:
            return (name, 1, 0, 0, 0, 0, name)
        lista = manual.get(fr) or []
        if it.key in lista:
            return (series_sort_name(fr), 0, 0, lista.index(it.key), 0, 0, name)
        return (series_sort_name(fr), 0, 1, 0,
                int(getattr(it, "order_ts", 0) or 0),
                int(getattr(it, "release_ts", 0) or 0), name)

    return key


def move_in_series(items: list, target, delta: int, manual: dict) -> dict:
    """Przesuwa `target` o `delta` pozycji w obrębie jego serii.

    `items` to gry WIDOCZNE w bieżącej zakładce. Zapisujemy pełną kolejność serii
    z tej zakładki, żeby względne położenie pozostałych gier nie skakało; klucze
    z innych zakładek (np. ta sama seria na innej platformie) zostają na końcu
    listy w dotychczasowej kolejności.
    """
    fr = getattr(target, "franchise", "") or ""
    if not fr:
        return manual
    key = make_sort_key(manual)
    czlonkowie = [it.key for it in sorted(items, key=key)
                  if (getattr(it, "franchise", "") or "") == fr]
    if target.key not in czlonkowie:
        return manual
    i = czlonkowie.index(target.key)
    j = i + delta
    if not 0 <= j < len(czlonkowie):
        return manual
    czlonkowie[i], czlonkowie[j] = czlonkowie[j], czlonkowie[i]
    reszta = [k for k in (manual.get(fr) or []) if k not in czlonkowie]
    wynik = dict(manual)
    wynik[fr] = czlonkowie + reszta
    return wynik


def reset_series(manual: dict, franchise: str) -> dict:
    """Wraca do kolejności z IGDB (usuwa ręczne ustawienie serii)."""
    wynik = dict(manual or {})
    wynik.pop(franchise, None)
    return wynik

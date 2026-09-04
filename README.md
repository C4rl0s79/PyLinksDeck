# PyLinks Deck

Dock z ikonami gier z PyLinksWeb — rysowany od zera, bez pośrednictwa powłoki
Windows.

## Po co, skoro jest pulpit i Fences

Ramki Fences to w praktyce Folder Portal: okno pokazujące zawartość katalogu,
rysowaną i tak przez powłokę. Stąd trzy ograniczenia, których nie da się tam obejść:

| Problem | Przyczyna | Co robi Deck |
| --- | --- | --- |
| Powyżej pewnego rozmiaru rośnie tylko odstęp, nie ikona | ikona shellowa to `.ico`, a jego największa klatka ma 256×256 | kafel powstaje z surowej okładki (600×900 i więcej); rozmiar ogranicza tylko rozdzielczość źródła |
| Po zmianie ekranu układ się rozjeżdża | Explorer trzyma pozycje ikon w pikselach dla bieżącej rozdzielczości | dock i panel wynikają z ułamków obszaru roboczego |
| Przy każdym ekranie trzeba ustawiać rozmiar od nowa | jedno globalne ustawienie widoku | osobny profil na każdy zestaw monitorów, przełączany automatycznie |

## Jak to działa

Na pulpicie leży **belka zakładek** — po jednej na grupę. Szerokość zakładki to
szerokość docka podzielona przez liczbę widocznych grup, więc belka zawsze jest
wypełniona równo, niezależnie od długości nazw.

- **najechanie na dock** → rozwija panel z kaflami na prawie cały pulpit,
- **kliknięcie zakładki** → przełącza wyświetlaną grupę,
- **kółko nad dockiem** → przerzuca zakładki,
- **zjechanie myszą** → panel się chowa (można wyłączyć),
- **prawy klik na docku** → pełne opcje.

Panel jest tak wysoki, jak trzeba: trzy gry nie rozpychają go na cały ekran, a
sto pięćdziesiąt wypełnia go do limitu z profilu.

## Uruchomienie

```bash
python main.py
```

Podgląd samego rysunku, bez szukania odsłoniętego pulpitu:

```bash
python main.py --shot podglad.png 8
```

## Sterowanie

| Akcja | Efekt |
| --- | --- |
| dwuklik na kaflu | uruchamia grę (przez jej skrót `.lnk`, ze wszystkimi argumentami) |
| Ctrl + kółko w panelu | rozmiar kafli bieżącej grupy |
| kółko nad dockiem | poprzednia / następna zakładka |
| kółko w panelu | płynne, animowane przewijanie |
| przeciągnięcie dolnej krawędzi panelu | ustawia zasięg — jak daleko sięgają ikony |
| prawy klik na docku | opcje: grupy, rozmiar i kształt kafli, logotypy, dock, panel, autostart |
| `Grupy…` | kolejność zakładek, widoczność, nazwy |
| klik w ikonę w zasobniku | pokazuje / ukrywa dock |
| dwuklik (efekt) | kafel rozciąga się na pełny ekran i gaśnie, panel się zwija |

### Siatka i skalowanie kafli

Odstęp między kaflami jest stały (8 px logicznych), a kafle dopasowują się do
szerokości panelu: rozmiar z profilu wyznacza *liczbę kolumn*, po czym kafle
rozciągają się tak, by wypełnić wiersz. Ctrl+kółko zmienia rozmiar preferowany,
czyli w praktyce liczbę kolumn. Wszystkie wymiary układu są logiczne, więc
proporcje i odstępy wyglądają tak samo przy każdej rozdzielczości i każdym
skalowaniu ekranu.

### Renderowanie kafli

Kręcenie kółkiem nie pokazuje po kolei wszystkich rozmiarów, przez które
przejeżdżasz. W trakcie skalowania panel rysuje kafel, który już ma w pamięci,
rozciągnięty do nowej ramki; render właściwego rozmiaru rusza dopiero po
zatrzymaniu kółka (ok. 0,2 s). Gotowe rozmiary lądują w cache na dysku, więc
powrót do wcześniejszej skali jest natychmiastowy.

## Wygląd — osobno dla każdej zakładki

`Wygląd grupy: <nazwa>` w opcjach dotyczy **aktywnej zakładki**, więc PC może mieć
kafle kwadratowe, a konsole portretowe. `Zastosuj ten wygląd do wszystkich grup`
kopiuje ustawienia na resztę.

**Kształt kafla** — okładka 2:3 albo kwadrat.

**Dopasowanie okładki**:

- **Wypełnij kafel (kadruj)** — domyślne. Kafel jest zawsze pełny; o tym, która
  część obrazu zostaje, decyduje `offset` z PyLinksWeb. Plakat wyraźnie szerszy
  od ramki straci boki — to świadomy wybór na rzecz równej siatki.
- **Wpisz w całości — jak PyLinksWeb** — wierne odwzorowanie jego ikon (`fit`
  i `offset` z bazy), kosztem pasów przy okładkach o innych proporcjach.

Kadr (`offset`) zawsze pochodzi z PyLinksWeb — sprawdzone porównaniem piksel po
pikselu z jego `display_thumb_img`: przy kwadracie wynik jest identyczny.

**Grzbiet platformy** — gdy w PyLinksWeb włączony jest `icon_platform_spine`,
kwadratowa ikona ROM-a to pionowy grzbiet z logotypem plus okładka rozciągnięta
na resztę pola (i dlatego takie ikony nie mają pustych pasów — `fit`/`offset`
w ogóle nie wchodzą tam w grę). Deck odtwarza tę kompozycję, ale renderuje ją
wprost w rozmiarze kafla, więc grzbiet jest ostry także przy 512 px. Dotyczy
wyłącznie ROM-ów i kafla kwadratowego; `Zawsze` / `Nigdy` wymuszają zachowanie.

## Logotypy platform

Zakładka pokazuje logotyp platformy zamiast nazwy — grafiki bierzemy z katalogu
`platform_logo_dir` z konfiguracji PyLinksWeb (u Ciebie `D:\PyLinks\platform_logos`),
tego samego, z którego powstają grzbiety okładek.

Logotypy są bardzo szerokie (od 3:1 do prawie 9:1), więc skalujemy je w obu
wymiarach naraz i schodzimy na tekst, gdy w danej szerokości zakładki wyszłyby
niższe niż 11 px. Ciemne logotypy (czarne litery) dostają jasny podkład —
odwracanie kolorów odpadło, bo robiło z czerwonego SNES-a cyjanowy.

Przełącznik `Logotypy platform → Pokazuj zamiast nazw` w opcjach wyłącza je
w całości.

## Skąd bierze dane

Deck **tylko czyta** katalog PyLinksWeb (domyślnie `D:\py\PyLinksWeb`), niczego
tam nie zapisuje:

- `LINKS/<PLATFORMA>/*.lnk` — lista gier i sposób uruchomienia,
- `Cache/covers/icon/` — okładki w pełnej rozdzielczości,
- `Cache/pylinks.db` — kadrowanie (`crops`) i rodzice setów MAME,
- `config.json` — kolekcje (stają się zakładkami) i katalog logotypów.

Klucz gry jest odtwarzany tak samo jak w PyLinksWeb (`api._game_key`); gdy nie
trafia — bo `.lnk` zsanityzował tytuł, set MAME jest klonem albo Steam użył
`-applaunch` — Deck schodzi po zapasowych indeksach. Na bibliotece 663 pozycji bez
okładki zostaje 5, i to takie, które PyLinksWeb również ich nie ma.

Katalog wskazuje się przez `Katalog PyLinksWeb…` w opcjach. Bez wskazania Deck
szuka sam: sprawdza `D:\Links` (katalog spakowanego `PyLinksWeb.exe`) i
`D:\py\PyLinksWeb` (katalog z kodem), po czym wybiera ten z **nowszym**
`config.json`. To rozróżnienie ma znaczenie — obie lokalizacje mają komplet
plików, ale tylko jedna jest tą, w której naprawdę pracujesz.

`LINKS/Kolekcje/<nazwa>/` jest pomijane przy skanowaniu: to te same gry co
w katalogach platform, a przynależność do kolekcji i tak bierzemy z `config.json`.

Można też ustawić kluczem `pylinks_dir` w
`%LOCALAPPDATA%\PyLinksDeck\settings.json` albo zmienną `PYLINKS_DIR`.

## Ustawienia a ekrany

Zakładki (kolejność, widoczność, nazwy, wygląd) i zachowanie panelu są **wspólne
dla wszystkich ekranów** — przepięcie monitora nie zmienia tego, co ukryte ani
jak wygląda siatka. Od zestawu monitorów zależą wyłącznie wymiary docka i panelu,
zapisane ułamkiem ekranu.

Rozmiar kafla to **liczba kolumn**, nie piksele: 200 px to 18 % szerokości ekranu
1080p i 8 % ekranu 1440p, więc piksel nie przenosi się między ekranami, a liczba
kafli w wierszu wygląda wszędzie tak samo.

## Stan aplikacji

`%LOCALAPPDATA%\PyLinksDeck\`:

- `layouts.json` — profile: zakładki, ich kolejność, rozmiary kafli, wymiary docka i panelu,
- `thumbs/` — cache wyrenderowanych kafli (kasowalny, odbuduje się),
- `lnk_cache.json` — odczytane skróty (COM na 700 plikach jest wolny),
- `settings.json` — ustawienia niezależne od ekranu (`pylinks_dir`, `always_on_top`, `attach_mode`).

`Ustaw wszystko od nowa` w opcjach odtwarza profil bieżącego zestawu ekranów.

`Odśwież bibliotekę` przeładowuje listę gier **wraz z grafiką** (czyści cache
miniatur i logotypów). Gdy okładkę podmieniono bez zmiany daty pliku, użyj
`Wyczyść cache miniatur` — nazwa w cache wychodzi wtedy taka sama.

## Warstwa pulpitu

Deck rysuje wyłącznie na **ekranie głównym**. Dock i panel nie są zwykłymi
oknami: nie pojawiają się w Alt+Tab, nie zabierają focusu i leżą pod wszystkim,
co masz otwarte.

Rzecz nieoczywista: „dno kolejności Z" (`HWND_BOTTOM`) to w Windows miejsce **pod
tapetą i ikonami pulpitu**. Okno tam wysłane jest dla systemu w pełni widoczne,
a użytkownik nie widzi nic. Podobnie kończy się próba przypięcia do Progman —
Windows 11 odmawia `SetParent` między procesami, a nawet po udanym przypięciu
tapetę rysuje WorkerW leżące wyżej.

Dlatego domyślny tryb to `desktop`: okno wstawione w kolejności Z **tuż nad
warstwę pulpitu**. Strażnik co 3 sekundy sprawdza, czy Explorer nie podniósł
pulpitu nad nas, i w razie potrzeby wstawia okna z powrotem. Jeśli wolisz mieć
dock zawsze widoczny, także nad oknami — `Zawsze na wierzchu` w opcjach.

## Autostart

`Uruchamiaj przy starcie Windows` w opcjach dopisuje wpis do
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run` — gałąź użytkownika, bez
uprawnień administratora. Program startuje przez `pythonw.exe`, więc przy
logowaniu nie mruga okno konsoli. Odznaczenie kasuje wpis. Po przeniesieniu
katalogu Deck sam aktualizuje ścieżkę przy najbliższym starcie.

## Jedna instancja

Deck pilnuje, żeby działała tylko jedna kopia (nazwany mutex sesji). Kolejne
uruchomienie pokazuje dock już działającej instancji i kończy pracę — dwie kopie
nadpisywałyby sobie profil i rysowały dock na docku.

## Historia zmian

Patrz [CHANGELOG.md](CHANGELOG.md). Wersja bieżąca: `deck.__version__`.

## Wymagania

`PySide6`, `Pillow`, `pywin32` (patrz `requirements.txt`). Windows.

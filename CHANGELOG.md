# Changelog

Format wg [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/).
Wersjonowanie semantyczne.

## [0.6.2] — 2026-09-23

### Naprawione
- **Ustawienia docka gubiły się przy przełączaniu ekranów.** Klucz profilu
  liczyłem z nazwy monitora (`QScreen.name()`), a Windows nadaje ją zależnie od
  tego, które ekrany są włączone i który jest główny. Laptop bywał raz jednym,
  raz drugim urządzeniem, więc przy każdym przełączeniu „tylko ekran 1/2" albo
  zmianie ekranu głównego powstawał **nowy, pusty profil** — stąd wrażenie, że
  ustawienia się nie zapisują. W pliku było 29 profili na 8 realnych ekranów,
  w tym sześć wpisów samego laptopa.
- **Profil zależy teraz wyłącznie od ekranu, na którym Deck stoi** — jego
  rozmiaru i skalowania (klucz `2048x1280@1.25`, czytelny zamiast skrótu).
  Podłączenie drugiego monitora nie zmienia już wymiarów docka, bo dock i panel
  dzielą szerokość ekranu głównego i nic więcej ich nie obchodzi.
- **Stare profile są scalane, nie kasowane:** wpisy tego samego ekranu łączą się
  w jeden, wygrywa ten ze zmienionymi ustawieniami (29 → 8 u mnie w teście).
  Przed migracją powstaje kopia `layouts.json.pre-v4-backup`.
- **Dock zostawał w rozmiarze poprzedniego ekranu.** Przy zmianie ekranu
  głównego Qt nie zawsze wysyła sygnał, a gdy wysyła, Windows bywa jeszcze przy
  starych wymiarach — dock 2048 px logicznych z laptopa lądował na monitorze
  3840 px i zajmował dwie trzecie szerokości, choć w menu stało „cała szerokość".
  Stan ekranu jest teraz sprawdzany cyklicznie (co 3 s, razem ze strażnikiem
  warstwy), monitory podłączone w trakcie działania są obserwowane tak samo jak
  te obecne przy starcie, a okna są przypisywane do ekranu głównego **przed**
  nadaniem wymiarów, żeby Qt nie przeliczał ich w skali poprzedniego monitora.

## [0.6.1] — 2026-09-15

### Naprawione
- **Pełne tytuły pod kaflami.** Przy włączonych podpisach długi tytuł był ucinany
  wielokropkiem po jednej linii. Teraz zawija się w tyle wierszy, ile potrzeba;
  wiersz siatki ma wysokość najdłuższego tytułu w nim, więc obrazki i podpisy
  stoją na wspólnej linii, a kolejny wiersz nie nachodzi na tekst. Wysokość
  panelu dopasowuje się do zawiniętych podpisów. Bez podpisów siatka działa jak
  dawniej.
- **Automat przed portem w serii.** Port (np. Tekken na PS1) ma w PyLinksWeb datę
  oryginału — tę samą co wersja arcade — więc kolejność zależała od nazwy. Remis
  rozstrzyga teraz data wydania danej wersji: Tekken (MAME, 1994-12) stoi przed
  Tekkenem na PS1 (1995-03).

## [0.6.0] — 2026-09-15

### Dodane
- **Gry jednej serii stoją obok siebie, w kolejności.** Dane o seriach przychodzą
  z PyLinksWeb (Ustawienia → „Rozpoznaj serie gier", IGDB). Seria zajmuje miejsce,
  w którym alfabetycznie wypada JEJ nazwa (przedimek „The" pomijany), a w środku
  gry układają się wg daty wydania — remake i port mają już datę oryginału.
  Gry bez rozpoznanej serii układają się po nazwie, dokładnie jak wcześniej,
  a brak danych z PyLinksWeb niczego nie zmienia.

  Rozwiązuje przypadki, których nazwa nie oddaje: „Judgment" i „Like a Dragon"
  nie odpływają pod J i L od reszty Yakuzy, a trylogia Legend of Heroes na PSP
  staje w kolejności wydań, a nie amerykańskiej numeracji.

- **Prawy klik na kaflu → „◀ Wcześniej w serii" / „▶ Później w serii".** IGDB zna
  tylko daty, a kolejność fabularna bywa inna (Yakuza 0 przed Kiwami). Ręczne
  ustawienie jest zapamiętywane w ustawieniach Decka; „Przywróć kolejność wg dat
  wydania" je cofa. Nowa gra serii dołącza na końcu wg daty, a przestawienie
  w zakładce jednej platformy nie gubi pozycji z innych platform.

### Szczegóły
- Klucz odtwarzany z nazwy pliku skrótu bywa inny niż w PyLinksWeb (dwukropek →
  podkreślnik), więc obok dopasowania dokładnego jest indeks po znormalizowanej
  nazwie — jak przy kadrach. Na skrótach użytkownika: 21 z 21 rozpoznanych.
- `deck/series_order.py` + `tests/test_series_order.py` (11 testów na prawdziwych
  datach z IGDB).

## [0.5.1] — 2026-09-14

### Naprawione
- **Kolorowe logotypy dostawały w zakładkach białą podkładkę** (GB, NES, N64,
  SNESMSU1, a także 32X, NSW, PS4, Neo Geo, Arcade). Podkładka jest dla logo
  czarnych, niewidocznych na ciemnej belce, ale „ciemne" rozpoznawałem po samej
  średniej jasności poniżej 96. Nasycona czerwień Nintendo ma jasność ok. 90,
  a granat Game Boya 65, więc kolorowe logo brałem za czarne. SNES się wymykał,
  bo jasne kółka przycisków podnoszą średnią do 119. Teraz podkładkę dostaje
  tylko logo ciemne **i bezbarwne** (nasycenie < 0,30) — to samo kryterium, którego
  od początku używają grzbiety na kaflach.
- **Bardzo szerokie logotypy zamieniały się w napis** (GBA 8,6:1). Przy 19
  zakładkach na ekranie 2048 px logo GBA po wpasowaniu miało 10,4 px wysokości,
  a próg czytelności wynosił 11 px, więc zakładka pokazywała tekst „GBA". Margines
  logo w zakładce zmniejszony z 16 do 8 px, a próg z 11 do 8 px.

## [0.5.0] — 2026-08-30

### Naprawione
- **Przepięcie na ekran o innej rozdzielczości resetowało konfigurację.** Inny
  zestaw monitorów to inna sygnatura, a dla nieznanej sygnatury tworzyłem profil
  **od zera** — stąd inne ukryte zakładki i inne rozmiary kafli. Zamiast chronić
  układ, mechanizm profili go gubił.
- **Rozmiar kafla trzymany w pikselach** nie przenosił się między ekranami:
  200 px to 18 % szerokości ekranu 1080p i 8 % ekranu 1440p, więc ten sam zapis
  dawał zupełnie inną siatkę.

### Zmienione
- **Ustawienia rozdzielone na wspólne i zależne od ekranu.** Zakładki — ich
  kolejność, widoczność, nazwy i wygląd — oraz zachowanie panelu są teraz
  **wspólne dla wszystkich ekranów**: to wybory użytkownika i nie mają powodu
  zmieniać się z rozdzielczością. Per zestaw monitorów zostają wyłącznie wymiary
  docka i panelu, i to zapisane ułamkiem ekranu.
- **Rozmiar kafla wyrażony liczbą kolumn**, nie pikselami. Liczba kafli w wierszu
  wygląda tak samo na projektorze i na 4K — to ona jest niezmiennikiem układu.
  Ctrl+kółko zmienia liczbę kolumn (w górę = mniej kolumn, czyli większe kafle),
  a w opcjach doszło `Kafli w wierszu`.
- Format zapisu podniesiony do wersji 3. Stary plik jest **migrowany**, nie
  kasowany: zakładki, ukrycia i wygląd zostają, a rozmiary w pikselach są
  przeliczane na kolumny. Wymiary docka i panelu każdego znanego ekranu również
  się przenoszą.

## [0.4.5] — 2026-08-30

### Naprawione
- **Cała szerokość kafla pustki po prawej stronie panelu.** Liczyłem odstępy jako
  `(kolumny - 1)`, a Qt rezerwuje odstęp przy **każdej** komórce siatki: wiersz
  zajmuje `kolumny × (kafel + odstęp)`. Wychodziło o kilka pikseli za dużo, Qt
  cofało się do mniejszej liczby kolumn i zostawiało po prawej miejsce na cały
  kafel. Przy panelu 2028 px było to 6 zaplanowanych kolumn wobec 5 ułożonych.
- **Siatka znów wyśrodkowana** — reszta po podziale (najwyżej kilka pikseli)
  rozkłada się równo na oba marginesy, zamiast dosuwać kafle do lewej.

## [0.4.4] — 2026-08-30

### Zmienione
- **Siatka kafli: stały odstęp, kafle dopasowane do szerokości.** Dotąd rozmiar
  kafla był sztywny, a nadmiar szerokości lądował w odstępach (0.4.3) albo
  w marginesach (0.3.0) — w obu przypadkach robiły się z tego dziury. Teraz jest
  odwrotnie: odstęp to stałe 8 px, liczba kolumn wynika z rozmiaru *preferowanego*
  (tego z profilu, zmienianego Ctrl+kółkiem), a kafle rozciągają się tak, by
  wypełnić wiersz co do piksela.
- Proporcje, odstęp i wypełnienie są niezależne od rozdzielczości i skalowania
  ekranu: cała arytmetyka układu idzie w pikselach logicznych, a fizyczne dokłada
  dopiero render (px × devicePixelRatio). Sprawdzone dla 1920×1080, 2560×1600
  i 3840×2160 przy skalowaniu 100–200 %: proporcja kafla trzyma się 1,500 (albo
  1,000 dla kwadratu), a niewykorzystana szerokość nie przekracza kilku pikseli
  na cały wiersz.

## [0.4.3] — 2026-08-30

### Naprawione
- **Szerokie puste marginesy po bokach kafli.** Wyśrodkowanie siatki dodane
  w 0.3.0 dzieliło resztę z dzielenia szerokości panelu przez kafel na dwa
  marginesy — przy kaflu 400 px wychodziło po ~140 px pustki z każdej strony.
  Nadmiar rozkłada się teraz **między kolumny** (szerokość komórki siatki zamiast
  marginesów widoku), więc kafle sięgają od krawędzi do krawędzi, zachowując
  zadany rozmiar. Kafel jest przy tym wyśrodkowany w komórce, a animacja
  uruchomienia startuje z jego rzeczywistego położenia.

## [0.4.2] — 2026-08-26

### Naprawione
- **„Odśwież bibliotekę" nie pokazywało podmienionych ikon** — dopiero restart.
  Przeładowywana była lista gier, ale nie grafika: kafle siedzą w cache
  pamięciowym pod kluczem (gra, rozmiar, tryb), a znacznik pliku źródłowego
  jest tylko w nazwie pliku na dysku. Odświeżenie czyści teraz cache miniatur
  i wczytane logotypy, oraz ponownie odczytuje ustawienia grzbietu z PyLinksWeb.

### Dodane
- **`Wyczyść cache miniatur`** w opcjach — kasuje wyrenderowane kafle z dysku
  i liczy je od nowa. Potrzebne, gdy okładka została podmieniona bez zmiany daty
  pliku: nazwa w cache wychodzi wtedy identyczna i zwykłe odświeżenie nie
  wystarcza.

## [0.4.1] — 2026-08-26

### Naprawione
- **Gry PS1 i PS2 nie startowały z docka**, choć te same skróty działały
  z Eksploratora. Uruchamialiśmy je przez `os.startfile` na pliku `.lnk`, czyli
  oddawaliśmy sprawę powłoce razem z całym środowiskiem naszego procesu —
  a w wersji spakowanej PyInstallerem jest ono podmienione (rozpakowany katalog
  `_MEI` na początku `PATH`, zmienne Qt wskazujące na nasze wtyczki). DuckStation
  i PCSX2 również są aplikacjami Qt i to dziedziczyły.
  Teraz uruchamiamy wprost: cel, argumenty i katalog roboczy bierzemy ze skrótu
  (i tak je odczytujemy), proces dostaje środowisko oczyszczone ze śladów
  PyInstallera i jest odpięty (`DETACHED_PROCESS`), więc zamknięcie Decka go nie
  ubija. `os.startfile` zostaje wyłącznie dla skrótów bez czytelnego celu.

### Dodane
- Tryb diagnostyczny `--launch <skrót>` — uruchamia grę tą samą drogą co dwuklik
  i wypisuje cel, argumenty, katalog oraz wynik. Działa przed blokadą instancji,
  więc można go użyć przy pracującym Decku.

## [0.4.0] — 2026-08-25

### Dodane
- **Wysuwanie i zwijanie panelu.** Po najechaniu na dock panel wyjeżdża spod
  belki (210 ms, OutCubic), a po zjechaniu myszą chowa się szybciej (160 ms,
  InCubic) — ruch „do przodu" może potrwać, ruch „z drogi" ma nie zawadzać.
- **Efekt uruchomienia gry.** Dwuklik odrywa kafel od siatki, rozciąga go na
  pełny ekran i wygasza (340 ms), a panel zwija się za nim. Emulator albo Steam
  potrafią zbierać się kilka sekund i bez tego nie widać, że kliknięcie w ogóle
  zadziałało. Okno efektu nie przyjmuje wejścia (`WindowTransparentForInput`),
  więc nie blokuje pulpitu nawet na moment, i kasuje się samo.
- Przełącznik **`Animacje`** w opcjach — wyłącza oba efekty.

## [0.3.3] — 2026-08-25

### Dodane
- **Tryb „Rozciągnij do kafla"** — domyślny. Plakat jest skalowany do ramki bez
  zachowania proporcji: kafel wychodzi pełny, nic z plakatu nie znika i nic nie
  zostaje dołożone. Poprzednie dwa podejścia zawsze poświęcały jedno albo
  drugie — kadrowanie zjadało tytuły kwadratowych plakatów arcade, a wpisanie
  w ramkę wymagało tła. Cenę płaci się teraz proporcjami, i to świadomie.

### Zmienione
- Dopasowanie okładki ma trzy warianty: `Rozciągnij do kafla (nic nie ucina)`,
  `Wypełnij kadrując (ucina brzegi)` i `Wpisz w całości — jak PyLinksWeb`.
  Ustawienie jest osobne dla każdej zakładki, więc PC może zostać na kadrowaniu,
  gdzie kwadratowe kafle wypełniają się dobrze, a MAME rozciągać.

## [0.3.2] — 2026-08-25

### Zmienione
- **Kafel jest zawsze kadrowany, nigdy nie dostaje podkładki.** Tryb z rozmytym
  tłem (0.3.0) zniknął razem z całą heurystyką proporcji: skoro w PyLinksWeb jest
  `offset`, to on decyduje, co zostaje w kadrze. Plakat wyraźnie szerszy od ramki
  straci przy tym boki — świadomy wybór na rzecz równej, pełnej siatki.
- Dopasowanie okładki ma teraz dwie pozycje zamiast trzech: `Wypełnij kafel
  (kadruj)` i `Wpisz w całości — jak PyLinksWeb`.

## [0.3.1] — 2026-08-25

### Naprawione
- **Regresja z 0.3.0: kwadratowy kafel przestał wypełniać się okładką.** Tryb
  „Automatycznie (bez ucinania)" oceniał tylko *wielkość* różnicy proporcji, więc
  okładka PC (0,71) w kwadratowym kaflu trafiała do tej samej kategorii co
  kwadratowy plakat arcade w ramce 2:3 i lądowała wpisana na rozmytym tle —
  zamiast zostać wykadrowana, po to przecież jest `offset` z PyLinksWeb.
  Teraz decyduje *kierunek* przycięcia: plakat węższy (lub do 18 % szerszy) od
  ramki jest kadrowany i wypełnia kafel, a tylko wyraźnie szerszy — którego
  cięcie zjadałoby tytuł przy bocznej krawędzi — dostaje tło z rozmycia.

## [0.3.0] — 2026-08-25

### Dodane
- **Wygląd osobno dla każdej zakładki** — kształt kafla, rozmiar, dopasowanie
  okładki i grzbiet ustawia się per grupa (`Wygląd grupy: …`), plus
  `Zastosuj ten wygląd do wszystkich grup`.
- **Grzbiet platformy** dla kwadratowych kafli ROM-ów — port
  `add_platform_spine` z PyLinksWeb, renderowany wprost w rozmiarze kafla
  (bez pośrednictwa 256-pikselowego `.ico`).
- **Tryb „Automatycznie (bez ucinania)"** — plakat o proporcjach zbliżonych do
  ramki wypełnia kafel, a mocno odbiegający (np. kwadratowe plakaty arcade)
  jest wpisany w całości na rozmytym tle z siebie samego. Siatka zostaje równa,
  tytuły przy krawędziach nie znikają.
- **Regulacja prędkości przewijania** (`Przewijanie`: bardzo wolne → szybkie).
- **Wybór katalogu danych PyLinksWeb** (`Katalog PyLinksWeb…`) plus autodetekcja
  po nowszym `config.json`.
- **Zasięg panelu przeciąganiem** dolnej krawędzi; zapisywany jako ułamek
  wysokości ekranu.
- **Blokada drugiej instancji** (nazwany mutex) — dwie kopie biły się o ten sam
  profil i rysowały dock na docku.
- Wyśrodkowanie siatki kafli i przyciski masowe (`Wszystkie` / `Żadna`)
  w oknie `Grupy…`.
- **Pakowanie do przenośnego `.exe`** (PyInstaller onefile, `pylinks_deck.spec`)
  wraz z ikoną aplikacji `deck.ico`. Wynik trafia do `D:/GIT/bin/PyLinksDeck.exe`;
  ustawienia i tak zostają w `%LOCALAPPDATA%\PyLinksDeck`, więc plik jest przenośny.

### Naprawione
- **Zły katalog danych** — Deck czytał `D:\py\PyLinksWeb` (kod źródłowy)
  zamiast `D:\Links` (dane spakowanego `PyLinksWeb.exe`). Skutkowało to starszą
  biblioteką: mniej kadrów, jedna kolekcja zamiast czterech.
- **Kadry gubione przy tytułach ze znakami specjalnymi** — klucz odtwarzany
  z nazwy `.lnk` ma apostrof zamieniony na podkreślenie
  (`assassin_s creed odyssey`), więc nie trafiał w `assassin's creed odyssey`
  z bazy. Kadry są teraz wyszukiwane także po znormalizowanym tytule.
- **Cache kafli ignorował zmianę kadru** — `offset` nie wchodził do klucza, więc
  wracał stary obrazek mimo poprawnych ustawień.
- **Deformacja przy dużych kaflach** — górny limit rozmiaru ścinał samą
  wysokość, przez co kafel 2:3 renderował się jako 1:1,16: kadr zjadał górę
  i dół, a w komórce zostawały pasy wyglądające jak rosnące odstępy. Limit
  zmniejsza teraz oba boki naraz (i wzrósł z 1024 do 1408 px).
- **Przewijanie przestało działać** po dodaniu animacji —
  `QPropertyAnimation.state()` zwraca obiekt enum prawdziwy także dla `Stopped`,
  więc kod brał nieustawiony cel i wywalał się przy każdym obrocie kółka.
- **Krok przewijania liczony z wysokości kafla** — przy dużych ikonach jeden
  obrót przeskakiwał niemal cały ekran; teraz to ułamek widocznego obszaru.
- **Globalny `icon_fit_mode`** z konfiguracji PyLinksWeb był ignorowany na rzecz
  zaszytego `pad`.
- `LINKS/Kolekcje/` bywało brane za platformę — te same gry liczyły się dwa razy.
- Zrzut kontrolny (`--shot`) zwracał puste okno: `render()` na oknie
  z przezroczystym tłem daje pustą powierzchnię, więc używamy `grab()`.

## [0.2.0] — 2026-08-25

### Zmienione
- **Przebudowa UI na dock z zakładkami.** Ramki rozstawiane po pulpicie
  odpadły — w Fences to Folder Portal i nie wnosiły nic ponad niego. Teraz na
  pulpicie leży belka zakładek (szerokość zakładki = szerokość docka ÷ liczba
  grup), najechanie rozwija panel z kaflami, kliknięcie przełącza grupę.
- Panel dopasowuje wysokość do zawartości, do limitu z profilu.

### Dodane
- Logotypy platform w zakładkach (z `platform_logo_dir` PyLinksWeb), skalowane
  w obu wymiarach; ciemne dostają jasny podkład.
- Skalowanie kafli bez pokazywania rozmiarów pośrednich — w trakcie kręcenia
  kółkiem rysowany jest kafel z pamięci, render właściwego rozmiaru rusza po
  zatrzymaniu.
- Ręczna kolejność zakładek, ich widoczność i nazwy (`Grupy…`).
- Autostart przez `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

### Naprawione
- **Overlay niewidoczny** — `HWND_BOTTOM` to w Windows miejsce *pod* tapetą
  i ikonami pulpitu, a `SetParent` do Progman nie przechodzi między procesami
  w Windows 11. Okna wstawiane są teraz tuż nad warstwę pulpitu, ze strażnikiem
  przywracającym je, gdy Explorer podniesie pulpit.

## [0.1.0] — 2026-08-25

### Dodane
- Pierwsza wersja: ramki z kaflami na pulpicie, profile per zestaw monitorów,
  kafle renderowane z surowych okładek (bez sufitu 256 px, który ogranicza ikony
  powłoki), biblioteka czytana z `LINKS/`, `Cache/` i `config.json` PyLinksWeb.

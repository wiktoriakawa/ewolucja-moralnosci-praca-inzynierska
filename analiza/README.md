# Podstawowa analiza wyników

Moduł `jakosc.py` sprawdza jakość danych jednego przebiegu symulacji,
oblicza podstawowe miary pokoleń i tworzy wykresy. Nie sprawdza założeń
konkretnych przebiegów pilotażowych P1–P3.

Skrypty w katalogu:

- `jakosc.py` – kontrola jakości jednego przebiegu (sekcje poniżej);
- `eksploracja.py` – eksploracja danych pilotażu (sekcja „Eksploracja danych
  pilotażu”);
- `kalibracja.py` – analiza serii kalibracyjnych (sekcja „Analiza serii
  kalibracyjnych”);
- `oplacalnosc_kradziezy.py` – opłacalność kradzieży i ciągi dylematów
  (sekcja o tej samej nazwie).

## Dane wejściowe

Należy wskazać katalog jednego przebiegu zawierający cztery pliki:

```text
konfiguracja.json
pokolenia.csv
agenci.csv
dylematy.csv
```

Przed uruchomieniem trzeba zainstalować zależności projektu i aktywować
środowisko wirtualne. Polecenia należy wykonywać z katalogu głównego
repozytorium.

## Uruchomienie

Przykład analizy jednego przebiegu w PowerShellu:

```powershell
$env:PYTHONPATH = "src"
python -m analiza.jakosc wyniki/P2_niedobor_z201 `
    --wyjscie wyniki_analizy
```

Argument `--wyjscie` wskazuje katalog bazowy i jest opcjonalny. Bez niego
zostanie użyty katalog `wyniki_analizy`. Wewnątrz skrypt automatycznie tworzy
osobny katalog zawierający nazwę przebiegu oraz datę i czas analizy, np.:

```text
wyniki_analizy/P2_niedobor_z201_2026-11-02_15-30-12/
```

Dzięki temu kolejne uruchomienia nie nadpisują wcześniejszych wyników.

Kontrola obejmuje m.in. ciągłość numerów pokoleń, zgodność agregatów
pokoleń z danymi agentów, przypisanie dylematów do agentów, reguły śmierci
i kwalifikacji oraz zgodność klas, wyników i kwot akcji.

## Kontrola powtarzalności

Opcja `--porownaj` sprawdza wymaganie NF-03 przez porównanie trzech plików
CSV dwóch przebiegów wykonanych z tą samą konfiguracją i ziarnem:

```powershell
$env:PYTHONPATH = "src"
python -m analiza.jakosc wyniki/P3_a `
    --porownaj wyniki/P3_b `
    --wyjscie wyniki_analizy
```

Plik `konfiguracja.json` nie jest porównywany, ponieważ zawiera czas
uruchomienia przebiegu.

## Wyniki

Skrypt tworzy:

- `kontrola_jakosci.csv` – wynik każdej kontroli wraz ze szczegółami;
- `pokolenia_analiza.csv` – dane pokoleń rozszerzone o `M_pop` i liczbę
  rodziców;
- `przezywalnosc.png` – przeżywalność w kolejnych pokoleniach;
- `moralnosc_populacji.png` – wartość `M_pop` w kolejnych pokoleniach;
- `liczba_rodzicow.png` – liczbę rodziców w kolejnych pokoleniach.

Moralność populacji jest liczona według wzoru:

```text
M_pop = (S - K) / D
```

Gdy w pokoleniu nie wystąpił żaden dylemat (`D = 0`), `M_pop` otrzymuje
wartość `NaN`.

## Kod zakończenia

Program zwraca kod `0`, jeżeli wszystkie kontrole jakości przeszły, oraz
kod `1`, jeżeli wykryto niezgodność. Szczegóły znajdują się wtedy w pliku
`kontrola_jakosci.csv`.

## Opłacalność kradzieży i ciągi dylematów

Skrypt `oplacalnosc_kradziezy.py` liczy z plików `dylematy.csv` pilotażu, bez nowej
symulacji, dwie tabele do decyzji o biernych dylematach (#21):

- odsetek dylematów, w których hipotetyczny oczekiwany zysk z kradzieży
  `p · min(x, zasoby_celu) − c_k` był ujemny – przy zasobach celu z początku kroku,
  a nie w chwili wykonania kradzieży;
- ciągi dylematów (kolejne kroki z zapisanym dylematem wobec tego samego celu)
  oraz udział akcji obojętnych u agentów z `D ≥ 200`.

Dane wejściowe: lokalny katalog z podkatalogami przebiegów P1–P2 (np. `P1_z101`,
`P2_niedobor_z201`), w każdym `konfiguracja.json` i `dylematy.csv`. Opcja `--serie`
wybiera przebiegi po początku nazwy (domyślnie `P1 P2`); `p`, `x` i `c_k` muszą być
takie same we wszystkich przebiegach.

```powershell
$env:PYTHONPATH = "src"
python -m analiza.oplacalnosc_kradziezy lokalne/wyniki_pilotazu `
    --serie P1 P2 --wyjscie wyniki/analiza/oplacalnosc
```

Skrypt tworzy (wiersz = seria i `alfa`):

- `oplacalnosc.csv` – liczbę przebiegów i dylematów, `ujemny_zysk` (odsetek łącznie
  dla ziaren, więc ważony liczbą dylematów), `ujemny_zysk_min` i `ujemny_zysk_max`
  (zakres odsetka w przebiegach) oraz te same odsetki wśród kradzieży i dzieleń;
- `ciagi_dylematow.csv` – liczbę agentów z `D ≥ 1`, mediany `D` i liczby ciągów,
  `udzial_D200`, `dlugie_ciagi_wsrod_D200` (udział agentów z najwyżej 2 ciągami –
  długie powtarzanie dylematu, niekoniecznie bierność), `obojetne_wsrod_D200`
  (średni udział akcji obojętnych w dylematach agenta) i `ciagi_na_D`. Gdy żaden
  agent nie ma `D ≥ 200`, obie miary „wśród D200” mają wartość `NaN`.

Ciąg nie jest pełnym fizycznym spotkaniem: krok, w którym cel stoi dalej przed
agentem, ale warunki dylematu nie są spełnione, nie ma wiersza w `dylematy.csv`
i przerywa ciąg.

## Eksploracja danych pilotażu

Skrypt `eksploracja.py` liczy z zapisanych plików CSV pilotażu (serie P1
i P2; P3 pomija, bo służy tylko powtarzalności) profil zachowań oraz
współczynniki `M`, `M_wyg` i `M_pop`, wypisuje liczby i zapisuje wykresy
i tabele LaTeX-a do punktów 4.3.1 i 4.4 dokumentu etapu 2. Symulacji nie
uruchamia – poza odtworzeniem pokolenia zerowego na potrzeby punktu 4.4.3.

Dane wejściowe: lokalny katalog z podkatalogami przebiegów pilotażu (np.
`P1_z101`, `P2_niedobor_z201`), w każdym `konfiguracja.json`, `pokolenia.csv`,
`agenci.csv` i `dylematy.csv`; potrzebne są obie serie, P1 i P2.

```powershell
$env:PYTHONPATH = "src"
python -m analiza.eksploracja lokalne/wyniki_pilotazu --wyjscie wyniki/analiza
```

Opcje: `--wyjscie` (domyślnie `wyniki/analiza`), `--a` (wygładzanie `M_wyg`,
domyślnie 2) i `--D-min` (próg liczby dylematów, domyślnie 5). Skrypt tworzy
w katalogu wyjściowym (tabele LaTeX-a w podkatalogu `tabele/`):

- punkt 4.3.1 – `D_podsumowanie.csv`, `M_rozrzut_wg_D.csv`, `histogram_D.pdf`,
  `M_od_D.pdf`, `tabele/tab_dylematy.tex`, `tabele/tab_rozrzut.tex`;
- punkt 4.4.2 – `statystyki_P1.csv`, `statystyki_P2_*.csv`,
  `tabele/tab_statystyki_P1.tex`, `tabele/tab_statystyki_P2.tex`;
- punkt 4.4.3 – `udzialy_akcji_P1.csv`, `pokolenie_zerowe.pdf`;
- punkt 4.4.4 – `przebieg_w_pokoleniach.csv`, `przebieg_wybrane_pokolenia.csv`,
  `akcje_w_pokoleniach.csv`, `przezywalnosc.pdf`, `M_pop.pdf`,
  `akcje_w_pokoleniach.pdf`.

Funkcje wczytujące dane z `eksploracja.py` wykorzystują też `kalibracja.py`
i `oplacalnosc_kradziezy.py`, więc ich zmiana wymaga uruchomienia testów
wszystkich trzech skryptów.

## Analiza serii kalibracyjnych

Skrypt `kalibracja.py` podsumowuje serię kalibracyjną uruchomioną trybem
serii: K1, K2, K2b, K3 albo K4 (pytania, warianty i kryteria wyboru opisuje
`konfiguracje/kalibracja/plan_kalibracji.md`). Dla każdego wariantu liczy
średnią i odchylenie między ziarnami, sprawdza warunki dopuszczalności
z planu, a w K2, K2b, K3 i K4 wskazuje też wariant wybrany według reguły
z planu.

Dane wejściowe: katalog serii, czyli `katalog` z sekcji `[seria]` pliku serii
(np. `wyniki/K3`). Analiza bierze tylko przebiegi ze statusem `zakonczony`
w `status.csv`, a gdy tego pliku nie ma – wszystkie podkatalogi
z `konfiguracja.json`. Z każdego przebiegu czyta `pokolenia.csv`
i `agenci.csv`, a w K1 i K4 także `dylematy.csv`. K3 i K4 wymagają kolumny
`roznorodnosc` w `pokolenia.csv`, czyli danych z wersji kodu z pomiarem
różnorodności genetycznej.

```powershell
$env:PYTHONPATH = "src"
python -m moralnosc seria konfiguracje/kalibracja/K3.toml
python -m analiza.kalibracja K3 wyniki/K3 --wyjscie wyniki/analiza/K3
```

Opcje: `--wyjscie` (domyślnie `wyniki/analiza/<seria>`), `--a` (wygładzanie
`M_wyg`, domyślnie 2), `--D-min` (próg liczby dylematów, domyślnie 5)
i `--ostatnie` (z ilu ostatnich pokoleń uśredniać miary końcowe, domyślnie
5). Seria K1b jest w planie, ale jej analizy jeszcze nie ma – skrypt kończy
się wtedy kodem 2.

Skrypt wypisuje tabelę wariantów i listę wariantów dopuszczalnych, a do
katalogu wyjściowego zapisuje `<seria>_podsumowanie.csv`,
`<seria>_podsumowanie.tex` (tabela do dokumentu z etykietą `tab:<seria>`;
liczb w niej nie poprawia się ręcznie, tylko uruchamia skrypt ponownie)
oraz wykresy:

| Seria | Wykresy |
|---|---|
| K1 | `K1_koncentracja.pdf`, `K1_entropia.pdf` |
| K2, K2b | `<seria>_zakwalifikowani.pdf`, `<seria>_awaryjny.pdf` |
| K3 | `K3_roznorodnosc.pdf`, `K3_odziedziczalnosc.pdf` |
| K4 | `K4_kontakty.pdf` |

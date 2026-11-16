# Podstawowa analiza wyników

Moduł `jakosc.py` sprawdza jakość danych jednego przebiegu symulacji,
oblicza podstawowe miary pokoleń i tworzy wykresy. Nie sprawdza założeń
konkretnych przebiegów pilotażowych P1–P3.

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

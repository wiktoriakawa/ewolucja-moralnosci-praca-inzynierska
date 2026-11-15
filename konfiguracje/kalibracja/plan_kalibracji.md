# Plan i macierz eksperymentów kalibracyjnych KM3 (issue #27)

**Wersja 1.1 (15.11.2026).** Kryteria wyboru każdej serii ustalono przed jej uruchomieniem (kryterium akceptacji #27). Decyzje metodyczne: Wiktoria (A/R metodyki eksperymentów); kryterium K2 – Wojtek (#29); akceptacja planu – zatwierdzenie PR przez oboje. Plan przygotowany z pomocą AI (Claude). Definicje serii leżą obok (`K1.toml`, `K2.toml`, `K2b.toml`, `K3.toml`, `K4.toml`); tabele planu trafiają do dokumentu KM3 (p. 4.2, dodatek B).

Historia: 1.0 (14.11) – serie K1–K5 i kryteria przed K1; 1.1 (15.11) – kryterium K2 (ustalone przed K2), seria uzupełniająca K2b dodana po K2 i sprawdzenie odporności wyboru K2 na nowych ziarnach, doprecyzowane kryterium K4, szacunek kosztu bez wyników.

## 1. Cel

Dobrać wartości referencyjne parametrów modelu z warstwą ukrytą (D2) tak, aby w eksperymentach docelowych (CA-1–CA-4, Lab04): (a) decyzje agentów były zróżnicowane, a nie prawie deterministyczne (problem z P1, Lab02 p. 4.4.3); (b) selekcja działała bez częstego wymierania i bez zaniku kwalifikacji (P2, Lab02 p. 4.4.4); (c) mutacja utrzymywała różnorodność bez niszczenia odziedziczonych strategii (D11); (d) znany był koszt czasu i danych (NF-06, NF-07).

## 2. Parametry stałe (wszystkie serie)

Konfiguracja bazowa `konfiguracje/bazowa.toml` (Lab02, dodatek A): plansza 64×64, N = 200, 300 kroków na pokolenie, pojemność pól z [1, 5], m = 1, ruch 0, s = 2, c_k = 1, p = 0,5, x = 5, tryb softmax, E0 = 50, w_max = 4, R = 2.

Zmiany wspólne dla KM3: `siec.h = 8` (rejestr decyzji D2; opcjonalna K1b sprawdza h ∈ {0, 4, 8, 16}). Każda seria zmienia tylko parametry z kolumny „Zmieniane”; pozostałe biorą wartości wybrane we wcześniejszych seriach (kolejność K1 → K2 → K3 → K4 → K5).

## 3. Serie

| Seria | Issue, osoba | Pytanie | Zmieniane (wartości) | Stałe (poza bazową) | Pokoleń × kroków | Ziarna | Przebiegów | Miary | Kryterium wyboru (ustalone przed analizą) |
|---|---|---|---|---|---|---|---|---|---|
| K1 | #28, Wiktoria | Czy softmax daje zróżnicowane decyzje? | skala ∈ {5, 10, 50} × τ ∈ {0,5; 1; 2} (`K1.toml`) | h = 8, α = 1,0, T = 50 | 10 × 300 | 401, 402, 403 | 27 | koncentracja decyzji agenta w pokoleniu 0 (mediana udziału najczęstszej akcji; P1: 0,89), entropia akcji populacji (pokolenie 0 i ostatnie 5), odsetek agentów z D ≥ 5, mediana D, udział zbierania na końcu, sd między ziarnami | (1) brak wymarcia w ≥ 2 z 3 ziaren; (2) mediana D w pokoleniu 0 ≥ 5; spośród spełniających – najniższa koncentracja w pokoleniu 0, a przy remisie (różnica < sd) wyższa entropia końcowa; τ = 1 i skala = 5 zostają, jeśli żaden wariant nie poprawia koncentracji o więcej niż sd |
| K1b (opcjonalna) | #28, Wiktoria | Ile neuronów ukrytych? (karta tematu: „analiza efektywności różnych konfiguracji neuronowych”) | h ∈ {0, 4, 8, 16} | skala, τ z K1; α = 1,0; T = 50 | 10 × 300 | 401–403 | 12 | jak K1 + czas na pokolenie | h = 8, chyba że inne h daje niższą koncentrację o więcej niż sd przy czasie ≤ 2× h = 8; bez K1b → h = 8 z D2, porównanie w Lab04 |
| K2 | #29, Wojtek | Gdzie selekcja działa bez wymierania? | T ∈ {30, 50, 70} × α ∈ {0,85; 1,0}; E0 nie jest zmieniane | skala = 50, τ = 2 i h = 8 z K1; E0 = 50 | 30 × 300 | 501, 502, 503 | 18 | przeżywalność, udział zakwalifikowanych wśród żywych, udział pokoleń z wariantem awaryjnym, wymarcia, zmienność między ziarnami | Odrzucamy warianty z wymarciem, z wariantem awaryjnym w ponad 10 % pokoleń albo z medianą udziału zakwalifikowanych wśród żywych poza przedziałem 10–50 %. Jeśli T = 50 i α = 1,0 spełniają warunki, pozostają wartościami referencyjnymi; w przeciwnym razie wybieramy wariant z najmniejszym udziałem mechanizmu awaryjnego, następnie z najmniejszą zmiennością między ziarnami, a przy dalszym remisie – najbliższy wartościom bazowym. |
| K2b | #29, Wojtek | Czy na gęstszej siatce wokół wyniku K2 da się ograniczyć zmienność między ziarnami i wariant awaryjny? | T ∈ {40, 50, 60} × α ∈ {0,90; 0,95; 1,0} (`K2b.toml`) | jak K2 | 30 × 300 | 501, 502, 503 (jak K2, dla porównywalności – wyjątek od rozłącznych ziaren) | 27 | jak K2 | jak K2; odporność wybranego wariantu sprawdzamy na nowych ziarnach 504–506 (ta sama siatka, `K2b_walidacja.toml`) i opisujemy w dokumencie |
| K3 | #30, Wiktoria | Czy mutacja utrzymuje różnorodność? | r ∈ {0,5/L; 1/L; 3/L} × σ ∈ {0,1; 0,2; 0,4} (L = 120 przy h = 8, n_we = 5; `K3.toml`) | skala, τ z K1; T, α z K2/K2b | 50 × 300 | 601, 602, 603 | 27 | różnorodność ρ (średnia odległość euklidesowa genomów) w pokoleniu 0 i ostatnim, iloraz ρ_koniec/ρ_0; korelacja M_wyg rodzic–potomek (pary z D ≥ 5) i liczba par; M_pop; wariant awaryjny | (1) brak wymarcia w ≥ 2 z 3 ziaren; (2) korelacja rodzic–potomek > 0 w każdym ziarnie przy ≥ 30 parach; (3) ρ_koniec/ρ_0 ≥ 0,25 po 50 pokoleniach; spośród spełniających – najwyższa korelacja; przy remisie (< sd) wartości bliższe bazowym (1/L, 0,2) |
| K4 | #30, Wiktoria | Jak lokalność narodzin wpływa na wyniki? | R ∈ {1, 2, 5, 63} (63 = cała plansza dla każdego rodzica; `K4.toml`) | skala, τ z K1; T, α z K2/K2b; (r, σ) z K3 | 50 × 300 | 701, 702, 703 | 12 | udział dylematów między rodzeństwem (pokrewieństwo), mediana D (kontakty), M_pop, różnorodność końcowa, korelacja rodzic–potomek | (1) brak wymarcia i wariant awaryjny w najwyżej 10 % pokoleń w każdym ziarnie (jak K2); (2) R = 2 (D12) zostaje, jeżeli spełnia (1), a korelacja rodzic–potomek przy R = 2 nie przekracza korelacji przy R = 63 (narodziny globalne) o więcej niż sd; w przeciwnym razie część „odziedziczalności” przy R = 2 wynika ze wspólnego otoczenia – wybieramy najmniejsze R spełniające (1), dla którego różnica do R = 63 mieści się w sd; wynik K4 służy głównie CA-4 |
| K5 | #31, Wojtek | Koszt konfiguracji referencyjnej | – (konfiguracja referencyjna) | wszystkie z K1–K4 | 500 × 300 (NF-06: 200 agentów × 500 pokoleń) | 801 | 1 (+1 powtórzenie NF-03) | czas, szczytowa RAM, rozmiar katalogu, kontrola jakości, NF-03 | NF-06: ≤ 30 min; NF-07: ≤ 8 GB RAM, ≤ 1 GB danych |

Przebiegi: K1 27, K1b 12 (opcjonalnie), K2 18, K2b 27 (+ 27 w sprawdzeniu na ziarnach 504–506), K3 27, K4 12, K5 2.

## 4. Ziarna i powtórzenia

- 3 ziarna na wariant (gdyby harmonogram się opóźnił – 2, z adnotacją w dokumencie); ziarna rozłączne z dotychczasowymi (próba przeżycia 1–5; pilotaż 101–105, 201–203, 301) i między seriami (4xx, 5xx, 6xx, 7xx, 8xx), żeby żaden wynik nie był „dopasowany” do ziarna z innej serii. Wyjątek: K2b zagęszcza siatkę K2 na tych samych ziarnach 501–503, więc wybór z K2b sprawdzamy na nowych ziarnach 504–506.
- Wariant × ziarno = jeden przebieg w osobnym katalogu `wyniki/<seria>/<seria>_<wariant>_z<ziarno>/` (np. `wyniki/K1/K1_s10_t0.5_z402/`) z `konfiguracja.json` (konfiguracja, ziarno, commit – wersja kodu).
- Agregacja: średnia po ziarnach ± odchylenie standardowe (w tabelach), linie ziaren + średnia (na wykresach, jak w Lab02 rys. przeżywalności). Niepewność = rozrzut między ziarnami; przy 3 ziarnach nie robimy testów istotności, tylko porównujemy różnice z sd.
- Pokolenia: K1 – 10 (zróżnicowanie decyzji widać w pokoleniu 0 i w pierwszych pokoleniach adaptacji); K3, K4 – 50 (jak P2; różnorodność i odziedziczalność potrzebują wielu pokoleń); K5 – 500 (NF-06).

## 5. Przebiegi zakończone wymarciem

Przebieg, w którym wymarła populacja, liczy się jako „wymarcie” i wchodzi tylko do miar przeżycia; miary z ostatnich pokoleń liczymy z pozostałych ziaren i podajemy, z ilu. Wariant z wymarciem w ≥ 2 z 3 ziaren jest odrzucany. Reguła „wymarcie kończy przebieg” (Lab02) pozostaje (decyzja do rejestru decyzji v0.3).

## 6. Kontrola jakości

Każdy przebieg przed analizą przechodzi `analiza/jakosc.py` (po #26 – z kontrolą nowych kolumn); dwa przebiegi z tym samym ziarnem w K5 muszą dać identyczne CSV (NF-03, `--porownaj`). Przebiegi niezaliczone są wyłączane i wymienione w dodatku B. Jeśli przyczyną jest błąd reguły kontroli, a nie danych (sprawdzony odtworzeniem przebiegu), przebieg zostaje w analizie, a wyjaśnienie trafia do dodatku B.

## 7. Szacunek kosztu

Ok. 0,33 s i ok. 1,5 MB na pokolenie przy h = 8 (czas – pomiar konfiguracji bazowej z 11.11; dane – rozmiar plików pierwszej serii, w 99 % `dylematy.csv`; Mac, Python 3.14.5, NumPy 2.5.4).

| Seria | Przebiegów × pokoleń | Czas | Dane |
|---|---|---|---|
| K1 | 27 × 10 | ok. 1,5 min | ok. 0,4 GB |
| K1b | 12 × 10 | ok. 1 min | ok. 0,2 GB |
| K2 | 18 × 30 | ok. 3 min | ok. 0,8 GB |
| K2b (+ sprawdzenie) | 27 × 30 (+ 27 × 30) | ok. 4,5 min (+ 4,5 min) | ok. 1,2 GB (+ 1,2 GB) |
| K3 | 27 × 50 | ok. 7,5 min | ok. 2,0 GB |
| K4 | 12 × 50 | ok. 3,5 min | ok. 0,9 GB |
| K5 | 1 × 500 (×2) | ok. 3 min (×2) | ok. 0,75 GB (×2) – blisko NF-07 (≤ 1 GB na przebieg) |

Razem ok. 35 min obliczeń i ok. 8 GB danych w `wyniki/` (poza Gitem); wąskim gardłem jest analiza i opis, nie obliczenia.

## 8. Wykonanie

Każdą serię uruchamiamy trybem serii (#23) z katalogu `kod/`, raz, do pustego katalogu:

```bash
PYTHONPATH=src python -m moralnosc seria konfiguracje/kalibracja/<seria>.toml
```

Do analizy idą tylko przebiegi ze statusem `zakonczony` w `wyniki/<seria>/status.csv`; wersja kodu, Python i NumPy są w `konfiguracja.json` każdego przebiegu. Wartości przejmowane z wcześniejszych serii wpisujemy do `[stale]` w pliku serii przed jej uruchomieniem, z komentarzem o źródle. Wartości r w `K3.toml` są liczone dla L = 120 (h = 8).

Analiza: `PYTHONPATH=src python -m analiza.kalibracja <seria> wyniki/<seria> --wyjscie wyniki/analiza/<seria>` (tabele CSV i LaTeX, wykresy PDF o stałych nazwach).

## 9. Macierz przebiegów (dodatek B dokumentu)

Tabelę „wariant, ziarno, katalog, commit, status, kontrola jakości” składa `analiza/kalibracja.py` ze `status.csv` serii i metadanych `konfiguracja.json` przebiegów; uzupełniamy ją po wykonaniu serii.

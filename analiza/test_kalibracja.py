"""Testy analiza/kalibracja.py – wartości policzone ręcznie z definicji (seria K1)."""
import numpy as np
import pandas as pd
import pytest

from analiza import kalibracja
from moralnosc.__main__ import main as moralnosc_main


def test_entropia_akcji_rownomierna_i_jedna_akcja():
    pokolenia = pd.DataFrame({f"akcja_{k}": [10, 0, 0] for k in range(8)})
    pokolenia.loc[1, "akcja_4"] = 300               # jedna akcja → 0 bitów
    pokolenia.loc[2, ["akcja_4", "akcja_7"]] = 50   # dwie po równo → 1 bit

    H = kalibracja.entropia_akcji(pokolenia)

    np.testing.assert_allclose(H.to_numpy(), [3.0, 0.0, 1.0])


def test_entropia_nie_zmienia_wejscia():
    pokolenia = pd.DataFrame({**{f"akcja_{k}": [k, 1] for k in range(8)}, "pokolenie": [0, 1]})
    kopia = pokolenia.copy()

    kalibracja.entropia_akcji(pokolenia)

    pd.testing.assert_frame_equal(pokolenia, kopia)


def test_przebiegi_serii_tylko_zakonczone(tmp_path, capsys):
    # status.csv z trybu serii: do analizy tylko „zakonczony”, reszta wypisana na stderr
    katalog = tmp_path / "K1"
    katalog.mkdir()
    pd.DataFrame({
        "id": ["K1_a_z1", "K1_b_z1", "K1_c_z1"],
        "wariant": ["a", "b", "c"],
        "ziarno": [1, 1, 1],
        "status": ["zakonczony", "blad", "pominiety"],
        "katalog": ["wyniki/K1/K1_a_z1", "wyniki/K1/K1_b_z1", "wyniki/K1/K1_c_z1"],
        "blad": ["", "ValueError: x", "katalog wynikowy nie jest pusty"],
    }).to_csv(katalog / "status.csv", index=False)

    przebiegi = kalibracja._przebiegi_serii(katalog)

    assert przebiegi == [katalog / "K1_a_z1"]
    bledy = capsys.readouterr().err
    assert "K1_b_z1" in bledy and "K1_c_z1" in bledy


def test_przebiegi_serii_bez_statusu(tmp_path):
    # bez status.csv: posortowane podkatalogi z konfiguracja.json, inne pomijane
    for nazwa in ("P_b", "P_a"):
        (tmp_path / nazwa).mkdir()
        (tmp_path / nazwa / "konfiguracja.json").write_text("{}", encoding="utf-8")
    (tmp_path / "bez_konfiguracji").mkdir()

    assert kalibracja._przebiegi_serii(tmp_path) == [tmp_path / "P_a", tmp_path / "P_b"]

def _akcje(**liczniki) -> dict[str, int]:
    return {f"akcja_{k}": liczniki.get(f"a{k}", 0) for k in range(8)}


def test_podsumuj_K1_policzone_recznie():
    # dwa ziarna jednego wariantu: A przeżywa 2 pokolenia, B kończy się po pierwszym
    pokolenia = pd.DataFrame([
        {"przebieg": "A", "pokolenie": 0, "zywi_koniec": 3, **_akcje(**{f"a{k}": 10 for k in range(8)})},
        {"przebieg": "A", "pokolenie": 1, "zywi_koniec": 5, **_akcje(a4=80)},
        {"przebieg": "B", "pokolenie": 0, "zywi_koniec": 0, **_akcje(a4=40, a7=40)},
    ]).assign(skala=5.0, tau=1.0, pokolenia_plan=2)
    agenci = pd.DataFrame({
        "przebieg": ["A", "A", "A", "B", "B"], "pokolenie": 0, "id": [1, 2, 3, 1, 2], "D": [5, 7, 2, 5, 9],
    })
    # dylematy pokolenia 0 (tyle wierszy, ile D): A1 – 3 z 5 to akcja 4 (0,6); A2 – 6 z 7 (6/7);
    # A3 – 2 decyzje (< D_min, pomijany); B1 – 5 z 5 (1,0); B2 – 9 z 9 (1,0)
    wiersze = (
        [("A", 1, 4)] * 3 + [("A", 1, 6)] * 2 + [("A", 2, 4)] * 6 + [("A", 2, 7)]
        + [("A", 3, 5)] * 2 + [("B", 1, 5)] * 5 + [("B", 2, 7)] * 9
    )
    dylematy = pd.DataFrame(wiersze, columns=["przebieg", "id", "akcja"])

    wynik = kalibracja.podsumuj_K1(pokolenia, agenci, dylematy, D_min=5, ostatnie=1)

    assert len(wynik) == 1
    w = wynik.iloc[0]
    kon_A, kon_B = (0.6 + 6 / 7) / 2, 1.0
    assert w["ziarna"] == 2
    assert w["przezycie"] == pytest.approx(0.5)
    assert w["koncentracja_p0"] == pytest.approx((kon_A + kon_B) / 2)
    assert w["koncentracja_p0_sd"] == pytest.approx(np.std([kon_A, kon_B], ddof=1))
    assert w["entropia_p0"] == pytest.approx(2.0)        # A: 3 bity, B: 1 bit
    assert w["entropia_koniec"] == pytest.approx(0.5)    # ostatnie pokolenie: A 0, B 1
    assert w["zbieranie_koniec"] == pytest.approx(0.75)  # A 80/80, B 40/80
    assert w["udzial_D_min"] == pytest.approx((2 / 3 + 1) / 2)
    assert w["mediana_D_p0"] == pytest.approx(6.0)       # A: mediana(5, 7, 2) = 5, B: 7
    assert not w["dopuszczalny"]                         # przeżycie 1/2 < 2/3


def _pokolenie_K2(
    przebieg: str,
    T: float,
    alfa: float,
    *,
    zywi: int = 10,
    zakwalifikowani: int = 3,
    awaryjny: bool = False,
) -> dict[str, object]:
    return {
        "przebieg": przebieg,
        "pokolenie": 0,
        "pokolenia_plan": 1,
        "zywi_koniec": zywi,
        "zakwalifikowani": zakwalifikowani,
        "awaryjny": awaryjny,
        "T": T,
        "alfa": alfa,
    }


def test_komorka_zapisuje_odchylenie_udzialu_w_punktach_procentowych():
    wiersz = pd.Series(
        {
            "udzial_zakwalifikowanych": 0.395,
            "udzial_zakwalifikowanych_sd": 0.091,
        }
    )

    assert (
        kalibracja._komorka(wiersz, "udzial_zakwalifikowanych")
        == "39{,}5\\% (9{,}1~p.p.)"
    )


def test_podsumuj_K2_pozostawia_dopuszczalne_wartosci_bazowe():
    pokolenia = pd.DataFrame(
        [
            *[
                _pokolenie_K2(f"bazowy_z{ziarno}", 50.0, 1.0)
                for ziarno in (1, 2, 3)
            ],
            *[
                _pokolenie_K2(
                    f"alternatywny_z{ziarno}",
                    30.0,
                    0.85,
                    zakwalifikowani=2,
                )
                for ziarno in (1, 2, 3)
            ],
        ]
    )

    wynik = kalibracja.podsumuj_K2(pokolenia)

    assert wynik["dopuszczalny"].all()
    wybrany = wynik[wynik["wybrany"]].iloc[0]
    assert wybrany["T"] == 50.0
    assert wybrany["alfa"] == 1.0
    assert wybrany["udzial_zakwalifikowanych"] == pytest.approx(0.3)
    assert wybrany["udzial_awaryjny"] == 0.0


def test_podsumuj_K2_odrzuca_niestabilne_warianty():
    pokolenia = pd.DataFrame(
        [
            _pokolenie_K2("wymarcie_z1", 30.0, 1.0, zywi=0, zakwalifikowani=0),
            _pokolenie_K2("wymarcie_z2", 30.0, 1.0),
            _pokolenie_K2("wymarcie_z3", 30.0, 1.0),
            _pokolenie_K2("awaryjny_z1", 50.0, 0.85, awaryjny=True),
            _pokolenie_K2("awaryjny_z2", 50.0, 0.85),
            _pokolenie_K2("awaryjny_z3", 50.0, 0.85),
            *[
                _pokolenie_K2(
                    f"za_duzo_z{ziarno}",
                    70.0,
                    1.0,
                    zakwalifikowani=6,
                )
                for ziarno in (1, 2, 3)
            ],
        ]
    )

    wynik = kalibracja.podsumuj_K2(pokolenia)

    assert not wynik["dopuszczalny"].any()
    assert not wynik["wybrany"].any()


BAZOWA = """
[przebieg]
ziarno = 1
pokolenia = 3
kroki = 20
[plansza]
H = 8
W = 8
[populacja]
N = 10
[zasoby]
c_min = 1.0
c_max = 5.0
alfa = 1.0
[obserwacje]
skala = 5.0
[koszty]
m = 0.1
ruch = 0.0
s = 2.0
c_k = 1.0
p = 0.5
x = 5.0
[siec]
tryb = "softmax"
tau = 1.0
h = 8
[ewolucja]
T = 0.0
E0 = 50.0
r = "auto"
sigma = 0.2
w_max = 4.0
R = 2
[zapis]
katalog = "wyniki/nieuzywany"
"""


def test_caly_skrypt_na_malej_serii(tmp_path):
    bazowa = tmp_path / "bazowa.toml"
    bazowa.write_text(BAZOWA, encoding="utf-8")
    katalog_serii = tmp_path / "wyniki" / "T1"
    definicja = tmp_path / "T1.toml"
    definicja.write_text(
        f"""
[seria]
nazwa = "T1"
bazowa = "{bazowa.as_posix()}"
katalog = "{katalog_serii.as_posix()}"
ziarna = [1, 2]

[[warianty]]
nazwa = "t0.5"
"siec.tau" = 0.5

[[warianty]]
nazwa = "t2"
"siec.tau" = 2.0
""",
        encoding="utf-8",
    )
    assert moralnosc_main(["seria", str(definicja)]) == 0

    wyjscie = tmp_path / "analiza"
    assert kalibracja.main(["K1", str(katalog_serii), "--wyjscie", str(wyjscie)]) == 0

    for plik in ("K1_podsumowanie.csv", "K1_podsumowanie.tex", "K1_koncentracja.pdf", "K1_entropia.pdf"):
        assert (wyjscie / plik).exists(), plik
    tabela = pd.read_csv(wyjscie / "K1_podsumowanie.csv")
    assert len(tabela) == 2
    assert tabela["ziarna"].tolist() == [2, 2]
    assert "tab:K1" in (wyjscie / "K1_podsumowanie.tex").read_text(encoding="utf-8")


def test_caly_skrypt_K2_na_malej_serii(tmp_path):
    bazowa = tmp_path / "bazowa.toml"
    bazowa.write_text(BAZOWA, encoding="utf-8")
    katalog_serii = tmp_path / "wyniki" / "K2"
    definicja = tmp_path / "K2.toml"
    definicja.write_text(
        f"""
[seria]
nazwa = "K2"
bazowa = "{bazowa.as_posix()}"
katalog = "{katalog_serii.as_posix()}"
ziarna = [1, 2]

[[warianty]]
nazwa = "T0_a1"
"ewolucja.T" = 0.0
"zasoby.alfa" = 1.0

[[warianty]]
nazwa = "T1_a0.85"
"ewolucja.T" = 1.0
"zasoby.alfa" = 0.85
""",
        encoding="utf-8",
    )
    assert moralnosc_main(["seria", str(definicja)]) == 0

    wyjscie = tmp_path / "analiza_K2"
    assert (
        kalibracja.main(["K2", str(katalog_serii), "--wyjscie", str(wyjscie)])
        == 0
    )

    for plik in (
        "K2_podsumowanie.csv",
        "K2_podsumowanie.tex",
        "K2_zakwalifikowani.pdf",
        "K2_awaryjny.pdf",
    ):
        assert (wyjscie / plik).exists(), plik
    tabela = pd.read_csv(wyjscie / "K2_podsumowanie.csv")
    assert len(tabela) == 2
    assert tabela["ziarna"].tolist() == [2, 2]
    tabela_tex = (wyjscie / "K2_podsumowanie.tex").read_text(encoding="utf-8")
    assert "tab:K2" in tabela_tex
    assert "$T$ / $\\alpha$" in tabela_tex


def test_k2b_uzywa_logiki_k2_i_wlasnych_nazw_plikow(tmp_path):
    bazowa = tmp_path / "bazowa.toml"
    bazowa.write_text(BAZOWA, encoding="utf-8")
    katalog_serii = tmp_path / "wyniki" / "K2b"
    definicja = tmp_path / "K2b.toml"
    definicja.write_text(
        f"""
[seria]
nazwa = "K2b"
bazowa = "{bazowa.as_posix()}"
katalog = "{katalog_serii.as_posix()}"
ziarna = [1]

[[warianty]]
nazwa = "T0_a0.9"
"ewolucja.T" = 0.0
"zasoby.alfa" = 0.9
""",
        encoding="utf-8",
    )
    assert moralnosc_main(["seria", str(definicja)]) == 0

    wyjscie = tmp_path / "analiza_K2b"
    assert (
        kalibracja.main(["K2b", str(katalog_serii), "--wyjscie", str(wyjscie)])
        == 0
    )

    for plik in (
        "K2b_podsumowanie.csv",
        "K2b_podsumowanie.tex",
        "K2b_zakwalifikowani.pdf",
        "K2b_awaryjny.pdf",
    ):
        assert (wyjscie / plik).exists(), plik
    assert "tab:K2b" in (wyjscie / "K2b_podsumowanie.tex").read_text(
        encoding="utf-8"
    )


# --- K3 ---------------------------------------------------------------------------------

@pytest.fixture
def agenci_dwa_pokolenia():
    """Pokolenie 0: agenci 0, 1, 2; pokolenie 1: potomkowie 10, 11 (rodzic 0), 12 (rodzic 2), 13 (rodzic 1).
    Potomek 12 ma D = 1 < D_min, więc jego para odpada. M_wyg(a = 2) = (S − K)/(D + 2):
    pary (rodzic, potomek) = (0,5; 0,375), (0,5; 0,0), (−0,5; −0,25)."""
    return pd.DataFrame(
        {
            "przebieg": ["X"] * 7,
            "pokolenie": [0, 0, 0, 1, 1, 1, 1],
            "id": [0, 1, 2, 10, 11, 12, 13],
            "id_rodzica": [-1, -1, -1, 0, 0, 2, 1],
            "S": [4, 0, 0, 3, 1, 0, 0],
            "K": [0, 4, 4, 0, 1, 0, 2],
            "N_o": [2, 2, 2, 3, 4, 1, 4],
            "D": [6, 6, 6, 6, 6, 1, 6],
        }
    )


def test_odziedziczalnosc_policzona_recznie(agenci_dwa_pokolenia):
    wynik = kalibracja.odziedziczalnosc(agenci_dwa_pokolenia, a=2.0, D_min=5).set_index("przebieg")

    assert wynik.loc["X", "pary"] == 3  # potomek 12 odpada (D = 1 < D_min)
    oczekiwana = np.corrcoef([0.5, 0.5, -0.5], [0.375, 0.0, -0.25])[0, 1]
    assert wynik.loc["X", "korelacja"] == pytest.approx(oczekiwana)
    assert wynik.loc["X", "udzial_par"] == pytest.approx(3 / 4)  # 4 potomków w pokoleniu 1


def test_odziedziczalnosc_bez_par_daje_nan(agenci_dwa_pokolenia):
    wynik = kalibracja.odziedziczalnosc(agenci_dwa_pokolenia, a=2.0, D_min=100).set_index("przebieg")

    assert wynik.loc["X", "pary"] == 0
    assert np.isnan(wynik.loc["X", "korelacja"])
    assert wynik.loc["X", "udzial_par"] == 0.0


def test_roznorodnosc_w_czasie_wymaga_kolumny():
    pokolenia = pd.DataFrame({"przebieg": ["X"], "pokolenie": [0], "r": [0.01], "sigma": [0.2]})

    with pytest.raises(ValueError, match="roznorodnosc"):
        kalibracja.roznorodnosc_w_czasie(pokolenia)


def _seria_K3(agenci_wzor, warianty):
    """Tabele pokolenia i agenci dla wariantów {sigma: {przebieg: [(rho, awaryjny, zywi), ...]}};
    r = 1/L przy h = 8, agenci każdego przebiegu jak w fixture (2 pokolenia)."""
    pokolenia, agenci = [], []
    for sigma, przebiegi in warianty.items():
        for nazwa, wiersze in przebiegi.items():
            for pokolenie, (rho, awaryjny, zywi) in enumerate(wiersze):
                pokolenia.append({
                    "przebieg": nazwa, "pokolenie": pokolenie, "zywi_koniec": zywi, "awaryjny": awaryjny,
                    "roznorodnosc": rho, "r": 1 / 120, "sigma": sigma, "h": 8, "pokolenia_plan": 2,
                })
            agenci.append(agenci_wzor.assign(przebieg=nazwa))
    return pd.DataFrame(pokolenia), pd.concat(agenci, ignore_index=True)


def test_podsumuj_K3_policzone_recznie(agenci_dwa_pokolenia):
    # dwa warianty o identycznych danych: remis w korelacji → wybrany bliższy bazowemu (sigma = 0,2)
    przebiegi = {
        "1": [(10.0, False, 3), (5.0, True, 4)],   # rho 10 → 5: iloraz 0,5; awaryjny w 1 z 2 pokoleń
        "2": [(8.0, False, 3), (6.0, False, 4)],   # iloraz 0,75
    }
    pokolenia, agenci = _seria_K3(
        agenci_dwa_pokolenia,
        {0.2: {f"A{k}": w for k, w in przebiegi.items()}, 0.4: {f"B{k}": w for k, w in przebiegi.items()}},
    )

    wynik = kalibracja.podsumuj_K3(pokolenia, agenci, a=2.0, D_min=5, ostatnie=1, min_par=3).set_index("sigma")

    korelacja = np.corrcoef([0.5, 0.5, -0.5], [0.375, 0.0, -0.25])[0, 1]
    for sigma in (0.2, 0.4):
        w = wynik.loc[sigma]
        assert (w["ziarna"], w["przezycie"], w["r_L"]) == (2, 1.0, 1.0)
        assert w["rho_iloraz"] == pytest.approx(0.625)
        assert w["rho_iloraz_sd"] == pytest.approx(np.std([0.5, 0.75], ddof=1))
        assert w["korelacja"] == pytest.approx(korelacja)
        assert w["pary_min"] == 3
        assert w["udzial_awaryjny"] == pytest.approx(0.25)
        assert w["M_pop_koniec"] == pytest.approx(1 / 19)  # pokolenie 1: (ΣS − ΣK)/ΣD = (4 − 3)/19
        assert w["dopuszczalny"]
    assert wynik["wybrany"].tolist() == [True, False]


def test_podsumuj_K3_wymarcie_tylko_w_przezyciu(agenci_dwa_pokolenia):
    # przebieg A2 wymiera po pierwszym pokoleniu: liczy się w przeżyciu, ale nie w miarach końcowych
    pokolenia, agenci = _seria_K3(
        agenci_dwa_pokolenia,
        {0.2: {"A1": [(10.0, False, 3), (5.0, False, 4)], "A2": [(8.0, False, 0)]}},
    )

    w = kalibracja.podsumuj_K3(pokolenia, agenci, a=2.0, D_min=5, ostatnie=1, min_par=3).iloc[0]

    assert w["przezycie"] == pytest.approx(0.5)
    assert w["rho_iloraz"] == pytest.approx(0.5)  # tylko A1
    assert not w["dopuszczalny"]                 # przeżycie 1/2 < 2/3


def test_caly_skrypt_K3_na_malej_serii(tmp_path):
    bazowa = tmp_path / "bazowa.toml"
    bazowa.write_text(BAZOWA, encoding="utf-8")
    katalog_serii = tmp_path / "wyniki" / "T3"
    definicja = tmp_path / "T3.toml"
    definicja.write_text(
        f"""
[seria]
nazwa = "T3"
bazowa = "{bazowa.as_posix()}"
katalog = "{katalog_serii.as_posix()}"
ziarna = [1, 2]

[[warianty]]
nazwa = "r1L_sg0.2"
"ewolucja.r" = {1 / 120!r}
"ewolucja.sigma" = 0.2

[[warianty]]
nazwa = "r3L_sg0.4"
"ewolucja.r" = 0.025
"ewolucja.sigma" = 0.4
""",
        encoding="utf-8",
    )
    assert moralnosc_main(["seria", str(definicja)]) == 0

    wyjscie = tmp_path / "analiza"
    assert kalibracja.main(["K3", str(katalog_serii), "--wyjscie", str(wyjscie)]) == 0

    for plik in ("K3_podsumowanie.csv", "K3_podsumowanie.tex", "K3_roznorodnosc.pdf", "K3_odziedziczalnosc.pdf"):
        assert (wyjscie / plik).exists(), plik
    tabela = pd.read_csv(wyjscie / "K3_podsumowanie.csv")
    assert tabela["r_L"].tolist() == [1.0, 3.0]
    tex = (wyjscie / "K3_podsumowanie.tex").read_text(encoding="utf-8")
    assert "tab:K3" in tex and "$rL$" in tex


# --- K4 ---------------------------------------------------------------------------------

def test_udzial_rodzenstwa_recznie():
    # pokolenie 1: agenci 10, 11 (rodzic 0) i 12 (rodzic 2); pokolenie 0 ma rodzica −1 i się nie liczy
    agenci = pd.DataFrame({
        "przebieg": "X",
        "pokolenie": [0, 0, 0, 1, 1, 1],
        "id": [0, 1, 2, 10, 11, 12],
        "id_rodzica": [-1, -1, -1, 0, 0, 2],
    })
    dylematy = pd.DataFrame({
        "przebieg": "X",
        "pokolenie": [0, 1, 1, 1, 1],
        "id": [0, 10, 10, 12, 11],
        "id_celu": [1, 11, 12, 10, 10],   # (0 → 1) pomijany; (10 → 11) i (11 → 10) to rodzeństwo
    })

    w = kalibracja.udzial_rodzenstwa(agenci, dylematy).set_index("przebieg").loc["X"]

    assert w["liczba_dylematow"] == 4
    assert w["udzial_rodzenstwa"] == pytest.approx(2 / 4)
    # poziom losowy pokolenia 1: rodzina {10, 11} → Σ n(n − 1) = 2, N(N − 1) = 6
    assert w["udzial_rodzenstwa_losowy"] == pytest.approx(1 / 3)


def _podsumowanie_K4(korelacje, sd, dopuszczalne=(True, True, True, True)):
    return pd.DataFrame({
        "R": [1, 2, 5, 63], "korelacja": korelacje, "korelacja_sd": sd, "dopuszczalny": list(dopuszczalne),
    })


def test_wybierz_R_zostaje_bazowe_w_granicach_sd():
    # R = 2 wyżej niż R = 63 o 0,05 przy sd 0,06 → remis, zostaje R = 2
    tabela = _podsumowanie_K4([0.30, 0.25, 0.22, 0.20], [0.05, 0.06, 0.04, 0.03])

    assert tabela.loc[kalibracja._wybierz_R(tabela), "R"] == 2


def test_wybierz_R_odrzuca_zawyzona_korelacje():
    # R = 1 i R = 2 przewyższają R = 63 o więcej niż sd → najmniejsze R w granicach: 5
    tabela = _podsumowanie_K4([0.40, 0.35, 0.22, 0.20], [0.03, 0.04, 0.03, 0.02])

    assert tabela.loc[kalibracja._wybierz_R(tabela), "R"] == 5


def test_wybierz_R_pomija_niedopuszczalne_bazowe():
    # R = 2 niedopuszczalne (np. wymarcie) → najmniejsze dopuszczalne w granicach sd: 1
    tabela = _podsumowanie_K4([0.21, 0.20, 0.22, 0.20], [0.03] * 4, dopuszczalne=(True, False, True, True))

    assert tabela.loc[kalibracja._wybierz_R(tabela), "R"] == 1


def test_caly_skrypt_K4_na_malej_serii(tmp_path):
    bazowa = tmp_path / "bazowa.toml"
    bazowa.write_text(BAZOWA, encoding="utf-8")
    katalog_serii = tmp_path / "wyniki" / "T4"
    definicja = tmp_path / "T4.toml"
    definicja.write_text(
        f"""
[seria]
nazwa = "T4"
bazowa = "{bazowa.as_posix()}"
katalog = "{katalog_serii.as_posix()}"
ziarna = [1, 2]

[[warianty]]
nazwa = "R1"
"ewolucja.R" = 1

[[warianty]]
nazwa = "R7"
"ewolucja.R" = 7
""",
        encoding="utf-8",
    )
    assert moralnosc_main(["seria", str(definicja)]) == 0

    wyjscie = tmp_path / "analiza"
    assert kalibracja.main(["K4", str(katalog_serii), "--wyjscie", str(wyjscie)]) == 0

    for plik in ("K4_podsumowanie.csv", "K4_podsumowanie.tex", "K4_kontakty.pdf"):
        assert (wyjscie / plik).exists(), plik
    tabela = pd.read_csv(wyjscie / "K4_podsumowanie.csv")
    assert tabela["R"].tolist() == [1, 7]
    assert tabela["udzial_rodzenstwa"].between(0, 1).all()
    assert "tab:K4" in (wyjscie / "K4_podsumowanie.tex").read_text(encoding="utf-8")

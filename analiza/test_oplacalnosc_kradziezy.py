"""Testy analiza/oplacalnosc_kradziezy.py – wartości policzone ręcznie."""
import json

import numpy as np
import pandas as pd
import pytest

from analiza import oplacalnosc_kradziezy as ok


def test_oczekiwany_zysk_recznie():
    # p = 0,5, x = 5, c_k = 1: zysk = 0,5·min(5, z) − 1
    zasoby_celu = pd.Series([0.5, 1.0, 2.0, 3.0, 10.0])

    zysk = ok.oczekiwany_zysk(zasoby_celu, p=0.5, x=5.0, c_k=1.0)

    assert zysk.tolist() == pytest.approx([-0.75, -0.5, 0.0, 0.5, 1.5])
    assert (zysk < 0).tolist() == [True, True, False, False, False]  # ujemny tylko dla z < 2


@pytest.fixture
def dylematy():
    """Agent 1: kroki 0–2 przed celem 9, krok 3 przed 8, krok 7 znów przed 9 → 3 ciągi, D = 5,
    najdłuższy 3, 3 akcje obojętne; agent 2: kroki 4–5 przed celem 1 → 1 ciąg, D = 2, 2 obojętne."""
    return pd.DataFrame(
        {
            "przebieg": ["X"] * 7,
            "seria": ["X"] * 7,
            "alfa": [1.0] * 7,
            "pokolenie": [0] * 7,
            "krok": [0, 1, 2, 3, 7, 4, 5],
            "id": [1, 1, 1, 1, 1, 2, 2],
            "id_celu": [9, 9, 9, 8, 9, 1, 1],
            "zasoby_celu": [1.0, 3.0, 3.0, 0.5, 3.0, 4.0, 4.0],
            "klasa": ["obojetna", "kradziez", "obojetna", "obojetna", "dzielenie", "obojetna", "obojetna"],
        }
    )


def test_ciagi_dylematow_policzone_recznie(dylematy):
    wynik = ok.ciagi_dylematow(dylematy).set_index("id")

    assert wynik.loc[1, ["D", "ciagi", "najdluzszy", "obojetne"]].tolist() == [5, 3, 3, 3]
    assert wynik.loc[2, ["D", "ciagi", "najdluzszy", "obojetne"]].tolist() == [2, 1, 2, 2]


def test_podsumuj_oplacalnosc(dylematy):
    wynik = ok.podsumuj_oplacalnosc(dylematy, p=0.5, x=5.0, c_k=1.0)

    assert len(wynik) == 1
    w = wynik.iloc[0]
    assert (w["seria"], w["alfa"], w["n"], w["przebiegi"]) == ("X", 1.0, 7, 1)
    assert w["ujemny_zysk"] == pytest.approx(2 / 7)          # zasoby celu 1,0 i 0,5
    assert (w["ujemny_zysk_min"], w["ujemny_zysk_max"]) == pytest.approx((2 / 7, 2 / 7))
    assert (w["n_kradziezy"], w["ujemny_wsrod_kradziezy"]) == (1, 0.0)  # kradzież przy zasobach 3,0
    assert (w["n_dzielen"], w["ujemny_wsrod_dzielen"]) == (1, 0.0)


def test_oplacalnosc_wazona_liczba_dylematow_z_zakresem_przebiegow():
    # przebieg A: 4 dylematy, 1 z ujemnym zyskiem (25 %); B: 1 dylemat, ujemny (100 %)
    d = pd.DataFrame({
        "przebieg": ["A"] * 4 + ["B"], "seria": "X", "alfa": 1.0,
        "zasoby_celu": [1.0, 3.0, 3.0, 3.0, 1.0], "klasa": "obojetna",
    })

    w = ok.podsumuj_oplacalnosc(d, p=0.5, x=5.0, c_k=1.0).iloc[0]

    assert w["przebiegi"] == 2
    assert w["ujemny_zysk"] == pytest.approx(2 / 5)  # łącznie – większy przebieg waży więcej
    assert (w["ujemny_zysk_min"], w["ujemny_zysk_max"]) == pytest.approx((0.25, 1.0))


def test_ciagi_nie_lacza_pokolen():
    # ten sam agent i cel w ostatnim kroku pokolenia 0 i pierwszym pokolenia 1 – dwa ciągi
    dylematy = pd.DataFrame({
        "przebieg": ["X", "X"], "pokolenie": [0, 1], "krok": [299, 0], "id": [1, 1], "id_celu": [9, 9],
        "klasa": ["obojetna", "kradziez"],
    })

    wynik = ok.ciagi_dylematow(dylematy)

    assert wynik["pokolenie"].tolist() == [0, 1]
    assert wynik["ciagi"].tolist() == [1, 1]
    assert wynik["D"].tolist() == [1, 1]


def test_podsumuj_ciagi_recznie():
    # trzech agentów: D = 250 w 1 ciągu (same obojętne), D = 300 w 5 ciągach (połowa obojętnych),
    # D = 3 w 2 ciągach (bez obojętnych)
    tabela = pd.DataFrame({
        "seria": "X", "alfa": 1.0, "D": [250, 300, 3], "ciagi": [1, 5, 2],
        "najdluzszy": [250, 100, 2], "obojetne": [250, 150, 0],
    })

    w = ok.podsumuj_ciagi(tabela).iloc[0]

    assert w["agenci"] == 3
    assert w["mediana_D"] == 250
    assert w["mediana_ciagow"] == 2
    assert w["udzial_D200"] == pytest.approx(2 / 3)
    assert w["dlugie_ciagi_wsrod_D200"] == pytest.approx(1 / 2)
    assert w["obojetne_wsrod_D200"] == pytest.approx((1.0 + 0.5) / 2)  # średnia po agentach
    assert w["ciagi_na_D"] == pytest.approx(8 / 553)


def test_dlugi_ciag_kradziezy_to_powtarzanie_a_nie_biernosc():
    # agent kradnie przez 250 kolejnych kroków temu samemu celowi: jeden długi ciąg, zero obojętnych
    kroki = np.arange(250)
    dylematy = pd.DataFrame({
        "przebieg": "X", "pokolenie": 0, "krok": kroki, "id": 1, "id_celu": 9, "klasa": "kradziez",
    })

    agenci = ok.ciagi_dylematow(dylematy).assign(seria="X", alfa=1.0)
    w = ok.podsumuj_ciagi(agenci).iloc[0]

    assert agenci[["D", "ciagi", "obojetne"]].iloc[0].tolist() == [250, 1, 0]
    assert w["dlugie_ciagi_wsrod_D200"] == 1.0
    assert w["obojetne_wsrod_D200"] == 0.0


def test_bez_agentow_z_duzym_D_miary_D200_to_nan():
    tabela = pd.DataFrame({
        "seria": "X", "alfa": 1.0, "D": [3, 10], "ciagi": [2, 4], "najdluzszy": [2, 5], "obojetne": [1, 5],
    })

    w = ok.podsumuj_ciagi(tabela).iloc[0]

    assert w["udzial_D200"] == 0.0
    assert np.isnan(w["dlugie_ciagi_wsrod_D200"])
    assert np.isnan(w["obojetne_wsrod_D200"])


def test_main_na_malych_danych(tmp_path, dylematy):
    # dwa przebiegi w układzie katalogów z pilotażu: konfiguracja.json + dylematy.csv
    for nazwa, alfa in (("P1_z1", 1.0), ("P2_niedobor_z2", 0.85)):
        katalog = tmp_path / "wyniki" / nazwa
        katalog.mkdir(parents=True)
        cfg = {"koszty": {"p": 0.5, "x": 5.0, "c_k": 1.0}, "zasoby": {"alfa": alfa}, "przebieg": {"ziarno": 1}}
        (katalog / "konfiguracja.json").write_text(json.dumps({"konfiguracja": cfg}), encoding="utf-8")
        dylematy.drop(columns=["przebieg", "seria", "alfa"]).to_csv(katalog / "dylematy.csv", index=False)

    wyjscie = tmp_path / "analiza"
    assert ok.main([str(tmp_path / "wyniki"), "--serie", "P1", "P2", "--wyjscie", str(wyjscie)]) == 0

    oplacalnosc = pd.read_csv(wyjscie / "oplacalnosc.csv")
    assert oplacalnosc[["seria", "alfa"]].values.tolist() == [["P1", 1.0], ["P2", 0.85]]
    assert oplacalnosc["ujemny_zysk"].tolist() == pytest.approx([2 / 7, 2 / 7], abs=1e-4)
    ciagi = pd.read_csv(wyjscie / "ciagi_dylematow.csv")
    assert len(ciagi) == 2
    assert ciagi["mediana_ciagow"].tolist() == [2.0, 2.0]  # agenci z 3 i 1 ciągiem

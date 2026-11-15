"""Analiza serii kalibracyjnych K1, K2, K2b i K3.

Wejście: katalog serii z trybu serii (status.csv i katalogi przebiegów). Wyjście w --wyjscie:
podsumowanie CSV i LaTeX oraz wykresy właściwe dla serii. Kryteria: plan_kalibracji.md.
Z katalogu kod/:  PYTHONPATH=src python -m analiza.kalibracja K1 wyniki/K1 --wyjscie wyniki/analiza/K1
"""
import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import NullLocator  # noqa: E402

from analiza import eksploracja as ek  # noqa: E402
from moralnosc.siec import dlugosc_genomu  # noqa: E402
from moralnosc.stan import N_WE, N_WY, ZBIERZ  # noqa: E402

# (sekcja, klucz, kolumna) – parametry przebiegu dopisywane do każdej tabeli
PARAMETRY_WARIANTU = (
    ("obserwacje", "skala", "skala"),
    ("siec", "tau", "tau"),
    ("siec", "h", "h"),
    ("zasoby", "alfa", "alfa"),
    ("ewolucja", "T", "T"),
    ("ewolucja", "E0", "E0"),
    ("ewolucja", "r", "r"),
    ("ewolucja", "sigma", "sigma"),
    ("ewolucja", "R", "R"),
    ("przebieg", "ziarno", "ziarno"),
    ("przebieg", "pokolenia", "pokolenia_plan"),
)

# kolumny, które odróżniają warianty w serii
WARIANT = {
    "K1": ["skala", "tau"],
    "K1b": ["h"],
    "K2": ["T", "alfa"],
    "K2b": ["T", "alfa"],
    "K3": ["r", "sigma"],
    "K4": ["R"],
}

MIARY_K1 = [
    "przezycie", "koncentracja_p0", "entropia_p0", "entropia_koniec",
    "udzial_D_min", "mediana_D_p0", "zbieranie_koniec",
]
MIARY_K2 = ["przezycie", "udzial_zakwalifikowanych", "udzial_awaryjny"]

PROG_PRZEZYCIA = 2 / 3  # plan, sekcja 3: brak wymarcia w co najmniej 2 z 3 ziaren

# Kryteria dopuszczalności K2 ustalone przed uruchomieniem serii:
# mechanizm awaryjny w najwyżej 10% pokoleń oraz mediana udziału
# zakwalifikowanych wśród żywych w każdym ziarnie od 10% do 50%.
MAKS_UDZIAL_AWARYJNY = 0.10
MIN_UDZIAL_ZAKWALIFIKOWANYCH = 0.10
MAKS_UDZIAL_ZAKWALIFIKOWANYCH = 0.50

MIARY_K3 = ["przezycie", "rho_iloraz", "korelacja", "pary", "M_pop_koniec", "udzial_awaryjny"]
# Kryteria K3 z planu (ustalone przed serią): ρ_koniec/ρ_0 ≥ 0,25 (średnio po ziarnach),
# korelacja M_wyg rodzic–potomek > 0 przy co najmniej 30 parach w każdym ziarnie.
MIN_ILORAZ_RHO = 0.25
MIN_PAR = 30

NAZWY_WARIANTU = {
    "skala": "Skala",
    "tau": "$\\tau$",
    "h": "$n_{\\mathrm{h}}$",
    "T": "$T$",
    "alfa": "$\\alpha$",
    "r": "$r$",
    "r_L": "$rL$",
    "sigma": "$\\sigma$",
    "R": "$R$",
}

ETYKIETY_TEX = {
    "przezycie": "Przeżycie",
    "koncentracja_p0": "Koncentracja (pok.~0)",
    "entropia_p0": "Entropia (pok.~0)",
    "entropia_koniec": "Entropia (koniec)",
    "udzial_D_min": "$D \\ge D_{\\min}$ (pok.~0)",
    "mediana_D_p0": "Mediana $D$ (pok.~0)",
    "zbieranie_koniec": "Zbieranie (koniec)",
    "udzial_zakwalifikowanych": "Zakwalifikowani wśród żywych",
    "udzial_awaryjny": "Pokolenia z wariantem awaryjnym",
    "rho_iloraz": "$\\rho_{\\mathrm{koniec}}/\\rho_0$",
    "korelacja": "Korelacja rodzic--potomek",
    "pary": "Pary ($D \\ge D_{\\min}$)",
    "M_pop_koniec": "$M_{\\mathrm{pop}}$ (koniec)",
}


# --- wczytywanie -----------------------------------------------------------------------

def opis_przebiegu(katalog: Path) -> dict[str, object]:
    """Parametry wariantu z konfiguracja.json (brak klucza, np. h w danych z Lab02 → None)."""
    cfg = ek._wczytaj_konfiguracje(katalog)
    opis: dict[str, object] = {"przebieg": katalog.name}
    for sekcja, klucz, kolumna in PARAMETRY_WARIANTU:
        opis[kolumna] = cfg.get(sekcja, {}).get(klucz)
    return opis


def _przebiegi_serii(katalog_serii: Path) -> list[Path]:
    """Ze status.csv tylko przebiegi „zakonczony”; bez status.csv – podkatalogi z konfiguracja.json."""
    plik_statusu = katalog_serii / "status.csv"
    if not plik_statusu.exists():
        return sorted(k for k in katalog_serii.iterdir() if (k / "konfiguracja.json").exists())
    status = pd.read_csv(plik_statusu)
    zakonczone = status["status"].eq("zakonczony")
    for wiersz in status[~zakonczone].itertuples():
        print(f"Pomijam {wiersz.id}: status {wiersz.status}", file=sys.stderr)
    # kolumna katalog jest względna wobec katalogu uruchomienia, więc bierzemy samą nazwę
    return sorted(katalog_serii / Path(k).name for k in status.loc[zakonczone, "katalog"])


def wczytaj_serie(katalog_serii: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """(pokolenia, agenci, nazwy przebiegów) serii z kolumnami opisu wariantu."""
    katalogi = _przebiegi_serii(katalog_serii)
    if not katalogi:
        raise ValueError(f"Brak zakończonych przebiegów w {katalog_serii}")
    wszystkie_pokolenia, wszyscy_agenci = [], []
    for katalog in katalogi:
        pokolenia, agenci, cfg = ek.wczytaj_przebieg(katalog)
        # przebieg, seria, alfa i ziarno dopisuje eksploracja; tu reszta parametrów
        reszta = {k: v for k, v in opis_przebiegu(katalog).items() if k not in ("przebieg", "alfa", "ziarno")}
        for tabela, lista in ((pokolenia, wszystkie_pokolenia), (agenci, wszyscy_agenci)):
            ek._dopisz_opis_przebiegu(tabela, katalog, cfg)
            lista.append(tabela.assign(**reszta))
    return (
        pd.concat(wszystkie_pokolenia, ignore_index=True),
        pd.concat(wszyscy_agenci, ignore_index=True),
        [k.name for k in katalogi],
    )


def wczytaj_dylematy_p0(katalog_serii: Path, przebiegi: list[str]) -> pd.DataFrame:
    """Dylematy pokolenia 0 (przebieg, id, akcja) – w K1 to ok. 1 % pliku, reszty nie wczytujemy."""
    tabele = []
    for nazwa in przebiegi:
        d = pd.read_csv(katalog_serii / nazwa / "dylematy.csv", usecols=["pokolenie", "id", "akcja"])
        tabele.append(d.loc[d["pokolenie"].eq(0), ["id", "akcja"]].assign(przebieg=nazwa))
    return pd.concat(tabele, ignore_index=True)


# --- K1: zróżnicowanie decyzji -----------------------------------------------------------

def entropia_akcji(pokolenia: pd.DataFrame) -> pd.Series:
    """Entropia rozkładu akcji w wierszu w bitach, H = −Σ p·log2 p: 0 (jedna akcja) … 3 (równo)."""
    liczniki = pokolenia[ek.KOLUMNY_AKCJI].to_numpy(dtype=float)
    p = liczniki / liczniki.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        skladniki = np.where(p > 0, p * np.log2(p), 0.0)
    return pd.Series(-skladniki.sum(axis=1), index=pokolenia.index, name="entropia")


def _miary_przebiegow_K1(
    pokolenia: pd.DataFrame, agenci: pd.DataFrame, dylematy: pd.DataFrame, D_min: int, ostatnie: int
) -> pd.DataFrame:
    """Miary K1 dla każdego przebiegu (indeks = przebieg)."""
    pok = pokolenia.assign(entropia=entropia_akcji(pokolenia))
    po_przebiegu = pok.groupby("przebieg")
    # przeżył: wszystkie zaplanowane pokolenia i ktoś żywy na końcu ostatniego
    przezycie = (po_przebiegu.size() == po_przebiegu["pokolenia_plan"].first()) & (
        po_przebiegu["zywi_koniec"].last() > 0
    )
    koniec = pok[pok["pokolenie"] > po_przebiegu["pokolenie"].transform("max") - ostatnie]
    akcje_koniec = koniec.groupby("przebieg")[ek.KOLUMNY_AKCJI].sum()
    p0 = pok[pok["pokolenie"].eq(0)].set_index("przebieg")
    agenci_p0 = agenci[agenci["pokolenie"].eq(0)].groupby("przebieg")["D"]
    koncentracja = ek.najczestsza_akcja_w_dylematach(dylematy, min_decyzji=D_min)
    miary = pd.DataFrame(
        {
            "przezycie": przezycie.astype(float),
            "koncentracja_p0": koncentracja.groupby(level="przebieg").median(),
            "entropia_p0": p0["entropia"],
            "entropia_koniec": koniec.groupby("przebieg")["entropia"].mean(),
            "udzial_D_min": agenci_p0.apply(lambda D: (D >= D_min).mean()),
            "mediana_D_p0": agenci_p0.median(),
            "zbieranie_koniec": akcje_koniec[f"akcja_{ZBIERZ}"] / akcje_koniec.sum(axis=1),
        }
    )
    return miary.join(po_przebiegu[WARIANT["K1"]].first())


def podsumuj_K1(
    pokolenia: pd.DataFrame, agenci: pd.DataFrame, dylematy: pd.DataFrame, D_min: int, ostatnie: int = 5
) -> pd.DataFrame:
    """Wiersz = wariant (skala, tau): miary średnio po ziarnach, `_sd` – odchylenie między ziarnami.

    dopuszczalny = przeżycie w ≥ 2/3 ziaren i średnia mediana D w pokoleniu 0 ≥ D_min (plan K1).
    """
    miary = _miary_przebiegow_K1(pokolenia, agenci, dylematy, D_min, ostatnie)
    grupy = miary.groupby(WARIANT["K1"])
    wynik = pd.concat([grupy.size().rename("ziarna"), grupy[MIARY_K1].mean()], axis=1)
    for miara in MIARY_K1[1:]:  # odchylenie przeżycia (0/1) nic nie mówi
        wynik.insert(wynik.columns.get_loc(miara) + 1, f"{miara}_sd", grupy[miara].std())
    wynik["dopuszczalny"] = (wynik["przezycie"] >= PROG_PRZEZYCIA - 1e-9) & (wynik["mediana_D_p0"] >= D_min)
    return wynik.reset_index()


def _miary_przebiegow_K2(pokolenia: pd.DataFrame) -> pd.DataFrame:
    """Miary stabilności selekcji K2 dla każdego przebiegu."""
    pok = pokolenia.copy()
    pok["udzial_zakwalifikowanych"] = pok["zakwalifikowani"].div(
        pok["zywi_koniec"].where(pok["zywi_koniec"].gt(0))
    )
    po_przebiegu = pok.groupby("przebieg")
    przezycie = (po_przebiegu.size() == po_przebiegu["pokolenia_plan"].first()) & (
        po_przebiegu["zywi_koniec"].last() > 0
    )
    miary = pd.DataFrame(
        {
            "przezycie": przezycie.astype(float),
            "udzial_zakwalifikowanych": po_przebiegu[
                "udzial_zakwalifikowanych"
            ].median(),
            "udzial_awaryjny": po_przebiegu["awaryjny"].mean(),
        }
    )
    return miary.join(po_przebiegu[WARIANT["K2"]].first())


def podsumuj_K2(pokolenia: pd.DataFrame) -> pd.DataFrame:
    """Podsumowuje K2 po ziarnach i wskazuje wariant zgodny z planem."""
    miary = _miary_przebiegow_K2(pokolenia)
    grupy = miary.groupby(WARIANT["K2"])
    wynik = pd.concat([grupy.size().rename("ziarna"), grupy[MIARY_K2].mean()], axis=1)
    for miara in MIARY_K2[1:]:
        wynik.insert(wynik.columns.get_loc(miara) + 1, f"{miara}_sd", grupy[miara].std())

    wynik["udzial_awaryjny_max"] = grupy["udzial_awaryjny"].max()
    wynik["udzial_zakwalifikowanych_min"] = grupy[
        "udzial_zakwalifikowanych"
    ].min()
    wynik["udzial_zakwalifikowanych_max"] = grupy[
        "udzial_zakwalifikowanych"
    ].max()
    wynik["dopuszczalny"] = (
        wynik["przezycie"].eq(1.0)
        & wynik["udzial_awaryjny_max"].le(MAKS_UDZIAL_AWARYJNY)
        & wynik["udzial_zakwalifikowanych_min"].ge(
            MIN_UDZIAL_ZAKWALIFIKOWANYCH
        )
        & wynik["udzial_zakwalifikowanych_max"].le(
            MAKS_UDZIAL_ZAKWALIFIKOWANYCH
        )
    )
    wynik = wynik.reset_index()
    wynik["odleglosc_od_bazowego"] = (
        (wynik["T"] - 50.0).abs() / 20.0
        + (wynik["alfa"] - 1.0).abs() / 0.15
    )
    wynik["wybrany"] = False

    bazowy = (
        wynik["dopuszczalny"]
        & np.isclose(wynik["T"], 50.0)
        & np.isclose(wynik["alfa"], 1.0)
    )
    if bazowy.any():
        wynik.loc[bazowy, "wybrany"] = True
    else:
        kandydaci = wynik[wynik["dopuszczalny"]].sort_values(
            [
                "udzial_awaryjny",
                "udzial_zakwalifikowanych_sd",
                "odleglosc_od_bazowego",
                "T",
                "alfa",
            ]
        )
        if not kandydaci.empty:
            wynik.loc[kandydaci.index[0], "wybrany"] = True
    return wynik


def _wykres_od_tau(podsumowanie: pd.DataFrame, miara: str, opis_y: str, plik: Path) -> None:
    """Miara w funkcji tau (oś logarytmiczna), linia na skalę, słupki = sd między ziarnami."""
    fig, os_ = plt.subplots(figsize=(3.2, 2.4))
    for skala, grupa in podsumowanie.groupby("skala"):
        grupa = grupa.sort_values("tau")
        os_.errorbar(
            grupa["tau"], grupa[miara], yerr=grupa[f"{miara}_sd"],
            marker="o", markersize=4, capsize=3, label=f"skala {skala:g}".replace(".", ","),
        )
    os_.set_xscale("log", base=2)
    os_.set_xticks(sorted(podsumowanie["tau"].unique()))
    os_.xaxis.set_minor_locator(NullLocator())
    ek._przecinki(os_, x=True)
    os_.set_xlabel("temperatura $\\tau$")
    os_.set_ylabel(opis_y)
    os_.legend(fontsize="small", frameon=False)
    ek._zapisz_wykres(fig, plik)


def wykres_K1(podsumowanie: pd.DataFrame, plik_koncentracja: Path, plik_entropia: Path) -> None:
    """Koncentracja decyzji w pokoleniu 0 i entropia akcji na końcu w funkcji tau."""
    _wykres_od_tau(podsumowanie, "koncentracja_p0", "koncentracja decyzji (pok. 0)", plik_koncentracja)
    _wykres_od_tau(podsumowanie, "entropia_koniec", "entropia akcji [bit]", plik_entropia)


def _wykres_K2_miary(
    podsumowanie: pd.DataFrame,
    miara: str,
    opis_y: str,
    plik: Path,
) -> None:
    """Miara K2 w funkcji T; linia na wartość alfa, słupki = sd między ziarnami."""
    fig, os_ = plt.subplots(figsize=(3.2, 2.4))
    for alfa, grupa in podsumowanie.groupby("alfa"):
        grupa = grupa.sort_values("T")
        os_.errorbar(
            grupa["T"],
            grupa[miara],
            yerr=grupa[f"{miara}_sd"],
            marker="o",
            markersize=4,
            capsize=3,
            label=f"$\\alpha$ = {alfa:g}".replace(".", ","),
        )
    os_.set_xticks(sorted(podsumowanie["T"].unique()))
    os_.set_ylim(0, 1)
    ek._przecinki(os_, x=True)
    os_.set_xlabel("próg reprodukcji $T$")
    os_.set_ylabel(opis_y)
    os_.legend(fontsize="small", frameon=False)
    ek._zapisz_wykres(fig, plik)


def wykres_K2(
    podsumowanie: pd.DataFrame,
    plik_zakwalifikowani: Path,
    plik_awaryjny: Path,
) -> None:
    """Udział zakwalifikowanych i wariantu awaryjnego dla kombinacji T i alfa."""
    _wykres_K2_miary(
        podsumowanie,
        "udzial_zakwalifikowanych",
        "mediana udziału zakwalifikowanych",
        plik_zakwalifikowani,
    )
    _wykres_K2_miary(
        podsumowanie,
        "udzial_awaryjny",
        "udział pokoleń z wariantem awaryjnym",
        plik_awaryjny,
    )


# --- K3: różnorodność i odziedziczalność ----------------------------------------------

def _korelacja_par(pary: pd.DataFrame) -> float:
    """Korelacja Pearsona M_wyg potomka i rodzica; NaN przy < 3 parach albo zerowej wariancji."""
    if len(pary) < 3 or pary["M_wyg"].std() == 0 or pary["M_wyg_rodzica"].std() == 0:
        return float("nan")
    return float(pary["M_wyg"].corr(pary["M_wyg_rodzica"]))


def odziedziczalnosc(agenci: pd.DataFrame, a: float, D_min: int) -> pd.DataFrame:
    """Na przebieg: pary rodzic–potomek z D ≥ D_min po obu stronach, korelacja ich M_wyg(a)
    i udział par wśród potomków (pokolenia ≥ 1)."""
    ag = ek.dodaj_wspolczynniki(agenci, a)
    # rodzic z pokolenia g − 1 dopasowany do potomka z pokolenia g; pokolenie 0 (id_rodzica = −1) odpada samo
    rodzice = ag[["przebieg", "pokolenie", "id", "M_wyg", "D"]].rename(
        columns={"id": "id_rodzica", "M_wyg": "M_wyg_rodzica", "D": "D_rodzica"}
    )
    rodzice["pokolenie"] += 1
    pary = ag.merge(rodzice, on=["przebieg", "pokolenie", "id_rodzica"])
    pary = pary[pary["D"].ge(D_min) & pary["D_rodzica"].ge(D_min)]
    potomkowie = ag[ag["pokolenie"].ge(1)].groupby("przebieg").size()
    wynik = pd.DataFrame({"przebieg": potomkowie.index})
    wynik["pary"] = wynik["przebieg"].map(pary.groupby("przebieg").size()).fillna(0).astype(int)
    wynik["korelacja"] = wynik["przebieg"].map(
        {nazwa: _korelacja_par(grupa) for nazwa, grupa in pary.groupby("przebieg")}
    ).astype(float)
    wynik["udzial_par"] = wynik["pary"] / wynik["przebieg"].map(potomkowie)
    return wynik


def roznorodnosc_w_czasie(pokolenia: pd.DataFrame) -> pd.DataFrame:
    """Różnorodność ρ w kolejnych pokoleniach: wiersz = (r, sigma, pokolenie), średnia, min i max po ziarnach."""
    if "roznorodnosc" not in pokolenia.columns:
        raise ValueError("Brak kolumny 'roznorodnosc' w pokolenia.csv – dane sprzed pomiaru różnorodności (#26)")
    return (
        pokolenia.groupby([*WARIANT["K3"], "pokolenie"])["roznorodnosc"]
        .agg(["mean", "min", "max"])
        .reset_index()
    )


def _r_razy_L(tabela: pd.DataFrame) -> pd.Series:
    """r w jednostkach 1/L (L z h przebiegu): 0,5, 1 albo 3; r = "auto" to 1."""
    L = tabela["h"].map(lambda h: dlugosc_genomu(N_WE, N_WY, int(h)))
    r = pd.to_numeric(tabela["r"].replace("auto", np.nan), errors="coerce")
    return (r * L).fillna(1.0).round(6)


def _miary_przebiegow_K3(
    pokolenia: pd.DataFrame, agenci: pd.DataFrame, a: float, D_min: int, ostatnie: int
) -> pd.DataFrame:
    """Miary K3 dla każdego przebiegu (indeks = przebieg)."""
    if "roznorodnosc" not in pokolenia.columns:
        raise ValueError("Brak kolumny 'roznorodnosc' w pokolenia.csv – dane sprzed pomiaru różnorodności (#26)")
    pok = pokolenia.sort_values(["przebieg", "pokolenie"])
    po_przebiegu = pok.groupby("przebieg")
    przezycie = (po_przebiegu.size() == po_przebiegu["pokolenia_plan"].first()) & (
        po_przebiegu["zywi_koniec"].last() > 0
    )
    m_pop = ek.m_pop(agenci)
    m_pop = m_pop[m_pop["pokolenie"] > m_pop.groupby("przebieg")["pokolenie"].transform("max") - ostatnie]
    miary = pd.DataFrame(
        {
            "przezycie": przezycie.astype(float),
            "rho_0": po_przebiegu["roznorodnosc"].first(),
            "rho_koniec": po_przebiegu["roznorodnosc"].last(),
            "M_pop_koniec": m_pop.groupby("przebieg")["M_pop"].mean(),
            "udzial_awaryjny": po_przebiegu["awaryjny"].mean(),
        }
    )
    miary["rho_iloraz"] = miary["rho_koniec"] / miary["rho_0"]
    miary = miary.join(odziedziczalnosc(agenci, a, D_min).set_index("przebieg")[["pary", "korelacja"]])
    # plan, sekcja 5: miary końcowe tylko z przebiegów bez wymarcia
    koncowe = ["rho_koniec", "rho_iloraz", "M_pop_koniec", "pary", "korelacja"]
    miary.loc[miary["przezycie"].eq(0), koncowe] = np.nan
    return miary.join(po_przebiegu[[*WARIANT["K3"], "h"]].first())


def podsumuj_K3(
    pokolenia: pd.DataFrame,
    agenci: pd.DataFrame,
    a: float,
    D_min: int,
    ostatnie: int = 5,
    min_par: int = MIN_PAR,
) -> pd.DataFrame:
    """Wiersz = wariant (r, sigma): miary średnio po ziarnach (`_sd` – odchylenie), flaga
    „dopuszczalny” i „wybrany” według kryteriów K3 z planu."""
    miary = _miary_przebiegow_K3(pokolenia, agenci, a, D_min, ostatnie)
    miary["r_L"] = _r_razy_L(miary)
    grupy = miary.groupby([*WARIANT["K3"], "r_L"])
    wynik = pd.concat([grupy.size().rename("ziarna"), grupy[MIARY_K3].mean()], axis=1)
    for miara in MIARY_K3[1:]:  # odchylenie przeżycia (0/1) nic nie mówi
        wynik.insert(wynik.columns.get_loc(miara) + 1, f"{miara}_sd", grupy[miara].std())
    wynik["korelacja_min"] = grupy["korelacja"].min()
    wynik["pary_min"] = grupy["pary"].min()
    wynik["dopuszczalny"] = (
        wynik["przezycie"].ge(PROG_PRZEZYCIA - 1e-9)
        & wynik["korelacja_min"].gt(0)
        & wynik["pary_min"].ge(min_par)
        & wynik["rho_iloraz"].ge(MIN_ILORAZ_RHO)
    )
    wynik = wynik.reset_index()
    wynik["wybrany"] = False
    kandydaci = wynik[wynik["dopuszczalny"]]
    if not kandydaci.empty:
        najlepszy = kandydaci.loc[kandydaci["korelacja"].idxmax()]
        sd = 0.0 if pd.isna(najlepszy["korelacja_sd"]) else najlepszy["korelacja_sd"]
        # remis = różnica w granicach sd najlepszego; wtedy bliżej bazowych r = 1/L, sigma = 0,2
        remis = kandydaci[kandydaci["korelacja"] >= najlepszy["korelacja"] - sd].assign(
            odleglosc=lambda t: np.abs(np.log2(t["r_L"])) + np.abs(np.log2(t["sigma"] / 0.2))
        )
        wybrany = remis.sort_values(["odleglosc", "korelacja"], ascending=[True, False]).index[0]
        wynik.loc[wybrany, "wybrany"] = True
    return wynik


def wykres_K3(
    srednie: pd.DataFrame, podsumowanie: pd.DataFrame, plik_roznorodnosc: Path, plik_odziedziczalnosc: Path
) -> None:
    """(1) ρ w kolejnych pokoleniach – kolor: sigma, styl linii: r; (2) korelacja rodzic–potomek
    w funkcji sigma, linia na r, słupki = sd między ziarnami."""

    def opis_r(wartosc: float) -> str:
        return f"r = {wartosc:g}/L".replace(".", ",")

    r_L = dict(zip(podsumowanie["r"], podsumowanie["r_L"]))
    style = dict(zip(sorted(podsumowanie["r_L"].unique()), [":", "-", "--", "-."]))
    kolory = {s: f"C{i}" for i, s in enumerate(sorted(podsumowanie["sigma"].unique()))}
    fig, os_ = plt.subplots(figsize=(3.2, 2.4))
    for (r, sigma), grupa in srednie.groupby(["r", "sigma"]):
        os_.plot(grupa["pokolenie"], grupa["mean"], color=kolory[sigma], linestyle=style[r_L[r]], linewidth=1)
    uchwyty = [Line2D([], [], color=k, label=f"$\\sigma$ = {s:g}".replace(".", ",")) for s, k in kolory.items()]
    uchwyty += [Line2D([], [], color="0.3", linestyle=st, label=opis_r(w)) for w, st in style.items()]
    os_.legend(handles=uchwyty, fontsize="x-small", frameon=False, ncol=2)
    ek._przecinki(os_)
    os_.set_xlabel("pokolenie")
    os_.set_ylabel("różnorodność $\\rho$")
    ek._zapisz_wykres(fig, plik_roznorodnosc)

    fig, os_ = plt.subplots(figsize=(3.2, 2.4))
    for wartosc, grupa in podsumowanie.groupby("r_L"):
        grupa = grupa.sort_values("sigma")
        os_.errorbar(
            grupa["sigma"], grupa["korelacja"], yerr=grupa["korelacja_sd"],
            marker="o", markersize=4, capsize=3, linestyle=style[wartosc], label=opis_r(wartosc),
        )
    os_.axhline(0, color="0.6", linewidth=0.8)
    os_.set_xscale("log", base=2)
    os_.set_xticks(sorted(podsumowanie["sigma"].unique()))
    os_.xaxis.set_minor_locator(NullLocator())
    ek._przecinki(os_, x=True)
    os_.set_xlabel("siła mutacji $\\sigma$")
    os_.set_ylabel("korelacja $M_{\\mathrm{wyg}}$ rodzic–potomek")
    os_.legend(fontsize="small", frameon=False)
    ek._zapisz_wykres(fig, plik_odziedziczalnosc)


# --- zapis i uruchomienie --------------------------------------------------------------

def _komorka(wiersz: pd.Series, kolumna: str) -> str:
    """„średnia (sd)”; udziały w procentach, ich sd w punktach procentowych."""
    if kolumna == "przezycie":
        return f"{round(wiersz['przezycie'] * wiersz['ziarna'])}/{int(wiersz['ziarna'])}"
    udzial = kolumna.startswith(("udzial", "zbieranie"))
    format_ = ek.procent_tex if udzial else ek.liczba_tex
    tekst = format_(wiersz[kolumna])
    if f"{kolumna}_sd" in wiersz.index:
        odchylenie = wiersz[f"{kolumna}_sd"]
        if udzial and not pd.isna(odchylenie):
            tekst_odchylenia = f"{ek.liczba_tex(odchylenie * 100, miejsca=1)}~p.p."
        else:
            tekst_odchylenia = format_(odchylenie)
        tekst += f" ({tekst_odchylenia})"
    return tekst


def _wartosc_tex(wartosc: object) -> str:
    """Wartość parametru bez zbędnych zer: 0.5 → 0{,}5, 5.0 → 5."""
    return "--" if pd.isna(wartosc) else f"{wartosc:g}".replace(".", "{,}")


def zapisz_podsumowanie(
    tabela: pd.DataFrame,
    katalog: Path,
    nazwa: str,
    podpis: str,
    etykieta: str,
    miary: list[str] | None = None,
) -> None:
    """CSV (4 miejsca) i tabela LaTeX: wariant, potem miary (domyślnie wszystkie znane) jako „średnia (sd)”."""
    tabela.to_csv(katalog / f"{nazwa}.csv", index=False, float_format="%.4f")
    kolumny_wariantu = [k for k in NAZWY_WARIANTU if k in tabela.columns]
    if "r_L" in kolumny_wariantu:  # r w jednostkach 1/L czytelniejsze niż 0,0041667
        kolumny_wariantu.remove("r")
    miary = miary or [k for k in ETYKIETY_TEX if k in tabela.columns]
    wiersze = [
        [" / ".join(_wartosc_tex(w[k]) for k in kolumny_wariantu)] + [_komorka(w, m) for m in miary]
        for _, w in tabela.iterrows()
    ]
    ek.zapisz_tabele_tex(
        wiersze,
        katalog / f"{nazwa}.tex",
        naglowek=[" / ".join(NAZWY_WARIANTU[k] for k in kolumny_wariantu)] + [ETYKIETY_TEX[m] for m in miary],
        podpis=podpis,
        etykieta=etykieta,
        szerokosc_pierwszej=0.11,
    )
    # zapisz_tabele_tex wpisuje w nagłówku eksploracja.py – poprawiamy źródło
    plik_tex = katalog / f"{nazwa}.tex"
    plik_tex.write_text(
        plik_tex.read_text(encoding="utf-8").replace("analiza/eksploracja.py", "analiza/kalibracja.py", 1),
        encoding="utf-8",
    )


def utworz_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m analiza.kalibracja")
    parser.add_argument(
        "seria",
        choices=sorted(WARIANT),
        help="seria: K1, K2, K2b lub K3 (K4 – kolejny krok)",
    )
    parser.add_argument("katalog", type=Path, help="katalog serii z trybu serii")
    parser.add_argument("--wyjscie", type=Path, default=None, help="domyślnie wyniki/analiza/<seria>")
    parser.add_argument("--a", type=float, default=2.0, help="wygładzanie M_wyg (Lab02: a = 2)")
    parser.add_argument("--D-min", dest="D_min", type=int, default=5, help="próg D (Lab02: 5)")
    parser.add_argument("--ostatnie", type=int, default=5, help="ile ostatnich pokoleń uśredniać")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Podsumowanie serii: CSV, tabela LaTeX, wykresy i lista wariantów dopuszczalnych."""
    # Windows może uruchomić Pythona z kodowaniem CP1252, które nie obsługuje
    # części polskich znaków ani symboli używanych w podsumowaniu konsolowym.
    ustaw_kodowanie = getattr(sys.stdout, "reconfigure", None)
    if ustaw_kodowanie is not None:
        ustaw_kodowanie(encoding="utf-8")

    arg = utworz_parser().parse_args(argv)
    if arg.seria not in ("K1", "K2", "K2b", "K3"):
        print(f"Analiza serii {arg.seria} będzie w kolejnym PR.", file=sys.stderr)
        return 2
    wyjscie = arg.wyjscie or Path("wyniki/analiza") / arg.seria
    wyjscie.mkdir(parents=True, exist_ok=True)

    pokolenia, agenci, przebiegi = wczytaj_serie(arg.katalog)
    if arg.seria == "K1":
        dylematy = wczytaj_dylematy_p0(arg.katalog, przebiegi)
        podsumowanie = podsumuj_K1(
            pokolenia, agenci, dylematy, arg.D_min, arg.ostatnie
        )
        ziarna = int(podsumowanie["ziarna"].max())
        zapisz_podsumowanie(
            podsumowanie, wyjscie, "K1_podsumowanie",
            podpis=(
                "Seria K1: zróżnicowanie decyzji dla kombinacji skali obserwacji i temperatury $\\tau$ "
                f"(średnia po {ziarna} ziarnach, w nawiasie odchylenie między ziarnami; koncentracja -- "
                f"mediana udziału najczęstszej akcji agenta w dylematach pokolenia 0 dla agentów z $D \\ge {arg.D_min}$; "
                f"„koniec” -- ostatnie {arg.ostatnie} pokoleń)"
            ),
            etykieta="tab:K1",
        )
        wykres_K1(
            podsumowanie,
            wyjscie / "K1_koncentracja.pdf",
            wyjscie / "K1_entropia.pdf",
        )
        dopuszczalne = podsumowanie[podsumowanie["dopuszczalny"]].sort_values(
            "koncentracja_p0"
        )
        opis_dopuszczalnych = (
            f"Dopuszczalne (przeżycie >= 2/3, mediana D w pok. 0 >= {arg.D_min}), "
            "od najniższej koncentracji:"
        )
        kolumny = [
            *WARIANT["K1"],
            "koncentracja_p0",
            "koncentracja_p0_sd",
            "entropia_koniec",
            "entropia_koniec_sd",
        ]
    elif arg.seria in ("K2", "K2b"):
        nazwa_serii = arg.seria
        podsumowanie = podsumuj_K2(pokolenia)
        ziarna = int(podsumowanie["ziarna"].max())
        zapisz_podsumowanie(
            podsumowanie,
            wyjscie,
            f"{nazwa_serii}_podsumowanie",
            podpis=(
                f"Seria {nazwa_serii}: stabilność selekcji dla kombinacji progu reprodukcji $T$ "
                f"i dostępności zasobów $\\alpha$ (średnia po {ziarna} ziarnach, "
                "w nawiasie odchylenie między ziarnami)"
            ),
            etykieta=f"tab:{nazwa_serii}",
        )
        wykres_K2(
            podsumowanie,
            wyjscie / f"{nazwa_serii}_zakwalifikowani.pdf",
            wyjscie / f"{nazwa_serii}_awaryjny.pdf",
        )
        dopuszczalne = podsumowanie[podsumowanie["dopuszczalny"]].sort_values(
            ["wybrany", "udzial_awaryjny", "udzial_zakwalifikowanych_sd"],
            ascending=[False, True, True],
        )
        opis_dopuszczalnych = (
            "Dopuszczalne (bez wymarcia, wariant awaryjny <= 10%, mediana udziału "
            "zakwalifikowanych w każdym ziarnie 10-50%):"
        )
        kolumny = [
            *WARIANT["K2"],
            "udzial_zakwalifikowanych",
            "udzial_zakwalifikowanych_sd",
            "udzial_awaryjny",
            "udzial_awaryjny_sd",
            "wybrany",
        ]

    elif arg.seria == "K3":
        podsumowanie = podsumuj_K3(pokolenia, agenci, arg.a, arg.D_min, arg.ostatnie)
        ziarna = int(podsumowanie["ziarna"].max())
        zapisz_podsumowanie(
            podsumowanie,
            wyjscie,
            "K3_podsumowanie",
            podpis=(
                "Seria K3: różnorodność genetyczna i odziedziczalność zachowania dla kombinacji "
                "prawdopodobieństwa mutacji $r$ (w jednostkach $1/L$) i siły mutacji $\\sigma$ "
                f"(średnia po {ziarna} ziarnach, w nawiasie odchylenie między ziarnami; korelacja "
                f"$M_{{\\mathrm{{wyg}}}}$ ($a = {arg.a:g}$) rodzica i potomka dla par, w których oboje mają "
                f"$D \\ge {arg.D_min}$; „koniec” -- ostatnie {arg.ostatnie} pokoleń)"
            ),
            etykieta="tab:K3",
            miary=MIARY_K3,
        )
        wykres_K3(
            roznorodnosc_w_czasie(pokolenia),
            podsumowanie,
            wyjscie / "K3_roznorodnosc.pdf",
            wyjscie / "K3_odziedziczalnosc.pdf",
        )
        dopuszczalne = podsumowanie[podsumowanie["dopuszczalny"]].sort_values(
            ["wybrany", "korelacja"], ascending=[False, False]
        )
        opis_dopuszczalnych = (
            f"Dopuszczalne (przeżycie >= 2/3, korelacja > 0 przy >= {MIN_PAR} parach w każdym ziarnie, "
            f"rho_koniec/rho_0 >= {MIN_ILORAZ_RHO:g}); pierwszy – wybrany:"
        )
        kolumny = [
            *WARIANT["K3"],
            "r_L",
            "rho_iloraz",
            "korelacja",
            "korelacja_sd",
            "pary_min",
            "wybrany",
        ]

    print(f"Przebiegi: {len(przebiegi)}, warianty: {len(podsumowanie)}")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(podsumowanie.round(3).to_string(index=False))
    print(f"\n{opis_dopuszczalnych}")
    print(
        dopuszczalne[kolumny].round(3).to_string(index=False)
        if len(dopuszczalne)
        else "brak"
    )
    print(f"\nWyniki: {wyjscie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

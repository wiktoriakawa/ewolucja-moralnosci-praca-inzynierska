"""Opłacalność kradzieży i „bierne” dylematy w danych pilotażu (Lab03, decyzja #21).

Liczone z dylematy.csv, bez nowej symulacji: (1) w ilu dylematach oczekiwany zysk
z kradzieży p·min(x, zasoby_celu) − c_k był ujemny; (2) ile różnych spotkań (ciągów
kolejnych kroków przed tym samym celem) kryje się za liczbą dylematów D.
Z katalogu kod/:  PYTHONPATH=src python -m analiza.oplacalnosc_kradziezy ../asystent/Lab02/wyniki \\
    --serie P1 P2 --wyjscie wyniki/analiza/oplacalnosc
"""
import argparse
from pathlib import Path

import pandas as pd

from analiza.eksploracja import _dopisz_opis_przebiegu, _wczytaj_konfiguracje

KOLUMNY = ["pokolenie", "krok", "id", "id_celu", "zasoby_celu", "klasa"]
KLUCZ_AGENTA = ["przebieg", "pokolenie", "id"]
PROG_DUZEGO_D = 200  # Lab02: 14–20 % agentów z D > 200 przy α ≥ 1


def oczekiwany_zysk(zasoby_celu: pd.Series, p: float, x: float, c_k: float) -> pd.Series:
    """p · min(x, zasoby_celu) − c_k (D5); przy p = 0,5, x = 5, c_k = 1 ujemny, gdy zasoby celu < 2."""
    return zasoby_celu.clip(upper=x) * p - c_k


def podsumuj_oplacalnosc(dylematy: pd.DataFrame, p: float, x: float, c_k: float) -> pd.DataFrame:
    """Wiersz = (seria, alfa): liczba dylematów i odsetek z ujemnym zyskiem – ogółem, w kradzieżach, w dzieleniach."""
    d = dylematy.assign(ujemny=oczekiwany_zysk(dylematy["zasoby_celu"], p, x, c_k) < 0)
    grupy = d.groupby(["seria", "alfa"])
    kradziez, dzielenie = d["klasa"].eq("kradziez"), d["klasa"].eq("dzielenie")
    wynik = pd.DataFrame({
        "n": grupy.size(),
        "ujemny_zysk": grupy["ujemny"].mean(),
        "n_kradziezy": kradziez.groupby([d["seria"], d["alfa"]]).sum(),
        "ujemny_wsrod_kradziezy": d[kradziez].groupby(["seria", "alfa"])["ujemny"].mean(),
        "n_dzielen": dzielenie.groupby([d["seria"], d["alfa"]]).sum(),
        "ujemny_wsrod_dzielen": d[dzielenie].groupby(["seria", "alfa"])["ujemny"].mean(),
    })
    return wynik.reset_index()


def spotkania(dylematy: pd.DataFrame) -> pd.DataFrame:
    """Na (przebieg, pokolenie, id): D (kroki w dylemacie), spotkania (ciągi kolejnych kroków
    przed tym samym celem) i najdłuższe spotkanie w krokach."""
    d = dylematy.sort_values([*KLUCZ_AGENTA, "krok"])[[*KLUCZ_AGENTA, "krok", "id_celu"]]
    g = d.groupby(KLUCZ_AGENTA, sort=False)
    # nowe spotkanie: inny cel albo przerwa w krokach; pierwszy wiersz grupy (NaN po shift) zawsze
    nowe = (g["id_celu"].shift() != d["id_celu"]) | (g["krok"].shift() + 1 != d["krok"])
    numer = nowe.groupby([d[k] for k in KLUCZ_AGENTA], sort=False).cumsum().rename("spotkanie")
    dlugosci = d.groupby([*(d[k] for k in KLUCZ_AGENTA), numer], sort=False).size()
    wynik = dlugosci.groupby(level=KLUCZ_AGENTA, sort=False).agg(D="sum", spotkania="size", najdluzsze="max")
    return wynik.reset_index()


def podsumuj_spotkania(tabela: pd.DataFrame) -> pd.DataFrame:
    """Wiersz = (seria, alfa); tylko agenci z D ≥ 1. „Bierni”: D ≥ 200 przy co najwyżej 2 spotkaniach."""
    t = tabela.assign(
        duze_D=tabela["D"] >= PROG_DUZEGO_D,
        bierny=(tabela["D"] >= PROG_DUZEGO_D) & (tabela["spotkania"] <= 2),
    )
    grupy = t.groupby(["seria", "alfa"])
    wynik = pd.DataFrame({
        "agenci": grupy.size(),
        "mediana_D": grupy["D"].median(),
        "mediana_spotkan": grupy["spotkania"].median(),
        "udzial_D200": grupy["duze_D"].mean(),
        "bierni_wsrod_D200": t[t["duze_D"]].groupby(["seria", "alfa"])["bierny"].mean(),
        "spotkania_na_D": grupy["spotkania"].sum() / grupy["D"].sum(),
    })
    return wynik.reset_index()


def wczytaj_dylematy(katalog: Path, przebiegi: list[str]) -> pd.DataFrame:
    """Potrzebne kolumny dylematy.csv z opisem przebiegu (przebieg, seria, alfa, ziarno)."""
    tabele = []
    for nazwa in przebiegi:
        d = pd.read_csv(katalog / nazwa / "dylematy.csv", usecols=KOLUMNY)
        _dopisz_opis_przebiegu(d, katalog / nazwa, _wczytaj_konfiguracje(katalog / nazwa))
        tabele.append(d)
    return pd.concat(tabele, ignore_index=True)


def koszty_kradziezy(katalog: Path, przebiegi: list[str]) -> tuple[float, float, float]:
    """(p, x, c_k) – muszą być takie same we wszystkich przebiegach."""
    wartosci = {
        nazwa: tuple(_wczytaj_konfiguracje(katalog / nazwa)["koszty"][k] for k in ("p", "x", "c_k"))
        for nazwa in przebiegi
    }
    if len(set(wartosci.values())) != 1:
        raise ValueError(f"Różne p, x, c_k w przebiegach: {wartosci}")
    return next(iter(wartosci.values()))


def utworz_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m analiza.oplacalnosc_kradziezy",
        description="Opłacalność kradzieży i bierne dylematy w danych pilotażu.",
    )
    parser.add_argument("katalog", type=Path, help="katalog z podkatalogami przebiegów")
    parser.add_argument("--serie", nargs="+", default=["P1", "P2"], help="serie do wczytania")
    parser.add_argument("--wyjscie", type=Path, default=Path("wyniki/analiza/oplacalnosc"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Liczy obie tabele, wypisuje je i zapisuje jako oplacalnosc.csv i spotkania.csv."""
    arg = utworz_parser().parse_args(argv)
    arg.wyjscie.mkdir(parents=True, exist_ok=True)
    przebiegi = [
        k.name for k in sorted(arg.katalog.iterdir()) if k.is_dir() and k.name.split("_")[0] in arg.serie
    ]
    if not przebiegi:
        raise ValueError(f"Brak przebiegów serii {arg.serie} w {arg.katalog}")
    p, x, c_k = koszty_kradziezy(arg.katalog, przebiegi)
    dylematy = wczytaj_dylematy(arg.katalog, przebiegi)

    oplacalnosc = podsumuj_oplacalnosc(dylematy, p, x, c_k)
    opis = dylematy[["przebieg", "seria", "alfa"]].drop_duplicates()
    tabela_spotkan = podsumuj_spotkania(spotkania(dylematy).merge(opis, on="przebieg"))

    print(f"Przebiegi: {len(przebiegi)}, dylematy: {len(dylematy)}; p = {p}, x = {x}, c_k = {c_k}")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("\nOpłacalność kradzieży (odsetek dylematów z ujemnym oczekiwanym zyskiem):")
        print(oplacalnosc.round(4).to_string(index=False))
        print(f"\nSpotkania (agenci z D ≥ 1; „bierni” = D ≥ {PROG_DUZEGO_D} przy ≤ 2 spotkaniach):")
        print(tabela_spotkan.round(4).to_string(index=False))
    oplacalnosc.to_csv(arg.wyjscie / "oplacalnosc.csv", index=False, float_format="%.4f")
    tabela_spotkan.to_csv(arg.wyjscie / "spotkania.csv", index=False, float_format="%.4f")
    print(f"\nWyniki: {arg.wyjscie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

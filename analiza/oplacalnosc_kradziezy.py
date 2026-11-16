"""Opłacalność kradzieży i ciągi dylematów w danych pilotażu (Lab03, decyzja #21).

Liczone z dylematy.csv, bez nowej symulacji: (1) w ilu dylematach hipotetyczny oczekiwany
zysk z kradzieży p·min(x, zasoby_celu) − c_k był ujemny; (2) ile ciągów dylematów wobec tego
samego celu kryje się za liczbą dylematów D i jak często agenci z dużym D wybierali akcję obojętną.
Argument to lokalny katalog z wynikami przebiegów P1–P2 (dane spoza repozytorium), np.:
    PYTHONPATH=src python -m analiza.oplacalnosc_kradziezy lokalne/wyniki_pilotazu --serie P1 P2
"""
import argparse
from pathlib import Path

import pandas as pd

from analiza.eksploracja import _dopisz_opis_przebiegu, _wczytaj_konfiguracje

KOLUMNY = ["pokolenie", "krok", "id", "id_celu", "zasoby_celu", "klasa"]
KLUCZ_AGENTA = ["przebieg", "pokolenie", "id"]
GRUPA = ["seria", "alfa"]
PROG_DUZEGO_D = 200  # Lab02: 14–20 % agentów z D > 200 przy α ≥ 1


def oczekiwany_zysk(zasoby_celu: pd.Series, p: float, x: float, c_k: float) -> pd.Series:
    """Hipotetyczny oczekiwany zysk p · min(x, zasoby_celu) − c_k (D5) przy zasobach celu z migawki
    na początku kroku – przed akcjami innych agentów, więc nie zysk faktycznie wykonanej kradzieży."""
    return zasoby_celu.clip(upper=x) * p - c_k


def podsumuj_oplacalnosc(dylematy: pd.DataFrame, p: float, x: float, c_k: float) -> pd.DataFrame:
    """Wiersz = (seria, alfa): odsetki dylematów z ujemnym zyskiem łącznie dla ziaren (ważone liczbą
    dylematów) – ogółem, w kradzieżach, w dzieleniach – i zakres odsetka ogółem w przebiegach."""
    d = dylematy.assign(ujemny=oczekiwany_zysk(dylematy["zasoby_celu"], p, x, c_k) < 0)
    grupy = d.groupby(GRUPA)
    kradziez, dzielenie = d["klasa"].eq("kradziez"), d["klasa"].eq("dzielenie")
    w_przebiegach = d.groupby([*GRUPA, "przebieg"])["ujemny"].mean().groupby(GRUPA)
    wynik = pd.DataFrame({
        "przebiegi": w_przebiegach.size(),
        "n": grupy.size(),
        "ujemny_zysk": grupy["ujemny"].mean(),
        "ujemny_zysk_min": w_przebiegach.min(),
        "ujemny_zysk_max": w_przebiegach.max(),
        "n_kradziezy": kradziez.groupby([d["seria"], d["alfa"]]).sum(),
        "ujemny_wsrod_kradziezy": d[kradziez].groupby(GRUPA)["ujemny"].mean(),
        "n_dzielen": dzielenie.groupby([d["seria"], d["alfa"]]).sum(),
        "ujemny_wsrod_dzielen": d[dzielenie].groupby(GRUPA)["ujemny"].mean(),
    })
    return wynik.reset_index()


def ciagi_dylematow(dylematy: pd.DataFrame) -> pd.DataFrame:
    """Na (przebieg, pokolenie, id): D, akcje obojętne, ciągi (kolejne kroki z zapisanym dylematem
    wobec tego samego celu) i najdłuższy ciąg. Krok bez dylematu przerywa ciąg, więc ciąg to nie
    całe fizyczne spotkanie: cel mógł stać dalej, ale bez spełnionych warunków dylematu."""
    d = dylematy.sort_values([*KLUCZ_AGENTA, "krok"])[[*KLUCZ_AGENTA, "krok", "id_celu", "klasa"]]
    g = d.groupby(KLUCZ_AGENTA, sort=False)
    # nowy ciąg: inny cel albo przerwa w krokach; pierwszy wiersz grupy (NaN po shift) zawsze
    nowy = (g["id_celu"].shift() != d["id_celu"]) | (g["krok"].shift() + 1 != d["krok"])
    klucz = [d[k] for k in KLUCZ_AGENTA]
    numer = nowy.groupby(klucz, sort=False).cumsum().rename("ciag")
    dlugosci = d.groupby([*klucz, numer], sort=False).size()
    wynik = dlugosci.groupby(level=KLUCZ_AGENTA, sort=False).agg(D="sum", ciagi="size", najdluzszy="max")
    wynik["obojetne"] = d["klasa"].eq("obojetna").groupby(klucz, sort=False).sum()
    return wynik.reset_index()


def podsumuj_ciagi(tabela: pd.DataFrame) -> pd.DataFrame:
    """Wiersz = (seria, alfa); agenci z D ≥ 1. Wśród agentów z D ≥ 200: udział z najwyżej 2 ciągami
    (długie powtarzanie dylematu) i średni udział akcji obojętnych (bierność); bez takich agentów NaN."""
    duze = tabela["D"] >= PROG_DUZEGO_D
    t = tabela.assign(
        duze_D=duze,
        dlugie_ciagi=duze & (tabela["ciagi"] <= 2),
        udzial_obojetnych=tabela["obojetne"] / tabela["D"],
    )
    grupy, duze_grupy = t.groupby(GRUPA), t[duze].groupby(GRUPA)
    wynik = pd.DataFrame({
        "agenci": grupy.size(),
        "mediana_D": grupy["D"].median(),
        "mediana_ciagow": grupy["ciagi"].median(),
        "udzial_D200": grupy["duze_D"].mean(),
        "dlugie_ciagi_wsrod_D200": duze_grupy["dlugie_ciagi"].mean(),
        "obojetne_wsrod_D200": duze_grupy["udzial_obojetnych"].mean(),
        "ciagi_na_D": grupy["ciagi"].sum() / grupy["D"].sum(),
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
        description="Opłacalność kradzieży i ciągi dylematów w danych pilotażu.",
    )
    parser.add_argument("katalog", type=Path, help="lokalny katalog z podkatalogami przebiegów P1–P2")
    parser.add_argument("--serie", nargs="+", default=["P1", "P2"], help="serie do wczytania")
    parser.add_argument("--wyjscie", type=Path, default=Path("wyniki/analiza/oplacalnosc"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """Liczy obie tabele, wypisuje je i zapisuje jako oplacalnosc.csv i ciagi_dylematow.csv."""
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
    tabela_ciagow = podsumuj_ciagi(ciagi_dylematow(dylematy).merge(opis, on="przebieg"))

    print(f"Przebiegi: {len(przebiegi)}, dylematy: {len(dylematy)}; p = {p}, x = {x}, c_k = {c_k}")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("\nOpłacalność kradzieży (odsetek dylematów z ujemnym oczekiwanym zyskiem; min–max w przebiegach):")
        print(oplacalnosc.round(4).to_string(index=False))
        print(f"\nCiągi dylematów (agenci z D ≥ 1; wśród D ≥ {PROG_DUZEGO_D}: udział z ≤ 2 ciągami"
              " i średni udział akcji obojętnych):")
        print(tabela_ciagow.round(4).to_string(index=False))
    oplacalnosc.to_csv(arg.wyjscie / "oplacalnosc.csv", index=False, float_format="%.4f")
    tabela_ciagow.to_csv(arg.wyjscie / "ciagi_dylematow.csv", index=False, float_format="%.4f")
    print(f"\nWyniki: {arg.wyjscie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

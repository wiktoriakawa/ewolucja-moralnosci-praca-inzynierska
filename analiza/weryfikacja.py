"""Końcowa weryfikacja wydajności i powtarzalności konfiguracji KM3."""

import argparse
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analiza.jakosc import analizuj, porownaj_przebiegi
from moralnosc.seria import wykonaj_serie, wczytaj_serie


LIMIT_CZASU_S = 30 * 60
LIMIT_RAM_B = 8 * 1024**3
LIMIT_DANYCH_B = 1024**3


class BladWeryfikacji(RuntimeError):
    """Błąd uniemożliwiający wykonanie pełnej weryfikacji KM3."""


def _rozmiar_katalogu(katalog: Path) -> int:
    """Zwraca łączny rozmiar zwykłych plików znajdujących się w katalogu."""
    return sum(plik.stat().st_size for plik in katalog.rglob("*") if plik.is_file())


def _calkowita_pamiec_b() -> int | None:
    """Zwraca ilość pamięci operacyjnej komputera, jeśli można ją odczytać."""
    if sys.platform == "win32":
        class StanPamieci(ctypes.Structure):
            _fields_ = [
                ("dlugosc", ctypes.c_ulong),
                ("obciazenie", ctypes.c_ulong),
                ("fizyczna_calkowita", ctypes.c_ulonglong),
                ("fizyczna_dostepna", ctypes.c_ulonglong),
                ("stronicowana_calkowita", ctypes.c_ulonglong),
                ("stronicowana_dostepna", ctypes.c_ulonglong),
                ("wirtualna_calkowita", ctypes.c_ulonglong),
                ("wirtualna_dostepna", ctypes.c_ulonglong),
                ("rozszerzona_dostepna", ctypes.c_ulonglong),
            ]

        stan = StanPamieci()
        stan.dlugosc = ctypes.sizeof(StanPamieci)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stan)):
            return int(stan.fizyczna_calkowita)
        return None

    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _szczytowa_pamiec_procesu_b() -> int | None:
    """Zwraca szczytowy rozmiar pamięci procesu od chwili jego uruchomienia."""
    if sys.platform == "win32":
        class LicznikiProcesu(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        liczniki = LicznikiProcesu()
        liczniki.cb = ctypes.sizeof(LicznikiProcesu)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(LicznikiProcesu),
            ctypes.c_ulong,
        )
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        uchwyt = kernel32.GetCurrentProcess()
        sukces = psapi.GetProcessMemoryInfo(
            uchwyt,
            ctypes.byref(liczniki),
            liczniki.cb,
        )
        return int(liczniki.PeakWorkingSetSize) if sukces else None

    try:
        import resource

        maksimum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mnoznik = 1 if sys.platform == "darwin" else 1024
        return int(maksimum * mnoznik)
    except (ImportError, OSError, ValueError):
        return None


def _srodowisko() -> dict[str, object]:
    """Zbiera informacje potrzebne do opisania warunków pomiaru."""
    return {
        "platforma": platform.platform(),
        "procesor": platform.processor() or "nieznany",
        "architektura": platform.machine(),
        "logiczne_cpu": os.cpu_count(),
        "ram_b": _calkowita_pamiec_b(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }


def _zapisz_tabele(podsumowanie: pd.DataFrame, katalog: Path) -> None:
    """Zapisuje podsumowanie przebiegów w CSV i w prostej tabeli LaTeX."""
    podsumowanie.to_csv(katalog / "K5_podsumowanie.csv", index=False)
    wiersze = [
        " & ".join(
            (
                str(wiersz.id).replace("_", r"\_"),
                str(wiersz.ziarno),
                str(wiersz.pokolenia),
                str(wiersz.zywi_koniec),
                f"{wiersz.czas_s:.3f}",
                f"{wiersz.rozmiar_MB:.1f}",
                "OK" if wiersz.kontrola_jakosci else "BŁĄD",
            )
        )
        + r" \\"
        for wiersz in podsumowanie.itertuples(index=False)
    ]
    (katalog / "K5_podsumowanie.tex").write_text(
        "\n".join(
            (
                r"\begin{tabular}{lrrrrrl}",
                r"\toprule",
                r"Przebieg & ziarno & pokolenia & żywi & czas [s] & dane [MB] & jakość \\",
                r"\midrule",
                *wiersze,
                r"\bottomrule",
                r"\end{tabular}",
                "",
            )
        ),
        encoding="utf-8",
    )


def _zapisz_wykres(katalog_przebiegu: Path, katalog_wyjscia: Path) -> None:
    """Tworzy wykres przeżywalności i różnorodności dla przebiegu K5."""
    pokolenia = pd.read_csv(katalog_przebiegu / "pokolenia.csv")
    fig, osie = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    osie[0].plot(pokolenia["pokolenie"], pokolenia["przezywalnosc"])
    osie[0].set_ylabel("Przeżywalność")
    osie[1].plot(pokolenia["pokolenie"], pokolenia["roznorodnosc"])
    osie[1].set_ylabel("Różnorodność")
    osie[1].set_xlabel("Pokolenie")
    for os_wykresu in osie:
        os_wykresu.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(katalog_wyjscia / "K5_przebieg.pdf")
    plt.close(fig)


def wykonaj_weryfikacje(
    definicja_toml: str | Path,
    katalog_analizy: str | Path,
) -> bool:
    """Uruchamia K5, kontroluje wyniki i zapisuje kompletne podsumowanie."""
    definicja = wczytaj_serie(definicja_toml)
    katalog_analizy = Path(katalog_analizy)
    katalog_analizy.mkdir(parents=True, exist_ok=True)
    rozpoczecie = datetime.now().astimezone()

    poczatek_serii = perf_counter()
    statusy = wykonaj_serie(definicja)
    czas_serii_s = perf_counter() - poczatek_serii
    zakonczone = [status for status in statusy if status["status"] == "zakonczony"]
    if len(zakonczone) != 2 or len(zakonczone) != len(statusy):
        raise BladWeryfikacji(
            "K5 wymaga dokładnie dwóch nowo zakończonych przebiegów; "
            "sprawdź status.csv i puste katalogi wynikowe"
        )

    katalogi = [Path(status["katalog"]) for status in zakonczone]
    poprawny_a = analizuj(
        katalogi[0],
        katalog_analizy / zakonczone[0]["id"],
        katalog_porownania=katalogi[1],
    )
    poprawny_b = analizuj(
        katalogi[1],
        katalog_analizy / zakonczone[1]["id"],
    )
    powtarzalnosc = all(
        wynik["poprawna"] for wynik in porownaj_przebiegi(katalogi[0], katalogi[1])
    )

    wiersze = []
    rozmiary = []
    for numer, (status, katalog) in enumerate(zip(zakonczone, katalogi)):
        pokolenia = pd.read_csv(katalog / "pokolenia.csv")
        rozmiar_b = _rozmiar_katalogu(katalog)
        rozmiary.append(rozmiar_b)
        wiersze.append(
            {
                "id": status["id"],
                "ziarno": status["ziarno"],
                "pokolenia": len(pokolenia),
                "zywi_koniec": int(pokolenia.iloc[-1]["zywi_koniec"]),
                "czas_s": float(status["czas_s"]),
                "rozmiar_MB": rozmiar_b / 10**6,
                "kontrola_jakosci": (poprawny_a, poprawny_b)[numer],
            }
        )

    podsumowanie = pd.DataFrame(wiersze)
    _zapisz_tabele(podsumowanie, katalog_analizy)
    _zapisz_wykres(katalogi[0], katalog_analizy)

    szczyt_ram_b = _szczytowa_pamiec_procesu_b()
    nf06 = bool((podsumowanie["czas_s"] <= LIMIT_CZASU_S).all())
    nf07_dane = all(rozmiar <= LIMIT_DANYCH_B for rozmiar in rozmiary)
    nf07_ram = szczyt_ram_b is not None and szczyt_ram_b <= LIMIT_RAM_B
    poprawna = (
        poprawny_a
        and poprawny_b
        and powtarzalnosc
        and nf06
        and nf07_dane
        and nf07_ram
    )
    metadane = {
        "seria": definicja.nazwa,
        "rozpoczecie": rozpoczecie.isoformat(),
        "zakonczenie": datetime.now().astimezone().isoformat(),
        "czas_serii_s": round(czas_serii_s, 3),
        "szczyt_ram_b": szczyt_ram_b,
        "rozmiar_danych_b": sum(rozmiary),
        "limity": {
            "NF-06_czas": nf06,
            "NF-07_RAM": nf07_ram,
            "NF-07_dane": nf07_dane,
        },
        "kontrola_jakosci": poprawny_a and poprawny_b,
        "powtarzalnosc_NF-03": powtarzalnosc,
        "srodowisko": _srodowisko(),
    }
    (katalog_analizy / "K5_weryfikacja.json").write_text(
        json.dumps(metadane, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return poprawna


def main(argv: list[str] | None = None) -> int:
    """Obsługuje końcową weryfikację KM3 z wiersza poleceń."""
    for strumien in (sys.stdout, sys.stderr):
        ustaw_kodowanie = getattr(strumien, "reconfigure", None)
        if ustaw_kodowanie is not None:
            ustaw_kodowanie(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Uruchom K5 i sprawdź wydajność, jakość oraz powtarzalność."
    )
    parser.add_argument(
        "definicja",
        type=Path,
        nargs="?",
        default=Path("konfiguracje/kalibracja/K5.toml"),
    )
    parser.add_argument(
        "--wyjscie",
        type=Path,
        default=Path("wyniki/analiza/K5"),
    )
    argumenty = parser.parse_args(argv)
    try:
        poprawna = wykonaj_weryfikacje(argumenty.definicja, argumenty.wyjscie)
    except (BladWeryfikacji, OSError, ValueError) as blad:
        print(f"Weryfikacja K5 nie powiodła się: {blad}", file=sys.stderr)
        return 2
    print(f"Podsumowanie zapisano w: {argumenty.wyjscie}")
    print("Weryfikacja KM3: " + ("OK" if poprawna else "BLEDY"))
    return 0 if poprawna else 1


if __name__ == "__main__":
    raise SystemExit(main())

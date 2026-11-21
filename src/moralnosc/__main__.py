"""Interfejs wiersza poleceń pakietu moralnosc."""

import argparse
from pathlib import Path
import sys

from moralnosc.konfiguracja import BladKonfiguracji, wczytaj_konfiguracje
from moralnosc.petla import uruchom_przebieg
from moralnosc.seria import BladSerii, wykonaj_serie, wczytaj_serie
from moralnosc.zapis import przygotuj_zapis


def utworz_parser() -> argparse.ArgumentParser:
    """Tworzy parser poleceń programu."""
    parser = argparse.ArgumentParser(prog="python -m moralnosc")
    podpolecenia = parser.add_subparsers(dest="polecenie", required=True)

    przebieg = podpolecenia.add_parser(
        "przebieg",
        help="uruchom jeden przebieg na podstawie pliku TOML",
    )
    przebieg.add_argument("konfiguracja", type=Path, help="sciezka do pliku TOML")
    przebieg.add_argument(
        "--animuj-pokolenia", type=int, nargs="+", metavar="N",
        help="numery pokoleń do zapisania jako GIF (od 0)",
    )
    przebieg.add_argument(
        "--fps", type=int, metavar="N",
        help="tempo odtwarzania GIF-a, od 1 do 100 klatek/s (domyślnie 20)",
    )

    seria = podpolecenia.add_parser(
        "seria",
        help="uruchom serię wariantów i ziaren na podstawie pliku TOML",
    )
    seria.add_argument("definicja", type=Path, help="sciezka do definicji serii TOML")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Obsługuje argumenty, uruchamia przebieg i zapisuje jego wyniki."""
    argumenty = utworz_parser().parse_args(argv)

    if argumenty.polecenie == "seria":
        try:
            definicja = wczytaj_serie(argumenty.definicja)
            statusy = wykonaj_serie(definicja)
        except (BladSerii, BladKonfiguracji, OSError) as blad:
            print(f"Blad serii: {blad}", file=sys.stderr)
            return 2

        for status in statusy:
            komunikat = f"{status['id']}: {status['status']}"
            if status["blad"]:
                komunikat += f" ({status['blad']})"
            print(komunikat)
        return 1 if any(status["status"] == "blad" for status in statusy) else 0

    try:
        cfg = wczytaj_konfiguracje(argumenty.konfiguracja)
    except (BladKonfiguracji, OSError) as blad:
        print(f"Blad konfiguracji: {blad}", file=sys.stderr)
        return 2

    katalog = Path(cfg["zapis"]["katalog"])
    pokolenia = set(argumenty.animuj_pokolenia or [])
    nagranie = None
    if argumenty.fps is not None and not pokolenia:
        print("Opcja --fps wymaga --animuj-pokolenia.", file=sys.stderr)
        return 2

    try:
        if pokolenia:
            from moralnosc.animacja import NagraniePokolen

            ostatnie = cfg["przebieg"]["pokolenia"] - 1
            if not all(0 <= p <= ostatnie for p in pokolenia):
                raise ValueError(f"Numery nagrywanych pokoleń muszą być w zakresie 0–{ostatnie}.")
            if katalog.exists() and (not katalog.is_dir() or any(katalog.iterdir())):
                raise ValueError("Przebieg z animacją wymaga nowego lub pustego katalogu wyników.")
            fps = 20 if argumenty.fps is None else argumenty.fps
            nagranie = NagraniePokolen(katalog / "animacje", pokolenia, fps=fps)
    except (ValueError, OSError) as blad:
        print(f"Błąd ustawień animacji: {blad}", file=sys.stderr)
        return 2

    try:
        callback = przygotuj_zapis(cfg)

        def po_pokoleniu(stan, pomiar, maska, awaryjny):
            callback(stan, pomiar, maska, awaryjny)
            sciezka = nagranie.zapisz_gif(stan)
            if sciezka is not None:
                print(f"Zapisano GIF: {sciezka}")

        stan = uruchom_przebieg(
            cfg,
            po_pokoleniu=po_pokoleniu if nagranie is not None else callback,
            po_klatce=nagranie.zapamietaj_klatke if nagranie is not None else None,
        )
    except OSError as blad:
        print(f"Błąd zapisu wyników: {blad}", file=sys.stderr)
        return 2

    nieosiagniete = sorted(p for p in pokolenia if p > stan.pokolenie)
    if nieosiagniete:
        print(f"Wymarcie populacji: pominięto animacje pokoleń {nieosiagniete}.")

    print(f"Zakonczono przebieg na pokoleniu {stan.pokolenie}.")
    print(f"Wyniki zapisano w: {cfg['zapis']['katalog']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

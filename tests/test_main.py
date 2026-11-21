"""Test interfejsu uruchamiania przebiegu z pliku konfiguracyjnego."""

import json

from PIL import Image
import pytest

from moralnosc import __main__ as cli
from moralnosc.konfiguracja import BladKonfiguracji


main = cli.main


def _utworz_toml(konfiguracja, katalog_wynikow, *, pokolenia=2, koszt_zycia=0.1):
    konfiguracja.write_text(
        f"""
[przebieg]
ziarno = 67
pokolenia = {pokolenia}
kroki = 2

[plansza]
H = 2
W = 2

[populacja]
N = 2

[zasoby]
c_min = 1.0
c_max = 2.0
alfa = 1.0

[obserwacje]
skala = 2.0

[koszty]
m = {koszt_zycia}
ruch = 0.0
s = 1.0
c_k = 0.5
p = 1.0
x = 1.0

[siec]
tryb = "argmax"
tau = 1.0
h = 0

[ewolucja]
T = 0.0
E0 = 100.0
r = 0.0
sigma = 0.0
w_max = 4.0
R = 1

[zapis]
katalog = "{katalog_wynikow.as_posix()}"
""".strip(),
        encoding="utf-8",
    )


def test_main_uruchamia_przebieg_i_zapisuje_wyniki(tmp_path):
    """Polecenie przebieg tworzy JSON i trzy pliki CSV."""
    katalog_wynikow = tmp_path / "wyniki"
    konfiguracja = tmp_path / "test.toml"
    _utworz_toml(konfiguracja, katalog_wynikow)

    kod_wyjscia = main(["przebieg", str(konfiguracja)])

    assert kod_wyjscia == 0
    assert {sciezka.name for sciezka in katalog_wynikow.iterdir()} == {
        "konfiguracja.json",
        "pokolenia.csv",
        "agenci.csv",
        "dylematy.csv",
    }
    with (katalog_wynikow / "konfiguracja.json").open(encoding="utf-8") as plik:
        zapisana_konfiguracja = json.load(plik)["konfiguracja"]
    assert zapisana_konfiguracja["przebieg"]["ziarno"] == 67
    assert zapisana_konfiguracja["przebieg"]["pokolenia"] == 2


def test_animacja_zapisuje_wybrane_pokolenia_bez_zmian_w_csv(tmp_path):
    zwykly = tmp_path / "zwykly"
    nagrany = tmp_path / "nagrany"
    konfiguracja = tmp_path / "test.toml"
    _utworz_toml(konfiguracja, zwykly, pokolenia=3)
    assert main(["przebieg", str(konfiguracja)]) == 0
    _utworz_toml(konfiguracja, nagrany, pokolenia=3)
    assert main(["przebieg", str(konfiguracja), "--animuj-pokolenia", "0", "2", "--fps", "10"]) == 0

    animacje = nagrany / "animacje"
    assert {plik.name for plik in animacje.iterdir()} == {"pokolenie_000.gif", "pokolenie_002.gif"}
    for plik in animacje.iterdir():
        with Image.open(plik) as gif:
            assert gif.n_frames == 3  # Stan początkowy oraz dwa pełne kroki.
            assert gif.info["duration"] == 100
    for nazwa in ("pokolenia.csv", "agenci.csv", "dylematy.csv"):
        assert (nagrany / nazwa).read_bytes() == (zwykly / nazwa).read_bytes()


def test_animacja_zapisuje_ostatni_krok_przy_wymarciu(tmp_path, capsys):
    katalog = tmp_path / "wyniki"
    konfiguracja = tmp_path / "test.toml"
    _utworz_toml(konfiguracja, katalog, koszt_zycia=1000.0)

    assert main(["przebieg", str(konfiguracja), "--animuj-pokolenia", "0", "1"]) == 0

    animacje = katalog / "animacje"
    assert {plik.name for plik in animacje.iterdir()} == {"pokolenie_000.gif"}
    assert "pominięto animacje pokoleń [1]" in capsys.readouterr().out
    with Image.open(animacje / "pokolenie_000.gif") as gif:
        assert gif.n_frames == 2  # Klatka początkowa i krok, w którym zginęli wszyscy.
        kolor_agenta = (14, 112, 114)
        assert kolor_agenta in {kolor for _, kolor in gif.convert("RGB").getcolors()}
        gif.seek(1)
        assert kolor_agenta not in {kolor for _, kolor in gif.convert("RGB").getcolors()}


@pytest.mark.parametrize("opcje", [
    ["--animuj-pokolenia", "2"],
    ["--animuj-pokolenia", "-1"],
    ["--animuj-pokolenia", "0", "--fps", "0"],
    ["--fps", "20"],
])
def test_bledne_ustawienia_animacji_nie_tworza_wynikow(tmp_path, opcje):
    katalog = tmp_path / "wyniki"
    konfiguracja = tmp_path / "test.toml"
    _utworz_toml(konfiguracja, katalog)

    assert main(["przebieg", str(konfiguracja), *opcje]) == 2
    assert not katalog.exists()


def test_main_czytelnie_konczy_program_dla_blednej_konfiguracji(
    tmp_path, monkeypatch, capsys
):
    """Błąd konfiguracji daje kod 2 i jedną wiadomość zamiast tracebacka."""
    def zglos_blad(_sciezka):
        raise BladKonfiguracji("siec.h: wartość musi być >= 0")

    monkeypatch.setattr(cli, "wczytaj_konfiguracje", zglos_blad)

    kod_wyjscia = main(["przebieg", str(tmp_path / "bledna.toml")])

    wynik = capsys.readouterr()
    assert kod_wyjscia == 2
    assert wynik.out == ""
    assert "siec.h" in wynik.err
    assert "Traceback" not in wynik.err


def test_main_uruchamia_serie_i_zwraca_blad_gdy_jeden_przebieg_sie_nie_udaje(
    tmp_path, monkeypatch, capsys
):
    """Polecenie seria raportuje wszystkie statusy i zwraca kod 1 po błędzie przebiegu."""
    definicja_toml = tmp_path / "seria.toml"
    definicja_toml.write_text(
        """
[seria]
nazwa = "test"
bazowa = "bazowa.toml"
katalog = "wyniki"
ziarna = [1]

[[warianty]]
nazwa = "wariant"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "wykonaj_serie",
        lambda _definicja: [
            {
                "id": "test_wariant_z1",
                "status": "blad",
                "blad": "RuntimeError: awaria",
            }
        ],
    )

    kod_wyjscia = main(["seria", str(definicja_toml)])

    wynik = capsys.readouterr()
    assert kod_wyjscia == 1
    assert "test_wariant_z1: blad" in wynik.out
    assert "RuntimeError: awaria" in wynik.out

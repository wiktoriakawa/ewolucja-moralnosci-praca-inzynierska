"""Testy końcowej weryfikacji konfiguracji referencyjnej KM3."""

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from analiza import weryfikacja


def _zapisz_przebieg(katalog: Path) -> None:
    """Tworzy minimalne dane pokoleń potrzebne podsumowaniu K5."""
    katalog.mkdir(parents=True)
    pd.DataFrame(
        {
            "pokolenie": [0, 1],
            "zywi_koniec": [2, 2],
            "przezywalnosc": [1.0, 1.0],
            "roznorodnosc": [1.0, 1.1],
        }
    ).to_csv(katalog / "pokolenia.csv", index=False)
    for nazwa in ("agenci.csv", "dylematy.csv"):
        (katalog / nazwa).write_text("kolumna\n", encoding="utf-8")


def test_wykonaj_weryfikacje_zapisuje_miary_tabele_i_wykres(tmp_path, monkeypatch):
    """Poprawne dwa przebiegi tworzą komplet materiałów końcowych K5."""
    katalog_a = tmp_path / "K5_a_z801"
    katalog_b = tmp_path / "K5_b_z801"
    katalog_analizy = tmp_path / "analiza"
    _zapisz_przebieg(katalog_a)
    _zapisz_przebieg(katalog_b)
    statusy = [
        {
            "id": "K5_a_z801",
            "wariant": "a",
            "ziarno": 801,
            "status": "zakonczony",
            "czas_s": 12.5,
            "katalog": str(katalog_a),
            "blad": "",
        },
        {
            "id": "K5_b_z801",
            "wariant": "b",
            "ziarno": 801,
            "status": "zakonczony",
            "czas_s": 12.7,
            "katalog": str(katalog_b),
            "blad": "",
        },
    ]
    monkeypatch.setattr(
        weryfikacja,
        "wczytaj_serie",
        lambda _sciezka: SimpleNamespace(nazwa="K5"),
    )
    monkeypatch.setattr(weryfikacja, "wykonaj_serie", lambda _definicja: statusy)
    monkeypatch.setattr(weryfikacja, "analizuj", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        weryfikacja,
        "porownaj_przebiegi",
        lambda *_args: [{"poprawna": True}],
    )
    monkeypatch.setattr(weryfikacja, "_szczytowa_pamiec_procesu_b", lambda: 10**8)
    monkeypatch.setattr(weryfikacja, "_srodowisko", lambda: {"python": "test"})

    poprawna = weryfikacja.wykonaj_weryfikacje("K5.toml", katalog_analizy)

    assert poprawna
    assert {
        "K5_podsumowanie.csv",
        "K5_podsumowanie.tex",
        "K5_przebieg.pdf",
        "K5_weryfikacja.json",
    }.issubset(plik.name for plik in katalog_analizy.iterdir())
    podsumowanie = pd.read_csv(katalog_analizy / "K5_podsumowanie.csv")
    assert podsumowanie["czas_s"].tolist() == [12.5, 12.7]
    metadane = json.loads(
        (katalog_analizy / "K5_weryfikacja.json").read_text(encoding="utf-8")
    )
    assert metadane["powtarzalnosc_NF-03"] is True
    assert metadane["limity"] == {
        "NF-06_czas": True,
        "NF-07_RAM": True,
        "NF-07_dane": True,
    }


def test_wykonaj_weryfikacje_odrzuca_niepelna_serie(tmp_path, monkeypatch):
    """Brak drugiego nowego przebiegu uniemożliwia sprawdzenie NF-03."""
    monkeypatch.setattr(
        weryfikacja,
        "wczytaj_serie",
        lambda _sciezka: SimpleNamespace(nazwa="K5"),
    )
    monkeypatch.setattr(
        weryfikacja,
        "wykonaj_serie",
        lambda _definicja: [
            {
                "id": "K5_a_z801",
                "status": "pominiety",
            }
        ],
    )

    try:
        weryfikacja.wykonaj_weryfikacje("K5.toml", tmp_path / "analiza")
    except weryfikacja.BladWeryfikacji as blad:
        assert "dokładnie dwóch" in str(blad)
    else:
        raise AssertionError("oczekiwano BladWeryfikacji")

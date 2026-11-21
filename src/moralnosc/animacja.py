"""Nagrywanie pozycji żywych agentów i eksport GIF-ów po pokoleniu."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont

from moralnosc.stan import Stan


# Obraz paletowy jest lżejszy od RGB przy składaniu setek klatek GIF-a.
TLO, PLANSZA, SIATKA, AGENT, TEKST, POMOCNICZY = range(6)
PALETA = [
    248, 250, 252,  # tło
    255, 255, 255,  # plansza
    223, 230, 238,  # siatka
    14, 112, 114,   # agenci
    25, 41, 59,     # tekst
    71, 91, 112,    # tekst pomocniczy
]


@dataclass(slots=True, frozen=True)
class Klatka:
    krok: int
    pozycje: NDArray[np.int64]


class NagraniePokolen:
    """Zachowuje klatki jednego pokolenia i zapisuje je do osobnego GIF-a."""

    def __init__(self, katalog: Path, pokolenia: set[int], *, fps: int = 20):
        if not 1 <= fps <= 100:
            raise ValueError("Tempo GIF-a musi mieć od 1 do 100 klatek na sekundę.")
        self.katalog = katalog
        self.pokolenia = frozenset(pokolenia)
        # W pliku GIF czas klatki ma dokładność do setnych sekundy.
        self.czas_klatki_ms = round(100 / fps) * 10
        self._klatki: list[Klatka] = []

    def zapamietaj_klatke(self, stan: Stan) -> None:
        """Zapisuje pozycje tylko w pokoleniach wybranych do nagrania."""
        if stan.pokolenie in self.pokolenia:
            # Filtrowanie maską żywych tworzy kopię. Kolejny krok zmienia
            # tablicę w Stanie, więc widok nadpisywałby wcześniejszą klatkę.
            pozycje = stan.pozycje[stan.zywy]
            self._klatki.append(Klatka(stan.krok, pozycje))

    def zapisz_gif(self, stan: Stan) -> Path | None:
        """Zapisuje klatki zakończonego pokolenia i zwalnia ich pamięć."""
        if stan.pokolenie not in self.pokolenia or not self._klatki:
            return None

        self.katalog.mkdir(parents=True, exist_ok=True)
        sciezka = self.katalog / f"pokolenie_{stan.pokolenie:03d}.gif"
        tlo, x0, y0, skala = _narysuj_plansze(*stan.zajetosc.shape)
        font_naglowka = ImageFont.load_default(size=21)
        font_podpisu = ImageFont.load_default(size=15)

        def narysuj(klatka: Klatka) -> Image.Image:
            obraz = tlo.copy()
            rysuj = ImageDraw.Draw(obraz)
            rysuj.text((20, 13), f"Pokolenie {stan.pokolenie}", fill=TEKST, font=font_naglowka)
            # Numer kroku odróżnia także klatki o tych samych pozycjach.
            rysuj.text(
                (21, 41),
                f"Krok {klatka.krok} / {stan.krok}   |   Agenci: {len(klatka.pozycje)}",
                fill=POMOCNICZY,
                font=font_podpisu,
            )
            promien = max(1, 0.37 * skala)
            for wiersz, kolumna in klatka.pozycje:
                x = x0 + (kolumna + 0.5) * skala
                y = y0 + (wiersz + 0.5) * skala
                rysuj.ellipse((x - promien, y - promien, x + promien, y + promien), fill=AGENT)
            return obraz

        with NamedTemporaryFile(dir=self.katalog, suffix=".tmp", delete=False) as plik:
            tymczasowa = Path(plik.name)
        try:
            narysuj(self._klatki[0]).save(
                tymczasowa,
                format="GIF",
                save_all=True,
                append_images=(narysuj(klatka) for klatka in self._klatki[1:]),
                duration=self.czas_klatki_ms,
                loop=0,
            )
            tymczasowa.replace(sciezka)
        finally:
            tymczasowa.unlink(missing_ok=True)
        self._klatki.clear()
        return sciezka


def _narysuj_plansze(H: int, W: int) -> tuple[Image.Image, float, float, float]:
    """Tworzy stałe tło i skalę wspólną dla obu osi planszy."""
    obszar_planszy = 448
    margines = 20
    obraz = Image.new("P", (obszar_planszy + 2 * margines, obszar_planszy + 82), TLO)
    obraz.putpalette(PALETA)
    skala = obszar_planszy / max(H, W)
    x0 = margines + (obszar_planszy - W * skala) / 2
    y0 = 62 + (obszar_planszy - H * skala) / 2
    x1 = x0 + W * skala
    y1 = y0 + H * skala
    rysuj = ImageDraw.Draw(obraz)
    rysuj.rectangle((x0, y0, x1, y1), fill=PLANSZA, outline=SIATKA)
    if skala >= 5:
        for wiersz in range(1, H):
            y = y0 + wiersz * skala
            rysuj.line((x0, y, x1, y), fill=SIATKA)
        for kolumna in range(1, W):
            x = x0 + kolumna * skala
            rysuj.line((x, y0, x, y1), fill=SIATKA)
    return obraz, x0, y0, skala

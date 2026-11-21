"""Test zapisu i rozmieszczenia agentów w kolejnych klatkach GIF-a."""

import numpy as np
from PIL import Image, ImageSequence

from moralnosc.animacja import NagraniePokolen
from moralnosc.stan import pusty_stan


def test_zapisane_klatki_pokazuja_ruch_agenta_w_odpowiednich_osiach(tmp_path):
    stan = pusty_stan(H=3, W=5, N=1, L=48)
    stan.zywy[:] = True
    stan.pozycje[0] = (1, 4)
    nagranie = NagraniePokolen(tmp_path, {0})
    nagranie.zapamietaj_klatke(stan)

    stan.krok = 1
    stan.pozycje[0] = (2, 0)
    nagranie.zapamietaj_klatke(stan)
    sciezka = nagranie.zapisz_gif(stan)

    with Image.open(sciezka) as gif:
        pozycje = []
        for klatka in ImageSequence.Iterator(gif):
            piksele = np.asarray(klatka.convert("RGB"))
            maska_agenta = np.all(piksele == (14, 112, 114), axis=-1)
            pozycje.append(np.argwhere(maska_agenta).mean(axis=0))

    (y0, x0), (y1, x1) = pozycje
    assert x1 < x0
    assert y1 > y0

#!/usr/bin/env python3
"""Recompresse les PNG des icones, sans perte.

CoreGraphics ecrit ses PNG sans filtre et le degrade ressort a ~110 Ko en
512x512. Un filtre PNG (sub, up, paeth) ramene le fichier a ~30 Ko. Le gain
vient du filtrage, pas de la compression : zlib fait le reste.

Usage (apres avoir genere les icones) :
    python3 deploiement/optimiser_png.py deploiement/pages/icones/*.png

Aucun pixel ne change : seuls la ligne de filtre et le niveau de compression
different. Le script choisit, pour chaque fichier, la strategie qui donne le
plus petit resultat (le filtre optimal depend du dessin).
"""
import struct
import sys
import zlib


def lire(chemin):
    d = open(chemin, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s : pas un PNG" % chemin)
    pos, idat, ihdr = 8, b"", None
    while pos < len(d):
        n = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        corps = d[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", corps)
        elif typ == b"IDAT":
            idat += corps
        pos += 12 + n
    return ihdr, zlib.decompress(idat)


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)


def defiltrer(brut, largeur, hauteur, canaux):
    pas = largeur * canaux
    lignes, pos, prec = [], 0, bytearray(pas)
    for _ in range(hauteur):
        f = brut[pos]
        ligne = bytearray(brut[pos + 1:pos + 1 + pas])
        pos += 1 + pas
        if f == 1:
            for i in range(canaux, pas):
                ligne[i] = (ligne[i] + ligne[i - canaux]) & 0xff
        elif f == 2:
            for i in range(pas):
                ligne[i] = (ligne[i] + prec[i]) & 0xff
        elif f == 3:
            for i in range(pas):
                gauche = ligne[i - canaux] if i >= canaux else 0
                ligne[i] = (ligne[i] + ((gauche + prec[i]) >> 1)) & 0xff
        elif f == 4:
            for i in range(pas):
                a = ligne[i - canaux] if i >= canaux else 0
                b = prec[i]
                c = prec[i - canaux] if i >= canaux else 0
                ligne[i] = (ligne[i] + paeth(a, b, c)) & 0xff
        elif f != 0:
            raise ValueError("filtre inconnu %d" % f)
        lignes.append(bytes(ligne))
        prec = ligne
    return lignes


def filtrer(lignes, canaux, filtre):
    """Applique un filtre unique a toutes les lignes (0, 1, 2 ou 4)."""
    if filtre == 0:
        return b"".join(b"\x00" + l for l in lignes)
    pas = len(lignes[0])
    prec = bytes(pas)
    sortie = bytearray()
    for ligne in lignes:
        if filtre == 1:
            sortie.append(1)
            sortie += bytes((ligne[i] - (ligne[i - canaux] if i >= canaux else 0)) & 0xff
                            for i in range(pas))
        elif filtre == 2:
            sortie.append(2)
            sortie += bytes((ligne[i] - prec[i]) & 0xff for i in range(pas))
        else:
            sortie.append(4)
            sortie += bytes((ligne[i] - paeth(ligne[i - canaux] if i >= canaux else 0,
                                              prec[i],
                                              prec[i - canaux] if i >= canaux else 0)) & 0xff
                            for i in range(pas))
        prec = ligne
    return bytes(sortie)


def ecrire(chemin, ihdr, corps):
    def bloc(t, c):
        return (struct.pack(">I", len(c)) + t + c
                + struct.pack(">I", zlib.crc32(t + c) & 0xffffffff))

    with open(chemin, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(bloc(b"IHDR", struct.pack(">IIBBBBB", *ihdr)))
        f.write(bloc(b"IDAT", corps))
        f.write(bloc(b"IEND", b""))


def optimiser(chemin):
    ihdr, donnees = lire(chemin)
    largeur, hauteur, profondeur, couleur, compression, filtrage, entrelacement = ihdr
    if profondeur != 8 or couleur not in (2, 6) or compression or filtrage or entrelacement:
        raise ValueError("%s : format PNG non prevu" % chemin)
    canaux = 3 if couleur == 2 else 4
    lignes = defiltrer(donnees, largeur, hauteur, canaux)

    avant = len(open(chemin, "rb").read())
    meilleur = None
    for filtre in (0, 1, 2, 4):
        corps = zlib.compress(filtrer(lignes, canaux, filtre), 9)
        if meilleur is None or len(corps) < len(meilleur):
            meilleur = corps
    ecrire(chemin, ihdr, meilleur)
    apres = len(open(chemin, "rb").read())
    print("%-26s %7d -> %6d octets" % (chemin.split("/")[-1], avant, apres))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage : optimiser_png.py fichier.png [...]")
    for chemin in sys.argv[1:]:
        optimiser(chemin)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suivi des matchs de plusieurs equipes d'un club (handball).

Principe :
  1. handapi.fr  -> decouverte du club, des equipes et de leurs poules (aucun ID en dur)
  2. ffhandball.fr -> lecture des pages poule + journee (donnees officielles, matchs joues
     ET matchs a venir)

Sortie :
  - affichage console : matchs joues / a venir par equipe
  - suivi_handball.csv : export complet
  - .suivi_handball_etat.json : etat precedent, pour signaler nouveaux matchs et
    nouveaux scores a chaque execution
"""

import csv
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ------------------------------------------------------------------ config

# Equipes suivies. La selection se fait sur le NOM DE LA COMPETITION
# (categorie + sexe), pas sur un identifiant.
EQUIPES_SUIVIES = [
    {"club": "Bonsecours", "categorie": "-13", "sexe": "M", "libelle": "U13M Bonsecours"},
    {"club": "Bonsecours", "categorie": "-15", "sexe": "M", "libelle": "U15M Bonsecours"},
    {"club": "Belbeuf", "categorie": "+16", "sexe": "F", "libelle": "SeniorF Belbeuf"},
]

SAISON = "saison-2026-2027-22"
FFHB = "https://www.ffhandball.fr/competitions/" + SAISON
HANDAPI = "https://api.handapi.fr"

DOSSIER = os.path.dirname(os.path.abspath(__file__))

# Dossier des fichiers PUBLIES (page, calendrier, json, csv, logos). Par defaut
# le dossier du script ; SUIVI_SORTIE permet de les ecrire directement dans la
# racine web d'un hebergement, le code et l'etat restant hors du domaine public.
SORTIE = os.path.abspath(os.environ.get("SUIVI_SORTIE") or DOSSIER)

FICHIER_CSV = os.path.join(SORTIE, "suivi_handball.csv")
FICHIER_JSON = os.path.join(SORTIE, "matchs.json")
FICHIER_ICS = os.path.join(SORTIE, "calendrier.ics")
FICHIER_HTML = os.path.join(SORTIE, "index.html")
FICHIER_ETAT = os.path.join(DOSSIER, ".suivi_handball_etat.json")
FICHIER_INDEX = os.path.join(DOSSIER, "ffhb_poules_index.json")
DOSSIER_LOGOS = os.path.join(SORTIE, "logos")

MAX_JOURNEES = 40
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ------------------------------------------------------------------ utils

def sans_accents(t):
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def slugifier(t):
    t = sans_accents(t).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def http_get(url, timeout=30):
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def http_get_safe(url, timeout=30):
    try:
        return http_get(url, timeout)
    except HTTPError as e:
        return None if e.code == 404 else None
    except (URLError, OSError):
        return None


def http_get_bytes(url, timeout=30):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


LOGOS = {}


def logo_local(fichier, taille=128):
    """Telecharge le logo FFHB dans logos/ (cache disque) et renvoie son chemin relatif.

    FFHB publie les logos sous la forme media-logos-clubs.ffhandball.fr/{taille}/{base}.webp
    ou {base} est le nom de fichier d'origine prive de son extension.
    """
    if not fichier:
        return None
    if fichier in LOGOS:
        return LOGOS[fichier]

    base = os.path.splitext(os.path.basename(str(fichier)))[0]
    nom = base + ".webp"
    chemin = os.path.join(DOSSIER_LOGOS, nom)
    rel = "logos/" + nom

    ok = os.path.exists(chemin) and os.path.getsize(chemin) > 0
    if not ok:
        try:
            data = http_get_bytes(f"https://media-logos-clubs.ffhandball.fr/{taille}/{base}.webp")
            os.makedirs(DOSSIER_LOGOS, exist_ok=True)
            with open(chemin, "wb") as f:
                f.write(data)
            ok = len(data) > 0
        except Exception:
            ok = False

    LOGOS[fichier] = rel if ok else None
    return LOGOS[fichier]


def handapi(path):
    return json.loads(http_get(HANDAPI + path, timeout=45))


# ------------------------------------------------------------------ ffhb

SMARTFIRE = re.compile(r"<smartfire-component name='([^']+)' attributes=\"([^\"]*)\"", re.DOTALL)


def composants(html):
    out = []
    for m in SMARTFIRE.finditer(html):
        b = m.group(2)
        for a, c in (("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
            b = b.replace(a, c)
        try:
            out.append((m.group(1), json.loads(b)))
        except Exception:
            continue
    return out


def composant(html, nom):
    for n, a in composants(html):
        if n == nom:
            return a
    return None


def rencontres_de(html):
    a = composant(html, "competitions---rencontre-list")
    return (a or {}).get("rencontres") or []


def equipes_de(html):
    a = composant(html, "competitions---poule-selector")
    if not a:
        return {}
    eqs = a.get("equipes") or a.get("equipe_options") or []
    return {e.get("id"): e.get("libelle") for e in eqs}


def classement_de(html):
    """Classement officiel publie par la poule (vide pour les coupes sans classement)."""
    a = composant(html, "competitions---mini-classement-or-ads")
    if not a:
        return []
    lignes = []
    for c in a.get("classements") or []:
        lignes.append({
            "place": c.get("place"),
            "equipe": c.get("equipe_libelle"),
            "points": c.get("point"),
            "joues": c.get("joue"),
            "gagnes": c.get("gagne"),
            "nuls": c.get("nul"),
            "perdus": c.get("perdu"),
            "buts_pour": c.get("butPlus"),
            "buts_contre": c.get("butMoins"),
            "difference": c.get("diff"),
            "structure_id": c.get("ext_structureId"),
            "logo": c.get("structure_logo") or None,
        })
    return lignes


def poule_id_de(html):
    a = composant(html, "competitions---journee-selector")
    if a:
        return str(a.get("ext_poule_id") or "")
    r = rencontres_de(html)
    if r:
        return str(r[0].get("extPouleId") or "")
    return ""


def numeros_journees(html):
    """Liste des journees declarees par la poule (evite les 404)."""
    a = composant(html, "competitions---journee-selector")
    if not a:
        return []
    brut = (a.get("poule") or {}).get("journees")
    if not brut:
        return []
    try:
        liste = json.loads(brut) if isinstance(brut, str) else brut
    except Exception:
        return []
    nums = []
    for j in liste:
        try:
            nums.append(int(j.get("journee_numero")))
        except (TypeError, ValueError):
            continue
    return sorted(set(nums))


# ------------------------------------------------------------------ resolution des URLs

_index_cache = None


def charger_index():
    """Cache local poule_id -> URL (issu des sitemaps FFHB)."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    if os.path.exists(FICHIER_INDEX):
        try:
            with open(FICHIER_INDEX, encoding="utf-8") as f:
                _index_cache = json.load(f)
                return _index_cache
        except Exception:
            pass
    _index_cache = {}
    return _index_cache


def construire_index(progress=None):
    """Telecharge l'index officiel des poules (sitemaps). Operation lourde, mise en cache."""
    global _index_cache
    print("  construction de l'index des poules FFHB (une seule fois, ~1 min)...")
    racine = http_get_safe("https://www.ffhandball.fr/sitemap_index.xml")
    if not racine:
        return {}
    sitemaps = re.findall(r"<loc>([^<]*competitions_poules-sitemap[^<]*)</loc>", racine)
    mapping = {}
    for i, sm in enumerate(sitemaps, 1):
        body = http_get_safe(sm, timeout=45) or ""
        for loc in re.findall(r"<loc>([^<]*)</loc>", body):
            m = re.search(r"/poule-(\d+)/?$", loc)
            if m:
                pid = m.group(1)
                if pid not in mapping or SAISON in loc:
                    mapping[pid] = loc
        if progress and i % 20 == 0:
            progress(i, len(sitemaps), len(mapping))
    _index_cache = mapping
    try:
        with open(FICHIER_INDEX, "w", encoding="utf-8") as f:
            json.dump(mapping, f)
    except Exception:
        pass
    return mapping


def resoudre_poule(poule_id, competition):
    """Retourne (url, html) de la page poule."""
    nom = competition.get("nom") or ""
    niveau = competition.get("niveau") or "departemental"
    cid = competition.get("id_ffhb") or ""
    slug = f"{slugifier(nom)}-{cid}"

    types = list(dict.fromkeys([niveau, "coupe-de-france"]))
    for typ in types:
        url = f"{FFHB}/{typ}/{slug}/poule-{poule_id}/"
        html = http_get_safe(url)
        if html and poule_id_de(html) == str(poule_id):
            return url, html

    # repli : index sitemaps (desactive par defaut : ~16 Mo sur disque)
    if os.environ.get("SUIVI_INDEX") != "1":
        return None, None

    index = charger_index()
    url = index.get(str(poule_id))
    if url:
        html = http_get_safe(url)
        if html and poule_id_de(html) == str(poule_id):
            return url, html

    index = construire_index(lambda i, n, c: print(f"    {i}/{n} sitemaps, {c} poules"))
    url = index.get(str(poule_id))
    if url:
        html = http_get_safe(url)
        if html and poule_id_de(html) == str(poule_id):
            return url, html
    return None, None


# ------------------------------------------------------------------ decoding des competitions

CATEGORIE_RE = re.compile(r"^\s*([+-])\s*(\d{1,2})\b")


def categorie_de(nom):
    m = CATEGORIE_RE.match(nom or "")
    if not m:
        return None
    return f"{m.group(1)}{int(m.group(2))}"


def sexe_de(nom):
    n = sans_accents(nom or "").upper()
    if "FEMININ" in n:
        return "F"
    if "MASCULIN" in n:
        return "M"
    return None


def competition_correspond(competition, cible):
    nom = competition.get("nom") or ""
    cat = categorie_de(nom)
    sexe = sexe_de(nom)

    attendu_cat = cible["categorie"]
    attendu_sexe = cible["sexe"]

    if sexe is not None and sexe != attendu_sexe:
        return False
    if attendu_sexe == "F" and sexe is None:
        return False

    if attendu_cat.startswith("+"):
        # senior : categorie +16 explicite, ou absence de categorie (coupes nationales)
        return cat is None or cat == attendu_cat
    return cat == attendu_cat


# ------------------------------------------------------------------ decouverte

def trouver_club(nom):
    cibles = handapi("/v1/clubs?q=" + nom.replace(" ", "+")).get("data", [])
    if not cibles:
        return None
    exact = [c for c in cibles if sans_accents(c.get("nom", "")).lower().find(sans_accents(nom).lower()) >= 0]
    pool = exact or cibles
    for c in pool:
        if c.get("ville") and sans_accents(c["ville"]).lower() == sans_accents(nom).lower():
            return c
    return pool[0]


def equipes_du_club(club_id):
    return handapi(f"/v1/clubs/{club_id}/equipes").get("data", [])


def poules_de_lequipe(equipe, cible):
    """Poules ou cette equipe est engagee, dans les competitions correspondant a la cible."""
    out = []
    for eng in equipe.get("engagements", []):
        comp = eng.get("competition") or {}
        poule = eng.get("poule") or {}
        if not competition_correspond(comp, cible):
            continue
        if not poule.get("id_ffhb"):
            continue
        out.append({
            "poule_id": str(poule["id_ffhb"]),
            "poule_nom": poule.get("nom"),
            "phase": (eng.get("phase") or {}).get("nom"),
            "phase_id": str((eng.get("phase") or {}).get("id_ffhb") or ""),
            "competition": comp,
        })
    return out


_COMPETITIONS = {}


def fiche_competition(competition_id):
    """Fiche handapi d'une competition (phases et poules), mise en cache."""
    cid = str(competition_id)
    if cid not in _COMPETITIONS:
        _COMPETITIONS[cid] = handapi(f"/v1/competitions/{cid}").get("data") or {}
    return _COMPETITIONS[cid]


def poules_de_competition(competition, phases_connues=()):
    """Tours suivants d'une competition de coupe (une phase = un tour = une poule).

    Les engagements renvoyes par handapi ne decrivent que la phase en cours :
    quand la federation publie le tour suivant, sa poule n'apparait nulle part
    dans les engagements. On lit donc la fiche de la competition et on ne garde
    que les phases posterieures a la derniere phase deja connue.

    L'expansion est reservee aux coupes : un championnat compte beaucoup de
    phases et de poules, la parcourir couterait des dizaines de pages.
    """
    nom = sans_accents(competition.get("nom") or "").upper()
    if "COUPE" not in nom:
        return []
    phases = fiche_competition(competition.get("id_ffhb")).get("phases") or []

    connues = {str(p) for p in phases_connues}
    dernier = -1
    for i, ph in enumerate(phases):
        if str(ph.get("id_ffhb")) in connues:
            dernier = i

    out = []
    for ph in phases[dernier + 1:]:
        for poule in ph.get("poules") or []:
            if not poule.get("id_ffhb"):
                continue
            out.append({
                "poule_id": str(poule["id_ffhb"]),
                "poule_nom": poule.get("nom"),
                "phase": ph.get("nom"),
                "competition": competition,
            })
    return out


# ------------------------------------------------------------------ scraping

def scraper_poule(poule_id, competition, etiquette, verbose=True):
    url, html_poule = resoudre_poule(poule_id, competition)
    if not html_poule:
        if verbose:
            print(f"    poule {poule_id} introuvable (URL non resolue)")
        return {"matchs": [], "classement": []}

    equipes = equipes_de(html_poule)
    nums = numeros_journees(html_poule)
    if not nums:
        nums = list(range(1, MAX_JOURNEES + 1))

    def garder(r):
        n1 = r.get("equipe1Libelle") or equipes.get(r.get("equipe1Id")) or ""
        n2 = r.get("equipe2Libelle") or equipes.get(r.get("equipe2Id")) or ""
        return etiquette in sans_accents(n1 + " " + n2).upper()

    trouves = {}
    nos_libelles = set()

    def ajouter(r):
        rid = str(r.get("ext_rencontreId") or r.get("id"))
        n1 = r.get("equipe1Libelle") or equipes.get(r.get("equipe1Id")) or "?"
        n2 = r.get("equipe2Libelle") or equipes.get(r.get("equipe2Id")) or "?"
        for n in (n1, n2):
            if etiquette in sans_accents(n).upper():
                nos_libelles.add(n)
        s1, s2 = r.get("equipe1Score"), r.get("equipe2Score")
        renseigne = s1 not in (None, "") and s2 not in (None, "")
        numerique = str(s1).isdigit() and str(s2).isdigit()
        joue = renseigne
        trouves[rid] = {
            "id": rid,
            "date": (r.get("date") or "")[:10],
            "heure": (r.get("date") or "")[11:16],
            "journee": str(r.get("journeeNumero") or ""),
            "domicile": n1,
            "exterieur": n2,
            "score_dom": s1 if joue else None,
            "score_ext": s2 if joue else None,
            "joue": joue,
            "score_valide": numerique,
            "competition": competition.get("nom"),
            "poule_id": poule_id,
            "poule": None,
            "url": url,
            # Code de la feuille de match electronique : sert a composer l URL
            # du PDF officiel (fdm.fdme.ffhandball.fr). Peut manquer.
            "fdm": r.get("fdmCode") or None,
            "logo_dom": r.get("structure1Logo") or None,
            "logo_ext": r.get("structure2Logo") or None,
        }

    for r in rencontres_de(html_poule):
        if garder(r):
            ajouter(r)

    lues, vides = 0, 0
    for j in nums:
        html_j = http_get_safe(url.rstrip("/") + f"/journee-{j}/")
        if not html_j:
            continue
        lues += 1
        ren = rencontres_de(html_j)
        if not ren:
            vides += 1
            if vides >= 2:
                break
            continue
        vides = 0
        for r in ren:
            if garder(r):
                ajouter(r)

    if verbose:
        print(f"    poule {poule_id} : {len(trouves)} match(s) ({lues} journee(s) lues)")
    return {
        "matchs": list(trouves.values()),
        "classement": classement_de(html_poule),
        "nos_equipes": sorted(nos_libelles),
        "url": url,
    }


def collecter():
    resultat = []
    for cible in EQUIPES_SUIVIES:
        print(f"\n=== {cible['libelle']} ===")
        club = trouver_club(cible["club"])
        if not club:
            print(f"  club '{cible['club']}' introuvable")
            continue
        cid = club.get("id_ffhb")
        if not club.get("logo_club"):
            club = {**club, **(handapi(f"/v1/clubs/{cid}").get("data") or {})}
        cible["_logo"] = club.get("logo_club")
        print(f"  club : {club.get('nom')} (id_ffhb={cid})")

        equipes = equipes_du_club(cid)
        poules, vus = [], set()
        equipes_retenues = []
        competitions = {}  # id_ffhb -> competition vue dans les engagements

        def retenir(p):
            if p["poule_id"] in vus:
                return False
            vus.add(p["poule_id"])
            poules.append(p)
            return True

        for eq in equipes:
            ps = poules_de_lequipe(eq, cible)
            if not ps:
                continue
            equipes_retenues.append(eq.get("nom"))
            for p in ps:
                retenir(p)
                comp = p["competition"]
                cle = str(comp.get("id_ffhb"))
                competitions.setdefault(cle, {"competition": comp, "phases": set()})
                if p.get("phase_id"):
                    competitions[cle]["phases"].add(p["phase_id"])

        # tours suivants des coupes : la poule du tour a venir n'est pas encore
        # listee dans les engagements de l'equipe
        for info in competitions.values():
            for p in poules_de_competition(info["competition"], info["phases"]):
                if retenir(p):
                    print(f"    + {p['phase']} / {p['poule_nom']}"
                          f" (poule {p['poule_id']})")

        if not poules:
            print("  aucune poule correspondante")
            continue

        # etiquette de filtrage : le nom d'equipe FFHB contient en general le nom du club
        etiquette = sans_accents(cible["club"]).upper()

        print(f"  equipes : {', '.join(sorted(set(equipes_retenues)))}")
        print(f"  {len(poules)} poule(s) :")
        for p in poules:
            print(f"    - {p['competition'].get('nom')} / {p['poule_nom']} (poule {p['poule_id']})")

        for p in poules:
            res = scraper_poule(p["poule_id"], p["competition"], etiquette)
            cible.setdefault("_classements", [])
            if res["classement"]:
                cible["_classements"].append({
                    "competition": p["competition"].get("nom"),
                    "phase": p.get("phase"),
                    "poule": p["poule_nom"],
                    "poule_id": p["poule_id"],
                    "url": res["url"],
                    "nos_equipes": res.get("nos_equipes", []),
                    "lignes": res["classement"],
                })
            for m in res["matchs"]:
                m["equipe"] = cible["libelle"]
                m["poule"] = p["poule_nom"]
                m["phase"] = p.get("phase")
                resultat.append(m)

    # deduplication globale
    vus, uniques = set(), []
    for m in resultat:
        cle = (m["equipe"], m["id"])
        if cle in vus:
            continue
        vus.add(cle)
        uniques.append(m)
    return uniques


# ------------------------------------------------------------------ affichage / export

def tri(m):
    return (m.get("date") or "9999-99-99", m.get("heure") or "")


def quand(m):
    if not m.get("date"):
        return "date a definir      "
    return f"{m['date']} {m['heure'] or '    '}"


def resultat(m):
    """Score officiel, ou code FFHB (FO = forfait, PE = penalite, ...)."""
    if not m.get("joue"):
        return "a jouer"
    return f"{m['score_dom']}-{m['score_ext']}"


def libelle_competition(m):
    comp = m.get("competition") or ""
    phase = (m.get("phase") or "").upper()
    if "PREPARATOIRE" in phase or "PREPA" in phase:
        return comp.replace("CHAMPIONNAT 76", "CHAMPIONNAT 76 / preparation").strip()
    return comp


def afficher(matchs):
    for cible in EQUIPES_SUIVIES:
        sel = sorted([m for m in matchs if m["equipe"] == cible["libelle"]], key=tri)
        joues = [m for m in sel if m["joue"]]
        avenir = [m for m in sel if not m["joue"]]

        print("\n" + "=" * 104)
        print(f"{cible['libelle'].upper()}  -  {len(joues)} joue(s), {len(avenir)} a venir")
        print("=" * 104)

        if not sel:
            print("  aucun match")
            continue

        print("  -- A VENIR --")
        if not avenir:
            print("     (aucun)")
        for m in avenir:
            print(f"  {quand(m)}  J{m['journee']:<2}  {m['domicile']} / {m['exterieur']:<34} [{libelle_competition(m)}]")

        print("  -- JOUES --")
        if not joues:
            print("     (aucun)")
        for m in joues:
            suffixe = "" if m.get("score_valide") else "   <-- code FFHB, pas un score"
            print(f"  {quand(m)}  J{m['journee']:<2}  {m['domicile']} / {m['exterieur']:<34} {resultat(m):<8} [{libelle_competition(m)}]{suffixe}")


def exporter_csv(matchs):
    cols = ["equipe", "date", "heure", "journee", "domicile", "exterieur",
            "score_dom", "score_ext", "score_valide", "joue",
            "competition", "poule", "phase", "id", "url"]
    with open(FICHIER_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for m in sorted(matchs, key=lambda x: (x["equipe"], tri(x))):
            w.writerow(m)
    print(f"\nCSV  : {FICHIER_CSV}")


# ------------------------------------------------------------------ sorties web

def exporter_json(matchs):
    """Contrat de donnees consomme par la page web, le calendrier et les alertes."""
    equipes = []
    for cible in EQUIPES_SUIVIES:
        sel = sorted([m for m in matchs if m["equipe"] == cible["libelle"]], key=tri)
        equipes.append({
            "libelle": cible["libelle"],
            "club": cible["club"],
            "categorie": cible["categorie"],
            "sexe": cible["sexe"],
            "logo": logo_local(cible.get("_logo")),
            "matchs": [
                {
                    "id": m["id"],
                    "date": m["date"],
                    "heure": m["heure"],
                    "journee": m["journee"],
                    "domicile": m["domicile"],
                    "exterieur": m["exterieur"],
                    "score_dom": m["score_dom"],
                    "score_ext": m["score_ext"],
                    "joue": m["joue"],
                    "score_valide": m.get("score_valide", True),
                    "competition": m["competition"],
                    "phase": m.get("phase"),
                    "poule": m.get("poule"),
                    "url": m["url"],
                    "fdm": m.get("fdm"),
                    "logo_dom": logo_local(m.get("logo_dom")),
                    "logo_ext": logo_local(m.get("logo_ext")),
                }
                for m in sel
            ],
            "classements": [
                dict(cl, lignes=[dict(l, logo=logo_local(l.get("logo"))) for l in cl["lignes"]])
                for cl in cible.get("_classements", [])
            ],
        })

    data = {
        "genere_le": datetime.now().astimezone().isoformat(timespec="seconds"),
        "equipes": equipes,
    }
    with open(FICHIER_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"JSON : {FICHIER_JSON}")
    return data


def echapper_ics(t):
    return (str(t or "")
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def exporter_ics(matchs):
    """Calendrier des matchs a venir, horaire inclus quand FFHB le publie."""
    from zoneinfo import ZoneInfo
    paris = ZoneInfo("Europe/Paris")

    def ligne_dt(m):
        d, h = m.get("date"), m.get("heure")
        if not d or not h:
            return None
        try:
            dt = datetime.strptime(f"{d} {h}", "%Y-%m-%d %H:%M").replace(tzinfo=paris)
        except ValueError:
            return None
        return dt.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")

    lignes = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Suivi Handball//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Handball - Bonsecours / Belbeuf",
        "X-WR-TIMEZONE:Europe/Paris",
        "X-WR-CALDESC:Matchs officiels FFHandball - Bonsecours / Belbeuf",
        # demande aux clients de re-interroger le flux (RFC 7986 + Google/Outlook)
        "REFRESH-INTERVAL;VALUE=DURATION:PT3H",
        "X-PUBLISHED-TTL:PT3H",
    ]
    stamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    for m in sorted(matchs, key=tri):
        dt = ligne_dt(m)
        if not dt:
            continue
        n += 1
        lignes += [
            "BEGIN:VEVENT",
            f"UID:{m['id']}@suivi-handball",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{dt}",
            "DURATION:PT1H30M",
            f"SUMMARY:{echapper_ics(m['domicile'] + ' - ' + m['exterieur'])}",
            f"DESCRIPTION:{echapper_ics((m.get('competition') or '') + ' / ' + (m.get('equipe') or ''))}",
            f"CATEGORIES:{echapper_ics(m.get('equipe') or '')}",
            "END:VEVENT",
        ]
    lignes.append("END:VCALENDAR")

    # newline="" : sans cela, Python traduit chaque "\n" en "\r\n" et les
    # lignes finissent en "\r\r\n", ce que certains clients de calendrier
    # refusent (RFC 5545 exige exactement CRLF).
    with open(FICHIER_ICS, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lignes) + "\r\n")
    print(f"ICS  : {FICHIER_ICS} ({n} evenement(s) date(s))")
    return n


def exporter_html(data):
    """Page autonome : aucun fichier externe, aucune execution serveur."""
    from vue_html import rendre_page

    page = rendre_page(data)
    with open(FICHIER_HTML, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"HTML : {FICHIER_HTML}")



def etat_et_alertes(matchs):
    ancien = {}
    if os.path.exists(FICHIER_ETAT):
        try:
            with open(FICHIER_ETAT, encoding="utf-8") as f:
                ancien = json.load(f)
        except Exception:
            ancien = {}

    nouveaux, maj = [], []
    for m in matchs:
        cle = f"{m['equipe']}|{m['id']}"
        memo = {"date": m["date"], "joue": m["joue"],
                "score_dom": m["score_dom"], "score_ext": m["score_ext"],
                "domicile": m["domicile"], "exterieur": m["exterieur"]}
        if cle not in ancien:
            nouveaux.append(m)
        else:
            a = ancien[cle]
            if (a.get("score_dom"), a.get("score_ext")) != (m["score_dom"], m["score_ext"]) and m["joue"]:
                maj.append(m)
        ancien[cle] = memo

    with open(FICHIER_ETAT, "w", encoding="utf-8") as f:
        json.dump(ancien, f, ensure_ascii=False, indent=1)

    print("\n" + "-" * 104)
    if nouveaux:
        print(f"NOUVEAU(X) MATCH(S) DEPUIS LA DERNIERE EXECUTION : {len(nouveaux)}")
        for m in sorted(nouveaux, key=tri):
            print(f"  + {m['equipe']:<22} {quand(m)}  {m['domicile']} / {m['exterieur']}  ({resultat(m)})")
    else:
        print("Aucun nouveau match depuis la derniere execution.")

    if maj:
        print(f"\nSCORE(S) MIS A JOUR : {len(maj)}")
        for m in sorted(maj, key=tri):
            print(f"  ~ {m['equipe']:<22} {quand(m)}  {m['domicile']} / {m['exterieur']}  -> {resultat(m)}")


def main():
    demarrer = datetime.now()
    os.makedirs(SORTIE, exist_ok=True)
    os.makedirs(DOSSIER_LOGOS, exist_ok=True)
    print("=" * 104)
    print(f"SUIVI HANDBALL - {demarrer:%d/%m/%Y %H:%M}")
    print("=" * 104)

    matchs = collecter()

    # Garde-fou : si ffhandball.fr ne repond plus correctement, mieux vaut ne
    # rien ecrire du tout que publier une page vide qui ecraserait la bonne.
    minimum = int(os.environ.get("SUIVI_MIN_MATCHS", "10"))
    if len(matchs) < minimum:
        print(f"\nCollecte interrompue : {len(matchs)} match(s) seulement "
              f"(minimum {minimum}).")
        print("Aucun fichier n'a ete ecrit, la version precedente reste en ligne.")
        return 3

    afficher(matchs)
    exporter_csv(matchs)
    data = exporter_json(matchs)
    exporter_ics(matchs)
    exporter_html(data)
    etat_et_alertes(matchs)

    print(f"\nTermine en {(datetime.now() - demarrer).total_seconds():.1f}s - "
          f"{len(matchs)} match(s) suivi(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

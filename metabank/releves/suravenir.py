"""Lecture des relevés d'information annuelle Suravenir (assurance vie Patrimoine Vie Plus, PER Pertinence Retraite).

Forme relevée sur les relevés 2023 à 2025 ; tout ce qui n'est pas reconnu devient une anomalie, jamais un zéro silencieux.
"""

import re
from dataclasses import replace
from decimal import Decimal

from metabank.releves.frais_supports import lire_frais_supports, taux_frais_fonds_euros
from metabank.releves.modele import Frais, Mouvements, Releve, Support
from metabank.releves.texte import (
    MOTIF_ISIN,
    MOTIF_MONTANT,
    ErreurLecture,
    a_plat,
    chercher_montant,
    colonnes,
    date_en_lettres,
    en_decimal,
    est_montant,
)

# Apostrophe droite (relevés 2025) ou typographique (2023, 2024).
TITRE = re.compile("RELEVE D['\u2019]INFORMATION ANNUELLE")
DEBUT_SUPPORTS = "LA SITUATION DE VOTRE CONTRAT AU"
FINS_SUPPORTS = ("SYNTHÈSE DES MOUVEMENTS", "Pour rappel", "EVOLUTION DE VOTRE PLAN")
DEBUT_MOUVEMENTS = "SYNTHÈSE DES MOUVEMENTS"
FINS_MOUVEMENTS = (
    "(1) La différence",
    "(4) Montant des frais",
    "EVOLUTION DE VOTRE PLAN",
    "INFORMATIONS RÉGLEMENTAIRES",
)
# Lignes de pied de page ou d'en-tête qui peuvent tomber au milieu d'un tableau, à un saut de page.
BRUIT = re.compile(
    r"^(Émis le|Page \d|N° Contrat|tourner S\.V\.P|Vie Plus - |Ce document|Société |et par le souscripteur)"
)
# Tolérance d'un centime par ligne : chaque montant du relevé est arrondi séparément.
CENTIME = Decimal("0.01")


def est_releve_suravenir(texte: str) -> bool:
    """Rendre vrai si le texte est un relevé d'information annuelle Suravenir."""
    return "Suravenir" in texte and TITRE.search(texte) is not None


def lire_releve_suravenir(texte: str, fichier: str = "", type_indique: str | None = None) -> Releve:
    """Rendre le relevé annuel lu dans le texte pdftotext -layout d'un PDF Suravenir.

    Args:
        texte: sortie de pdftotext -layout.
        fichier: nom du PDF, repris dans les anomalies.
        type_indique: type déduit du dossier (« assurance_vie », « per »…), prioritaire sur la déduction du texte.
    """
    plat = a_plat(texte)
    lignes = texte.splitlines()
    anomalies: list[str] = []
    est_per = "Valeur de transfert" in texte
    date_arrete, valeur = _valeur_au_31_decembre(plat)
    supports = _lire_supports(lignes, anomalies)
    mouvements = _lire_mouvements(lignes, anomalies)
    frais = _lire_frais(plat)
    frais_supports, anomalies_frais = lire_frais_supports(texte)
    anomalies += anomalies_frais
    releve = Releve(
        assureur="Suravenir",
        produit=_produit(lignes),
        numero=_numero(plat),
        type_contrat=type_indique or ("per" if est_per else "assurance_vie"),
        date_arrete=date_arrete,
        valeur=valeur,
        supports=tuple(supports),
        valeur_precedente=chercher_montant(
            rf"la valeur (?:de transfert )?de votre contrat au 31 décembre \d{{4}} était de ({MOTIF_MONTANT}) €", plat
        ),
        mouvements=mouvements,
        frais=frais,
        frais_supports=tuple(frais_supports),
        taux_frais_fonds_euros=taux_frais_fonds_euros(texte),
        versements_volontaires_annee=_versements_volontaires(plat, r"EVOLUTION DE VOTRE PLAN EN \d{4}")
        if est_per
        else None,
        versements_bruts_depuis_origine=_versements_volontaires(plat, r"DEPUIS L.ORIGINE") if est_per else None,
        fichier=fichier,
    )
    anomalies += controler(releve)
    return _avec_anomalies(releve, anomalies)


def controler(releve: Releve) -> list[str]:
    """Rendre les incohérences internes du relevé : sommes qui ne tombent pas juste, versements qui divergent."""
    anomalies = []
    somme = sum((support.valeur for support in releve.supports), Decimal(0))
    tolerance = CENTIME * (len(releve.supports) + 1)
    if abs(somme - releve.valeur) > tolerance:
        anomalies.append(f"somme des supports {somme} € ≠ valeur du contrat {releve.valeur} €")
    frais, mouvements = releve.frais, releve.mouvements
    if frais is not None:
        composantes = frais.sur_operations + frais.gestion_unites_compte + frais.gestion_fonds_euros
        if abs(composantes - frais.total) > 3 * CENTIME:
            anomalies.append(f"frais : composantes {composantes} € ≠ total annoncé {frais.total} €")
    if frais is not None and mouvements is not None:
        sur_operations = mouvements.frais_versements + mouvements.frais_arbitrages
        if abs(sur_operations - frais.sur_operations) > 2 * CENTIME:
            anomalies.append(
                f"frais sur opérations : synthèse {sur_operations} € ≠ total annoncé {frais.sur_operations} €"
            )
    if releve.versements_volontaires_annee is not None and mouvements is not None:
        ecart = releve.versements_volontaires_annee - mouvements.versements_bruts
        if abs(ecart) > Decimal("0.5"):
            anomalies.append(
                f"versements de l'année : {releve.versements_volontaires_annee} € au tableau « évolution du plan », "
                f"{mouvements.versements_bruts} € dans la synthèse des mouvements (écart {ecart} €)"
            )
    return anomalies


def _valeur_au_31_decembre(plat: str):
    trouve = re.search(
        rf"Valeur (?:de transfert )?\(\*\) de votre contrat au (\d{{1,2}}) (\w+) (\d{{4}}) : ({MOTIF_MONTANT}) €", plat
    )
    if trouve is None:
        raise ErreurLecture("valeur du contrat au 31 décembre introuvable : relevé de forme inconnue")
    return date_en_lettres(*trouve.group(1, 2, 3)), en_decimal(trouve.group(4))


def _produit(lignes: list[str]) -> str:
    for rang, ligne in enumerate(lignes):
        if TITRE.search(ligne):
            suivantes = (suivante.strip() for suivante in lignes[rang + 1 :])
            return next(suivante for suivante in suivantes if suivante).title()
    return "?"


def _numero(plat: str) -> str:
    trouve = re.search(r"Contrat N° : ([\dA-Z ]+?\d{6,})", plat)
    return trouve.group(1).strip() if trouve else "?"


def _bloc(lignes: list[str], debut: str, fins: tuple[str, ...]) -> list[str]:
    """Rendre les lignes entre la première contenant debut et la suivante contenant une des fins."""
    rangs = [rang for rang, ligne in enumerate(lignes) if debut in ligne]
    if not rangs:
        return []
    bloc = []
    for ligne in lignes[rangs[0] + 1 :]:
        if any(fin in ligne for fin in fins):
            break
        bloc.append(ligne)
    return bloc


def _lire_supports(lignes: list[str], anomalies: list[str]) -> list[Support]:
    supports = []
    for ligne in _bloc(lignes, DEBUT_SUPPORTS, FINS_SUPPORTS):
        cellules = colonnes(ligne)
        if not cellules or BRUIT.match(cellules[0]):
            continue
        isins = [rang for rang, cellule in enumerate(cellules) if re.fullmatch(MOTIF_ISIN, cellule)]
        if isins and len(cellules) == isins[0] + 4 and all(est_montant(c) for c in cellules[-3:]):
            rang = isins[0]
            parts, valeur_part, valeur = (en_decimal(c) for c in cellules[-3:])
            supports.append(Support(" ".join(cellules[:rang]), valeur, cellules[rang], parts, valeur_part))
        elif "FONDS EUROS" in ligne.upper() and est_montant(cellules[-1]):
            supports.append(Support(re.sub(r"\s*\(\d\)$", "", cellules[0]), en_decimal(cellules[-1])))
        elif any(est_montant(cellule) for cellule in cellules):
            anomalies.append(f"ligne de support non reconnue : {' | '.join(cellules)}")
    return supports


def _lire_mouvements(lignes: list[str], anomalies: list[str]) -> Mouvements:
    valeurs: dict[str, Decimal] = {}
    en_attente = None
    for ligne in _bloc(lignes, DEBUT_MOUVEMENTS, FINS_MOUVEMENTS):
        cellules = colonnes(ligne)
        if not cellules or BRUIT.match(cellules[0]) or cellules[0].startswith("Libellé"):
            continue
        montants = [en_decimal(c) for c in cellules if est_montant(c)]
        libelle = " ".join(c for c in cellules if not est_montant(c))
        if en_attente and montants and not libelle:
            # Libellé sur deux lignes (« Prélèvements sociaux sur la revalorisation / annuelle ») : montant seul.
            _ranger(en_attente, montants, valeurs, anomalies)
            en_attente = None
        elif libelle and montants:
            _ranger(libelle, montants, valeurs, anomalies)
        elif libelle and _champs(libelle):
            en_attente = libelle
    return Mouvements(**valeurs)


def _champs(libelle: str) -> tuple[str, ...] | None:
    """Rendre les champs de Mouvements portés, dans l'ordre des colonnes, par une ligne de ce libellé."""
    regles = (
        ("Versement", ("versements_nets", "frais_versements")),
        ("Arbitrage", ("arbitrages_debit", "arbitrages_credit", "frais_arbitrages")),
        ("Distribution", ("distributions",)),
        ("Revalorisation", ("revalorisation_fonds_euros",)),
        ("Prélèvements sociaux", ("prelevements_sociaux",)),
        ("Rachat", ("rachats",)),
    )
    return next((champs for debut, champs in regles if libelle.startswith(debut)), None)


def _ranger(libelle: str, montants: list[Decimal], valeurs: dict, anomalies: list[str]) -> None:
    champs = _champs(libelle)
    if champs is None or len(montants) > len(champs):
        anomalies.append(f"mouvement non reconnu : {libelle} {montants}")
        return
    if libelle.startswith("Rachat"):
        anomalies.append(f"rachat lu comme {montants[0]} € : vérifier sur le relevé (forme jamais rencontrée)")
    for champ, montant in zip(champs, montants, strict=False):
        valeurs[champ] = valeurs.get(champ, Decimal(0)) + montant


def _lire_frais(plat: str) -> Frais | None:
    montant = rf"({MOTIF_MONTANT}) €"
    total = chercher_montant(
        rf"montant total des frais imputés sur votre (?:contrat|plan) pour l.année \d{{4}} est de {montant}", plat
    )
    if total is None:
        return None
    return Frais(
        sur_operations=chercher_montant(rf"frais sur opération supporté par votre (?:contrat|plan) en \d{{4}} est de {montant}", plat) or Decimal(0),
        gestion_unites_compte=chercher_montant(rf"frais de gestion sur les supports en unités de compte est de {montant}", plat) or Decimal(0),
        gestion_fonds_euros=chercher_montant(rf"frais de gestion sur (?:le|les|le\(s\)) fonds en euros prélevés lors de la revalorisation annuelle est de {montant}", plat) or Decimal(0),
        total=total,
    )  # fmt: skip


def _versements_volontaires(plat: str, titre_bloc: str) -> Decimal | None:
    debut = re.search(titre_bloc, plat)
    if debut is None:
        return None
    # Le bloc tient en quelques centaines de caractères : borner évite d'attraper le bloc suivant.
    bloc = plat[debut.end() : debut.end() + 400]
    return chercher_montant(rf"Versements volontaires \(1\) ({MOTIF_MONTANT})", bloc)


def _avec_anomalies(releve: Releve, anomalies: list[str]) -> Releve:
    return replace(releve, anomalies=tuple(f"{releve.fichier} : {a}" if releve.fichier else a for a in anomalies))

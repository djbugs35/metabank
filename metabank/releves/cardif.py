"""Lecture des relevés de situation Cardif (espace client BNP Paribas), par exemple Cardif Essentiel Retraite.

Un relevé de situation est une photo à une date : valeur de rachat, total versé, supports. Ni mouvements ni frais.
"""

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal

from metabank.releves.modele import Releve, Support
from metabank.releves.texte import (
    MOTIF_MONTANT,
    ErreurLecture,
    a_plat,
    chercher_montant,
    colonnes,
    en_decimal,
    est_montant,
)

DEBUT_SUPPORTS = "Valeur de rachat et répartition"
# Colonnes d'une ligne de support : montant, répartition (%), prix de référence, plus ou moins-value.
MONTANTS_PAR_SUPPORT = 4


def est_situation_cardif(texte: str) -> bool:
    """Rendre vrai si le texte est un relevé de situation Cardif."""
    return "Relevé de situation" in texte and "Cardif" in texte


def lire_situation_cardif(texte: str, fichier: str = "", type_indique: str | None = None) -> Releve:
    """Rendre le relevé lu dans le texte pdftotext -layout d'un relevé de situation Cardif."""
    plat = a_plat(texte)
    contrat = re.search(r"du contrat (.+?) \(N° (\d+)\)", plat)
    valeur = re.search(rf"Valeur de rachat au (\d{{2}}/\d{{2}}/\d{{4}}) : ({MOTIF_MONTANT}) €", plat)
    if contrat is None or valeur is None:
        raise ErreurLecture("contrat ou valeur de rachat introuvable : relevé de situation de forme inconnue")
    supports = _lire_supports(texte.splitlines())
    releve = Releve(
        assureur="Cardif",
        produit=contrat.group(1),
        numero=contrat.group(2),
        type_contrat=type_indique or "inconnu",
        date_arrete=date(*reversed([int(n) for n in valeur.group(1).split("/")])),
        valeur=en_decimal(valeur.group(2)),
        supports=tuple(supports),
        versements_bruts_depuis_origine=chercher_montant(
            rf"Total brut versé depuis l.origine : ({MOTIF_MONTANT}) €", plat
        ),
        rachats_depuis_origine=chercher_montant(rf"Total racheté : ({MOTIF_MONTANT}) €", plat),
        fichier=fichier,
    )
    anomalies = []
    somme = sum((support.valeur for support in supports), Decimal(0))
    if abs(somme - releve.valeur) > Decimal("0.01") * (len(supports) + 1):
        anomalies.append(f"somme des supports {somme} € ≠ valeur de rachat {releve.valeur} €")
    return replace(releve, anomalies=tuple(f"{fichier} : {a}" if fichier else a for a in anomalies))


def _lire_supports(lignes: list[str]) -> list[Support]:
    """Rendre les supports ; un libellé coupé sur deux lignes est recollé à la ligne précédente."""
    rangs = [rang for rang, ligne in enumerate(lignes) if DEBUT_SUPPORTS in ligne]
    if not rangs:
        return []
    supports: list[Support] = []
    for ligne in lignes[rangs[0] + 1 :]:
        cellules = colonnes(ligne)
        if not cellules:
            continue
        montants = [cellule for cellule in cellules if est_montant(cellule)]
        texte = " ".join(cellule for cellule in cellules if not est_montant(cellule))
        if len(montants) >= MONTANTS_PAR_SUPPORT and texte:
            supports.append(Support(texte, en_decimal(montants[0])))
        elif montants:
            # Ligne « 100,00 » : total de la répartition, fin du tableau.
            break
        elif supports:
            dernier = supports[-1]
            supports[-1] = replace(dernier, libelle=f"{dernier.libelle} {texte}")
    return supports

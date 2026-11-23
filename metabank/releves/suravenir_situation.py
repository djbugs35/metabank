"""Lecture de la « Situation de votre contrat au … » Suravenir (Vie Plus) : valeur et fonds à une date. MODELE § 2.3.

Document ponctuel, sans mouvements de l'année ni frais : il donne la valeur de chaque fonds, le total, et les cumuls
de versements et de rachats depuis l'origine. Montants en euros.
"""

import re
from decimal import Decimal

from metabank.releves.modele import Releve, Support
from metabank.releves.texte import MOTIF_ISIN, MOTIF_MONTANT, ErreurLecture, date_numerique, en_decimal

TITRE = re.compile(r"Situation de votre contrat au (\d{2}/\d{2}/\d{4})")
NUMERO = re.compile(r"N°\s*([A-Z0-9]{1,3}\s+\d{6,})\s+du")
SUPPORT = re.compile(
    rf"^\s*(?P<libelle>\S.*?\S)\s{{2,}}(?P<isin>{MOTIF_ISIN})\s+(?P<parts>{MOTIF_MONTANT})\s+(?P<vl>{MOTIF_MONTANT})\s+"
    rf"(?P<pru>{MOTIF_MONTANT})\s+(?P<pv>{MOTIF_MONTANT})\s?%\s+\d+\.\d+\s?%\s+(?P<montant>{MOTIF_MONTANT})\s*$"
)
TOTAL = re.compile(rf"^\s*TOTAL\s+({MOTIF_MONTANT})\s*$", re.MULTILINE)
COMPARTIMENT = re.compile(rf"\d+\s*-\s*Compartiment\s+\d+\s+({MOTIF_MONTANT})\s*€")
ECART_TOLERE = Decimal(1)


def est_situation_suravenir(texte: str) -> bool:
    """Rendre vrai si le texte est une situation de contrat Suravenir (et non un relevé annuel)."""
    return "SURAVENIR" in texte.upper() and TITRE.search(texte) is not None and "Supports financiers" in texte


def _montant_apres(libelle: str, texte: str) -> Decimal | None:
    trouve = re.search(rf"{re.escape(libelle)}\s+({MOTIF_MONTANT})\s*€", texte)
    return en_decimal(trouve.group(1)) if trouve else None


def lire_situation_suravenir(texte: str, fichier: str = "", type_indique: str | None = None) -> Releve:
    """Rendre la situation lue : valeur totale, fonds, cumuls depuis l'origine, contrôles. MODELE § 2.3.

    Raises:
        ErreurLecture: date, numéro ou fonds introuvables.
    """
    titre, numero = TITRE.search(texte), NUMERO.search(texte)
    if not titre or not numero:
        raise ErreurLecture(f"{fichier} : date de situation ou numéro de contrat introuvable")
    lignes = texte.splitlines()
    rang = next(i for i, ligne in enumerate(lignes) if NUMERO.search(ligne))
    produit = next((ligne.strip() for ligne in reversed(lignes[:rang]) if ligne.strip()), "?").title()
    supports, vus = [], set()
    for ligne in lignes:
        trouve = SUPPORT.match(ligne)
        # Les pages répètent l'en-tête, jamais une ligne de fonds : chaque ISIN n'est compté qu'une fois.
        if trouve and trouve["isin"] not in vus:
            vus.add(trouve["isin"])
            supports.append(Support(" ".join(trouve["libelle"].split()), en_decimal(trouve["montant"]), trouve["isin"],
                                    en_decimal(trouve["parts"]), en_decimal(trouve["vl"])))  # fmt: skip
    if not supports:
        raise ErreurLecture(f"{fichier} : aucun fonds lu dans la situation")
    total = TOTAL.search(texte)
    compartiments = {en_decimal(m) for m in COMPARTIMENT.findall(texte)}
    somme = sum((s.valeur for s in supports), Decimal(0))
    valeur = en_decimal(total.group(1)) if total else sum(compartiments, Decimal(0)) if compartiments else somme
    versements = _montant_apres("Cumul des versements bruts", texte)
    rachats = _montant_apres("Cumul des rachats bruts", texte)
    anomalies = _controles(
        valeur, somme, versements, rachats, _montant_apres("Performance (+/- value fiscale) en €", texte)
    )
    type_contrat = type_indique or ("per" if "RETRAITE" in produit.upper() else "assurance_vie")
    return Releve("Suravenir", produit, numero.group(1), type_contrat, date_numerique(titre.group(1)), valeur,
                  tuple(supports), versements_bruts_depuis_origine=versements, rachats_depuis_origine=rachats,
                  anomalies=tuple(f"{fichier} : {a}" for a in anomalies), fichier=fichier)  # fmt: skip


def _controles(valeur: Decimal, somme: Decimal, versements: Decimal | None, rachats: Decimal | None,
               performance: Decimal | None) -> list[str]:  # fmt: skip
    anomalies = []
    if abs(somme - valeur) > ECART_TOLERE:
        anomalies.append(f"somme des fonds {somme} € pour un total de {valeur} €")
    if versements is not None and performance is not None:
        gain = valeur - versements + (rachats or Decimal(0))
        if abs(gain - performance) > ECART_TOLERE:
            anomalies.append(f"gain recalculé {gain} € pour une performance annoncée de {performance} €")
    return anomalies

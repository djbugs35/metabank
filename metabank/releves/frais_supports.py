"""Lecture du tableau Suravenir « Frais sur les supports d'investissement » (un relevé annuel, année écoulée).

Le tableau est mis en page en colonnes étroites : pdftotext le rend sur trois lignes par support.
  ligne au-dessus : frais de gestion du support (B) et frais totaux (B+C)
  ligne de l'ISIN : performance brute (A), nette (A-B), frais du contrat (C, en % puis en €), finale (A-B-C)
  ligne au-dessous : part de B rétrocédée, répétée sous B+C
Une ligne n'est retenue que si ses taux se recoupent (A-B, B+C…) : un tableau mal découpé est signalé, pas deviné.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from metabank.releves.texte import MOTIF_ISIN, en_decimal

POURCENT = re.compile(r"(-?\d+,\d+)\s?%")
# Montant en euros (frais du contrat) : nombre à virgule qui n'est pas suivi d'un « % ».
EUROS = re.compile(r"(?<![\d,])(\d{1,3}(?: \d{3})*,\d{2})(?![\d,]|\s?%)")
# Taux lus sur la ligne de l'ISIN : brute, brute 5 ans, nette, nette 5 ans, contrat, finale, finale 5 ans.
TAUX_LIGNE_ISIN = 7
LIGNES_VOISINES = 3
# Les taux sont arrondis au centième de point : deux arrondis cumulés.
TOLERANCE = Decimal("0.02")


@dataclass(frozen=True)
class FraisSupport:
    """Frais et performances d'un support sur l'année écoulée, en points de pourcentage (1,40 = 1,40 %)."""

    isin: str
    frais_support: Decimal
    retrocessions: Decimal
    frais_contrat: Decimal
    frais_contrat_euros: Decimal
    frais_totaux: Decimal
    performance_brute: Decimal
    performance_finale: Decimal
    performance_finale_5_ans: Decimal


def lire_frais_supports(texte: str) -> tuple[list[FraisSupport], list[str]]:
    """Rendre les frais de chaque support du tableau, et les lignes écartées faute de se recouper."""
    lignes = texte.splitlines()
    frais, anomalies = [], []
    for rang, ligne in enumerate(lignes):
        isin = re.search(MOTIF_ISIN, ligne)
        taux = POURCENT.findall(ligne)
        if isin is None or len(taux) < TAUX_LIGNE_ISIN - 2:
            continue
        lu = _lire_ligne(lignes, rang, isin.group(0))
        if isinstance(lu, FraisSupport):
            frais.append(lu)
        else:
            anomalies.append(f"frais du support {isin.group(0)} non lus : {lu}")
    return frais, anomalies


def taux_frais_fonds_euros(texte: str) -> Decimal | None:
    """Rendre le taux de frais annuels de gestion du (premier) fonds en euros, en points, ou None."""
    trouve = re.search(r"Taux de frais annuels de gestion\s+(-?\d+,\d+)\s?%", texte)
    return en_decimal(trouve.group(1)) if trouve else None


def _lire_ligne(lignes: list[str], rang: int, isin: str) -> "FraisSupport | str":
    taux = [en_decimal(t) for t in POURCENT.findall(lignes[rang])]
    euros = EUROS.findall(POURCENT.sub("", lignes[rang]))
    dessus = _voisine(lignes, range(rang - 1, rang - 1 - LIGNES_VOISINES, -1))
    dessous = _voisine(lignes, range(rang + 1, rang + 1 + LIGNES_VOISINES))
    if len(taux) == TAUX_LIGNE_ISIN - 2:
        taux = _avec_performances_au_dessus(lignes[rang - 1], taux)
    if len(taux) != TAUX_LIGNE_ISIN or len(euros) != 1 or dessus is None or dessous is None:
        return "ligne de forme inattendue"
    brute, _, nette, _, contrat, finale, finale_5_ans = taux
    support, totaux = dessus
    retrocessions = dessous[0]
    recoupements = (brute - support - nette, nette - contrat - finale, support + contrat - totaux)
    if any(abs(ecart) > TOLERANCE for ecart in recoupements):
        return f"taux incohérents (écarts {', '.join(str(e) for e in recoupements)})"
    return FraisSupport(
        isin=isin,
        frais_support=support,
        retrocessions=retrocessions,
        frais_contrat=contrat,
        frais_contrat_euros=en_decimal(euros[0]),
        frais_totaux=totaux,
        performance_brute=brute,
        performance_finale=finale,
        performance_finale_5_ans=finale_5_ans,
    )


def _avec_performances_au_dessus(ligne_dessus: str, taux: list[Decimal]) -> list[Decimal]:
    """Rendre les sept taux quand les performances à trois chiffres (« 121,74 ») sont remontées d'une ligne.

    Cas réel (fonds or 2025) : la colonne est trop étroite, le nombre monte d'une ligne et son « % » descend d'une.
    """
    nus = re.findall(r"(?<![\d,])-?\d+,\d+(?!\s?%|\d)", ligne_dessus)
    if len(nus) != 2:
        return taux
    brute_5_ans, nette_5_ans, contrat, finale, finale_5_ans = taux
    brute, nette = (en_decimal(n) for n in nus)
    return [brute, brute_5_ans, nette, nette_5_ans, contrat, finale, finale_5_ans]


def _voisine(lignes: list[str], rangs: range) -> tuple[Decimal, Decimal] | None:
    """Rendre les deux derniers taux de la première ligne voisine (sans ISIN) qui en porte au moins deux."""
    for rang in rangs:
        if not 0 <= rang < len(lignes) or re.search(MOTIF_ISIN, lignes[rang]):
            continue
        taux = POURCENT.findall(lignes[rang])
        if len(taux) >= 2:
            return en_decimal(taux[-2]), en_decimal(taux[-1])
    return None

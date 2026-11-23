"""Allocation : classe de chaque support, répartition, concentration, cible et rééquilibrage. MODELE § 13.

Montants en euros, parts en fractions. Des faits et une arithmétique, jamais une recommandation.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from metabank.releves import ReleveRange
from metabank.releves.modele import cle_du_contrat

ZERO = Decimal(0)
SEUIL_CONCENTRATION = Decimal("0.20")
SEUIL_DERIVE = Decimal("0.05")
A_CLASSER = "À classer"
FONDS_EUROS = "Fonds en euros"
# Ordre d'examen : le premier motif qui reconnaît le libellé l'emporte (« FLEXIBLE EQUITY » est d'abord une action,
# « EMERGING MARKETS CORPORATE » d'abord une obligation).
CLASSES_PAR_MOTIF: list[tuple[str, str]] = [
    (r"FONDS EUROS?\b|\bEUROS? COMPARTIMENT|\bACTIF GENERAL", FONDS_EUROS),
    (r"MONETAIRE|MONEY MARKET|TRESORERIE", "Monétaire"),
    (r"ATHENA|DEGRESSIF|AUTOCALL|PHOENIX|QUOTIDIEN", "Produits structurés"),
    (r"\bFCPR\b|\bFCPI\b|\bFIP\b|PRIVATE EQUITY", "Capital-investissement"),
    (r"\bSCPI\b|\bSCI\b|\bOPCI\b|IMMOBILI|\bREIT", "Immobilier"),
    (r"OBLIG|BOND|HIGH YIELD|CREDIT|CORPORATE|\bTAUX\b", "Obligations"),
    (r"EQUITY|ACTION|\bGOLD\b|BANKS|SMALL CAP|MSCI|S&P|CAC 40|STOXX", "Actions"),
    (r"FLEXIBLE|PATRIMOINE|ALLOCATION|DIVERSIFI|MULTI.?ASSET", "Diversifiés"),
]
CLASSES = [*dict.fromkeys(c for _, c in CLASSES_PAR_MOTIF), A_CLASSER]


@dataclass(frozen=True)
class Position:
    """Un support détenu : son contrat, sa classe (choisie ou déduite), sa valeur en euros et ses frais totaux
    (fonds et contrat, en points par an, au dernier relevé ; None s'ils n'y figurent pas)."""

    cle: str
    libelle: str
    titulaire: str
    contrat: str
    classe: str
    classe_choisie: bool
    valeur: Decimal
    frais_totaux: Decimal | None = None


def cle_support(libelle: str, isin: str | None) -> str:
    """Rendre la clé d'un support pour la classe choisie : son ISIN, sinon son libellé en majuscules."""
    return isin or libelle.strip().upper()


def classe_deduite(libelle: str) -> str:
    """Rendre la classe déduite des mots du libellé, ou « À classer »."""
    texte = libelle.upper()
    return next((c for motif, c in CLASSES_PAR_MOTIF if re.search(motif, texte)), A_CLASSER)


def positions(releves: list[ReleveRange], choisies: dict[str, str]) -> list[Position]:
    """Rendre les supports du dernier relevé de chaque contrat, avec leur classe. MODELE § 13."""
    derniers: dict[tuple[str, str], ReleveRange] = {}
    for r in releves:
        contrat_cle = (r.titulaire, cle_du_contrat(r.releve.numero))
        if contrat_cle not in derniers or r.releve.date_arrete > derniers[contrat_cle].releve.date_arrete:
            derniers[contrat_cle] = r
    # Une situation récente n'a pas de tableau des frais : ils viennent du dernier relevé qui en a un. MODELE § 2.3.
    frais_par_contrat: dict[tuple[str, str], dict[str, Decimal]] = {}
    for r in sorted(releves, key=lambda r: r.releve.date_arrete):
        if r.releve.frais_supports:
            frais_par_contrat[(r.titulaire, cle_du_contrat(r.releve.numero))] = {
                f.isin: f.frais_totaux for f in r.releve.frais_supports
            }
    resultat = []
    for (titulaire, numero), r in derniers.items():
        contrat = f"{r.releve.produit} …{r.releve.numero.replace(' ', '')[-4:]}"
        frais = frais_par_contrat.get((titulaire, numero), {})
        for s in r.releve.supports:
            cle = cle_support(s.libelle, s.isin)
            choisie = choisies.get(cle)
            resultat.append(Position(cle, s.libelle, r.titulaire, contrat, choisie or classe_deduite(s.libelle),
                                     choisie is not None, s.valeur, frais.get(s.isin or "")))  # fmt: skip
    return sorted(resultat, key=lambda p: -p.valeur)


def repartir(positions_: list[Position], liquidites: dict[str, Decimal]) -> list[tuple[str, Decimal, Decimal]]:
    """Rendre (classe ou liquidité, montant, part du patrimoine financier), classes dans l'ordre de CLASSES."""
    montants = {c: sum((p.valeur for p in positions_ if p.classe == c), ZERO) for c in CLASSES}
    montants.update(liquidites)
    total = sum(montants.values(), ZERO)
    return [(nom, m, m / total if total else ZERO) for nom, m in montants.items() if m]


def concentrations(positions_: list[Position], total: Decimal) -> list[Position]:
    """Rendre les supports qui pèsent plus de 20 % du patrimoine financier. MODELE § 13."""
    return [p for p in positions_ if total and p.valeur / total > SEUIL_CONCENTRATION]


def reequilibrer(valeurs: dict[str, Decimal], cible: dict[str, Decimal]) -> dict[str, Decimal]:
    """Rendre le versement par classe qui atteint la cible sans rien vendre (euros). MODELE § 13.

    Args:
        valeurs: valeur actuelle par classe des supports.
        cible: part visée par classe (fractions, somme 1).
    """
    actives = {c: part for c, part in cible.items() if part > 0}
    if not actives:
        return {}
    total_vise = max(valeurs.get(c, ZERO) / part for c, part in actives.items())
    return {c: max(part * total_vise - valeurs.get(c, ZERO), ZERO) for c, part in actives.items()}


def derives(parts: dict[str, Decimal], cible: dict[str, Decimal]) -> dict[str, Decimal]:
    """Rendre {classe : écart à la cible} pour les classes qui s'en écartent de plus de 5 points. MODELE § 13."""
    ecarts = {c: parts.get(c, ZERO) - part for c, part in cible.items()}
    return {c: e for c, e in ecarts.items() if abs(e) > SEUIL_DERIVE}

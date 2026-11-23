"""Budget : abonnements repérés, objectifs par catégorie, comparaison d'une année sur l'autre. MODELE § 7.13.

Montants en euros, dépenses en positif ; mois sous la forme « AAAA-MM ».
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from metabank.banque.categories import DEPENSE, OperationClassee, motif_suggere

ZERO = Decimal(0)
MOIS_MIN_ABONNEMENT = 3
DEBITS_PAR_MOIS_MAX = 2
ECART_MAX_ABONNEMENT = Decimal("1.2")
FENETRE_JOURS = 365


@dataclass(frozen=True)
class Abonnement:
    """Un prélèvement ou achat régulier chez un même marchand."""

    marchand: str
    categorie: str
    montant_habituel: Decimal
    mois: int
    cout_12_mois: Decimal


@dataclass(frozen=True)
class Objectif:
    """Une catégorie et son objectif mensuel, face au dernier mois complet et à la moyenne des 3 derniers."""

    categorie: str
    objectif: Decimal
    mois: str
    depense_mois: Decimal
    moyenne_3_mois: Decimal

    @property
    def depasse(self) -> bool:
        """Rendre vrai si la dépense du dernier mois complet dépasse l'objectif."""
        return self.depense_mois > self.objectif


def reperer_abonnements(classees: list[OperationClassee], fin: date) -> list[Abonnement]:
    """Rendre les dépenses régulières des 12 mois qui finissent à fin, de la plus chère à la moins chère. MODELE § 7.13."""
    groupes: dict[str, list[OperationClassee]] = defaultdict(list)
    for c in classees:
        if c.nature == DEPENSE and c.operation.montant < 0 and c.operation.jour > fin - timedelta(days=FENETRE_JOURS):
            groupes[motif_suggere(c.operation.libelle)].append(c)
    abonnements = []
    for groupe in groupes.values():
        mois = {f"{c.operation.jour:%Y-%m}" for c in groupe}
        montants = [-c.operation.montant for c in groupe]
        regulier = len(mois) >= MOIS_MIN_ABONNEMENT and len(groupe) <= DEBITS_PAR_MOIS_MAX * len(mois)
        if regulier and max(montants) <= ECART_MAX_ABONNEMENT * min(montants):
            marchand = groupe[-1].operation.libelle
            abonnements.append(Abonnement(marchand, groupe[-1].categorie, Decimal(median(montants)), len(mois),
                                          sum(montants, ZERO)))  # fmt: skip
    return sorted(abonnements, key=lambda a: -a.cout_12_mois)


def depenses_par_mois(classees: list[OperationClassee]) -> dict[str, dict[str, Decimal]]:
    """Rendre {catégorie : {mois : dépense nette}} ; un remboursement diminue la dépense de sa catégorie."""
    resultat: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for c in classees:
        if c.nature == DEPENSE:
            resultat[c.categorie][f"{c.operation.jour:%Y-%m}"] -= c.operation.montant
    return resultat


def suivre_objectifs(par_mois: dict[str, dict[str, Decimal]], objectifs: dict[str, Decimal],
                     mois_complets: list[str]) -> list[Objectif]:  # fmt: skip
    """Rendre chaque objectif face au dernier mois complet ; vide sans mois complet. MODELE § 7.13."""
    if not mois_complets:
        return []
    derniers = mois_complets[-3:]
    return [
        Objectif(categorie, objectif, mois_complets[-1], par_mois.get(categorie, {}).get(mois_complets[-1], ZERO),
                 sum((par_mois.get(categorie, {}).get(m, ZERO) for m in derniers), ZERO) / len(derniers))
        for categorie, objectif in sorted(objectifs.items())
    ]  # fmt: skip


def comparer_annees(par_mois: dict[str, dict[str, Decimal]], mois_complets: list[str]) -> list[tuple]:
    """Rendre (catégorie, 12 derniers mois, 12 précédents ou None) par catégorie, de la plus chère. MODELE § 7.13."""
    derniers, precedents = mois_complets[-12:], mois_complets[-24:-12]
    if len(derniers) < 12:
        return []
    lignes = []
    for categorie, mois in par_mois.items():
        recent = sum((mois.get(m, ZERO) for m in derniers), ZERO)
        avant = sum((mois.get(m, ZERO) for m in precedents), ZERO) if len(precedents) == 12 else None
        if recent or avant:
            lignes.append((categorie, recent, avant))
    return sorted(lignes, key=lambda ligne: -ligne[1])

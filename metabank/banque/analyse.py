"""Analyse d'un compte bancaire : soldes, entrées et sorties, dépenses par catégorie, frais, livrets. MODELE § 7."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from metabank.banque.categories import DEPENSE, EPARGNE, INTERNE, REVENU, OperationClassee, classer
from metabank.banque.modele import Compte

ZERO = Decimal(0)
# Taux du Livret A et du LDDS depuis le 1er août 2026 (info.gouv.fr) : repère du « manque à gagner » d'un solde
# dormant. À mettre à jour à chaque changement de taux (1er février et 1er août).
TAUX_LIVRET_A = Decimal("0.017")
TAUX_LIVRET_A_DEPUIS = date(2026, 8, 1)
# Coussin laissé sur le compte courant avant de parler d'argent qui dort : deux mois de dépenses.
MOIS_DE_COUSSIN = 2
INTERETS = ("INTERET", "REMUNERATION")


@dataclass(frozen=True)
class Mois:
    """Un mois civil du compte : solde en fin de mois et flux par nature, en euros (sorties en positif)."""

    mois: str
    solde_fin: Decimal
    revenus: Decimal
    depenses: Decimal
    epargne: Decimal
    interne: Decimal
    complet: bool


@dataclass(frozen=True)
class AnalyseCompte:
    """Tout ce que l'application affiche d'un compte, sur la période couverte par ses exports."""

    compte: Compte
    debut: date
    mois: tuple[Mois, ...]
    solde_moyen: Decimal
    revenus: Decimal
    depenses: Decimal
    epargne: Decimal
    interne: Decimal
    depenses_par_categorie: tuple[tuple[str, Decimal], ...]
    frais_bancaires: Decimal
    detail_frais: tuple[tuple[str, Decimal], ...]
    non_classees: tuple[tuple[str, Decimal, int], ...]
    interets_par_an: tuple[tuple[int, Decimal, Decimal], ...]

    @property
    def nombre_mois(self) -> Decimal:
        """Rendre la durée couverte en mois (30,44 jours), au moins 1."""
        return max(Decimal((self.compte.date_solde - self.debut).days + 1) / Decimal("30.44"), Decimal(1))

    @property
    def taux_epargne(self) -> Decimal | None:
        """Rendre (revenus - dépenses) / revenus : la part des revenus qui n'a pas été dépensée."""
        return (self.revenus - self.depenses) / self.revenus if self.revenus > 0 else None

    @property
    def coussin(self) -> Decimal:
        """Rendre le solde jugé utile sur un compte courant : deux mois de dépenses moyennes."""
        return self.depenses / self.nombre_mois * MOIS_DE_COUSSIN

    @property
    def argent_qui_dort(self) -> Decimal:
        """Rendre la part du solde moyen au-delà du coussin (0 pour un livret)."""
        if self.compte.type_compte != "courant":
            return ZERO
        return max(self.solde_moyen - self.coussin, ZERO)

    @property
    def manque_a_gagner(self) -> Decimal:
        """Rendre ce que l'argent qui dort rapporterait par an au taux du Livret A, en euros."""
        return self.argent_qui_dort * TAUX_LIVRET_A


def analyser(compte: Compte, regles_perso: list[tuple[str, str]]) -> AnalyseCompte:
    """Rendre l'analyse du compte sur la période de ses exports. MODELE § 7.3 à 7.6."""
    classees = classer(compte.operations, regles_perso)
    debut = compte.operations[0].jour if compte.operations else compte.date_solde
    totaux = _totaux(classees)
    par_categorie: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for c in classees:
        if c.nature == DEPENSE:
            par_categorie[c.categorie] -= c.operation.montant
    frais = [c for c in classees if c.categorie == "Frais bancaires"]
    return AnalyseCompte(
        compte=compte,
        debut=debut,
        mois=tuple(_mois(compte, classees, debut)),
        solde_moyen=_solde_moyen(compte, debut),
        revenus=totaux[REVENU],
        depenses=totaux[DEPENSE],
        epargne=totaux[EPARGNE],
        interne=totaux[INTERNE],
        depenses_par_categorie=tuple(sorted(par_categorie.items(), key=lambda kv: -kv[1])),
        frais_bancaires=-sum((c.operation.montant for c in frais), ZERO),
        detail_frais=tuple(_regrouper((c.operation.libelle, -c.operation.montant) for c in frais)),
        non_classees=tuple(_non_classees(classees)),
        interets_par_an=tuple(_interets(compte, debut)),
    )


def _totaux(classees: list[OperationClassee]) -> dict[str, Decimal]:
    """Rendre revenus (entrées) et dépenses, épargne, interne (sorties nettes, en positif)."""
    totaux = {REVENU: ZERO, DEPENSE: ZERO, EPARGNE: ZERO, INTERNE: ZERO}
    for c in classees:
        totaux[c.nature] += c.operation.montant if c.nature == REVENU else -c.operation.montant
    return totaux


def _solde_au(compte: Compte, jour: date) -> Decimal:
    """Rendre le solde en fin de journée : solde de l'export moins les opérations postérieures. MODELE § 7.3."""
    return compte.solde - sum((o.montant for o in compte.operations if o.jour > jour), ZERO)


def _solde_moyen(compte: Compte, debut: date) -> Decimal:
    """Rendre la moyenne des soldes de fin de journée, du premier jour de l'export au jour du solde."""
    jours = (compte.date_solde - debut).days + 1
    solde = _solde_au(compte, debut - timedelta(days=1))
    par_jour: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for operation in compte.operations:
        par_jour[operation.jour] += operation.montant
    total = ZERO
    for rang in range(jours):
        solde += par_jour.get(debut + timedelta(days=rang), ZERO)
        total += solde
    return total / jours


def _mois(compte: Compte, classees: list[OperationClassee], debut: date) -> list[Mois]:
    flux: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for c in classees:
        cle = f"{c.operation.jour:%Y-%m}"
        flux[cle][c.nature] += c.operation.montant if c.nature == REVENU else -c.operation.montant
    resultat, annee, mois = [], debut.year, debut.month
    while (annee, mois) <= (compte.date_solde.year, compte.date_solde.month):
        suivant = date(annee + mois // 12, mois % 12 + 1, 1)
        fin = min(suivant - timedelta(days=1), compte.date_solde)
        cle = f"{annee}-{mois:02d}"
        complet = date(annee, mois, 1) >= debut and suivant - timedelta(days=1) <= compte.date_solde
        f = flux[cle]
        resultat.append(Mois(cle, _solde_au(compte, fin), f[REVENU], f[DEPENSE], f[EPARGNE], f[INTERNE], complet))
        annee, mois = suivant.year, suivant.month
    return resultat


def _regrouper(lignes) -> list[tuple[str, Decimal]]:
    """Rendre les montants additionnés par libellé, du plus gros au plus petit."""
    sommes: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for libelle, montant in lignes:
        sommes[libelle[:80]] += montant
    return sorted(sommes.items(), key=lambda kv: -kv[1])


def _non_classees(classees: list[OperationClassee]) -> list[tuple[str, Decimal, int]]:
    """Rendre les libellés des « Autres dépenses », du plus coûteux au moins coûteux : de quoi écrire des règles."""
    groupes: dict[str, list[Decimal]] = defaultdict(list)
    for c in classees:
        if c.categorie == "Autres dépenses":
            groupes[c.operation.libelle[:60]].append(-c.operation.montant)
    return sorted(((l, sum(m, ZERO), len(m)) for l, m in groupes.items()), key=lambda t: -t[1])[:30]


def _interets(compte: Compte, debut: date) -> list[tuple[int, Decimal, Decimal]]:
    """Rendre, pour un livret, (année, intérêts crédités, solde moyen de l'année). MODELE § 7.6."""
    if compte.type_compte == "courant":
        return []
    resultat = []
    for annee in range(debut.year, compte.date_solde.year + 1):
        interets = sum((o.montant for o in compte.operations
                        if o.jour.year == annee and o.montant > 0 and any(m in o.libelle.upper() for m in INTERETS)),
                       ZERO)  # fmt: skip
        premier, dernier = max(date(annee, 1, 1), debut), min(date(annee, 12, 31), compte.date_solde)
        jours = (dernier - premier).days + 1
        moyenne = sum((_solde_au(compte, premier + timedelta(days=r)) for r in range(jours)), ZERO) / jours
        resultat.append((annee, interets, moyenne))
    return resultat

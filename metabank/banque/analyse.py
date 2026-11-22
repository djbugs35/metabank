"""Analyse d'un compte bancaire : soldes, entrées et sorties, dépenses par catégorie, frais, livrets. MODELE § 7."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from metabank.banque.categories import DEPENSE, EPARGNE, INTERNE, REVENU, OperationClassee, classer
from metabank.banque.modele import TYPES_LIVRETS, Compte

ZERO = Decimal(0)
# Taux du Livret A, identique pour le LDDS : (date d'effet, taux annuel net). Sources : economie.gouv.fr,
# info.gouv.fr. À compléter à chaque changement (1er février et 1er août).
TAUX_REGLEMENTES = (
    (date(2022, 8, 1), Decimal("0.020")),
    (date(2023, 2, 1), Decimal("0.030")),
    (date(2025, 2, 1), Decimal("0.024")),
    (date(2025, 8, 1), Decimal("0.017")),
    (date(2026, 2, 1), Decimal("0.015")),
    (date(2026, 8, 1), Decimal("0.017")),
)
TAUX_LIVRET_A_DEPUIS, TAUX_LIVRET_A = TAUX_REGLEMENTES[-1]
# Intérêts d'un livret : calculés au 31/12 et crédités au tout début de janvier ; avant le 16, ils sont ceux de
# l'année précédente (relevé BNP : « REMUNERATION NETTE » le 01/01/2026 pour 2025).
JOUR_LIMITE_INTERETS_JANVIER = 15
# Plafond des versements (service-public.fr) ; les intérêts peuvent le dépasser, pas les versements.
PLAFONDS = {"livret_a": Decimal(22950), "ldd": Decimal(12000)}
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
    interets_par_an: tuple["InteretsAnnee", ...]

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


@dataclass(frozen=True)
class InteretsAnnee:
    """Intérêts d'un livret pour une année, en euros ; taux en fractions. MODELE § 7.6."""

    annee: int
    interets: Decimal | None
    solde_moyen: Decimal
    taux_reglemente_moyen: Decimal | None
    solde_moyen_suppose: bool
    estimation: Decimal | None

    @property
    def taux_obtenu(self) -> Decimal | None:
        """Rendre intérêts / solde moyen, ou None si les intérêts ne sont pas encore versés."""
        return self.interets / self.solde_moyen if self.interets is not None and self.solde_moyen else None


def taux_au(jour: date) -> Decimal | None:
    """Rendre le taux du Livret A en vigueur ce jour-là, ou None avant le premier taux connu."""
    connus = [taux for debut, taux in TAUX_REGLEMENTES if debut <= jour]
    return connus[-1] if connus else None


def taux_moyen_annee(annee: int) -> Decimal | None:
    """Rendre la moyenne des taux en vigueur le 1er de chaque mois de l'année (les changements tombent le 1er)."""
    taux = [taux_au(date(annee, mois, 1)) for mois in range(1, 13)]
    return None if None in taux else sum(taux, ZERO) / 12


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


def _annee_des_interets(jour: date) -> int:
    return jour.year - 1 if jour.month == 1 and jour.day <= JOUR_LIMITE_INTERETS_JANVIER else jour.year


def _interets(compte: Compte, debut: date) -> list[InteretsAnnee]:
    """Rendre, pour un livret, les intérêts de chaque année et le solde moyen qui les a produits. MODELE § 7.6.

    Le solde moyen d'une année se calcule sur ses jours couverts par l'export. Si aucun ne l'est (intérêts de
    l'année passée crédités en janvier), il est supposé égal au solde de la veille du versement : c'est exact
    sans mouvement dans l'année, à vérifier sinon.
    """
    if compte.type_compte not in TYPES_LIVRETS:
        return []
    versements: dict[int, Decimal] = defaultdict(lambda: ZERO)
    veille: dict[int, date] = {}
    for o in compte.operations:
        if o.montant > 0 and any(m in o.libelle.upper() for m in INTERETS):
            annee = _annee_des_interets(o.jour)
            versements[annee] += o.montant
            veille.setdefault(annee, o.jour - timedelta(days=1))
    resultat = []
    for annee in range(min([debut.year, *versements]), compte.date_solde.year + 1):
        premier, dernier = max(date(annee, 1, 1), debut), min(date(annee, 12, 31), compte.date_solde)
        suppose = premier > dernier
        if suppose:
            moyenne = _solde_au(compte, veille.get(annee, debut - timedelta(days=1)))
        else:
            jours = (dernier - premier).days + 1
            moyenne = sum((_solde_au(compte, premier + timedelta(days=r)) for r in range(jours)), ZERO) / jours
        taux = taux_moyen_annee(annee)
        interets = versements.get(annee)
        estimation = compte.solde * taux if interets is None and annee == compte.date_solde.year and taux else None
        resultat.append(InteretsAnnee(annee, interets, moyenne, taux, suppose, estimation))
    return resultat

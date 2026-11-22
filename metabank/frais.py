"""Analyse des frais support par support, sur le dernier relevé annuel de chaque contrat. Formules : MODELE § 4."""

from dataclasses import dataclass, replace
from decimal import Decimal

from metabank.releves import ReleveRange
from metabank.releves.modele import Releve

ZERO = Decimal(0)
CENT = Decimal(100)


@dataclass(frozen=True)
class LigneFrais:
    """Un support du contrat, avec ses frais annuels en points (1,40 = 1,40 %) et leur coût en euros."""

    libelle: str
    isin: str | None
    valeur: Decimal
    frais_support: Decimal | None
    retrocessions: Decimal | None
    frais_contrat: Decimal | None
    performance_brute: Decimal | None
    performance_finale: Decimal | None
    performance_finale_5_ans: Decimal | None

    @property
    def frais_totaux(self) -> Decimal | None:
        """Rendre frais du support + frais du contrat, en points, ou None si l'un manque."""
        if self.frais_support is None or self.frais_contrat is None:
            return None
        return self.frais_support + self.frais_contrat

    @property
    def cout_annuel(self) -> Decimal | None:
        """Rendre le coût annuel en euros de ces frais sur la valeur détenue."""
        return None if self.frais_totaux is None else self.valeur * self.frais_totaux / CENT


@dataclass(frozen=True)
class AnalyseFrais:
    """Frais d'un contrat : visibles (relevé), dans les supports (cachés), rétrocédés, et simulation."""

    titulaire: str
    produit: str
    annee: int
    lignes: tuple[LigneFrais, ...]
    frais_releve: Decimal | None
    economie_annuelle: Decimal
    ecart_projete: Decimal
    frais_support_cible: Decimal
    rendement_brut_hypothese: Decimal
    horizon_ans: int

    @property
    def encours(self) -> Decimal:
        """Rendre la valeur totale du contrat au 31/12."""
        return sum((ligne.valeur for ligne in self.lignes), ZERO)

    @property
    def encours_connu(self) -> Decimal:
        """Rendre la valeur des supports dont les frais sont connus."""
        return sum((ligne.valeur for ligne in self.lignes if ligne.frais_totaux is not None), ZERO)

    @property
    def frais_contrat_estimes(self) -> Decimal:
        """Rendre les frais de gestion du contrat au taux actuel sur la valeur au 31/12, en euros par an."""
        return sum((ligne.valeur * (ligne.frais_contrat or ZERO) / CENT for ligne in self.lignes), ZERO)

    @property
    def frais_dans_supports(self) -> Decimal:
        """Rendre les frais prélevés dans la valeur des supports (absents du total du relevé), en euros par an."""
        return sum((ligne.valeur * (ligne.frais_support or ZERO) / CENT for ligne in self.lignes), ZERO)

    @property
    def retrocessions(self) -> Decimal:
        """Rendre la part des frais des supports reversée à l'assureur et au distributeur, en euros par an."""
        return sum((ligne.valeur * (ligne.retrocessions or ZERO) / CENT for ligne in self.lignes), ZERO)

    @property
    def cout_total(self) -> Decimal:
        """Rendre le coût annuel estimé de tous les frais (contrat + supports) sur l'encours connu, en euros."""
        return sum((ligne.cout_annuel or ZERO for ligne in self.lignes), ZERO)

    @property
    def taux_moyen(self) -> Decimal | None:
        """Rendre le taux de frais total moyen pondéré par la valeur, en points."""
        return self.cout_total / self.encours_connu * CENT if self.encours_connu else None


def analyser_frais(
    releves: list[ReleveRange],
    frais_support_cible: Decimal = Decimal("0.20"),
    rendement_brut: Decimal = Decimal(5),
    horizon_ans: int = 15,
) -> list[AnalyseFrais]:
    """Rendre l'analyse des frais du dernier relevé annuel de chaque contrat qui détaille ses supports.

    Args:
        frais_support_cible: frais d'un support peu cher pris pour la simulation (0,20 = 0,20 %, ordre de grandeur
            d'un ETF), en points.
        rendement_brut: rendement annuel avant tous frais supposé pour la projection, en points.
        horizon_ans: durée de la projection.
    """
    derniers: dict[tuple[str, str], ReleveRange] = {}
    for range_ in releves:
        if range_.releve.frais_supports:
            cle = (range_.titulaire, range_.releve.numero)
            if cle not in derniers or range_.releve.date_arrete > derniers[cle].releve.date_arrete:
                derniers[cle] = range_
    return [
        _analyser(range_.titulaire, range_.releve, frais_support_cible, rendement_brut, horizon_ans)
        for _, range_ in sorted(derniers.items())
    ]


def _analyser(titulaire: str, releve: Releve, cible: Decimal, rendement: Decimal, horizon: int) -> AnalyseFrais:
    par_isin = {frais.isin: frais for frais in releve.frais_supports}
    lignes = []
    for support in releve.supports:
        frais = par_isin.get(support.isin) if support.isin else None
        if support.isin is None:
            lignes.append(LigneFrais(support.libelle, None, support.valeur, ZERO, ZERO, releve.taux_frais_fonds_euros,
                                     None, None, None))  # fmt: skip
        else:
            lignes.append(LigneFrais(
                support.libelle, support.isin, support.valeur,
                frais.frais_support if frais else None, frais.retrocessions if frais else None,
                frais.frais_contrat if frais else None, frais.performance_brute if frais else None,
                frais.performance_finale if frais else None, frais.performance_finale_5_ans if frais else None,
            ))  # fmt: skip
    economie = sum(
        (l.valeur * max(l.frais_support - cible, ZERO) / CENT for l in lignes if l.frais_support is not None), ZERO
    )
    analyse = AnalyseFrais(titulaire, releve.produit, releve.date_arrete.year, tuple(lignes),
                           releve.frais.total if releve.frais else None, economie, ZERO, cible, rendement, horizon)  # fmt: skip
    return _avec_projection(analyse)


def projeter(valeur: Decimal, rendement_brut: Decimal, taux_frais: Decimal, horizon_ans: int) -> Decimal:
    """Rendre la valeur après horizon_ans à rendement brut moins frais, sans versement. MODELE § 4.3."""
    return valeur * (1 + (rendement_brut - taux_frais) / CENT) ** horizon_ans


def _avec_projection(analyse: AnalyseFrais) -> AnalyseFrais:
    if analyse.taux_moyen is None or not analyse.encours_connu:
        return analyse
    taux_cible = analyse.taux_moyen - analyse.economie_annuelle / analyse.encours_connu * CENT
    actuel = projeter(analyse.encours_connu, analyse.rendement_brut_hypothese, analyse.taux_moyen, analyse.horizon_ans)
    moins_cher = projeter(analyse.encours_connu, analyse.rendement_brut_hypothese, taux_cible, analyse.horizon_ans)
    return replace(analyse, ecart_projete=moins_cher - actuel)

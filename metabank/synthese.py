"""Synthèse sur un ensemble de contrats (foyer, personne, contrat) : versements, rentabilité et frais. MODELE § 6."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from metabank.bilan import BilanContrat
from metabank.frais_historique import HistoriqueFrais

ZERO = Decimal(0)
# Bornes du taux annualisé cherché par dichotomie : de -99 % à +1000 % par an.
TAUX_MIN, TAUX_MAX = -0.99, 10.0
ITERATIONS = 200


@dataclass(frozen=True)
class AnneeSynthese:
    """Une année civile, sommée sur les contrats à relevés annuels de l'ensemble."""

    annee: int
    verse: Decimal
    gain: Decimal
    frais_releve: Decimal
    frais_fonds: Decimal
    rendement: Decimal | None
    ouverture_dans_l_annee: bool

    @property
    def frais(self) -> Decimal:
        """Rendre frais du relevé + frais des fonds."""
        return self.frais_releve + self.frais_fonds


@dataclass(frozen=True)
class Synthese:
    """Chiffres d'un ensemble de contrats ; les relevés de situation n'entrent que dans les totaux."""

    nom: str
    valeur: Decimal
    verse: Decimal
    gain: Decimal
    frais_cumules: Decimal
    rendement_annualise: Decimal | None
    annees: tuple[AnneeSynthese, ...]
    sans_historique: tuple[str, ...]
    situations_dans_rendement: tuple[str, ...] = ()
    versements_incertains: bool = False


def synthetiser(nom: str, bilans: list[BilanContrat], historiques: list[HistoriqueFrais]) -> Synthese:
    """Rendre la synthèse des contrats donnés."""
    frais_fonds = {(h.titulaire, h.numero, a.annee): a.frais_fonds for h in historiques for a in h.annees}
    suivis = [b for b in bilans if b.annees]
    annees = tuple(_annee(annee, suivis, frais_fonds) for annee in sorted({a.annee for b in suivis for a in b.annees}))
    return Synthese(
        nom=nom,
        valeur=sum((b.valeur for b in bilans), ZERO),
        verse=sum((b.apports_cumules or ZERO for b in bilans), ZERO),
        gain=sum((b.gain_cumule or ZERO for b in bilans), ZERO),
        frais_cumules=sum((a.frais for a in annees), ZERO),
        rendement_annualise=_rendement_annualise(bilans),
        annees=annees,
        sans_historique=tuple(f"{b.titulaire} · {b.produit}" for b in bilans if not b.annees),
        situations_dans_rendement=tuple(f"{b.titulaire} · {b.produit}" for b in bilans if _situation_datee(b)),
        versements_incertains=any("versements de l'année" in a for b in bilans for a in b.anomalies),
    )


def _annee(annee: int, bilans: list[BilanContrat], frais_fonds: dict) -> AnneeSynthese:
    """Rendre l'année sommée ; rendement de Dietz sur les sommes, versements en milieu d'année. MODELE § 6.1."""
    lignes = [(b, a) for b in bilans for a in b.annees if a.annee == annee]
    debut = sum((a.valeur_debut for _, a in lignes), ZERO)
    gain = sum((a.gain for _, a in lignes), ZERO)
    base = debut + sum(((a.apports - a.rachats) * a.poids_versements for _, a in lignes), ZERO)
    return AnneeSynthese(
        annee=annee,
        verse=sum((a.apports for _, a in lignes), ZERO),
        gain=gain,
        frais_releve=sum((a.frais or ZERO for _, a in lignes), ZERO),
        frais_fonds=sum((frais_fonds.get((b.titulaire, b.numero, annee), ZERO) for b, _ in lignes), ZERO),
        rendement=gain / base if base > 0 else None,
        ouverture_dans_l_annee=any(a.poids_estime for _, a in lignes),
    )


def _rendement_annualise(bilans: list[BilanContrat]) -> Decimal | None:
    """Rendre le taux de rendement interne annualisé depuis l'ouverture. MODELE § 6.2."""
    flux: list[tuple[date, float]] = []
    for bilan in bilans:
        if bilan.annees:
            flux += _flux_annuels(bilan)
        elif _situation_datee(bilan):
            # Relevé de situation : seul le total versé est connu ; supposé versé à l'ouverture (taux minimal).
            flux += [(bilan.date_ouverture, -float(bilan.apports_cumules)), (bilan.date_valeur, float(bilan.valeur))]
    if not flux:
        return None
    taux = taux_rendement_interne(flux)
    return None if taux is None else Decimal(str(round(taux, 6)))


def _flux_annuels(bilan: BilanContrat) -> list[tuple[date, float]]:
    """Rendre les flux d'un contrat à relevés annuels : versements datés, valeur finale positive."""
    premiere, derniere = bilan.annees[0], bilan.annees[-1]
    flux = []
    if premiere.valeur_debut > 0:
        flux.append((date(premiere.annee - 1, 12, 31), -float(premiere.valeur_debut)))
    for annee in bilan.annees:
        ouverture = bilan.date_ouverture
        jour = ouverture if annee.valeur_debut == 0 and ouverture and ouverture.year == annee.annee else None
        flux.append((jour or date(annee.annee, 7, 1), -float(annee.apports - annee.rachats)))
    flux.append((date(derniere.annee, 12, 31), float(derniere.valeur_fin)))
    return flux


def _situation_datee(bilan: BilanContrat) -> bool:
    return not bilan.annees and bilan.date_ouverture is not None and bilan.apports_cumules is not None


def taux_rendement_interne(flux: list[tuple[date, float]]) -> float | None:
    """Rendre le taux annuel r qui annule Σ montant / (1 + r)^(années depuis le premier flux), ou None.

    Versements négatifs, valeur finale positive. Dichotomie : la valeur actuelle décroît quand r augmente.
    """
    origine = min(d for d, _ in flux)

    def valeur_actuelle(taux: float) -> float:
        return sum(montant / (1 + taux) ** ((d - origine).days / 365.25) for d, montant in flux)

    bas, haut = TAUX_MIN, TAUX_MAX
    if valeur_actuelle(bas) * valeur_actuelle(haut) > 0:
        return None
    for _ in range(ITERATIONS):
        milieu = (bas + haut) / 2
        if valeur_actuelle(bas) * valeur_actuelle(milieu) <= 0:
            haut = milieu
        else:
            bas = milieu
    return (bas + haut) / 2

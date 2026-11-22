"""Bilan par contrat : année par année et depuis l'origine. Formules : docs/MODELE.md."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from metabank.releves import ReleveRange
from metabank.releves.modele import Releve

ZERO = Decimal(0)


@dataclass(frozen=True)
class Annee:
    """Résultat d'une année civile d'un contrat (relevé annuel)."""

    annee: int
    valeur_debut: Decimal
    apports: Decimal
    rachats: Decimal
    valeur_fin: Decimal
    gain: Decimal
    frais: Decimal | None
    rendement: Decimal | None
    rendement_avant_frais: Decimal | None
    frais_sur_encours: Decimal | None


@dataclass(frozen=True)
class BilanContrat:
    """Bilan d'un contrat : années, cumul depuis l'origine connue, anomalies."""

    titulaire: str
    assureur: str
    produit: str
    numero: str
    type_contrat: str
    date_valeur: date
    valeur: Decimal
    annees: tuple[Annee, ...]
    apports_cumules: Decimal | None
    rachats_cumules: Decimal
    gain_cumule: Decimal | None
    frais_cumules: Decimal | None
    anomalies: tuple[str, ...] = field(default=())

    @property
    def numero_masque(self) -> str:
        """Rendre « …9974 » : de quoi reconnaître le contrat sans exposer le numéro."""
        return "…" + self.numero.replace(" ", "")[-4:]


def faire_bilans(releves: list[ReleveRange]) -> list[BilanContrat]:
    """Rendre un bilan par contrat (titulaire, numéro), à partir de tous ses relevés."""
    par_contrat: dict[tuple[str, str], list[Releve]] = {}
    for range_ in releves:
        par_contrat.setdefault((range_.titulaire, range_.releve.numero), []).append(range_.releve)
    return [
        _bilan_contrat(titulaire, sorted(liste, key=lambda r: r.date_arrete))
        for (titulaire, _), liste in sorted(par_contrat.items())
    ]


def calculer_annee(releve: Releve, valeur_debut: Decimal) -> Annee:
    """Rendre le résultat de l'année d'un relevé annuel. MODELE § 1."""
    mouvements = releve.mouvements
    apports, rachats = mouvements.versements_bruts, mouvements.rachats
    gain = releve.valeur - valeur_debut - apports + rachats
    frais = releve.frais.total if releve.frais else None
    # Date d'ouverture inconnue la première année : un rendement sur une durée inconnue ne voudrait rien dire.
    base = valeur_debut + (apports - rachats) / 2 if valeur_debut > ZERO else None
    encours_moyen = (valeur_debut + releve.valeur) / 2 if valeur_debut > ZERO else None
    return Annee(
        annee=releve.date_arrete.year,
        valeur_debut=valeur_debut,
        apports=apports,
        rachats=rachats,
        valeur_fin=releve.valeur,
        gain=gain,
        frais=frais,
        rendement=gain / base if base else None,
        rendement_avant_frais=(gain + frais) / base if base and frais is not None else None,
        frais_sur_encours=frais / encours_moyen if encours_moyen and frais is not None else None,
    )


def _bilan_contrat(titulaire: str, releves: list[Releve]) -> BilanContrat:
    anomalies = [anomalie for releve in releves for anomalie in releve.anomalies]
    annees = _annees(releves, anomalies)
    dernier = releves[-1]
    if annees:
        apports = sum((a.apports for a in annees), ZERO)
        rachats = sum((a.rachats for a in annees), ZERO)
        frais = sum((a.frais for a in annees if a.frais is not None), ZERO)
        gain = annees[-1].valeur_fin - apports + rachats
        if annees[0].valeur_debut > ZERO:
            anomalies.append(f"cumul depuis {annees[0].annee} seulement : relevés antérieurs absents")
            gain -= annees[0].valeur_debut
    else:
        # Relevé de situation seul : cumul depuis l'origine tel que donné par l'assureur. MODELE § 2.
        apports = dernier.versements_bruts_depuis_origine
        rachats = dernier.rachats_depuis_origine or ZERO
        gain = dernier.valeur - apports + rachats if apports is not None else None
        frais = None
    return BilanContrat(
        titulaire=titulaire,
        assureur=dernier.assureur,
        produit=dernier.produit,
        numero=dernier.numero,
        type_contrat=dernier.type_contrat,
        date_valeur=dernier.date_arrete,
        valeur=dernier.valeur,
        annees=tuple(annees),
        apports_cumules=apports,
        rachats_cumules=rachats,
        gain_cumule=gain,
        frais_cumules=frais,
        anomalies=tuple(anomalies),
    )


def _annees(releves: list[Releve], anomalies: list[str]) -> list[Annee]:
    annees: list[Annee] = []
    for releve in (r for r in releves if r.est_annuel):
        precedente = annees[-1].valeur_fin if annees else None
        if annees and releve.date_arrete.year != annees[-1].annee + 1:
            anomalies.append(f"relevé {annees[-1].annee + 1} absent : années non contiguës")
        if (
            precedente is not None
            and releve.valeur_precedente is not None
            and abs(precedente - releve.valeur_precedente) > Decimal("0.01")
        ):
            anomalies.append(
                f"{releve.date_arrete.year} : valeur de début {releve.valeur_precedente} € "
                f"≠ valeur de fin du relevé précédent {precedente} €"
            )
        debut = releve.valeur_precedente if releve.valeur_precedente is not None else (precedente or ZERO)
        annees.append(calculer_annee(releve, debut))
    return annees

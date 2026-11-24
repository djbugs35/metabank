"""Bilan par contrat : année par année et depuis l'origine. Formules : docs/MODELE.md."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from metabank.corrections import date_ouverture
from metabank.releves import ReleveRange
from metabank.releves.modele import Releve, cle_du_contrat

ZERO = Decimal(0)
MILIEU = Decimal("0.5")


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
    # Part de l'année où les versements ont travaillé (0,5 = milieu d'année) ; estimée si l'ouverture est inconnue.
    poids_versements: Decimal = Decimal("0.5")
    poids_estime: bool = False
    # Année d'ouverture : nombre de mois de placement (le rendement porte sur cette durée) ; None = année entière.
    duree_mois: int | None = None
    # Année en cours, d'après une situation : sa date (MODELE § 2.4) ; None = année close au 31/12.
    en_cours_au: date | None = None


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
    date_ouverture: date | None = None
    # Versé refait par les mouvements des années (euros), contrôle du versé lu ; None s'il ne se refait pas. § 2.3.
    verse_mouvements: Decimal | None = None

    @property
    def numero_masque(self) -> str:
        """Rendre « …9974 » : de quoi reconnaître le contrat sans exposer le numéro."""
        return "…" + self.numero.replace(" ", "")[-4:]


def faire_bilans(releves: list[ReleveRange], ouvertures: dict[str, date] | None = None) -> list[BilanContrat]:
    """Rendre un bilan par contrat (titulaire, numéro), à partir de tous ses relevés.

    Args:
        ouvertures: dates d'ouverture par numéro de contrat (data/corrections.json), pour l'année d'ouverture.
    """
    par_contrat: dict[tuple[str, str], list[Releve]] = {}
    for range_ in releves:
        par_contrat.setdefault((range_.titulaire, cle_du_contrat(range_.releve.numero)), []).append(range_.releve)
    return [
        # Date d'ouverture cherchée sur le numéro complet des relevés : une clé de Corrections peut être plus longue
        # que le dernier groupe (« U212345678 »).
        _bilan_contrat(
            titulaire,
            sorted(liste, key=lambda r: r.date_arrete),
            next((d for r in liste if (d := date_ouverture(r.numero, ouvertures or {}))), None),
        )
        for (titulaire, _), liste in sorted(par_contrat.items())
    ]


def calculer_annee(releve: Releve, valeur_debut: Decimal, ouverture: date | None = None) -> Annee:
    """Rendre le résultat de l'année d'un relevé annuel. MODELE § 1."""
    mouvements = releve.mouvements
    if mouvements is None:
        raise ValueError(f"{releve.fichier} : relevé sans synthèse des mouvements, pas un relevé annuel")
    apports, rachats = mouvements.versements_bruts, mouvements.rachats
    gain = releve.valeur - valeur_debut - apports + rachats
    frais = releve.frais.total if releve.frais else None
    poids, estime = _poids_versements(releve.date_arrete, valeur_debut, ouverture)
    # Année d'ouverture : rendement réel sur la période (gain / versé), pas ramené à une année entière.
    ouverture_annee = valeur_debut == ZERO
    capital = (apports - rachats) if ouverture_annee else valeur_debut + (apports - rachats) * poids
    base = capital if capital > ZERO else None
    encours_moyen = (valeur_debut + releve.valeur) / 2 if valeur_debut > ZERO else releve.valeur * poids
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
        poids_versements=poids,
        poids_estime=estime,
        duree_mois=_mois_jusqu_a(ouverture, releve.date_arrete) if ouverture_annee and ouverture else None,
    )


def _mois_jusqu_a(debut: date, fin: date) -> int:
    """Rendre le nombre de mois entamés entre debut et fin (30/07 -> 31/12 : 5 mois)."""
    return max(1, round((fin - debut).days / 30.44))


def _poids_versements(fin_annee: date, valeur_debut: Decimal, ouverture: date | None) -> tuple[Decimal, bool]:
    """Rendre la part de l'année où les versements ont travaillé, et si elle est supposée. MODELE § 1.2.

    L'année d'ouverture, les versements datent au plus tôt de l'ouverture : on les place à cette date.
    Sinon, faute de dates dans les relevés, au milieu de l'année.
    """
    if valeur_debut > ZERO:
        return MILIEU, False
    if ouverture is not None and ouverture.year == fin_annee.year:
        return Decimal((fin_annee - ouverture).days) / Decimal(365), False
    return MILIEU, True


def _bilan_contrat(titulaire: str, releves: list[Releve], ouverture: date | None) -> BilanContrat:
    anomalies = [anomalie for releve in releves for anomalie in releve.anomalies]
    annees = _annees(releves, anomalies, ouverture)
    en_cours = _annee_en_cours(releves, annees)
    annees_affichees = [*annees, en_cours] if en_cours else annees
    dernier = releves[-1]
    apports: Decimal | None
    gain: Decimal | None
    frais: Decimal | None
    verse_mouvements = None
    if annees and not dernier.est_annuel and dernier.versements_bruts_depuis_origine is not None:
        # Relevés annuels suivis d'une situation : versé et valeur lus sur la situation. MODELE § 2.3.
        apports = dernier.versements_bruts_depuis_origine
        rachats = dernier.rachats_depuis_origine or ZERO
        gain = dernier.valeur - apports + rachats
        frais = sum((a.frais for a in annees_affichees if a.frais is not None), ZERO)
        if en_cours is not None and annees[0].valeur_debut == ZERO:
            # Contrôle : le même versé refait par les mouvements de chaque année, depuis l'ouverture.
            verse_mouvements = sum((a.apports for a in annees_affichees), ZERO)
            _comparer_au_cumul_de_l_assureur(apports, verse_mouvements, anomalies)
    elif annees:
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
        annees=tuple(annees_affichees),
        apports_cumules=apports,
        rachats_cumules=rachats,
        gain_cumule=gain,
        frais_cumules=frais,
        anomalies=tuple(anomalies),
        date_ouverture=ouverture,
        verse_mouvements=verse_mouvements,
    )


ECART_CUMUL_TOLERE = Decimal(1)


def _comparer_au_cumul_de_l_assureur(lu: Decimal, mouvements: Decimal, anomalies: list[str]) -> None:
    """Signaler un versé lu sur le document qui diffère du versé refait par les mouvements. MODELE § 2.3."""
    if abs(lu - mouvements) > ECART_CUMUL_TOLERE:
        anomalies.append(
            f"versé {lu} € d'après le document, {mouvements} € d'après les mouvements (écart {lu - mouvements} €)"
        )


def _annees(releves: list[Releve], anomalies: list[str], ouverture: date | None) -> list[Annee]:
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
        annees.append(calculer_annee(releve, debut, ouverture))
    return annees


def _annee_en_cours(releves: list[Releve], annees: list[Annee]) -> Annee | None:
    """Rendre l'année en cours d'après une situation postérieure au dernier relevé annuel, ou None. MODELE § 2.4."""
    situation = releves[-1]
    annuels = [r for r in releves if r.est_annuel]
    if situation.est_annuel or not annees or not annuels:
        return None
    dernier = annuels[-1]
    if situation.date_arrete.year != dernier.date_arrete.year + 1:
        return None
    if situation.versements_annee_en_cours is None:
        return None
    debut = annees[-1].valeur_fin
    apports, rachats = situation.versements_annee_en_cours, situation.rachats_annee_en_cours or ZERO
    gain = situation.valeur - debut - apports + rachats
    base = debut + (apports - rachats) * MILIEU
    return Annee(annee=situation.date_arrete.year, valeur_debut=debut, apports=apports, rachats=rachats,
                 valeur_fin=situation.valeur, gain=gain, frais=situation.frais_annee_en_cours,
                 rendement=gain / base if base > ZERO else None,
                 rendement_avant_frais=None, frais_sur_encours=None, poids_versements=MILIEU, poids_estime=True,
                 duree_mois=situation.date_arrete.month, en_cours_au=situation.date_arrete)  # fmt: skip

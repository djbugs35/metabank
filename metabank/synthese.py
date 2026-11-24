"""Synthèse sur un ensemble de contrats (foyer, personne, contrat) : versements, rentabilité et frais. MODELE § 6."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from metabank.bilan import BilanContrat
from metabank.corrections import ANOMALIE_VERSEMENTS
from metabank.frais_historique import HistoriqueFrais
from metabank.rapport import nom_contrat
from metabank.releves.modele import cle_du_contrat

ZERO = Decimal(0)
# Au-delà de 25 % du capital de début, la date des versements change le rendement de plus d'un quart.
SEUIL_VERSEMENTS = Decimal("0.25")
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
    rendement_min: Decimal | None = None
    rendement_max: Decimal | None = None
    duree_mois: int | None = None
    en_cours_au: date | None = None
    capital: Decimal | None = None
    # MODELE § 6.4, en euros : valeurs de début et de fin de l'année, rachats de l'année.
    valeur_debut: Decimal = ZERO
    valeur_fin: Decimal = ZERO
    rachats: Decimal = ZERO

    @property
    def rendement_frais(self) -> Decimal | None:
        """Rendre les frais de l'année rapportés au même capital que le gain."""
        return self.frais / self.capital if self.capital else None

    @property
    def approximatif(self) -> bool:
        """Rendre vrai si la date inconnue des versements de l'année change sensiblement le rendement."""
        return self.rendement_min is not None

    @property
    def frais(self) -> Decimal:
        """Rendre frais du relevé + frais des fonds."""
        return self.frais_releve + self.frais_fonds


@dataclass(frozen=True)
class Progression:
    """Une fin d'année : valeur, variation, versé net et gagné cumulés (euros). MODELE § 6.4."""

    annee: int
    valeur: Decimal
    variation: Decimal
    verse_cumule: Decimal
    gain_cumule: Decimal
    en_cours_au: date | None
    verse_net_annee: Decimal = ZERO
    gain_annee: Decimal = ZERO


@dataclass(frozen=True)
class ChiffresAnnee:
    """Une année d'une ligne du tableau par contrat, en euros. MODELE § 6.5."""

    verse: Decimal
    gain_avant_frais: Decimal
    frais: Decimal
    gain: Decimal
    # Valeur au 31/12, ou à la date de la situation pour l'année en cours.
    valeur: Decimal = ZERO


@dataclass(frozen=True)
class LigneContrats:
    """Une ligne du tableau : un contrat, le cumul d'une personne (« personne ») ou le total (« total »)."""

    nom: str
    niveau: str
    annees: dict[int, ChiffresAnnee]
    # Valeur au dernier relevé ou à la dernière situation (euros) : l'argent qui y est aujourd'hui.
    valeur_actuelle: Decimal = ZERO
    # Depuis l'ouverture (euros), MODELE § 6.5. Document (fait foi) : versé, gagné. Opérations (contrôle) : versé,
    # gain hors frais, frais et gagné des années ; None quand elles ne se refont pas. Écarts : document moins opérations.
    verse: Decimal = ZERO
    gain: Decimal = ZERO
    verse_operations: Decimal | None = None
    gain_avant_frais: Decimal | None = None
    frais: Decimal | None = None
    gain_operations: Decimal | None = None
    ecart_verse: Decimal | None = None
    ecart_gain: Decimal | None = None


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
    # Versé lu moins versé refait par les mouvements, sur les contrats où les deux existent (euros). MODELE § 2.3.
    ecart_verse: Decimal = ZERO
    progression: tuple[Progression, ...] = ()
    # Valeur des contrats sans historique annuel (situation seule), absents de la progression (euros).
    valeur_sans_historique: Decimal = ZERO
    verse_sans_historique: Decimal = ZERO
    gain_sans_historique: Decimal = ZERO
    tableau: tuple[LigneContrats, ...] = ()

    @property
    def frais_par_an(self) -> Decimal | None:
        """Rendre les frais cumulés rapportés aux sommes placées chaque année (taux moyen annuel)."""
        capital = sum((a.capital for a in self.annees if a.capital), ZERO)
        return self.frais_cumules / capital if capital else None


def synthetiser(nom: str, bilans: list[BilanContrat], historiques: list[HistoriqueFrais]) -> Synthese:
    """Rendre la synthèse des contrats donnés."""
    frais_fonds = {
        (h.titulaire, cle_du_contrat(h.numero), a.annee): a.frais_fonds for h in historiques for a in h.annees
    }
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
        versements_incertains=any(ANOMALIE_VERSEMENTS in a for b in bilans for a in b.anomalies),
        progression=tuple(progresser(suivis, annees)),
        tableau=tuple(tableau_par_contrat(bilans, frais_fonds)),
        valeur_sans_historique=sum((b.valeur for b in bilans if not b.annees), ZERO),
        verse_sans_historique=sum((b.apports_cumules or ZERO for b in bilans if not b.annees), ZERO),
        gain_sans_historique=sum((b.gain_cumule or ZERO for b in bilans if not b.annees), ZERO),
        ecart_verse=sum((b.apports_cumules - b.verse_mouvements for b in bilans
                         if b.apports_cumules is not None and b.verse_mouvements is not None), ZERO),
    )  # fmt: skip


def _annee(annee: int, bilans: list[BilanContrat], frais_fonds: dict) -> AnneeSynthese:
    """Rendre l'année sommée sur les contrats. MODELE § 6.1.

    Rendement réel de l'année : gain / capital engagé. Un contrat ouvert dans l'année compte pour son versé
    (rendement sur sa durée de placement) ; ailleurs, les versements sont supposés en milieu d'année, et si leur date
    pèse (versements > 25 % du capital de début), la fourchette « tout en janvier / tout en décembre » est donnée.
    """
    lignes = [(b, a) for b in bilans for a in b.annees if a.annee == annee]
    debut = sum((a.valeur_debut for _, a in lignes), ZERO)
    gain = sum((a.gain for _, a in lignes), ZERO)
    flux_ouverture = sum((a.apports - a.rachats for _, a in lignes if a.valeur_debut == 0), ZERO)
    flux_courant = sum((a.apports - a.rachats for _, a in lignes if a.valeur_debut > 0), ZERO)
    fixe = debut + flux_ouverture
    rendement_min = rendement_max = None
    if debut > 0 and abs(flux_courant) > debut * SEUIL_VERSEMENTS:
        bornes = sorted(gain / base for base in (fixe + flux_courant, fixe) if base > 0)
        rendement_min, rendement_max = bornes[0], bornes[-1]
    durees = {a.duree_mois for _, a in lignes}
    return AnneeSynthese(
        annee=annee,
        verse=sum((a.apports for _, a in lignes), ZERO),
        gain=gain,
        frais_releve=sum((a.frais or ZERO for _, a in lignes), ZERO),
        frais_fonds=sum(
            (frais_fonds.get((b.titulaire, cle_du_contrat(b.numero), annee), ZERO) for b, _ in lignes), ZERO
        ),
        rendement=_division(gain, fixe + flux_courant / 2),
        capital=fixe + flux_courant / 2 if fixe + flux_courant / 2 > 0 else None,
        ouverture_dans_l_annee=any(a.poids_estime for _, a in lignes),
        rendement_min=rendement_min,
        rendement_max=rendement_max,
        duree_mois=durees.pop() if len(durees) == 1 else None,
        en_cours_au=max((a.en_cours_au for _, a in lignes if a.en_cours_au), default=None),
        valeur_debut=debut,
        valeur_fin=sum((a.valeur_fin for _, a in lignes), ZERO),
        rachats=sum((a.rachats for _, a in lignes), ZERO),
    )


def progresser(bilans: list[BilanContrat], annees: tuple[AnneeSynthese, ...]) -> list[Progression]:
    """Rendre la valeur des placements fin d'année par fin d'année, et ce qui l'a fait varier. MODELE § 6.4.

    Un contrat sans chiffres une année (pas encore de situation pour l'année en cours) y garde sa dernière valeur
    connue, sans flux ni gain : il ne sort pas de la barre.
    """
    suivis = [b for b in bilans if b.annees]
    precedente = sum((b.annees[0].valeur_debut for b in suivis), ZERO)
    resultat = []
    for a in annees:
        connues = [[x for x in b.annees if x.annee <= a.annee] for b in suivis]
        valeur = sum((faites[-1].valeur_fin for faites in connues if faites), ZERO)
        # Valeur de départ d'un contrat antérieur à ses relevés : comptée comme du versé, l'origine étant inconnue.
        verse = sum((faites[0].valeur_debut + sum((x.apports - x.rachats for x in faites), ZERO)
                     for faites in connues if faites), ZERO)  # fmt: skip
        resultat.append(Progression(a.annee, valeur, valeur - precedente, verse, valeur - verse, a.en_cours_au,
                                    a.verse - a.rachats, a.gain))  # fmt: skip
        precedente = valeur
    return resultat


def tableau_par_contrat(bilans: list[BilanContrat], frais_fonds: dict) -> list[LigneContrats]:
    """Rendre une ligne par contrat, le cumul de chaque personne (s'il y en a plusieurs) et le total. MODELE § 6.5.

    Un contrat à situation seule a une ligne sans années, avec sa seule valeur actuelle : le total retombe sur la
    valeur de l'ensemble.

    Args:
        frais_fonds: frais des fonds par (titulaire, contrat, année), en euros, comme pour l'année du foyer (§ 6.1).
    """
    contrats = []
    for b in sorted(bilans, key=lambda b: (b.titulaire, nom_contrat(b))):
        annees = {}
        for a in b.annees:
            frais = (a.frais or ZERO) + frais_fonds.get((b.titulaire, cle_du_contrat(b.numero), a.annee), ZERO)
            annees[a.annee] = ChiffresAnnee(a.apports, a.gain + frais, frais, a.gain, a.valeur_fin)
        verse, gain = b.apports_cumules or ZERO, b.gain_cumule or ZERO
        refait = b.verse_mouvements is not None and b.gain_operations is not None
        contrats.append((b.titulaire, LigneContrats(
            nom_contrat(b), "contrat", annees, b.valeur, verse, gain, b.verse_mouvements,
            sum((c.gain_avant_frais for c in annees.values()), ZERO) if refait else None,
            sum((c.frais for c in annees.values()), ZERO) if refait else None, b.gain_operations,
            verse - b.verse_mouvements if b.verse_mouvements is not None else None,
            gain - b.gain_operations if b.gain_operations is not None else None,
        )))  # fmt: skip
    lignes: list[LigneContrats] = []
    titulaires = list(dict.fromkeys(t for t, _ in contrats))
    for titulaire in titulaires:
        siens = [ligne for t, ligne in contrats if t == titulaire]
        lignes += siens
        if len(titulaires) > 1:
            lignes.append(_sommer(f"Total {titulaire}", "personne", siens))
    return [*lignes, _sommer("Total", "total", [ligne for _, ligne in contrats])] if contrats else []


def _sommer(nom: str, niveau: str, lignes: list[LigneContrats]) -> LigneContrats:
    def somme(annee: int, champ: str) -> Decimal:
        return sum((getattr(ligne.annees[annee], champ) for ligne in lignes if annee in ligne.annees), ZERO)

    annees = sorted({an for ligne in lignes for an in ligne.annees})
    sommes = {an: ChiffresAnnee(somme(an, "verse"), somme(an, "gain_avant_frais"), somme(an, "frais"), somme(an, "gain"),
                                sum((_valeur_en(ligne, an) for ligne in lignes), ZERO)) for an in annees}  # fmt: skip

    def total(champ: str) -> Decimal:
        return sum((getattr(ligne, champ) or ZERO for ligne in lignes), ZERO)

    def controle(champ: str) -> Decimal | None:
        valeurs = [getattr(ligne, champ) for ligne in lignes if getattr(ligne, champ) is not None]
        return sum(valeurs, ZERO) if valeurs else None

    return LigneContrats(nom, niveau, sommes, total("valeur_actuelle"), total("verse"), total("gain"),
                         *(controle(c) for c in ("verse_operations", "gain_avant_frais", "frais", "gain_operations",
                                                 "ecart_verse", "ecart_gain")))  # fmt: skip


def _valeur_en(ligne: LigneContrats, annee: int) -> Decimal:
    """Rendre la valeur du contrat en fin d'année : sa dernière connue (§ 6.4), 0 avant ses relevés."""
    connues = [an for an in ligne.annees if an <= annee]
    return ligne.annees[max(connues)].valeur if connues else ZERO


def _division(numerateur: Decimal, base: Decimal) -> Decimal | None:
    return numerateur / base if base > 0 else None


def _rendement_annualise(bilans: list[BilanContrat]) -> Decimal | None:
    """Rendre le taux de rendement interne annualisé depuis l'ouverture. MODELE § 6.2."""
    flux: list[tuple[date, float]] = []
    for bilan in bilans:
        if bilan.annees:
            flux += _flux_annuels(bilan)
        elif bilan.date_ouverture is not None and bilan.apports_cumules is not None and not bilan.annees:
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
    if bilan.apports_cumules is not None and bilan.verse_mouvements is not None:
        # Même versé que le gain affiché : l'écart (versé lu moins mouvements) est supposé versé à l'ouverture, seule
        # date sûre ; le taux est alors un minimum, comme pour une situation seule. MODELE § 6.2.
        debut_connu = bilan.date_ouverture or date(premiere.annee, 1, 1)
        flux.append((debut_connu, -float(bilan.apports_cumules - bilan.verse_mouvements)))
    for annee in bilan.annees:
        ouverture = bilan.date_ouverture
        jour = ouverture if annee.valeur_debut == 0 and ouverture and ouverture.year == annee.annee else None
        if annee.en_cours_au is not None:
            # Année en cours (MODELE § 2.4) : versements au milieu de la période, pas au 1er juillet.
            debut = date(annee.annee, 1, 1)
            jour = jour or debut + (annee.en_cours_au - debut) / 2
        flux.append((jour or date(annee.annee, 7, 1), -float(annee.apports - annee.rachats)))
    flux.append((derniere.en_cours_au or date(derniere.annee, 12, 31), float(derniere.valeur_fin)))
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

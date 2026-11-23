"""Projection retraite depuis la page : saisie validée, contrats du titulaire, trois scénarios. MODELE § 12."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from metabank.bilan import faire_bilans
from metabank.corrections import appliquer_verifications, lire_ouvertures
from metabank.donnees import charger
from metabank.retraite import mois_jusqu_au_depart, projeter

TYPES_RETRAITE = ("per", "perp")


def _nombre(saisie: dict, cle: str, mini: Decimal, maxi: Decimal) -> Decimal:
    try:
        valeur = Decimal(str(saisie.get(cle, "")))
    except InvalidOperation as erreur:
        raise ValueError(f"{cle} : nombre attendu") from erreur
    if not mini <= valeur <= maxi:
        raise ValueError(f"{cle} : entre {mini} et {maxi}")
    return valeur


def simuler_retraite(dossier: Path, saisie: dict, aujourd_hui: date | None = None) -> dict:
    """Rendre le capital actuel retenu et les trois scénarios (euros ; taux saisis en %). MODELE § 12.

    Args:
        saisie: titulaire, annee_depart, versement (€/mois), inflation (%), duree_retrait (ans), rendements (trois, en %),
            inclure_av (booléen).

    Raises:
        ValueError: saisie hors bornes, ou titulaire sans contrat retenu.
    """
    aujourd_hui = aujourd_hui or datetime.now().astimezone().date()
    annee = int(_nombre(saisie, "annee_depart", Decimal(aujourd_hui.year), Decimal(aujourd_hui.year + 60)))
    versement = _nombre(saisie, "versement", Decimal(0), Decimal(100000))
    inflation = _nombre(saisie, "inflation", Decimal(-5), Decimal(20)) / 100
    duree = int(_nombre(saisie, "duree_retrait", Decimal(1), Decimal(50)))
    rendements = saisie.get("rendements") or []
    if not isinstance(rendements, list) or len(rendements) != 3:
        raise ValueError("trois rendements attendus")
    taux = [_nombre({"rendement": r}, "rendement", Decimal(-10), Decimal(20)) / 100 for r in rendements]
    types = (*TYPES_RETRAITE, "assurance_vie") if saisie.get("inclure_av") else TYPES_RETRAITE
    donnees = charger(dossier)
    bilans = faire_bilans(appliquer_verifications(donnees.releves, dossier), lire_ouvertures(dossier))
    retenus = [b for b in bilans if b.titulaire == saisie.get("titulaire") and b.type_contrat in types]
    if not retenus:
        raise ValueError("aucun PER ou PERP pour ce titulaire (cochez les assurances vie pour les compter)")
    capital = sum((b.valeur for b in retenus), Decimal(0))
    mois = mois_jusqu_au_depart(aujourd_hui, annee)
    scenarios = [projeter(capital, versement, mois, t, inflation, duree) for t in taux]
    return {
        "capital_actuel": round(float(capital), 2),
        "contrats": [f"{b.produit} {b.numero_masque}" for b in retenus],
        "mois": mois,
        "scenarios": [
            {
                "rendement": float(s.rendement),
                "capital": round(float(s.capital), 2),
                "capital_reel": round(float(s.capital_reel), 2),
                "retrait_mensuel": round(float(s.retrait_mensuel), 2),
            }
            for s in scenarios
        ],
    }

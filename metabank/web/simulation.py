"""Simulation de frais pour la page : deux projections côte à côte, frais actuels et frais visés. MODELE § 4.3."""

from decimal import Decimal, InvalidOperation

from metabank.frais import projeter

HORIZON_MAX = 40
TAUX_MAX = Decimal(30)


class SimulationInvalide(ValueError):
    """Paramètre de simulation hors bornes : le message dit lequel."""


def simuler(parametres: dict) -> dict:
    """Rendre les valeurs année par année avec les frais actuels et avec les frais visés, et l'écart final.

    Args:
        parametres: « valeur » en euros, « rendement_brut », « frais_actuels » et « frais_vises » en points
            (5 = 5 % par an), « horizon » en années.

    Raises:
        SimulationInvalide: paramètre absent, négatif ou hors bornes.
    """
    valeur = _decimal(parametres, "valeur", Decimal(0), Decimal(10**9))
    rendement = _decimal(parametres, "rendement_brut", -TAUX_MAX, TAUX_MAX)
    actuels = _decimal(parametres, "frais_actuels", Decimal(0), TAUX_MAX)
    vises = _decimal(parametres, "frais_vises", Decimal(0), TAUX_MAX)
    horizon = parametres.get("horizon")
    if not isinstance(horizon, int) or not 1 <= horizon <= HORIZON_MAX:
        raise SimulationInvalide(f"horizon : entre 1 et {HORIZON_MAX} ans")
    serie_actuelle = [projeter(valeur, rendement, actuels, annee) for annee in range(horizon + 1)]
    serie_visee = [projeter(valeur, rendement, vises, annee) for annee in range(horizon + 1)]
    ecart = serie_visee[-1] - serie_actuelle[-1]
    return {
        "annees": list(range(horizon + 1)),
        "frais_actuels": [round(float(v), 2) for v in serie_actuelle],
        "frais_vises": [round(float(v), 2) for v in serie_visee],
        "ecart": round(float(ecart), 2),
        "ecart_taux": round(float(ecart / serie_actuelle[-1]), 6) if serie_actuelle[-1] else None,
        "frais_payes_actuels": round(float(_frais_payes(valeur, rendement, actuels, horizon)), 2),
        "frais_payes_vises": round(float(_frais_payes(valeur, rendement, vises, horizon)), 2),
    }


def _frais_payes(valeur: Decimal, rendement: Decimal, taux_frais: Decimal, horizon: int) -> Decimal:
    """Rendre la somme des frais prélevés chaque année : taux de frais fois valeur en début d'année."""
    return sum(
        (projeter(valeur, rendement, taux_frais, annee) * taux_frais / 100 for annee in range(horizon)), Decimal(0)
    )


def _decimal(parametres: dict, nom: str, minimum: Decimal, maximum: Decimal) -> Decimal:
    try:
        nombre = Decimal(str(parametres[nom]))
    except (KeyError, InvalidOperation) as erreur:
        raise SimulationInvalide(f"{nom} : nombre attendu") from erreur
    if not minimum <= nombre <= maximum:
        raise SimulationInvalide(f"{nom} : entre {minimum} et {maximum}")
    return nombre

"""Fraîcheur d'un compte : sa dernière donnée face à la fréquence de mise à jour attendue. MODELE § 9."""

from datetime import date

A_JOUR = "a_jour"
EN_RETARD = "en_retard"
TRES_EN_RETARD = "tres_en_retard"
JAMAIS = "jamais"


def evaluer_fraicheur(derniere_donnee: date | None, frequence_jours: int | None, aujourd_hui: date) -> str:
    """Rendre A_JOUR, EN_RETARD, TRES_EN_RETARD ou JAMAIS. MODELE § 9.

    Args:
        derniere_donnee: date la plus récente des données du compte (solde, opération, relevé), pas celle de l'import.
        frequence_jours: fréquence attendue, en jours ; None = inconnue (le compte est à jour dès qu'il a une donnée).
    """
    if derniere_donnee is None:
        return JAMAIS
    if frequence_jours is None:
        return A_JOUR
    age = (aujourd_hui - derniere_donnee).days
    if age <= frequence_jours:
        return A_JOUR
    return EN_RETARD if age <= 2 * frequence_jours else TRES_EN_RETARD

"""Mise en forme du bilan : texte pour le terminal, JSON pour les étapes suivantes (Wealthfolio, rapport IA)."""

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from metabank.bilan import BilanContrat

LIBELLES_TYPES = {"assurance_vie": "Assurance vie", "per": "PER", "perp": "PERP", "pea": "PEA", "cto": "CTO"}


def euros(montant: Decimal | None) -> str:
    """Rendre « 101 348 € » (arrondi à l'euro, espace fine insécable entre milliers), ou « — »."""
    if montant is None:
        return "—"
    return f"{montant:,.0f} €".replace(",", "\u202f")


def pourcent(taux: Decimal | None) -> str:
    """Rendre « 1,7 % » pour 0.017, ou « — »."""
    return "—" if taux is None else f"{taux * 100:.1f} %".replace(".", ",")


def formater_texte(bilans: list[BilanContrat], erreurs: list[str]) -> str:
    """Rendre le bilan lisible : un bloc par contrat, puis le total par titulaire et pour le foyer."""
    blocs = [_formater_contrat(bilan) for bilan in bilans]
    blocs.append(_formater_totaux(bilans))
    if erreurs:
        blocs.append("Fichiers non lus :\n" + "\n".join(f"  - {erreur}" for erreur in erreurs))
    return "\n\n".join(blocs)


def _formater_contrat(bilan: BilanContrat) -> str:
    titre = (
        f"{bilan.titulaire} — {LIBELLES_TYPES.get(bilan.type_contrat, bilan.type_contrat)} "
        f"{bilan.produit} ({bilan.assureur} {bilan.numero_masque})"
    )
    lignes = [titre, "-" * len(titre)]
    if bilan.annees:
        lignes.append(
            f"{'Année':<6}{'Versé':>11}{'Valeur fin':>13}{'Gain':>10}{'Rendement':>11}{'Frais':>9}{'Frais/encours':>15}"
        )
        lignes.extend(
            f"{a.annee:<6}{euros(a.apports):>11}{euros(a.valeur_fin):>13}{euros(a.gain):>10}"
            f"{pourcent(a.rendement):>11}{euros(a.frais):>9}{pourcent(a.frais_sur_encours):>15}"
            for a in bilan.annees
        )
    lignes.append(
        f"Depuis l'origine : versé {euros(bilan.apports_cumules)}, valeur {euros(bilan.valeur)} "
        f"au {bilan.date_valeur:%d/%m/%Y}, gain {euros(bilan.gain_cumule)}, frais {euros(bilan.frais_cumules)}"
    )
    if not bilan.annees:
        lignes.append("Relevé de situation seul : ni historique ni frais (déposer les relevés annuels).")
    lignes += [f"  ⚠ {anomalie}" for anomalie in bilan.anomalies]
    return "\n".join(lignes)


def _formater_totaux(bilans: list[BilanContrat]) -> str:
    lignes = ["Totaux (dernière valeur connue de chaque contrat)"]
    lignes.extend(
        _ligne_total(titulaire, [b for b in bilans if b.titulaire == titulaire])
        for titulaire in sorted({bilan.titulaire for bilan in bilans})
    )
    lignes.append(_ligne_total("Foyer", bilans))
    return "\n".join(lignes)


def _ligne_total(nom: str, bilans: list[BilanContrat]) -> str:
    valeur = sum((b.valeur for b in bilans), Decimal(0))
    verse = sum((b.apports_cumules or Decimal(0) for b in bilans), Decimal(0))
    frais = sum((b.frais_cumules or Decimal(0) for b in bilans), Decimal(0))
    return f"  {nom:<10} valeur {euros(valeur):>11}   versé {euros(verse):>11}   frais connus {euros(frais):>9}"


def en_json(bilans: list[BilanContrat]) -> str:
    """Rendre le bilan en JSON : montants en texte (exacts), dates ISO, numéros masqués."""

    def convertir(valeur):
        if isinstance(valeur, Decimal):
            return str(valeur)
        if isinstance(valeur, date):
            return valeur.isoformat()
        raise TypeError(type(valeur).__name__)

    contenu = []
    for bilan in bilans:
        donnees = asdict(bilan)
        donnees["numero"] = bilan.numero_masque
        contenu.append(donnees)
    return json.dumps(contenu, ensure_ascii=False, indent=2, default=convertir)

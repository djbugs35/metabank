"""Onglet Synoptique : une ligne par compte, de sa source jusqu'aux écrans, et ce qui sort de la machine. MODELE § 9."""

from datetime import date, datetime, timedelta
from pathlib import Path

from metabank.base.integration import ouvrir_base
from metabank.base.journal import EntreeJournal, lire_journal
from metabank.base.lecture import lire_dates_des_donnees
from metabank.configuration import lire_configuration
from metabank.connecteurs.contrat import Connecteur
from metabank.connecteurs.registre import composer_lecteur, lister_connecteurs
from metabank.synoptique import evaluer_fraicheur
from metabank.web.assistant import trouver_claude
from metabank.web.configuration_vues import etat_configuration

FENETRE_JOURNAL_JOURS = 30
ENTREES_PAR_COMPTE = 10
ALIMENTE = {
    "courant": "solde, opérations, budget",
    "locatif": "solde, opérations, budget",
    "livret_a": "solde, intérêts, plafond",
    "ldd": "solde, intérêts, plafond",
    "credit": "capital restant dû, mensualité",
    "assurance_vie": "valeur, fonds, frais",
    "per": "valeur, fonds, frais",
    "perp": "valeur, fonds",
}


def etat_synoptique(dossier: Path, aujourd_hui: date | None = None) -> dict:
    """Rendre les lignes du synoptique (une par compte) et les sorties de la machine (réseau, destinataire, contenu)."""
    # Date locale de la machine : un compte « à jour » se juge au calendrier du titulaire.
    aujourd_hui = aujourd_hui or datetime.now().astimezone().date()
    connecteurs = {c.nom: c for c in lister_connecteurs()}
    comptes = etat_configuration(dossier)["comptes"]
    dates: dict[str, date] = {}
    journal: list[EntreeJournal] = []
    if dossier.is_dir():
        connexion = ouvrir_base(dossier, composer_lecteur(list(connecteurs.values())))
        try:
            dates, journal = lire_dates_des_donnees(connexion), lire_journal(connexion)
        finally:
            connexion.close()
    depuis = (aujourd_hui - timedelta(days=FENETRE_JOURNAL_JOURS)).isoformat()
    lignes = [_ligne(c, connecteurs, dates.get(c["cle"]), journal, depuis, aujourd_hui) for c in comptes]
    return {"comptes": lignes, "sorties": _sorties(dossier), "aujourd_hui": aujourd_hui.isoformat()}


def _ligne(compte: dict, connecteurs: dict[str, Connecteur], derniere: date | None, journal: list[EntreeJournal],
           depuis: str, aujourd_hui: date) -> dict:  # fmt: skip
    principal = connecteurs.get(compte["principal"])
    secours = connecteurs.get(compte["secours"])
    entrees = [e for e in journal if compte["cle"] in e.compte_cle.split(",")]
    recentes = [e for e in entrees if e.le >= depuis]
    titulaire = compte["titulaire_saisi"] or compte["titulaire"]
    return {
        "cle": compte["cle"],
        "nom": f"{titulaire} · {compte['libelle_type']} {compte['etablissement']} {compte['numero_masque']}",
        "principal": principal.libelle if principal else "",
        "secours": secours.libelle if secours else "",
        "reseau": principal.reseau if principal else "",
        "mode_emploi": principal.mode_emploi if principal else "",
        "derniere_donnee": derniere.isoformat() if derniere else None,
        "frequence_jours": compte["frequence_jours"],
        "fraicheur": evaluer_fraicheur(derniere, compte["frequence_jours"], aujourd_hui),
        "alimente": ALIMENTE.get(compte["type_compte"], ""),
        "reussis_30_jours": sum(e.resultat == "ok" for e in recentes),
        "echecs_30_jours": sum(e.resultat != "ok" for e in recentes),
        "journal": [
            {
                "le": e.le,
                "connecteur": e.connecteur,
                "resultat": e.resultat,
                "elements": e.elements,
                "message": e.message,
                "fichier": e.archive.rpartition("/")[2],
            }
            for e in entrees[:ENTREES_PAR_COMPTE]
        ],
    }


def _sorties(dossier: Path) -> list[dict]:
    """Rendre ce qui peut sortir de la machine : aujourd'hui, seulement les questions à l'assistant."""
    actif = lire_configuration(dossier)["parametres"]["assistant_actif"]
    return [
        {
            "nom": "Assistant Claude",
            "reseau": "claude",
            "destinataire": "Claude Code (claude -p, sans outil, dans un dossier vide)",
            "contenu": "chiffres calculés par metabank et prénoms ; ni numéro de compte ni relevé",
            "etat": "désactivé" if not actif else "prêt" if trouver_claude() else "Claude Code absent",
        }
    ]

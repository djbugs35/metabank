"""Mise à jour automatique des comptes en connexion directe : une synchronisation par jour et par compte au plus.

Sans le titulaire, une banque n'accepte que quelques consultations par jour (DSP2) : une par jour suffit. Chaque
compte de l'accord Enable Banking déjà connu de la base (par un export CSV) est interrogé depuis sa dernière opération
moins 10 jours ; les opérations déjà connues, par l'une ou l'autre source, ne sont pas doublées (MODELE § 7.1 bis).
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from metabank.archivage import archiver_donnees
from metabank.base.integration import ouvrir_base
from metabank.connecteurs._enable_banking import lire_accord
from metabank.connecteurs.contrat import Reconnaissance
from metabank.connecteurs.enable_banking import SOURCE
from metabank.connecteurs.registre import (
    AccesCompte,
    AucunAccesDirect,
    composer_lecteur,
    lister_connecteurs,
    synchroniser_compte,
)
from metabank.depot_unique import CompteInconnu, provenance_du_compte

RECOUVREMENT_JOURS = 10
PREMIERE_FOIS_JOURS = 90


def _a_faire(dossier: Path, aujourd_hui: date, forcer: bool) -> tuple[list[AccesCompte], list[str], dict[str, date]]:
    """Rendre les accès à interroger, les messages des comptes écartés, et la date de départ de chacun."""
    accord = lire_accord()
    # Les exports rangés à la main depuis le dernier affichage doivent être en base avant la comparaison.
    archiver_donnees(dossier, lister_connecteurs())
    connexion = ouvrir_base(dossier, composer_lecteur(lister_connecteurs()))
    acces, messages, depuis = [], [], {}
    try:
        for compte in accord.get("comptes", []):
            ligne = connexion.execute(
                "SELECT id, cle FROM comptes WHERE etablissement = 'BNP' AND numero_masque = ? AND type_compte != 'credit'",
                (compte["masque"],),
            ).fetchone()
            if ligne is None:
                messages.append(
                    f"{compte['nom']} {compte['masque']} : pas encore en base (déposez un export CSV une fois)"
                )
                continue
            compte_id, cle = ligne
            deja = connexion.execute(
                "SELECT 1 FROM imports WHERE connecteur = ? AND resultat = 'ok' AND compte_cle = ? AND le >= ?",
                (SOURCE, cle, aujourd_hui.isoformat()),
            ).fetchone()
            if deja and not forcer:
                messages.append(f"{cle} : déjà mis à jour aujourd'hui")
                continue
            try:
                provenance = provenance_du_compte(connexion, Reconnaissance("BNP", "", compte["masque"]))
            except CompteInconnu as erreur:
                messages.append(f"{cle} : {erreur}")
                continue
            derniere = connexion.execute(
                "SELECT max(jour) FROM operations WHERE compte_id = ?", (compte_id,)
            ).fetchone()[0]
            depuis[cle] = (date.fromisoformat(derniere) - timedelta(days=RECOUVREMENT_JOURS) if derniere
                           else aujourd_hui - timedelta(days=PREMIERE_FOIS_JOURS))  # fmt: skip
            acces.append(AccesCompte(cle, provenance, SOURCE))
    finally:
        connexion.close()
    return acces, messages, depuis


def synchroniser_tout(dossier: Path, aujourd_hui: date | None = None, forcer: bool = False) -> list[str]:
    """Rendre un message par compte : éléments ajoutés, déjà à jour, ou raison de l'échec (sans montant)."""
    aujourd_hui = aujourd_hui or datetime.now().astimezone().date()
    if not lire_accord().get("session"):
        return []
    acces, messages, depuis = _a_faire(dossier, aujourd_hui, forcer)
    connecteurs = lister_connecteurs()
    for a in acces:
        try:
            resultat = synchroniser_compte(dossier, connecteurs, {}, a, depuis[a.compte_cle])
        except AucunAccesDirect as erreur:
            messages.append(f"{a.compte_cle} : non mis à jour ({erreur})")
            continue
        messages.append(
            f"{a.compte_cle} : {'réponse identique à la précédente' if resultat.deja_present else f'{resultat.elements} élément(s) ajouté(s)'}"
        )
    return messages

"""Mise à jour automatique des comptes en connexion directe : une synchronisation par jour et par compte au plus.

Sans le titulaire, une banque n'accepte que quelques consultations par jour (DSP2) : une par jour suffit. Chaque
compte de l'accord Enable Banking déjà connu de la base (par un export CSV) est interrogé depuis sa dernière opération
moins 10 jours ; les opérations déjà connues, par l'une ou l'autre source, ne sont pas doublées (MODELE § 7.1 bis).
"""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Message:
    """Le compte rendu d'un compte : texte en français et ton (« ok », « info » ou « erreur ») pour l'affichage."""

    texte: str
    ton: str


def _bilan_du_compte(dossier: Path, cle: str) -> tuple[int, str]:
    """Rendre le nombre d'opérations du compte et la date de son dernier solde (« JJ/MM/AAAA »)."""
    connexion = ouvrir_base(dossier, composer_lecteur(lister_connecteurs()))
    try:
        nombre, jour = connexion.execute(
            "SELECT (SELECT count(*) FROM operations o WHERE o.compte_id = c.id), "
            "(SELECT max(s.jour) FROM soldes s WHERE s.compte_id = c.id) FROM comptes c WHERE c.cle = ?",
            (cle,),
        ).fetchone()
    finally:
        connexion.close()
    return nombre, date.fromisoformat(jour).strftime("%d/%m/%Y") if jour else "?"


def synchroniser_tout(dossier: Path, aujourd_hui: date | None = None, forcer: bool = False) -> list[Message]:
    """Rendre un compte rendu par compte : comptes mis à jour d'abord, puis échecs, puis informations (sans montant)."""
    aujourd_hui = aujourd_hui or datetime.now().astimezone().date()
    if not lire_accord().get("session"):
        return []
    acces, ecartes, depuis = _a_faire(dossier, aujourd_hui, forcer)
    connecteurs = lister_connecteurs()
    messages = []
    for a in acces:
        avant, _ = _bilan_du_compte(dossier, a.compte_cle)
        try:
            synchroniser_compte(dossier, connecteurs, {}, a, depuis[a.compte_cle])
        except AucunAccesDirect as erreur:
            messages.append(Message(f"{a.compte_cle} : non mis à jour ({erreur})", "erreur"))
            continue
        apres, solde = _bilan_du_compte(dossier, a.compte_cle)
        nouvelles = apres - avant
        detail = (
            "aucune opération nouvelle"
            if not nouvelles
            else f"{nouvelles} opération{'s' if nouvelles > 1 else ''} nouvelle{'s' if nouvelles > 1 else ''}"
        )
        messages.append(Message(f"{a.compte_cle} : à jour, solde au {solde}, {detail}", "ok"))
    messages += [Message(texte, "info") for texte in ecartes]
    return sorted(messages, key=lambda m: ("ok", "erreur", "info").index(m.ton))

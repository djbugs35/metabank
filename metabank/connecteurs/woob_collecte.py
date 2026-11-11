"""Collecte des comptes et des supports via woob (frontière réseau du projet).

Les identifiants ne passent jamais par metabank : ils sont dans la configuration de woob
(« uv run woob config add bnporc »), hors dépôt. metabank ne fait que lire, sans aucun virement ni arbitrage.
"""

import getpass
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from requests.exceptions import RequestException
from woob.core.woob import VersionsMismatchError, Woob
from woob.exceptions import (
    BrowserIncorrectPassword,
    BrowserQuestion,
    BrowserUnavailable,
    DecoupledValidation,
    NeedInteractive,
)
from woob.tools.storage import StandardStorage

from metabank.connecteurs.woob_normalisation import traduire_compte
from metabank.modele import TYPES_AVEC_LIGNES, Compte

# Une banque peut enchaîner mot de passe, code SMS puis validation sur l'application : trois relances suffisent.
RELANCES_MAX = 3


class ErreurCollecte(Exception):
    """Collecte impossible sur un backend, avec un message qui dit quoi faire."""


@dataclass
class ResultatCollecte:
    """Comptes collectés, et erreurs par backend (une banque en panne n'arrête pas les autres)."""

    comptes: list[Compte] = field(default_factory=list)
    erreurs: dict[str, str] = field(default_factory=dict)


def collecter(noms_backends: list[str], dossier_session: Path, interactif: bool) -> ResultatCollecte:
    """Rendre les comptes et supports de chaque backend woob nommé.

    Args:
        noms_backends: noms donnés aux backends lors de « woob config add ».
        dossier_session: où garder cookies et jetons entre deux collectes.
        interactif: vrai si quelqu'un est là pour un code SMS ou une validation sur téléphone.
    """
    resultat = ResultatCollecte()
    for nom, backend in _charger_backends(noms_backends, dossier_session).items():
        try:
            with backend:
                resultat.comptes += _collecter_backend(nom, backend, interactif)
        except ErreurCollecte as erreur:
            resultat.erreurs[nom] = str(erreur)
    for nom in set(noms_backends) - set(resultat.erreurs) - {c.source.removeprefix("woob:") for c in resultat.comptes}:
        resultat.erreurs.setdefault(nom, "aucun compte rendu (backend absent de la configuration woob ?)")
    return resultat


def _charger_backends(noms_backends: list[str], dossier_session: Path) -> dict:
    dossier_session.mkdir(parents=True, exist_ok=True)
    try:
        # Au tout premier lancement, Woob() télécharge la liste de ses modules : il faut le réseau.
        woob = Woob(storage=StandardStorage(str(dossier_session / "woob.storage")))
        return woob.load_backends(names=noms_backends)
    except VersionsMismatchError as erreur:
        raise ErreurCollecte("modules woob absents ou périmés : lancer « uv run woob config update »") from erreur
    except RequestException as erreur:
        raise ErreurCollecte(f"dépôt des modules woob injoignable (réseau ?) : {erreur}") from erreur


def _collecter_backend(nom: str, backend, interactif: bool) -> list[Compte]:
    if interactif:
        # Sans cette valeur, woob refuse de déclencher une double authentification (mode « tâche planifiée »).
        _regler(backend, "request_information", {})
    comptes_woob = _executer(backend, lambda: list(backend.iter_accounts()), interactif)
    comptes = []
    for compte_woob in comptes_woob:
        investissements = []
        if _a_des_lignes(compte_woob) and hasattr(backend, "iter_investment"):
            investissements = _executer(backend, lambda c=compte_woob: list(backend.iter_investment(c)), interactif)
        comptes.append(traduire_compte(nom, compte_woob, investissements))
    return comptes


def _executer(backend, action: Callable[[], list], interactif: bool) -> list:
    """Rendre le résultat de l'action, en répondant aux demandes de double authentification si on peut."""
    for _ in range(RELANCES_MAX):
        try:
            return action()
        except BrowserQuestion as question:
            if not interactif:
                raise ErreurCollecte("la banque pose une question : relancer avec --interactif") from question
            for champ in question.fields:
                _regler(backend, champ.id, _demander(champ))
        except DecoupledValidation as validation:
            if not interactif:
                raise ErreurCollecte("validation sur téléphone requise : relancer avec --interactif") from validation
            print(f"[{backend.name}] {validation.message}")
            _regler(backend, "resume", True)
        except NeedInteractive as besoin:
            raise ErreurCollecte("double authentification requise : relancer avec --interactif") from besoin
        except BrowserIncorrectPassword as erreur:
            raise ErreurCollecte(
                f"identifiants refusés : « uv run woob config edit {backend.name} » ({erreur})"
            ) from erreur
        except BrowserUnavailable as erreur:
            raise ErreurCollecte(f"site de la banque indisponible ou modifié : {erreur}") from erreur
    raise ErreurCollecte(f"authentification non aboutie après {RELANCES_MAX} relances")


def _a_des_lignes(compte_woob) -> bool:
    return traduire_compte("", compte_woob).type_compte in TYPES_AVEC_LIGNES


def _regler(backend, cle: str, valeur) -> None:
    if cle in backend.config:
        backend.config[cle].set(valeur)


def _demander(champ) -> str:
    libelle = f"{getattr(champ, 'label', None) or champ.id} : "
    return getpass.getpass(libelle) if getattr(champ, "masked", False) else input(libelle)

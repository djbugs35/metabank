"""Relier ses comptes par Enable Banking, puis comparer ce que la DSP2 rend à ce que les exports CSV disent déjà.

« metabank enable-banking relier » : demande l'accord (dans MesComptes pour BNP), enregistre la session et les comptes
autorisés dans ~/.config/metabank/enable_banking.json. « metabank enable-banking comparer » : rapproche, compte par
compte, les opérations des deux sources, sans rien écrire en base ; le rapport ne montre que des nombres d'opérations,
ni montant ni libellé. C'est sur ce rapport que se décide la règle qui évitera de compter deux fois une opération
arrivée par les deux chemins.
"""

import secrets
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from metabank.connecteurs._enable_banking import (
    ACCORD,
    Client,
    code_de_retour,
    enregistrer_accord,
    lire_accord,
    masquer_iban,
)
from metabank.donnees import charger

JOURS_ACCORD = 180


def trouver_banque(client: Client, nom: str, pays: str = "FR") -> str:
    """Rendre le nom exact de la banque pour l'API (« BNP Paribas »).

    Raises:
        ValueError: aucune banque, ou plusieurs, ne correspondent au nom donné.
    """
    noms = [b["name"] for b in client.banques(pays)]
    exacts = [n for n in noms if n.lower() == nom.lower()]
    proches = exacts or [n for n in noms if nom.lower() in n.lower()]
    if len(proches) != 1:
        raise ValueError(f"banque « {nom} » : {len(proches)} correspondances ({', '.join(proches[:8])})")
    return proches[0]


def relier(client: Client, banque: str, demander: Callable[[str], str], ouvrir: Callable[[str], object],
           jours: int = JOURS_ACCORD, chemin: Path = ACCORD) -> dict:  # fmt: skip
    """Rendre l'accord enregistré : demande l'accord à la banque, lit l'adresse de retour collée, ouvre la session.

    Args:
        demander: pose une question au titulaire et rend sa réponse (input en ligne de commande).
        ouvrir: ouvre l'adresse d'accord dans le navigateur.
    """
    nom = trouver_banque(client, banque)
    etat = secrets.token_urlsafe(16)
    adresse = client.demander_accord(nom, "FR", jours, etat)
    ouvrir(adresse)
    retour = demander("Adresse de la page d'arrivée (copiez-la depuis la barre d'adresse) : ")
    if f"state={etat}" not in retour:
        raise ValueError("cette adresse ne vient pas de l'accord qui vient d'être demandé : recommencez")
    session = client.ouvrir_session(code_de_retour(retour))
    comptes = [
        {"uid": c["uid"], "masque": masquer_iban((c.get("account_id") or {}).get("iban", "")), "nom": c.get("name", ""),
         "devise": c.get("currency", "EUR")}
        for c in session.get("accounts", [])
    ]  # fmt: skip
    accord = {"application": client.application, "banque": nom, "session": session.get("session_id", ""),
              "fin": (session.get("access") or {}).get("valid_until", ""), "comptes": comptes}  # fmt: skip
    enregistrer_accord(accord, chemin)
    return accord


def montant_signe(operation: dict) -> Decimal:
    """Rendre le montant d'une opération DSP2 en euros : négatif pour un débit (« DBIT »)."""
    montant = Decimal(str(operation["transaction_amount"]["amount"]))
    return -montant if operation.get("credit_debit_indicator") == "DBIT" else montant


def _jour(operation: dict, champ: str) -> date | None:
    valeur = operation.get(champ)
    return date.fromisoformat(valeur[:10]) if valeur else None


def comparer_sources(operations_dsp2: list[dict], operations_csv: list, debut: date, fin: date) -> dict[str, int]:
    """Rendre combien d'opérations de ]debut, fin] se retrouvent d'une source à l'autre, selon la date retenue.

    Une paire (jour, montant) d'un côté s'apparie à la même de l'autre, autant de fois qu'elle y figure.
    """
    dans = [o for o in operations_dsp2 if o.get("status", "BOOK") == "BOOK"]
    csv = Counter((o.jour, o.montant) for o in operations_csv if debut < o.jour <= fin)
    resultat = {"csv": sum(csv.values()), "dsp2": 0}
    for champ in ("booking_date", "value_date", "transaction_date"):
        cles = Counter((j, montant_signe(o)) for o in dans if (j := _jour(o, champ)) and debut < j <= fin)
        resultat["dsp2"] = max(resultat["dsp2"], sum(cles.values()))
        resultat[f"apparies_{champ}"] = sum((cles & csv).values())
    resultat["en_attente"] = sum(1 for o in operations_dsp2 if o.get("status") == "PDNG")
    return resultat


def comparer(client: Client, dossier: Path, jours: int, accord: dict | None = None) -> list[str]:
    """Rendre, compte par compte, le rapprochement DSP2 / exports CSV sur la période commune (nombres seulement)."""
    accord = accord if accord is not None else lire_accord()
    # La DSP2 ne couvre que les comptes de paiement : un prêt de même fin de numéro n'est pas un candidat.
    comptes_csv = {c.numero_masque: c for c in charger(dossier).comptes if c.type_compte != "credit"}
    lignes = []
    aujourd_hui = datetime.now().astimezone().date()
    for compte in accord.get("comptes", []):
        csv = comptes_csv.get(compte["masque"])
        if csv is None:
            lignes.append(f"{compte['nom']} {compte['masque']} : aucun export CSV de ce numéro en base")
            continue
        debut = aujourd_hui - timedelta(days=jours)
        operations = client.operations(compte["uid"], debut)
        champs = sorted({cle for o in operations for cle in o})
        r = comparer_sources(operations, list(csv.operations), debut, csv.date_solde)
        lignes.append(f"{csv.libelle} : du {debut} au {csv.date_solde}, " + ", ".join(f"{k} {v}" for k, v in r.items())
                      + f" ; champs DSP2 : {', '.join(champs)}")  # fmt: skip
    return lignes

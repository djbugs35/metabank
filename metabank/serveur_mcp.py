"""Serveur MCP local de metabank, en lecture seule : « uv run python -m metabank mcp ».

Protocole Model Context Protocol sur l'entrée et la sortie standard : un message JSON-RPC 2.0 par ligne. La sortie
standard ne porte que des réponses ; rien d'autre n'y est jamais écrit (un journal la corromprait). Pas de réseau :
Claude Code lance ce processus sur la machine et lui parle par ses tuyaux.

Enregistrement dans Claude Code (une fois) :
  claude mcp add metabank -- uv run --directory <dossier du dépôt> python -m metabank mcp
"""

import json
import sys
from pathlib import Path
from typing import TextIO

from metabank import __version__
from metabank.outils_mcp import OUTILS, OutilInconnu, appeler

VERSIONS_DU_PROTOCOLE = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
METHODE_INCONNUE = -32601
REQUETE_INVALIDE = -32600
ARGUMENTS_INVALIDES = -32602
JSON_ILLISIBLE = -32700
CONSIGNES = (
    "Chiffres du patrimoine d'un foyer, calculés par metabank (code testé). Commentez-les, n'en calculez pas d'autres ; "
    "montants en euros, taux en fractions. Lecture seule : aucun outil ne modifie quoi que ce soit. Pas de conseil "
    "personnalisé d'investissement : des faits, des comparaisons et des simulations."
)


def repondre(message: dict, dossier: Path) -> dict | None:
    """Rendre la réponse JSON-RPC au message, ou None pour une notification (sans « id »)."""
    methode, ident = message.get("method"), message.get("id")
    if ident is None:
        return None
    if methode == "initialize":
        demandee = (message.get("params") or {}).get("protocolVersion")
        version = demandee if demandee in VERSIONS_DU_PROTOCOLE else VERSIONS_DU_PROTOCOLE[0]
        return _resultat(ident, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "metabank", "version": __version__},
            "instructions": CONSIGNES,
        })  # fmt: skip
    if methode == "ping":
        return _resultat(ident, {})
    if methode == "tools/list":
        outils = [{"name": o.nom, "description": o.description, "inputSchema": o.schema} for o in OUTILS]
        return _resultat(ident, {"tools": outils})
    if methode == "tools/call":
        return _appeler_outil(ident, message.get("params") or {}, dossier)
    return _erreur(ident, METHODE_INCONNUE, f"méthode inconnue : {methode}")


def _appeler_outil(ident: object, params: dict, dossier: Path) -> dict:
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _erreur(ident, ARGUMENTS_INVALIDES, "arguments : objet attendu")
    try:
        contenu = appeler(dossier, str(params.get("name")), arguments)
    except OutilInconnu as erreur:
        return _erreur(ident, ARGUMENTS_INVALIDES, f"outil inconnu : {erreur.args[0]}")
    except (ValueError, TypeError) as erreur:
        # Erreur d'usage : rendue à Claude comme résultat en erreur, pour qu'il corrige ses arguments.
        return _resultat(ident, {"content": [{"type": "text", "text": str(erreur)}], "isError": True})
    texte = json.dumps(contenu, ensure_ascii=False)
    return _resultat(ident, {"content": [{"type": "text", "text": texte}], "structuredContent": contenu,
                             "isError": False})  # fmt: skip


def _resultat(ident: object, resultat: dict) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "result": resultat}


def _erreur(ident: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


def servir(dossier: Path, entree: TextIO = sys.stdin, sortie: TextIO = sys.stdout) -> None:
    """Répondre à chaque ligne de l'entrée jusqu'à sa fermeture."""
    for ligne in entree:
        if not ligne.strip():
            continue
        try:
            message = json.loads(ligne)
        except json.JSONDecodeError:
            reponse: dict | None = _erreur(None, JSON_ILLISIBLE, "JSON illisible")
        else:
            reponse = repondre(message, dossier) if isinstance(message, dict) else _erreur(None, REQUETE_INVALIDE,
                                                                                         "objet JSON-RPC attendu")  # fmt: skip
        if reponse is not None:
            sortie.write(json.dumps(reponse, ensure_ascii=False) + "\n")
            sortie.flush()

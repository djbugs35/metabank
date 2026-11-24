"""Relevé d'assureur en JSON et retour, sans perte : montants en texte décimal, dates en ISO 8601.

Sert à garder en base le relevé tel que le lecteur l'a compris, pour que les analyses rendent les mêmes chiffres
qu'en relisant le PDF.
"""

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from metabank.releves.frais_supports import FraisSupport
from metabank.releves.modele import Distribution, Frais, Mouvements, Operation, Releve, Support


def releve_en_json(releve: Releve) -> str:
    """Rendre le relevé en JSON (clés triées : deux relevés égaux donnent le même texte)."""
    return json.dumps(asdict(releve), default=str, ensure_ascii=False, sort_keys=True)


def releve_depuis_json(texte: str) -> Releve:
    """Rendre le relevé écrit par releve_en_json."""
    d = json.loads(texte)
    return Releve(
        assureur=d["assureur"],
        produit=d["produit"],
        numero=d["numero"],
        type_contrat=d["type_contrat"],
        date_arrete=date.fromisoformat(d["date_arrete"]),
        valeur=Decimal(d["valeur"]),
        supports=tuple(
            Support(
                s["libelle"],
                Decimal(s["valeur"]),
                s["isin"],
                _decimal(s["parts"]),
                _decimal(s["valeur_part"]),
                _decimal(s.get("prix_de_revient")),
            )
            for s in d["supports"]
        ),
        valeur_precedente=_decimal(d["valeur_precedente"]),
        mouvements=None if d["mouvements"] is None else Mouvements(**_decimaux(d["mouvements"])),
        frais=None if d["frais"] is None else Frais(**_decimaux(d["frais"])),
        versements_volontaires_annee=_decimal(d["versements_volontaires_annee"]),
        versements_bruts_depuis_origine=_decimal(d["versements_bruts_depuis_origine"]),
        rachats_depuis_origine=_decimal(d["rachats_depuis_origine"]),
        frais_supports=tuple(FraisSupport(**{**_decimaux(f), "isin": f["isin"]}) for f in d["frais_supports"]),
        taux_frais_fonds_euros=_decimal(d["taux_frais_fonds_euros"]),
        primes_non_remboursees=_decimal(d.get("primes_non_remboursees")),
        versements_annee_en_cours=_decimal(d.get("versements_annee_en_cours")),
        rachats_annee_en_cours=_decimal(d.get("rachats_annee_en_cours")),
        frais_annee_en_cours=_decimal(d.get("frais_annee_en_cours")),
        performance_annoncee=_decimal(d.get("performance_annoncee")),
        distributions=tuple(
            Distribution(date.fromisoformat(x["jour"]), x["support"], Decimal(x["montant"]))
            for x in d.get("distributions", [])
        ),
        operations=tuple(
            Operation(date.fromisoformat(o["jour"]), o["nature"], o["libelle"], o["isin"], Decimal(o["montant"]))
            for o in d.get("operations", [])
        ),
        anomalies=tuple(d["anomalies"]),
        fichier=d["fichier"],
    )


def _decimal(valeur: str | None) -> Decimal | None:
    return None if valeur is None else Decimal(valeur)


def _decimaux(champs: dict[str, Any]) -> dict[str, Decimal]:
    return {cle: Decimal(valeur) for cle, valeur in champs.items() if cle != "isin"}

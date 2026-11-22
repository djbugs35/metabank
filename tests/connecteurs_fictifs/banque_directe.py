"""Connecteur direct fictif : une « banque » qui répond en JSON, ou refuse quand son jeton vaut « refuse »."""

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from metabank.base.lot import CompteLu, Lot, OperationLue
from metabank.connecteurs.contrat import AccesIndisponible, ConnecteurDirect, Reconnaissance, Reglage, Reponse


class BanqueDirecte(ConnecteurDirect):
    """Connecteur direct de test."""

    nom = "banque_directe"
    libelle = "Banque directe fictive"
    etablissements = ("Fictive",)
    types_comptes = ("courant",)
    reglages = (Reglage("banque_directe.jeton", "Jeton", secret=True),)

    def synchroniser(self, valeurs: Mapping[str, str], compte_cle: str, depuis: date) -> Reponse:
        """Rendre une opération fictive datée de depuis."""
        if valeurs.get(f"{self.nom}.jeton") == "refuse":
            raise AccesIndisponible("accord expiré")
        corps = {"source": self.nom, "compte": compte_cle, "jour": depuis.isoformat(), "montant": "-12.30"}
        return Reponse(f"{self.nom}-{depuis.isoformat()}.json", json.dumps(corps).encode())

    def reconnaitre(self, nom: str, contenu: bytes) -> Reconnaissance | None:  # noqa: ARG002 (signature imposée par le contrat)
        """Rendre le compte si le contenu est une réponse de cette banque."""
        entete = f'{{"source": "{self.nom}"'.encode()
        return Reconnaissance("Fictive", "courant", "****1234") if contenu.startswith(entete) else None

    def lire(self, provenance: str, nom: str, contenu: bytes) -> Lot:  # noqa: ARG002 (signature imposée par le contrat)
        """Rendre le lot de la réponse."""
        corps = json.loads(contenu)
        compte = CompteLu(
            corps["compte"], provenance.split("/", maxsplit=1)[0], "Fictive", "courant", "****1234", "Courant"
        )
        jour = date.fromisoformat(corps["jour"])
        operation = OperationLue(compte.cle, f"d-{corps['jour']}", jour, "Prélèvement", Decimal(corps["montant"]))
        return Lot(self.nom, (compte,), (operation,))


CONNECTEUR = BanqueDirecte()

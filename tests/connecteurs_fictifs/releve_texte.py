"""Connecteur de fichiers fictif : un relevé texte « RELEVE\\njour;libellé;montant »."""

from datetime import date
from decimal import Decimal

from metabank.base.lot import CompteLu, Lot, OperationLue
from metabank.connecteurs.contrat import ConnecteurFichier, Reconnaissance

ENTETE = b"RELEVE\n"


class ReleveTexte(ConnecteurFichier):
    """Connecteur de fichiers de test, sans réglage."""

    nom = "releve_texte"
    libelle = "Relevé texte fictif"
    etablissements = ("Fictive",)
    types_comptes = ("courant",)

    def reconnaitre(self, nom: str, contenu: bytes) -> Reconnaissance | None:  # noqa: ARG002 (signature imposée par le contrat)
        """Rendre le compte si le fichier commence par l'en-tête du relevé."""
        return Reconnaissance("Fictive", "courant", "****1234") if contenu.startswith(ENTETE) else None

    def lire(self, provenance: str, nom: str, contenu: bytes) -> Lot:  # noqa: ARG002 (signature imposée par le contrat)
        """Rendre une opération par ligne."""
        compte = CompteLu("FICTIVE:courant:****1234", "Alice", "Fictive", "courant", "****1234", "Courant")
        operations = []
        for ligne in contenu.decode().splitlines()[1:]:
            jour, libelle, montant = ligne.split(";")
            operations.append(OperationLue(compte.cle, ligne, date.fromisoformat(jour), libelle, Decimal(montant)))
        return Lot(self.nom, (compte,), tuple(operations))


CONNECTEUR = ReleveTexte()

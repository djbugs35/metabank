"""Relevé de situation Cardif (PERP), en PDF. Lecteur : releves/cardif.py."""

from metabank.connecteurs._releves import ConnecteurReleve
from metabank.releves.cardif import est_situation_cardif, lire_situation_cardif
from metabank.releves.modele import Releve


class CardifPdf(ConnecteurReleve):
    """Relevé de situation Cardif : valeur et supports à une date, sans mouvements de l'année."""

    nom = "cardif_pdf"
    libelle = "Relevé de situation Cardif (PDF)"
    assureur = "Cardif"
    etablissements = ("Cardif",)
    types_comptes = ("perp",)

    def est_de_la_forme(self, texte: str) -> bool:
        """Rendre vrai pour un relevé de situation Cardif."""
        return est_situation_cardif(texte)

    def lire_texte(self, texte: str, fichier: str, type_indique: str | None) -> Releve:
        """Rendre le relevé de situation lu."""
        return lire_situation_cardif(texte, fichier, type_indique)


CONNECTEUR = CardifPdf()

"""Relevé annuel Suravenir (assurance vie, PER), en PDF. Lecteur : releves/suravenir.py."""

from metabank.connecteurs._releves import ConnecteurReleve
from metabank.releves.modele import Releve
from metabank.releves.suravenir import est_releve_suravenir, lire_releve_suravenir


class SuravenirPdf(ConnecteurReleve):
    """Relevé annuel Suravenir : valeur, supports, mouvements et frais de l'année."""

    nom = "suravenir_pdf"
    libelle = "Relevé annuel Suravenir (PDF)"
    assureur = "Suravenir"
    mode_emploi = "Dans l'espace client de l'assureur (Suravenir, ou le distributeur du contrat) : relevé annuel d'information, en PDF ; le déposer dans l'onglet Relevés chaque année."
    etablissements = ("Suravenir",)
    types_comptes = ("assurance_vie", "per")

    def est_de_la_forme(self, texte: str) -> bool:
        """Rendre vrai pour un relevé annuel Suravenir."""
        return est_releve_suravenir(texte)

    def lire_texte(self, texte: str, fichier: str, type_indique: str | None) -> Releve:
        """Rendre le relevé annuel lu."""
        return lire_releve_suravenir(texte, fichier, type_indique)


CONNECTEUR = SuravenirPdf()

"""Situation de contrat Suravenir (Vie Plus) en PDF : valeur et fonds à une date. Lecteur : releves/suravenir_situation.py."""

from metabank.connecteurs._releves import ConnecteurReleve
from metabank.releves.modele import Releve
from metabank.releves.suravenir_situation import est_situation_suravenir, lire_situation_suravenir


class SuravenirSituationPdf(ConnecteurReleve):
    """Situation de contrat Suravenir : valeur, fonds et cumuls depuis l'origine, à la date demandée."""

    nom = "suravenir_situation_pdf"
    libelle = "Situation de contrat Suravenir (PDF)"
    mode_emploi = (
        "Dans l'espace client Vie Plus ou Suravenir : « Situation de votre contrat », en PDF ; la déposer dans l'onglet "
        "Relevés quand vous voulez une valeur à jour entre deux relevés annuels."
    )
    assureur = "Suravenir"
    etablissements = ("Suravenir",)
    types_comptes = ("assurance_vie", "per")

    def est_de_la_forme(self, texte: str) -> bool:
        """Rendre vrai pour une situation de contrat Suravenir."""
        return est_situation_suravenir(texte)

    def lire_texte(self, texte: str, fichier: str, type_indique: str | None) -> Releve:
        """Rendre la situation lue."""
        return lire_situation_suravenir(texte, fichier, type_indique)


CONNECTEUR = SuravenirSituationPdf()

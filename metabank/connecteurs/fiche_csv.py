"""Fiche CSV metabank d'un contrat (« metabank-<année>.csv ») : la seule source des relevés en base. MODELE § 0.

Écrite par les lecteurs de PDF à côté des PDF (fiches.py), corrigeable à la main dans Excel. Les PDF eux-mêmes ne
donnent plus que le contrat ; ses chiffres viennent de la fiche.
"""

import re

from metabank.base.lot import CompteLu, LectureImpossible, Lot, ReleveLu
from metabank.connecteurs._provenance import morceaux_provenance
from metabank.connecteurs._releves import lot_du_releve
from metabank.connecteurs.contrat import ConnecteurFichier, Reconnaissance
from metabank.releves.fiche import FicheIllisible, est_fiche, lire_fiche


def _texte(contenu: bytes) -> str | None:
    try:
        texte = contenu.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return texte if est_fiche(texte) else None


class FicheCsv(ConnecteurFichier):
    """Fiche metabank : synthèse, fonds et opérations lus dans les PDF d'un contrat, pour une année."""

    nom = "fiche_csv"
    libelle = "Fiche metabank d'un contrat (CSV écrit à côté des PDF)"
    mode_emploi = (
        "Écrite au démarrage à côté des PDF du contrat (metabank-<année>.csv) ; corrigeable dans Excel. « Relire les "
        "PDF » (onglet Relevés) la réécrit depuis les PDF."
    )
    etablissements = ("Suravenir", "Cardif")
    types_comptes = ("assurance_vie", "per", "perp")

    def reconnaitre(self, nom: str, contenu: bytes) -> Reconnaissance | None:  # noqa: ARG002 (signature du contrat)
        """Rendre le contrat de la fiche, ou None si ce n'est pas une fiche metabank."""
        texte = _texte(contenu)
        if texte is None:
            return None
        try:
            releves = lire_fiche(texte)
        except FicheIllisible:
            return Reconnaissance("", "")
        if not releves:
            return Reconnaissance("", "")
        chiffres = re.sub(r"\D", "", releves[0].numero)
        return Reconnaissance(releves[0].assureur, releves[0].type_contrat, "****" + chiffres[-4:] if chiffres else "")

    def lire(self, provenance: str, nom: str, contenu: bytes) -> Lot:
        """Rendre le lot : le contrat et un relevé par PDF cité dans la fiche.

        Raises:
            LectureImpossible: champ illisible (la ligne est nommée) ou fiche sans relevé.
        """
        titulaire, _ = morceaux_provenance(provenance)
        try:
            releves = lire_fiche(_texte(contenu) or "")
        except FicheIllisible as erreur:
            raise LectureImpossible(f"{nom} : {erreur}") from erreur
        if not releves:
            raise LectureImpossible(f"{nom} : fiche sans ligne")
        comptes: dict[str, CompteLu] = {}
        lus: list[ReleveLu] = []
        for releve in releves:
            lot = lot_du_releve(self.nom, titulaire, releve)
            comptes.update({c.cle: c for c in lot.comptes})
            lus += lot.releves
        return Lot(self.nom, tuple(comptes.values()), releves=tuple(lus))


CONNECTEUR = FicheCsv()

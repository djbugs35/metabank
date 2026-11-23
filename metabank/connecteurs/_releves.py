"""Socle des connecteurs de relevés d'assureurs en PDF (Suravenir, Cardif) : du texte du PDF au lot."""

import re

from metabank.base.lot import CompteLu, LectureImpossible, Lot, ReleveLu
from metabank.connecteurs._provenance import morceaux_provenance
from metabank.connecteurs.contrat import ConnecteurFichier, Reconnaissance
from metabank.releves import TYPES_PAR_PREFIXE
from metabank.releves.modele import Releve
from metabank.releves.texte import ErreurLecture, extraire_texte_contenu


class ConnecteurReleve(ConnecteurFichier):
    """Relevé PDF d'un assureur. Une classe fille donne `assureur`, `est_de_la_forme` et `lire_texte`."""

    assureur: str = ""

    def est_de_la_forme(self, texte: str) -> bool:
        """Rendre vrai si le texte du PDF est un relevé de ce connecteur."""
        raise NotImplementedError

    def lire_texte(self, texte: str, fichier: str, type_indique: str | None) -> Releve:
        """Rendre le relevé lu dans le texte du PDF."""
        raise NotImplementedError

    def reconnaitre(self, nom: str, contenu: bytes) -> Reconnaissance | None:  # noqa: ARG002 (signature du contrat)
        """Rendre l'assureur si le PDF est un de ses relevés ; lève LectureImpossible si pdftotext manque."""
        texte = _texte(contenu)
        return Reconnaissance(self.assureur, "") if texte is not None and self.est_de_la_forme(texte) else None

    def lire(self, provenance: str, nom: str, contenu: bytes) -> Lot:
        """Rendre le lot du relevé : le contrat, et le relevé complet. Le type vient du préfixe du dossier."""
        texte = _texte(contenu) or ""
        titulaire, morceaux = morceaux_provenance(provenance)
        try:
            releve = self.lire_texte(texte, nom, TYPES_PAR_PREFIXE.get(morceaux[0].upper()))
        except ErreurLecture as erreur:
            raise LectureImpossible(f"{nom} : {erreur}") from erreur
        return lot_du_releve(self.nom, titulaire, releve)


def lot_du_releve(connecteur: str, titulaire: str, releve: Releve) -> Lot:
    """Rendre le lot d'un relevé : son contrat, identifié par l'assureur, le type, le titulaire et la fin du numéro.

    Raises:
        LectureImpossible: le relevé ne donne aucun chiffre du numéro de contrat.
    """
    chiffres = re.sub(r"\D", "", releve.numero)
    if not chiffres:
        raise LectureImpossible(f"{releve.fichier} : numéro de contrat introuvable")
    masque = "****" + chiffres[-4:]
    cle = f"{releve.assureur}:{releve.type_contrat}:{titulaire}:{masque}"
    compte = CompteLu(cle, titulaire, releve.assureur, releve.type_contrat, masque, releve.produit)
    return Lot(connecteur, (compte,), releves=(ReleveLu(cle, releve),))


def _texte(contenu: bytes) -> str | None:
    try:
        return extraire_texte_contenu(contenu)
    except ErreurLecture as erreur:
        raise LectureImpossible(str(erreur)) from erreur

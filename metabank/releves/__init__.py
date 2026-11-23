"""Lecture des relevés PDF d'assureurs, rangés dans data/<titulaire>/<type - assureur - contrat>/…/*.pdf."""

from dataclasses import dataclass
from pathlib import Path

from metabank.base.archives import DOSSIERS_RESERVES
from metabank.releves.cardif import est_situation_cardif, lire_situation_cardif
from metabank.releves.modele import Releve
from metabank.releves.suravenir import est_releve_suravenir, lire_releve_suravenir
from metabank.releves.texte import ErreurLecture, extraire_texte

# Préfixe du nom de dossier de contrat (« AV - Suravenir - … ») -> type de contrat.
TYPES_PAR_PREFIXE = {"AV": "assurance_vie", "PER": "per", "PERP": "perp", "PEA": "pea", "CTO": "cto"}


@dataclass(frozen=True)
class ReleveRange:
    """Relevé lu, avec le titulaire déduit de son emplacement."""

    titulaire: str
    releve: Releve


def lire_releve(texte: str, fichier: str = "", type_indique: str | None = None) -> Releve:
    """Rendre le relevé lu dans le texte d'un PDF, quel que soit l'assureur reconnu."""
    if est_releve_suravenir(texte):
        return lire_releve_suravenir(texte, fichier, type_indique)
    if est_situation_cardif(texte):
        return lire_situation_cardif(texte, fichier, type_indique)
    raise ErreurLecture("assureur ou forme de relevé non reconnus")


def lire_dossier(dossier: Path) -> tuple[list[ReleveRange], list[str]]:
    """Rendre les relevés de tous les PDF de dossier/<titulaire>/<contrat>/, et les erreurs de lecture."""
    releves, erreurs = [], []
    for pdf in sorted(dossier.glob("*/*/**/*.pdf")):
        titulaire, dossier_contrat = pdf.relative_to(dossier).parts[:2]
        if titulaire in DOSSIERS_RESERVES:
            continue
        prefixe = dossier_contrat.split(" - ")[0].strip().upper()
        try:
            releve = lire_releve(extraire_texte(pdf), pdf.name, TYPES_PAR_PREFIXE.get(prefixe))
        except ErreurLecture as erreur:
            erreurs.append(f"{titulaire}/{pdf.name} : {erreur}")
            continue
        releves.append(ReleveRange(titulaire, releve))
    return releves, erreurs

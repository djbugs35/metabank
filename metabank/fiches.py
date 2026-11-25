"""Fiches CSV des contrats : écrites à côté des PDF, une par compte et par année. MODELE § 0.

Au démarrage, chaque PDF de contrat rangé sous data/<titulaire>/<compte>/ est lu par son lecteur, et ce qu'il dit est
écrit dans « metabank-<année>.csv » du même dossier. Une fiche existante n'est jamais réécrite : les corrections faites
à la main y restent. Un PDF que la fiche ne cite pas encore y est ajouté à la fin. « Relire les PDF » (relire=True)
les réécrit toutes depuis les PDF, en effaçant les corrections.
"""

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from metabank.base.archives import DOSSIERS_RESERVES
from metabank.base.verrou import VERROU_DONNEES
from metabank.connecteurs._provenance import morceaux_provenance
from metabank.connecteurs._releves import ConnecteurReleve
from metabank.connecteurs.contrat import Connecteur
from metabank.releves import TYPES_PAR_PREFIXE
from metabank.releves.fiche import BOM, NOM, ecrire_fiche, lignes_du_releve, sources_de_la_fiche
from metabank.releves.texte import ErreurLecture, extraire_texte_contenu


@dataclass
class BilanFiches:
    """Ce que la préparation a fait : fiches écrites, PDF ajoutés, PDF illisibles (avec la raison)."""

    ecrites: list[str] = field(default_factory=list)
    illisibles: list[str] = field(default_factory=list)


def preparer_fiches(dossier_data: Path, connecteurs: list[Connecteur], relire: bool = False) -> BilanFiches:
    """Rendre le bilan de l'écriture des fiches manquantes (ou de toutes, si relire) à côté des PDF de contrats."""
    with VERROU_DONNEES:
        lecteurs = [c for c in connecteurs if isinstance(c, ConnecteurReleve)]
        bilan = BilanFiches()
        par_dossier: dict[Path, list[Path]] = defaultdict(list)
        for pdf in sorted(dossier_data.glob("*/*/**/*")):
            if (
                pdf.is_file()
                and pdf.suffix.lower() == ".pdf"
                and pdf.relative_to(dossier_data).parts[0] not in DOSSIERS_RESERVES
            ):
                par_dossier[pdf.parent].append(pdf)
        for dossier, pdfs in par_dossier.items():
            _preparer_dossier(dossier_data, dossier, pdfs, lecteurs, relire, bilan)
        return bilan


def _preparer_dossier(dossier_data: Path, dossier: Path, pdfs: list[Path], lecteurs: list[ConnecteurReleve],
                      relire: bool, bilan: BilanFiches) -> None:  # fmt: skip
    deja = set() if relire else {s for f in dossier.glob(NOM.format(annee="*")) for s in sources_de_la_fiche(_lire(f))}
    _, morceaux = morceaux_provenance(dossier.relative_to(dossier_data).as_posix())
    type_indique = TYPES_PAR_PREFIXE.get(morceaux[0].upper())
    nouvelles: dict[int, list[list[str]]] = defaultdict(list)
    for pdf in pdfs:
        if pdf.name in deja:
            continue
        try:
            texte = extraire_texte_contenu(pdf.read_bytes())
        except ErreurLecture as erreur:
            bilan.illisibles.append(f"{pdf.relative_to(dossier_data)} : {erreur}")
            continue
        lecteur = next((c for c in lecteurs if c.est_de_la_forme(texte)), None) if texte else None
        if lecteur is None or texte is None:
            continue
        try:
            releve = lecteur.lire_texte(texte, pdf.name, type_indique)
        except ErreurLecture as erreur:
            bilan.illisibles.append(f"{pdf.relative_to(dossier_data)} : {erreur}")
            continue
        nouvelles[releve.date_arrete.year] += lignes_du_releve(releve)
    for annee, lignes in nouvelles.items():
        fiche = dossier / NOM.format(annee=annee)
        anciennes = [] if relire or not fiche.exists() else _lignes(_lire(fiche))
        _ecrire(fiche, ecrire_fiche(anciennes + lignes))
        bilan.ecrites.append(str(fiche.relative_to(dossier_data)))


def _lire(fiche: Path) -> str:
    return fiche.read_text(encoding="utf-8")


def _lignes(texte: str) -> list[list[str]]:
    """Rendre les lignes d'une fiche existante, sans son en-tête, telles qu'écrites (corrections comprises)."""
    return list(csv.reader(io.StringIO(texte.lstrip(BOM)), delimiter=";"))[1:]


def _ecrire(fiche: Path, texte: str) -> None:
    """Écrire la fiche atomiquement (temporaire puis renommage)."""
    temporaire = fiche.with_name(fiche.name + ".tmp")
    temporaire.write_text(texte, encoding="utf-8")
    temporaire.replace(fiche)

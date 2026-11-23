"""Dépôt d'un relevé PDF ou d'un export CSV depuis la page : lu, puis archivé et enregistré en base.

Rangement : data/archives/<titulaire>/<contrat>/<année>/ pour un relevé, data/archives/<titulaire>/<compte>/ pour un
export. Le fichier n'est archivé que s'il a été reconnu : un fichier illisible ou d'une source inconnue est refusé,
pour que les archives ne contiennent que ce que metabank sait lire.
"""

import re
import tempfile
from pathlib import Path

from metabank.banque.bnp import ExportIllisible, decoder, est_export_bnp, lire_export_bnp
from metabank.banque.modele import TYPES_PAR_PREFIXE as TYPES_BANQUE
from metabank.base.archives import DOSSIER as DOSSIER_ARCHIVES
from metabank.base.integration import importer_fichier
from metabank.connecteurs.registre import composer_lecteur, lister_connecteurs
from metabank.corrections import cle_contrat
from metabank.depot_unique import importer_sans_titulaire
from metabank.releves import TYPES_PAR_PREFIXE, lire_releve
from metabank.releves.modele import Releve
from metabank.releves.texte import ErreurLecture, extraire_texte

TAILLE_MAX = 20 * 1024 * 1024
TITULAIRE_VALIDE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' -]{0,39}$")
CARACTERES_INTERDITS = re.compile(r"[^\w .,'()-]")
PREFIXES_PAR_TYPE = {type_: prefixe for prefixe, type_ in TYPES_PAR_PREFIXE.items()}


class DepotRefuse(ValueError):
    """Relevé refusé : le message dit pourquoi, en français."""


def deposer_releve(dossier: Path, titulaire: str, nom_fichier: str, contenu: bytes) -> dict:
    """Rendre où le fichier a été archivé (chemin relatif à data/), après l'avoir lu et enregistré en base.

    Raises:
        DepotRefuse: fichier vide, trop gros, pas un PDF, titulaire invalide ou relevé non reconnu.
    """
    titulaire = titulaire.strip()
    if titulaire and not TITULAIRE_VALIDE.match(titulaire):
        raise DepotRefuse("prénom du titulaire invalide")
    if not contenu or len(contenu) > TAILLE_MAX:
        raise DepotRefuse("fichier vide ou de plus de 20 Mo")
    if not titulaire:
        return _deposer_sans_titulaire(dossier, nom_fichier, contenu)
    if not contenu.startswith(b"%PDF"):
        return _deposer_export(dossier, titulaire, nom_fichier, contenu)
    releve = _lire(contenu, nom_fichier)
    provenance = f"{titulaire}/{_dossier_contrat(dossier, titulaire, releve)}"
    if releve.est_annuel:
        provenance += f"/{releve.date_arrete.year}"
    chemin, deja = _archiver(dossier, provenance, _nom_propre(nom_fichier), contenu)
    return _reponse(chemin, releve, deja_present=deja)


def _deposer_sans_titulaire(dossier: Path, nom_fichier: str, contenu: bytes) -> dict:
    """Rendre où le fichier a été archivé, rangé d'après son contenu dans le dossier de son compte déjà connu."""
    extension = ".pdf" if contenu.startswith(b"%PDF") else ".csv"
    try:
        resultat = importer_sans_titulaire(dossier, lister_connecteurs(), _nom_propre(nom_fichier, extension), contenu)
    except ValueError as erreur:
        # Compte encore inconnu, fichier non reconnu ou illisible : la page demande alors le titulaire.
        raise DepotRefuse(str(erreur)) from erreur
    return {"chemin": f"{DOSSIER_ARCHIVES}/{resultat.chemin}", "connecteur": resultat.connecteur,
            "deja_present": resultat.deja_present}  # fmt: skip


def _archiver(dossier: Path, provenance: str, nom: str, contenu: bytes) -> tuple[str, bool]:
    """Rendre le chemin de l'archive, relatif à data/, et vrai si ce contenu était déjà archivé."""
    try:
        resultat = importer_fichier(dossier, provenance, nom, contenu, composer_lecteur(lister_connecteurs()))
    except ValueError as erreur:
        # Lu par le dépôt mais refusé par le connecteur (contrôle de cohérence, montant inexact) : rien n'est archivé.
        raise DepotRefuse(str(erreur)) from erreur
    return f"{DOSSIER_ARCHIVES}/{resultat.chemin}", resultat.deja_present


def _sous_dossiers(dossier: Path, titulaire: str) -> list[Path]:
    """Rendre les dossiers de comptes du titulaire, archivés d'abord, puis ceux encore rangés à la main."""
    racines = (dossier / DOSSIER_ARCHIVES / titulaire, dossier / titulaire)
    return [d for racine in racines if racine.is_dir() for d in sorted(racine.iterdir()) if d.is_dir()]


def _lire(contenu: bytes, nom_fichier: str) -> Releve:
    with tempfile.TemporaryDirectory() as temporaire:
        pdf = Path(temporaire) / "releve.pdf"
        pdf.write_bytes(contenu)
        try:
            return lire_releve(extraire_texte(pdf), nom_fichier)
        except ErreurLecture as erreur:
            raise DepotRefuse(f"relevé non reconnu : {erreur}") from erreur


def _dossier_contrat(dossier: Path, titulaire: str, releve: Releve) -> str:
    """Rendre le nom du dossier du contrat : celui qui finit par le numéro, sinon un nouveau, nommé comme les autres."""
    cle = cle_contrat(releve.numero)
    existants = [d.name for d in _sous_dossiers(dossier, titulaire) if d.name.replace(" ", "").endswith(cle)]
    if existants:
        return existants[0]
    prefixe = PREFIXES_PAR_TYPE.get(releve.type_contrat, "AUTRE")
    return _nom_propre(f"{prefixe} - {releve.assureur} - {releve.produit} {cle}", extension="")


def _nom_propre(nom: str, extension: str = ".pdf") -> str:
    """Rendre un nom de fichier sans chemin ni caractère spécial, terminé par l'extension."""
    base = CARACTERES_INTERDITS.sub("_", Path(nom).name).strip(" .") or "releve"
    if extension and not base.lower().endswith(extension):
        base += extension
    return base[:150]


def _reponse(chemin: str, releve: Releve, deja_present: bool) -> dict:
    return {
        "chemin": chemin,
        "assureur": releve.assureur,
        "produit": releve.produit,
        "date": releve.date_arrete.isoformat(),
        "annuel": releve.est_annuel,
        "deja_present": deja_present,
    }


def _deposer_export(dossier: Path, titulaire: str, nom_fichier: str, contenu: bytes) -> dict:
    """Rendre où l'export bancaire (CSV BNP) a été rangé : dans le dossier du compte qui finit par ses chiffres."""
    try:
        texte = decoder(contenu)
    except UnicodeDecodeError as erreur:
        raise DepotRefuse("ni un PDF ni un export CSV lisible") from erreur
    if not est_export_bnp(texte):
        raise DepotRefuse("ni un relevé PDF reconnu ni un export d'opérations BNP")
    try:
        export = lire_export_bnp(texte, nom_fichier)
    except ExportIllisible as erreur:
        raise DepotRefuse(str(erreur)) from erreur
    chiffres = export.numero_masque.lstrip("*")
    existants = [
        d.name for d in _sous_dossiers(dossier, titulaire)
        if d.name.split(" - ")[0].strip().upper() in TYPES_BANQUE and d.name.strip().endswith(chiffres)
    ]  # fmt: skip
    nom_compte = export.nom.upper()
    prefixe = "LA" if "LIVRET A" in nom_compte else "LDD" if "LDD" in nom_compte else "CC"
    cible = existants[0] if existants else f"{prefixe} - BNP - {chiffres}"
    chemin, deja = _archiver(dossier, f"{titulaire}/{cible}", _nom_propre(nom_fichier, extension=".csv"), contenu)
    return {"chemin": chemin, "assureur": "BNP", "produit": export.nom,
            "date": export.date_solde.isoformat(), "annuel": False, "deja_present": deja}  # fmt: skip

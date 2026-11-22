"""Dépôt d'un relevé PDF depuis la page : il est lu, puis rangé dans data/<titulaire>/<contrat>/<année>/.

Le fichier n'est rangé que s'il a été reconnu : un PDF illisible ou d'un assureur inconnu est refusé, pour que
data/ ne contienne que ce que metabank sait lire.
"""

import re
import tempfile
from pathlib import Path

from metabank.banque.bnp import ExportIllisible, decoder, est_export_bnp, lire_export_bnp
from metabank.banque.modele import TYPES_PAR_PREFIXE as TYPES_BANQUE
from metabank.corrections import cle_contrat
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
    """Rendre où le relevé a été rangé, après l'avoir lu et écrit dans dossier/<titulaire>/<contrat>/.

    Raises:
        DepotRefuse: fichier vide, trop gros, pas un PDF, titulaire invalide ou relevé non reconnu.
    """
    titulaire = titulaire.strip()
    if not TITULAIRE_VALIDE.match(titulaire):
        raise DepotRefuse("prénom du titulaire invalide")
    if not contenu or len(contenu) > TAILLE_MAX:
        raise DepotRefuse("fichier vide ou de plus de 20 Mo")
    if not contenu.startswith(b"%PDF"):
        return _deposer_export(dossier, titulaire, nom_fichier, contenu)
    releve = _lire(contenu, nom_fichier)
    dossier_contrat = _dossier_contrat(dossier / titulaire, releve)
    cible = dossier_contrat / str(releve.date_arrete.year) if releve.est_annuel else dossier_contrat
    nom = _nom_propre(nom_fichier)
    chemin = cible / nom
    if chemin.exists() and chemin.read_bytes() == contenu:
        return _reponse(dossier, chemin, releve, deja_present=True)
    rang = 2
    while chemin.exists():
        chemin = cible / f"{Path(nom).stem} ({rang}).pdf"
        rang += 1
    cible.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(".pdf.tmp")
    temporaire.write_bytes(contenu)
    temporaire.replace(chemin)
    return _reponse(dossier, chemin, releve, deja_present=False)


def _lire(contenu: bytes, nom_fichier: str) -> Releve:
    with tempfile.TemporaryDirectory() as temporaire:
        pdf = Path(temporaire) / "releve.pdf"
        pdf.write_bytes(contenu)
        try:
            return lire_releve(extraire_texte(pdf), nom_fichier)
        except ErreurLecture as erreur:
            raise DepotRefuse(f"relevé non reconnu : {erreur}") from erreur


def _dossier_contrat(dossier_titulaire: Path, releve: Releve) -> Path:
    """Rendre le dossier du contrat : celui dont le nom finit par le numéro, sinon un nouveau, nommé comme les autres."""
    cle = cle_contrat(releve.numero)
    if dossier_titulaire.exists():
        existants = [d for d in dossier_titulaire.iterdir() if d.is_dir() and d.name.replace(" ", "").endswith(cle)]
        if existants:
            return existants[0]
    prefixe = PREFIXES_PAR_TYPE.get(releve.type_contrat, "AUTRE")
    return dossier_titulaire / _nom_propre(f"{prefixe} - {releve.assureur} - {releve.produit} {cle}", extension="")


def _nom_propre(nom: str, extension: str = ".pdf") -> str:
    """Rendre un nom de fichier sans chemin ni caractère spécial, terminé par l'extension."""
    base = CARACTERES_INTERDITS.sub("_", Path(nom).name).strip(" .") or "releve"
    if extension and not base.lower().endswith(extension):
        base += extension
    return base[:150]


def _reponse(dossier: Path, chemin: Path, releve: Releve, deja_present: bool) -> dict:
    return {
        "chemin": str(chemin.relative_to(dossier)),
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
    dossier_titulaire = dossier / titulaire
    existants = [
        d for d in (dossier_titulaire.iterdir() if dossier_titulaire.exists() else [])
        if d.is_dir() and d.name.split(" - ")[0].strip().upper() in TYPES_BANQUE and d.name.strip().endswith(chiffres)
    ]  # fmt: skip
    nom_compte = export.nom.upper()
    prefixe = "LA" if "LIVRET A" in nom_compte else "LDD" if "LDD" in nom_compte else "CC"
    cible = existants[0] if existants else dossier_titulaire / f"{prefixe} - BNP - {chiffres}"
    nom = _nom_propre(nom_fichier, extension=".csv")
    chemin = cible / nom
    if chemin.exists() and chemin.read_bytes() == contenu:
        deja = True
    else:
        deja, rang = False, 2
        while chemin.exists():
            chemin = cible / f"{Path(nom).stem} ({rang}).csv"
            rang += 1
        cible.mkdir(parents=True, exist_ok=True)
        temporaire = chemin.with_suffix(".csv.tmp")
        temporaire.write_bytes(contenu)
        temporaire.replace(chemin)
    return {"chemin": str(chemin.relative_to(dossier)), "assureur": "BNP", "produit": export.nom,
            "date": export.date_solde.isoformat(), "annuel": False, "deja_present": deja}  # fmt: skip

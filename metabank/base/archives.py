"""Archives brutes : chaque fichier entré dans metabank, gardé tel quel dans data/archives/.

La base se reconstruit depuis elles seules (base/integration.py) : on n'y modifie ni n'y efface rien.
Rangement : data/archives/<provenance>/<nom>, la provenance étant le dossier du compte (« Alice/CC - BNP - 1234 »).
L'ordre des imports est celui des dates de modification des fichiers : une copie de data/ doit les conserver
(cp -p, rsync -a), sinon la base reconstruite garde les mêmes chiffres mais attribue autrement les doublons.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

DOSSIER = "archives"


class CheminRefuse(ValueError):
    """Provenance ou nom de fichier qui sortirait de data/archives/ ou serait invisible."""


@dataclass(frozen=True)
class Archive:
    """Un fichier archivé.

    Attributes:
        chemin: relatif à data/archives/, séparateur « / ».
        empreinte: SHA-256 du contenu, en hexadécimal : deux fichiers identiques ont la même.
        taille: en octets.
        archivee_le: date de modification du fichier, UTC, ISO 8601 à la microseconde.
    """

    chemin: str
    empreinte: str
    taille: int
    archivee_le: str


def calculer_empreinte(contenu: bytes) -> str:
    """Rendre le SHA-256 du contenu, en hexadécimal."""
    return hashlib.sha256(contenu).hexdigest()


def choisir_chemin(dossier_data: Path, provenance: str, nom: str) -> Path:
    """Rendre un chemin libre pour ce fichier : data/archives/<provenance>/<nom>, ou « nom (2) » s'il est pris.

    Raises:
        CheminRefuse: provenance absolue, avec « .. », vide, ou nom de fichier caché.
    """
    morceaux = PurePosixPath(provenance).parts
    if not morceaux or PurePosixPath(provenance).is_absolute() or any(m in (".", "..") for m in morceaux):
        raise CheminRefuse(f"provenance refusée : {provenance!r}")
    propre = Path(nom.replace("\\", "/")).name
    if not propre or propre.startswith(".") or propre.endswith(".tmp"):
        raise CheminRefuse(f"nom de fichier refusé : {nom!r}")
    dossier = dossier_data / DOSSIER / Path(*morceaux)
    chemin, rang = dossier / propre, 2
    while chemin.exists():
        chemin = dossier / f"{Path(propre).stem} ({rang}){Path(propre).suffix}"
        rang += 1
    return chemin


def ecrire_archive(dossier_data: Path, chemin: Path, contenu: bytes) -> Archive:
    """Rendre l'archive écrite à chemin (temporaire puis renommage, pour ne jamais laisser un fichier tronqué)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    temporaire.write_bytes(contenu)
    temporaire.replace(chemin)
    return decrire_archive(dossier_data, chemin)


def decrire_archive(dossier_data: Path, chemin: Path) -> Archive:
    """Rendre la description d'un fichier de data/archives/ (empreinte, taille, date de modification)."""
    contenu = chemin.read_bytes()
    nanosecondes = chemin.stat().st_mtime_ns
    # Pas de st_mtime (flottant) : à 1,7e9 secondes, sa précision ne garantit plus la microseconde.
    le = datetime.fromtimestamp(nanosecondes // 10**9, tz=UTC).replace(microsecond=nanosecondes // 1000 % 10**6)
    return Archive(
        chemin=chemin.relative_to(dossier_data / DOSSIER).as_posix(),
        empreinte=calculer_empreinte(contenu),
        taille=len(contenu),
        archivee_le=le.isoformat(timespec="microseconds"),
    )


def lister_archives(dossier_data: Path) -> list[Archive]:
    """Rendre les archives dans l'ordre où elles sont entrées (date de modification, puis chemin)."""
    racine = dossier_data / DOSSIER
    if not racine.is_dir():
        return []
    fichiers = (
        f for f in racine.rglob("*") if f.is_file() and not f.name.startswith(".") and not f.name.endswith(".tmp")
    )
    return sorted((decrire_archive(dossier_data, f) for f in fichiers), key=lambda a: (a.archivee_le, a.chemin))

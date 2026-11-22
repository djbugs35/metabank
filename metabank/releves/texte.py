"""Outils communs de lecture du texte extrait des PDF (pdftotext -layout)."""

import re
import shutil
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path

# Montant français : « 1 418,01 », « 57 994,02 », « 50 », « -743,90 ». Espace simple ou insécable entre milliers.
MOTIF_MONTANT = r"-?\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:,\d+)?"
MOTIF_ISIN = r"[A-Z]{2}[A-Z0-9]{9}\d"
# pdftotext -layout sépare les colonnes par au moins deux espaces ; un seul espace reste dans une cellule.
SEPARATEUR_COLONNES = re.compile(r"\s{2,}")
MOIS = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
}  # fmt: skip


class ErreurLecture(Exception):
    """PDF illisible ou de forme inconnue, avec un message qui dit quoi faire."""


def extraire_texte(pdf: Path) -> str:
    """Rendre le texte du PDF mis en page (colonnes alignées), via pdftotext de poppler."""
    if shutil.which("pdftotext") is None:
        raise ErreurLecture("pdftotext absent : « brew install poppler » (Mac) ou « apt install poppler-utils »")
    resultat = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=False)
    if resultat.returncode != 0:
        raise ErreurLecture(f"{pdf.name} : pdftotext a échoué ({resultat.stderr.strip()})")
    return resultat.stdout


def en_decimal(montant: str) -> Decimal:
    """Rendre le Decimal d'un montant écrit à la française (« 1 418,01 » -> 1418.01)."""
    return Decimal(re.sub(r"[ \u00a0\u202f]", "", montant).replace(",", "."))


def colonnes(ligne: str) -> list[str]:
    """Rendre les cellules non vides d'une ligne mise en page."""
    return [cellule for cellule in SEPARATEUR_COLONNES.split(ligne.strip()) if cellule]


def est_montant(texte: str) -> bool:
    """Rendre vrai si le texte est un montant seul."""
    return re.fullmatch(MOTIF_MONTANT, texte) is not None


def a_plat(texte: str) -> str:
    """Rendre le texte sur une seule ligne, espaces réduits : les phrases coupées en fin de ligne se recollent."""
    return re.sub(r"\s+", " ", texte)


def date_en_lettres(jour: str, mois: str, annee: str) -> date:
    """Rendre la date de « 31 décembre 2025 »."""
    return date(int(annee), MOIS[mois.lower()], int(jour))


def chercher_montant(motif: str, texte: str) -> Decimal | None:
    """Rendre le montant capturé par le premier groupe du motif dans le texte à plat, ou None."""
    trouve = re.search(motif, texte, flags=re.IGNORECASE)
    return en_decimal(trouve.group(1)) if trouve else None

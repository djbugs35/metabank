"""Fixtures communes : PDF simulés et dossier data/ fictif rangé à l'ancienne (données fictives seulement)."""

from pathlib import Path

import pytest

import metabank.connecteurs._releves as socle_releves
from metabank import releves
from tests.test_credit import _export_credit

EXEMPLES = Path(__file__).parent / "exemples"
# Un faux PDF : cet en-tête suivi du texte que pdftotext rendrait (tests/exemples/*.txt).
ENTETE_PDF = b"%PDF-fictif\n"


@pytest.fixture
def pdf_simules(monkeypatch):
    """Remplacer pdftotext : le texte du faux PDF suit son en-tête."""

    def texte(contenu: bytes) -> str | None:
        return contenu.removeprefix(ENTETE_PDF).decode() if contenu.startswith(ENTETE_PDF) else None

    monkeypatch.setattr(socle_releves, "extraire_texte_contenu", texte)
    monkeypatch.setattr(releves, "extraire_texte", lambda pdf: texte(pdf.read_bytes()))


def pdf(nom: str) -> bytes:
    """Rendre un faux PDF dont le texte est tests/exemples/<nom>."""
    return ENTETE_PDF + (EXEMPLES / nom).read_bytes()


def ranger(dossier: Path, chemin: str, contenu: bytes) -> None:
    """Écrire un fichier sous dossier/, dossiers compris."""
    fichier = dossier / chemin
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_bytes(contenu)


@pytest.fixture
def donnees(tmp_path, pdf_simules) -> Path:  # noqa: ARG001 (fixture requise, valeur inutile)
    """Rendre un data/ fictif rangé à l'ancienne : relevés, comptes, livret et crédit."""
    ranger(tmp_path, "Alice/AV - Suravenir - Vie Plus 270549974/2025/releve.pdf", pdf("suravenir_av_2025.txt"))
    ranger(tmp_path, "Bruno/PER - Suravenir - Per 123456789/2024/releve.pdf", pdf("suravenir_per_2024.txt"))
    ranger(tmp_path, "Bruno/PERP - Cardif - Perp 987654/situation.pdf", pdf("cardif_situation.txt"))
    ranger(tmp_path, "Alice/CC - BNP - 1234/export.csv", (EXEMPLES / "bnp_courant.csv").read_bytes())
    ranger(tmp_path, "Alice/LA - BNP - 5678/export.csv", (EXEMPLES / "bnp_livret.csv").read_bytes())
    ranger(tmp_path, "Crédits/RP - BNP - 6783/pret.csv", _export_credit().encode())
    (tmp_path / "corrections.json").write_text("{}")
    return tmp_path

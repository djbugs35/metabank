"""Connecteurs réels (BNP, Suravenir, Cardif) et passage à la base : mêmes chiffres que les anciens lecteurs.

Les PDF sont simulés : « %PDF-fictif » suivi du texte que pdftotext rendrait (tests/exemples/*.txt).
"""

from pathlib import Path

import pytest

import metabank.connecteurs._releves as socle_releves
from metabank import releves
from metabank.archivage import archiver_donnees, comparer_avec_fichiers
from metabank.banque import lire_comptes
from metabank.base.integration import FICHIER_BASE, importer_fichier, ouvrir_base, reconstruire
from metabank.base.lecture import lire_comptes_bancaires, lire_releves
from metabank.base.lot import LectureImpossible
from metabank.base.schema import ouvrir
from metabank.connecteurs.registre import composer_lecteur, lister_connecteurs, trouver
from metabank.releves.serialisation import releve_depuis_json, releve_en_json
from metabank.releves.texte import ErreurLecture
from tests.test_credit import _export_credit

EXEMPLES = Path(__file__).parent / "exemples"
ENTETE_PDF = b"%PDF-fictif\n"
CONNECTEURS = lister_connecteurs()


@pytest.fixture(autouse=True)
def pdf_simules(monkeypatch):
    """Remplacer pdftotext : le texte du faux PDF suit son en-tête."""

    def texte(contenu: bytes) -> str | None:
        return contenu.removeprefix(ENTETE_PDF).decode() if contenu.startswith(ENTETE_PDF) else None

    monkeypatch.setattr(socle_releves, "extraire_texte_contenu", texte)
    monkeypatch.setattr(releves, "extraire_texte", lambda pdf: texte(pdf.read_bytes()))


def lire_comptes_bancaires_fichiers(dossier: Path) -> list:
    return lire_comptes(dossier)[0]


def _pdf(nom: str) -> bytes:
    return ENTETE_PDF + (EXEMPLES / nom).read_bytes()


def _ranger(dossier: Path, chemin: str, contenu: bytes) -> None:
    fichier = dossier / chemin
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_bytes(contenu)


@pytest.fixture
def donnees(tmp_path) -> Path:
    """Rendre un data/ fictif rangé à l'ancienne : relevés, comptes, livret et crédit."""
    _ranger(tmp_path, "Alice/AV - Suravenir - Vie Plus 270549974/2025/releve.pdf", _pdf("suravenir_av_2025.txt"))
    _ranger(tmp_path, "Bruno/PER - Suravenir - Per 123456789/2024/releve.pdf", _pdf("suravenir_per_2024.txt"))
    _ranger(tmp_path, "Bruno/PERP - Cardif - Perp 987654/situation.pdf", _pdf("cardif_situation.txt"))
    _ranger(tmp_path, "Alice/CC - BNP - 1234/export.csv", (EXEMPLES / "bnp_courant.csv").read_bytes())
    _ranger(tmp_path, "Alice/LA - BNP - 5678/export.csv", (EXEMPLES / "bnp_livret.csv").read_bytes())
    _ranger(tmp_path, "Crédits/RP - BNP - 6783/pret.csv", _export_credit().encode())
    (tmp_path / "corrections.json").write_text("{}")
    return tmp_path


def test_chaque_fichier_existant_trouve_son_connecteur(donnees):
    bilan = archiver_donnees(donnees, CONNECTEURS)
    assert (bilan.archives, bilan.deja_presents, bilan.refus) == (6, 0, [])


def test_la_base_donne_les_memes_chiffres_que_les_anciens_lecteurs(donnees):
    archiver_donnees(donnees, CONNECTEURS)
    assert comparer_avec_fichiers(donnees, CONNECTEURS) == []


def test_archiver_deux_fois_ne_double_rien_et_laisse_les_fichiers_d_origine(donnees):
    archiver_donnees(donnees, CONNECTEURS)
    bilan = archiver_donnees(donnees, CONNECTEURS)
    assert (bilan.archives, bilan.deja_presents) == (0, 6)
    assert (donnees / "Alice/CC - BNP - 1234/export.csv").exists()
    assert comparer_avec_fichiers(donnees, CONNECTEURS) == []


def test_les_anciens_lecteurs_ignorent_le_dossier_des_archives(donnees):
    avant = (len(releves.lire_dossier(donnees)[0]), len(lire_comptes_bancaires_fichiers(donnees)))
    archiver_donnees(donnees, CONNECTEURS)
    assert (len(releves.lire_dossier(donnees)[0]), len(lire_comptes_bancaires_fichiers(donnees))) == avant


def test_la_base_reconstruite_garde_les_memes_chiffres(donnees):
    archiver_donnees(donnees, CONNECTEURS)
    (donnees / FICHIER_BASE).unlink()
    reconstruire(donnees, composer_lecteur(CONNECTEURS))
    assert comparer_avec_fichiers(donnees, CONNECTEURS) == []


def test_un_ecart_entre_fichiers_et_base_est_signale(donnees):
    archiver_donnees(donnees, CONNECTEURS)
    _ranger(donnees, "Alice/LDD - BNP - 9999/nouveau.csv", (EXEMPLES / "bnp_livret.csv").read_bytes().replace(
        b"****5678", b"****9999"))  # fmt: skip
    (donnees / "Alice/CC - BNP - 1234/export.csv").unlink()
    ecarts = comparer_avec_fichiers(donnees, CONNECTEURS)
    assert "compte Alice ldd ****9999 : absent de la base" in ecarts
    assert "compte Alice courant ****1234 : en base mais plus dans les fichiers" in ecarts


def test_le_credit_range_dans_credits_revient_au_foyer(donnees):
    archiver_donnees(donnees, CONNECTEURS)
    connexion = ouvrir(donnees / FICHIER_BASE)
    credits = [c for c in lire_comptes_bancaires(connexion) if c.type_compte == "credit"]
    connexion.close()
    assert [(c.titulaire, c.nom) for c in credits] == [("Joint", "Crédit rp")]


def test_les_supports_d_un_releve_sont_en_base_avec_leurs_parts(donnees):
    archiver_donnees(donnees, CONNECTEURS)
    connexion = ouvrir(donnees / FICHIER_BASE)
    nombre, avec_isin = connexion.execute("SELECT count(*), count(isin) FROM positions").fetchone()
    contrats = connexion.execute("SELECT numero_masque FROM comptes WHERE type_compte = 'assurance_vie'").fetchall()
    connexion.close()
    assert nombre > 0 and avec_isin > 0
    assert contrats == [("****6789",)]


def test_un_releve_fait_l_aller_retour_en_json_sans_perte(donnees):
    for range_ in releves.lire_dossier(donnees)[0]:
        assert releve_depuis_json(releve_en_json(range_.releve)) == range_.releve


def test_un_export_bnp_hors_d_un_dossier_de_type_connu_est_refuse(tmp_path):
    lire = composer_lecteur(CONNECTEURS)
    with pytest.raises(LectureImpossible, match="ni un crédit"):
        importer_fichier(tmp_path, "Alice/Divers", "e.csv", (EXEMPLES / "bnp_courant.csv").read_bytes(), lire)


def test_un_export_bnp_abime_est_refuse_avec_sa_raison(tmp_path):
    abime = (EXEMPLES / "bnp_courant.csv").read_bytes() + b"pas;une;ligne\n"
    with pytest.raises(LectureImpossible, match="champs"):
        importer_fichier(tmp_path, "Alice/CC - BNP - 1234", "e.csv", abime, composer_lecteur(CONNECTEURS))


def test_un_pdf_d_assureur_inconnu_n_est_reconnu_par_personne():
    lire = composer_lecteur(CONNECTEURS)
    assert lire("Alice/AV - X - 1", "x.pdf", ENTETE_PDF + b"Assureur inconnu\n") is None


def test_sans_pdftotext_un_pdf_est_refuse_avec_le_moyen_de_l_installer(monkeypatch):
    def absent(_contenu: bytes) -> str:
        raise ErreurLecture("pdftotext absent : « brew install poppler »")

    monkeypatch.setattr(socle_releves, "extraire_texte_contenu", absent)
    with pytest.raises(LectureImpossible, match="brew install poppler"):
        trouver(CONNECTEURS, "suravenir_pdf").reconnaitre("x.pdf", b"%PDF")


def test_la_base_se_rouvre_sans_reconstruire_quand_elle_existe(donnees):
    archiver_donnees(donnees, CONNECTEURS)
    connexion = ouvrir_base(donnees, composer_lecteur(CONNECTEURS))
    assert len(lire_releves(connexion)) == 3
    connexion.close()


def test_un_solde_d_export_incoherent_est_signale_comme_par_les_anciens_lecteurs(donnees):
    lignes = (EXEMPLES / "bnp_courant.csv").read_text().splitlines()
    decembre = [ligne for ligne in lignes[1:] if ligne[3:10] == "12/2025"]
    entete = lignes[0].split(";")
    entete[3], entete[5] = "20/12/2025", "1,00"
    _ranger(donnees, "Alice/CC - BNP - 1234/ancien.csv", "\n".join([";".join(entete), *decembre]).encode())
    archiver_donnees(donnees, CONNECTEURS)
    connexion = ouvrir(donnees / FICHIER_BASE)
    courant = next(c for c in lire_comptes_bancaires(connexion) if c.type_compte == "courant")
    connexion.close()
    assert len(courant.anomalies) == 1 and "ancien.csv" in courant.anomalies[0]
    assert comparer_avec_fichiers(donnees, CONNECTEURS) == []

"""Base SQLite et archives : import sans doublon, reconstruction à l'identique. Données fictives."""

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from metabank.base.archives import CheminRefuse, lister_archives
from metabank.base.integration import FICHIER_BASE, FichierNonReconnu, importer_fichier, ouvrir_base, reconstruire
from metabank.base.lot import CompteLu, LectureImpossible, Lot, OperationLue, SoldeLu
from metabank.base.montants import MontantInexact, depuis_centimes, en_centimes
from metabank.base.schema import VERSION, BaseTropRecente, ouvrir

PROVENANCE = "Alice/CC - Fictive - 1234"
COMPTE = CompteLu("FICTIVE:courant:****1234", "Alice", "Fictive", "courant", "****1234", "Compte courant")


def lire_fictif(provenance: str, nom: str, contenu: bytes) -> Lot | None:
    """Lire le format de test : une ligne « jour;libellé;montant » par opération, « solde;jour;montant » à la fin."""
    del provenance, nom
    texte = contenu.decode()
    if not texte.startswith("FICTIF\n"):
        return None
    if "ILLISIBLE" in texte:
        raise LectureImpossible("ligne illisible")
    operations, soldes = [], []
    for ligne in texte.splitlines()[1:]:
        a, b, c = ligne.split(";")
        if a == "solde":
            soldes.append(SoldeLu(COMPTE.cle, date.fromisoformat(b), Decimal(c)))
        else:
            operations.append(OperationLue(COMPTE.cle, f"{a}|{b}|{c}", date.fromisoformat(a), b, Decimal(c)))
    return Lot("fictif", (COMPTE,), tuple(operations), tuple(soldes))


JANVIER = b"FICTIF\n2026-01-05;Boulangerie;-3.50\n2026-01-28;Salaire;2000.00\nsolde;2026-01-31;2996.50\n"
FEVRIER = b"FICTIF\n2026-01-28;Salaire;2000.00\n2026-02-03;Loyer;-800.00\nsolde;2026-02-28;2196.50\n"


def _importer(dossier: Path, nom: str, contenu: bytes):
    return importer_fichier(dossier, PROVENANCE, nom, contenu, lire_fictif)


def _contenu_base(dossier: Path) -> str:
    connexion = ouvrir(dossier / FICHIER_BASE)
    try:
        return "\n".join(connexion.iterdump())
    finally:
        connexion.close()


def test_un_montant_au_centime_pres_fait_l_aller_retour_en_centimes():
    assert en_centimes(Decimal("-3.5")) == -350
    assert depuis_centimes(-350) == Decimal("-3.50")


def test_une_fraction_de_centime_est_refusee_plutot_qu_arrondie():
    with pytest.raises(MontantInexact):
        en_centimes(Decimal("0.005"))


def test_une_nouvelle_base_est_creee_a_la_derniere_version_du_schema(tmp_path):
    connexion = ouvrir(tmp_path / "b.db")
    assert connexion.execute("PRAGMA user_version").fetchone()[0] == VERSION
    connexion.close()
    ouvrir(tmp_path / "b.db").close()


def test_une_base_ecrite_par_une_version_plus_recente_est_refusee(tmp_path):
    connexion = ouvrir(tmp_path / "b.db")
    connexion.execute(f"PRAGMA user_version = {VERSION + 1}")
    connexion.close()
    with pytest.raises(BaseTropRecente):
        ouvrir(tmp_path / "b.db")


def test_un_numero_de_compte_complet_n_entre_pas_en_base():
    with pytest.raises(ValueError, match="non masqué"):
        CompteLu("x", "Alice", "Fictive", "courant", "30004000000001234", "Compte")


def test_une_operation_sans_son_compte_rend_le_lot_invalide():
    with pytest.raises(ValueError, match="absents"):
        Lot("fictif", (), (OperationLue("inconnu", "1", date(2026, 1, 1), "x", Decimal(1)),))


def test_un_fichier_importe_est_archive_et_enregistre(tmp_path):
    resultat = _importer(tmp_path, "janvier.txt", JANVIER)
    assert (resultat.chemin, resultat.elements, resultat.deja_present) == (f"{PROVENANCE}/janvier.txt", 3, False)
    assert (tmp_path / "archives" / resultat.chemin).read_bytes() == JANVIER
    connexion = ouvrir(tmp_path / FICHIER_BASE)
    assert connexion.execute("SELECT sum(montant_centimes) FROM operations").fetchone()[0] == 199650
    connexion.close()


def test_le_meme_fichier_depose_deux_fois_n_est_ni_archive_ni_compte_deux_fois(tmp_path):
    _importer(tmp_path, "janvier.txt", JANVIER)
    resultat = _importer(tmp_path, "copie.txt", JANVIER)
    assert resultat.deja_present and resultat.chemin.endswith("janvier.txt") and resultat.connecteur == "fictif"
    assert len(lister_archives(tmp_path)) == 1


def test_une_operation_presente_dans_deux_exports_n_est_comptee_qu_une_fois(tmp_path):
    _importer(tmp_path, "janvier.txt", JANVIER)
    assert _importer(tmp_path, "fevrier.txt", FEVRIER).elements == 2
    connexion = ouvrir(tmp_path / FICHIER_BASE)
    assert connexion.execute("SELECT count(*) FROM operations").fetchone()[0] == 3
    connexion.close()


def test_un_nom_deja_pris_par_un_autre_contenu_recoit_un_numero(tmp_path):
    _importer(tmp_path, "export.txt", JANVIER)
    assert _importer(tmp_path, "export.txt", FEVRIER).chemin == f"{PROVENANCE}/export (2).txt"


def test_un_fichier_non_reconnu_est_refuse_sans_etre_archive(tmp_path):
    with pytest.raises(FichierNonReconnu):
        _importer(tmp_path, "inconnu.txt", b"autre chose")
    assert lister_archives(tmp_path) == []


def test_un_lot_invalide_ne_laisse_aucune_archive(tmp_path):
    with pytest.raises(MontantInexact):
        _importer(tmp_path, "centimes.txt", b"FICTIF\n2026-01-05;Arrondi;-0.005\n")
    assert lister_archives(tmp_path) == []


@pytest.mark.parametrize("provenance", ["../ailleurs", "/absolu", ""])
def test_une_provenance_qui_sortirait_des_archives_est_refusee(tmp_path, provenance):
    with pytest.raises(CheminRefuse):
        importer_fichier(tmp_path, provenance, "janvier.txt", JANVIER, lire_fictif)


def test_une_base_effacee_se_reconstruit_a_l_identique(tmp_path):
    _importer(tmp_path, "janvier.txt", JANVIER)
    _importer(tmp_path, "fevrier.txt", FEVRIER)
    avant = _contenu_base(tmp_path)
    (tmp_path / FICHIER_BASE).unlink()
    ouvrir_base(tmp_path, lire_fictif).close()
    assert _contenu_base(tmp_path) == avant


def test_la_reconstruction_suit_l_ordre_d_entree_des_archives(tmp_path):
    fevrier = _importer(tmp_path, "b-fevrier.txt", FEVRIER)
    janvier = _importer(tmp_path, "a-janvier.txt", JANVIER)
    os.utime(tmp_path / "archives" / fevrier.chemin, ns=(1, 1_000_000_000))
    os.utime(tmp_path / "archives" / janvier.chemin, ns=(1, 2_000_000_000))
    reconstruire(tmp_path, lire_fictif)
    connexion = ouvrir(tmp_path / FICHIER_BASE)
    premiere = connexion.execute("SELECT chemin FROM archives WHERE id = 1").fetchone()[0]
    connexion.close()
    assert premiere == fevrier.chemin


def test_une_archive_illisible_est_notee_au_journal_sans_arreter_la_reconstruction(tmp_path):
    _importer(tmp_path, "janvier.txt", JANVIER)
    dossier = tmp_path / "archives" / PROVENANCE
    (dossier / "abime.txt").write_bytes(b"FICTIF\nILLISIBLE\n")
    (dossier / "etranger.txt").write_bytes(b"pas un export")
    reconstruire(tmp_path, lire_fictif)
    connexion = ouvrir(tmp_path / FICHIER_BASE)
    journal = dict(connexion.execute("SELECT a.chemin, resultat FROM imports JOIN archives a ON a.id = archive_id"))
    nombre = connexion.execute("SELECT count(*) FROM operations").fetchone()[0]
    connexion.close()
    assert journal == {
        f"{PROVENANCE}/janvier.txt": "ok",
        f"{PROVENANCE}/abime.txt": "erreur",
        f"{PROVENANCE}/etranger.txt": "refus",
    }
    assert nombre == 2


def test_le_solde_d_un_jour_deja_connu_prend_la_valeur_du_dernier_import(tmp_path):
    _importer(tmp_path, "janvier.txt", JANVIER)
    _importer(tmp_path, "corrige.txt", b"FICTIF\nsolde;2026-01-31;2900.00\n")
    connexion = ouvrir(tmp_path / FICHIER_BASE)
    assert connexion.execute("SELECT montant_centimes FROM soldes").fetchall() == [(290000,)]
    connexion.close()

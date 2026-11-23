"""Passage à la base : copier les fichiers rangés dans data/<titulaire>/… vers data/archives/, puis vérifier.

Les fichiers d'origine ne sont ni déplacés ni modifiés : on peut relancer, comparer, et ne les retirer qu'une fois
la vérification sans écart. Le rapport ne montre ni montant ni numéro complet.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

from metabank.banque import lire_comptes
from metabank.base.archives import DOSSIERS_RESERVES
from metabank.base.integration import importer_fichier, ouvrir_base
from metabank.base.lecture import lire_comptes_bancaires, lire_releves
from metabank.connecteurs.contrat import Connecteur
from metabank.connecteurs.registre import composer_lecteur
from metabank.releves import lire_dossier

EXTENSIONS = (".pdf", ".csv")


@dataclass
class BilanArchivage:
    """Ce que l'archivage a fait : fichiers archivés, déjà présents, refusés (avec la raison)."""

    archives: int = 0
    deja_presents: int = 0
    refus: list[str] = field(default_factory=list)


def archiver_donnees(dossier_data: Path, connecteurs: list[Connecteur]) -> BilanArchivage:
    """Rendre le bilan de la copie en archives de chaque PDF et CSV rangé sous data/<titulaire>/<compte>/.

    Ordre des chemins : celui des anciens lecteurs, pour que le dernier export d'un compte en donne la description.
    """
    lire = composer_lecteur(connecteurs)
    bilan = BilanArchivage()
    fichiers = sorted(
        f
        for f in dossier_data.glob("*/*/**/*")
        if f.is_file()
        and f.suffix.lower() in EXTENSIONS
        and f.relative_to(dossier_data).parts[0] not in DOSSIERS_RESERVES
    )
    for fichier in fichiers:
        relatif = fichier.relative_to(dossier_data)
        try:
            resultat = importer_fichier(
                dossier_data, relatif.parent.as_posix(), fichier.name, fichier.read_bytes(), lire
            )
        except ValueError as erreur:
            # FichierNonReconnu, LectureImpossible, CheminRefuse, montant inexact : le fichier suivant passe quand même.
            bilan.refus.append(f"{relatif} : {erreur}")
            continue
        if resultat.deja_present:
            bilan.deja_presents += 1
        else:
            bilan.archives += 1
    return bilan


def comparer_avec_fichiers(dossier_data: Path, connecteurs: list[Connecteur]) -> list[str]:
    """Rendre les écarts entre ce que les anciens lecteurs tirent des fichiers et ce que la base contient.

    Une liste vide veut dire : mêmes relevés, mêmes comptes, mêmes soldes, mêmes opérations.
    """
    connexion = ouvrir_base(dossier_data, composer_lecteur(connecteurs))
    try:
        releves_base, comptes_base = lire_releves(connexion), lire_comptes_bancaires(connexion)
    finally:
        connexion.close()
    releves_fichiers, _ = lire_dossier(dossier_data)
    comptes_fichiers, _ = lire_comptes(dossier_data)
    return _ecarts_releves(releves_fichiers, releves_base) + _ecarts_comptes(comptes_fichiers, comptes_base)


def _ecarts_releves(fichiers: list, base: list) -> list[str]:
    def index(liste: list) -> dict:
        # Le nom de fichier peut gagner un « (2) » en archive : il ne compte pas.
        return {
            (r.titulaire, r.releve.numero, r.releve.date_arrete, r.releve.est_annuel): replace(r.releve, fichier="")
            for r in liste
        }

    attendus, obtenus = index(fichiers), index(base)
    ecarts = []
    for cle in sorted(attendus.keys() | obtenus.keys(), key=str):
        titulaire, numero, jour, _ = cle
        nom = f"relevé {titulaire} …{numero.replace(' ', '')[-4:]} du {jour}"
        if cle not in obtenus:
            ecarts.append(f"{nom} : absent de la base")
        elif cle not in attendus:
            ecarts.append(f"{nom} : en base mais plus dans les fichiers")
        elif attendus[cle] != obtenus[cle]:
            ecarts.append(f"{nom} : contenu différent")
    if len(fichiers) != len(attendus):
        ecarts.append(
            f"{len(fichiers) - len(attendus)} relevé(s) en double dans les fichiers, gardé(s) une fois en base"
        )
    return ecarts


def _ecarts_comptes(fichiers: list, base: list) -> list[str]:
    def index(liste: list) -> dict:
        return {(c.titulaire, c.type_compte, c.numero_masque): c for c in liste}

    attendus, obtenus = index(fichiers), index(base)
    ecarts = []
    for cle in sorted(attendus.keys() | obtenus.keys()):
        nom = f"compte {cle[0]} {cle[1]} {cle[2]}"
        attendu, obtenu = attendus.get(cle), obtenus.get(cle)
        if obtenu is None or attendu is None:
            ecarts.append(f"{nom} : {'absent de la base' if obtenu is None else 'en base mais plus dans les fichiers'}")
            continue
        ecarts.extend(
            f"{nom} : {champ} différent"
            for champ in ("nom", "banque", "date_solde", "solde", "anomalies")
            if getattr(attendu, champ) != getattr(obtenu, champ)
        )
        if sorted(attendu.operations, key=repr) != sorted(obtenu.operations, key=repr):
            ecarts.append(
                f"{nom} : opérations différentes ({len(attendu.operations)} attendues, {len(obtenu.operations)})"
            )
    return ecarts

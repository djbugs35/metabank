"""Comptes bancaires rangés dans data/<titulaire>/<CC|LA|LDD - banque - compte>/…/*.csv. MODELE § 7."""

from collections import Counter
from pathlib import Path

from metabank.banque.bnp import ExportIllisible, decoder, lire_export_bnp
from metabank.banque.modele import TYPES_PAR_PREFIXE, Compte, Export, Operation


def lire_comptes(dossier: Path) -> tuple[list[Compte], list[str]]:
    """Rendre les comptes bancaires de dossier/, chacun fusionné depuis tous ses exports, et les erreurs de lecture."""
    comptes, erreurs = [], []
    if not dossier.exists():
        return comptes, erreurs
    for dossier_compte in sorted(dossier.glob("*/*")):
        morceaux = [m.strip() for m in dossier_compte.name.split(" - ")]
        type_compte = TYPES_PAR_PREFIXE.get(morceaux[0].upper())
        if not dossier_compte.is_dir() or type_compte is None:
            continue
        exports = []
        for csv in sorted(dossier_compte.rglob("*.csv")):
            try:
                exports.append(lire_export_bnp(decoder(csv.read_bytes()), csv.name))
            except ExportIllisible as erreur:
                erreurs.append(f"{dossier_compte.parent.name}/{csv.name} : {erreur}")
        if exports:
            banque = morceaux[1] if len(morceaux) > 1 else "?"
            comptes.append(fusionner(dossier_compte.parent.name, banque, type_compte, exports))
    return comptes, erreurs


def fusionner(titulaire: str, banque: str, type_compte: str, exports: list[Export]) -> Compte:
    """Rendre le compte issu de plusieurs exports qui se chevauchent. MODELE § 7.1.

    Une opération (jour, libellé, montant) présente n fois dans un export compte n fois ; deux exports qui la
    contiennent tous deux ne la doublent pas (on garde le plus grand nombre). Le solde est celui de l'export le
    plus récent ; les soldes des autres exports servent de contrôle.
    """
    compte_par_cle: Counter = Counter()
    exemple: dict[tuple, Operation] = {}
    for export in exports:
        dans_export = Counter((o.jour, o.libelle, o.montant) for o in export.operations)
        for cle, nombre in dans_export.items():
            compte_par_cle[cle] = max(compte_par_cle[cle], nombre)
        exemple.update({(o.jour, o.libelle, o.montant): o for o in export.operations})
    operations = sorted((exemple[cle] for cle, nombre in compte_par_cle.items() for _ in range(nombre)),
                        key=lambda o: o.jour)  # fmt: skip
    reference = max(exports, key=lambda e: (e.date_solde, len(e.operations)))
    anomalies = []
    for export in exports:
        apres = sum((o.montant for o in operations if export.date_solde < o.jour <= reference.date_solde), start=0)
        attendu = reference.solde - apres
        if export is not reference and attendu != export.solde:
            anomalies.append(f"solde de {export.fichier} : {export.solde} € annoncé, {attendu} € recalculé")
    return Compte(titulaire, banque, type_compte, reference.nom, reference.numero_masque, reference.date_solde,
                  reference.solde, tuple(operations), tuple(anomalies))  # fmt: skip

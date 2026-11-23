"""Export CSV des opérations BNP Paribas (« Télécharger mes opérations ») : comptes, livrets, prêts.

Lecteur : banque/bnp.py. Le type de compte vient du préfixe du dossier (CC, LOCATIF, LA, LDD) ; un prêt est
reconnu à son contenu et, rangé dans un dossier « Crédits », rattaché au foyer (MODELE § 7).
"""

from collections import Counter

from metabank.banque import TITULAIRE_CREDITS, est_credit, est_dossier_credits
from metabank.banque.bnp import ExportIllisible, decoder, est_export_bnp, lire_export_bnp
from metabank.banque.modele import TYPES_PAR_PREFIXE, Export
from metabank.base.lot import CompteLu, LectureImpossible, Lot, OperationLue, SoldeLu
from metabank.connecteurs._provenance import morceaux_provenance
from metabank.connecteurs.contrat import ConnecteurFichier, Reconnaissance


class BnpCsv(ConnecteurFichier):
    """Export d'opérations BNP : solde à une date et opérations qui y mènent."""

    nom = "bnp_csv"
    libelle = "Export des opérations BNP Paribas (CSV)"
    mode_emploi = "Sur le site BNP Paribas, dans le compte : « Télécharger mes opérations », format CSV ; déposer le fichier dans l'onglet Relevés. Un export recouvre le précédent sans le doubler."
    etablissements = ("BNP Paribas",)
    types_comptes = ("courant", "locatif", "livret_a", "ldd", "credit")

    def reconnaitre(self, nom: str, contenu: bytes) -> Reconnaissance | None:
        """Rendre le compte si le fichier est un export d'opérations BNP : numéro masqué, et « credit » pour un prêt."""
        try:
            texte = decoder(contenu)
        except UnicodeDecodeError:
            return None
        if not est_export_bnp(texte):
            return None
        try:
            export = lire_export_bnp(texte, nom)
        except ExportIllisible:
            return Reconnaissance("BNP", "")
        return Reconnaissance("BNP", "credit" if est_credit(export) else "", export.numero_masque)

    def lire(self, provenance: str, nom: str, contenu: bytes) -> Lot:
        """Rendre le lot de l'export : le compte, ses opérations et son solde.

        Raises:
            LectureImpossible: export illisible, ou dossier sans type de compte connu pour un compte qui n'est
                pas un prêt.
        """
        try:
            export = lire_export_bnp(decoder(contenu), nom)
        except (ExportIllisible, UnicodeDecodeError) as erreur:
            raise LectureImpossible(f"{nom} : {erreur}") from erreur
        compte = _compte(provenance, export)
        return Lot(self.nom, (compte,), _operations(compte.cle, export), (SoldeLu(compte.cle, export.date_solde,
                                                                                    export.solde),))  # fmt: skip


def _compte(provenance: str, export: Export) -> CompteLu:
    titulaire, morceaux = morceaux_provenance(provenance)
    banque = morceaux[1] if len(morceaux) > 1 else "?"
    if est_credit(export):
        type_compte, libelle = "credit", f"Crédit {morceaux[0].lower()}"
        titulaire = TITULAIRE_CREDITS if est_dossier_credits(titulaire) else titulaire
    else:
        type_compte, libelle = TYPES_PAR_PREFIXE.get(morceaux[0].upper(), ""), export.nom
        if not type_compte:
            raise LectureImpossible(f"{provenance} : ni un crédit ni un type de compte connu")
    cle = f"{banque}:{type_compte}:{export.numero_masque}"
    return CompteLu(cle, titulaire, banque, type_compte, export.numero_masque, libelle)


def _operations(compte_cle: str, export: Export) -> tuple[OperationLue, ...]:
    # Identifiant = (jour, libellé, montant, rang parmi les identiques de l'export) : deux cafés le même jour restent
    # deux opérations, et un export qui recouvre le précédent ne les double pas (MODELE § 7.1).
    rangs: Counter = Counter()
    operations = []
    for o in export.operations:
        rangs[(o.jour, o.libelle, o.montant)] += 1
        identifiant = f"{o.jour.isoformat()}|{o.libelle}|{o.montant}|{rangs[(o.jour, o.libelle, o.montant)]}"
        operations.append(OperationLue(compte_cle, identifiant, o.jour, o.libelle, o.montant, o.type_banque,
                                       o.sous_type))  # fmt: skip
    return tuple(operations)


CONNECTEUR = BnpCsv()

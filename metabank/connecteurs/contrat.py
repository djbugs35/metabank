"""Ce qu'un connecteur doit savoir faire. Repris de metascrap (scrap_libs/acces/contrat.py).

QUATRE FAMILLES, UN SEUL CONTRAT
    fichier     reconnaît un fichier à son contenu, puis le lit (relevé PDF, export CSV).
    direct      interroge un service avec l'accord du titulaire (DSP2) ; sa réponse brute est archivée comme un
                fichier, qu'il sait ensuite relire : la base se reconstruit sans le rappeler.
    calcul      produit une donnée sans rien importer (capital restant dû projeté, intérêts attendus).
    reference   données publiques sans rien de personnel (valeurs liquidatives, indices, repères annuels).

ACTIF = SES RÉGLAGES SONT RENSEIGNÉS
    Un connecteur est actif quand chacun de ses réglages a une valeur ; sans réglage, il l'est toujours. Pas
    d'interrupteur à part : la présence du réglage est le réglage. Les valeurs secrètes viennent du coffre de la
    machine (trousseau macOS sur le Mac, autre coffre sur le NAS QNAP), jamais d'un fichier du dépôt ni de la base.

LECTURE SEULE
    Aucun connecteur ne passe de virement, d'ordre ni d'arbitrage : le contrat n'offre que des lectures.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from metabank.base.lot import Lot

FAMILLE_FICHIER = "fichier"
FAMILLE_DIRECT = "direct"
FAMILLE_CALCUL = "calcul"
FAMILLE_REFERENCE = "reference"

# Ce qui sort de la machine, affiché dans le synoptique.
RESEAU_LOCAL = "local"
RESEAU_DSP2 = "dsp2"
RESEAU_PUBLIC = "public"


class AccesIndisponible(RuntimeError):
    """Le service n'a pas répondu, ou a refusé (accord expiré, quota atteint) : essayer l'accès de secours."""


@dataclass(frozen=True)
class Reglage:
    """Un réglage attendu par un connecteur.

    Attributes:
        nom: unique parmi tous les connecteurs, préfixé du nom du connecteur (« enable_banking.application »).
        secret: rangé dans le coffre de la machine, jamais affiché ni écrit ailleurs.
    """

    nom: str
    libelle: str
    secret: bool = False


@dataclass(frozen=True)
class Reconnaissance:
    """Ce qu'un connecteur déduit d'un fichier sans le lire en entier : à quel compte il se rapporte.

    Attributes:
        numero_masque: « ****1234 », vide si le fichier ne le dit pas.
        titulaire: vide si le fichier ne le dit pas (le registre des comptes le dira).
    """

    etablissement: str
    type_compte: str
    numero_masque: str = ""
    titulaire: str = ""


@dataclass(frozen=True)
class EtatAcces:
    """L'état d'un accès direct, pour le synoptique. Une valeur inconnue reste vide, jamais devinée.

    Attributes:
        echeance: fin de l'accord donné à la banque, ou None (DSP2 : 180 jours).
    """

    joignable: bool = False
    echeance: date | None = None
    message: str = ""


@dataclass(frozen=True)
class Reponse:
    """La réponse brute d'un service, à archiver telle quelle (JSON en général)."""

    nom: str
    contenu: bytes


class Connecteur:
    """Une source de données. À dériver, une classe par source, dans un module de metabank/connecteurs/.

    Attributes:
        nom: identifiant court et stable, celui du journal et du registre des comptes.
        etablissements: établissements couverts, tels qu'affichés (« BNP Paribas »).
        types_comptes: types de comptes couverts (« courant », « livret_a », « assurance_vie »…).
        reglages: réglages qui le rendent actif.
        mode_emploi: comment le titulaire obtient la donnée, affiché dans le synoptique.
    """

    nom: str = ""
    libelle: str = ""
    famille: str = FAMILLE_FICHIER
    reseau: str = RESEAU_LOCAL
    etablissements: tuple[str, ...] = ()
    types_comptes: tuple[str, ...] = ()
    reglages: tuple[Reglage, ...] = ()
    mode_emploi: str = ""

    def est_actif(self, valeurs: Mapping[str, str]) -> bool:
        """Rendre vrai si chacun de ses réglages a une valeur non vide dans valeurs."""
        return all(str(valeurs.get(r.nom) or "").strip() for r in self.reglages)


class ConnecteurFichier(Connecteur):
    """Famille « fichier » : un fichier déposé, reconnu à son contenu et non à son nom."""

    famille = FAMILLE_FICHIER

    def reconnaitre(self, nom: str, contenu: bytes) -> Reconnaissance | None:
        """Rendre le compte auquel le fichier se rapporte, ou None s'il n'est pas de ce connecteur.

        Doit être rapide et ne jamais lever : tous les connecteurs sont essayés sur chaque fichier.
        """
        raise NotImplementedError

    def lire(self, provenance: str, nom: str, contenu: bytes) -> Lot:
        """Rendre le lot du fichier, déjà reconnu.

        Args:
            provenance: dossier de l'archive (« Alice/CC - BNP - 1234 »), qui porte le titulaire tant que le
                registre des comptes n'existe pas.

        Raises:
            LectureImpossible: format inattendu ou contrôle de cohérence échoué.
        """
        raise NotImplementedError


class ConnecteurDirect(ConnecteurFichier):
    """Famille « direct » : sa réponse est archivée, puis relue par reconnaitre() et lire() comme un fichier."""

    famille = FAMILLE_DIRECT
    reseau = RESEAU_DSP2

    def synchroniser(self, valeurs: Mapping[str, str], compte_cle: str, depuis: date) -> Reponse:
        """Rendre la réponse brute du service pour ce compte, opérations depuis la date donnée comprises.

        Raises:
            AccesIndisponible: service injoignable ou accord refusé.
        """
        raise NotImplementedError

    def etat(self, valeurs: Mapping[str, str]) -> EtatAcces:  # noqa: ARG002 (signature imposée par le contrat)
        """Rendre l'état de l'accès. Coûte un appel au service : à la demande seulement."""
        return EtatAcces()


class ConnecteurCalcul(Connecteur):
    """Famille « calcul » : des chiffres déduits de la base et des saisies, sans import ni réseau."""

    famille = FAMILLE_CALCUL

    def produire(self, jour: date) -> Lot:
        """Rendre le lot calculé pour ce jour (soldes projetés…)."""
        raise NotImplementedError


class ConnecteurReference(Connecteur):
    """Famille « référence » : données publiques. N'envoie que des ISIN ou des noms d'indices, rien de personnel."""

    famille = FAMILLE_REFERENCE
    reseau = RESEAU_PUBLIC

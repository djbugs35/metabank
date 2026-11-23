"""Connexion directe par Enable Banking (DSP2) : comptes de paiement BNP, en lecture seule.

La réponse de la banque est archivée comme un fichier (JSON, IBAN masqués), puis relue par lire() : la base se
reconstruit sans rappeler la banque. Une opération déjà apportée par l'export CSV n'est pas comptée deux fois
(MODELE § 7.1 bis). Seules les opérations comptabilisées (« BOOK ») entrent ; celles en attente attendent.
"""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal

from metabank.banque.modele import TYPES_PAR_PREFIXE
from metabank.base.lot import CompteLu, LectureImpossible, Lot, OperationLue, SoldeLu
from metabank.connecteurs._enable_banking import Client, EnableBankingIndisponible, lire_accord, masquer_iban
from metabank.connecteurs._provenance import morceaux_provenance
from metabank.connecteurs.contrat import AccesIndisponible, ConnecteurDirect, EtatAcces, Reconnaissance, Reponse

SOURCE = "enable_banking"
# Solde retenu, du plus sûr au moins sûr : comptable de clôture, comptable intermédiaire, puis disponible.
TYPES_DE_SOLDE = ("CLBD", "ITBD", "XPCD", "ITAV", "CLAV")


def _masquer(valeur: object) -> object:
    """Rendre la réponse avec chaque IBAN réduit à « ****1234 » : rien de plus n'est utile, rien de plus n'est gardé."""
    if isinstance(valeur, dict):
        return {k: masquer_iban(v) if k == "iban" and isinstance(v, str) else _masquer(v) for k, v in valeur.items()}
    if isinstance(valeur, list):
        return [_masquer(v) for v in valeur]
    return valeur


class EnableBanking(ConnecteurDirect):
    """Comptes BNP par Enable Banking ; l'export CSV reste l'accès de secours."""

    nom = SOURCE
    libelle = "Connexion directe BNP Paribas (Enable Banking, DSP2)"
    mode_emploi = (
        "Mis à jour automatiquement, une fois par jour au plus. L'accord donné à la banque se renouvelle tous les "
        "180 jours : « uv run python -m metabank enable-banking relier » puis validation dans MesComptes."
    )
    etablissements = ("BNP Paribas",)
    types_comptes = ("courant", "locatif")

    def est_actif(self, valeurs: Mapping[str, str]) -> bool:  # noqa: ARG002 (signature du contrat)
        """Rendre vrai quand un accord est enregistré (~/.config/metabank/enable_banking.json)."""
        return bool(lire_accord().get("session"))

    def etat(self, valeurs: Mapping[str, str]) -> EtatAcces:  # noqa: ARG002 (signature du contrat)
        """Rendre la fin de l'accord enregistré, sans appeler la banque."""
        accord = lire_accord()
        fin = accord.get("fin", "")
        return EtatAcces(joignable=bool(accord.get("session")), echeance=date.fromisoformat(fin[:10]) if fin else None,
                         message=f"accord jusqu'au {fin[:10]}" if fin else "aucun accord")  # fmt: skip

    def synchroniser(self, valeurs: Mapping[str, str], compte_cle: str, depuis: date) -> Reponse:  # noqa: ARG002
        """Rendre la réponse de la banque pour ce compte (soldes et opérations depuis la date), IBAN masqués."""
        accord = lire_accord()
        masque = compte_cle.rsplit(":", 1)[-1]
        compte = next((c for c in accord.get("comptes", []) if c["masque"] == masque), None)
        if compte is None or not accord.get("application"):
            raise AccesIndisponible(f"compte {masque} absent de l'accord Enable Banking")
        client = Client(accord["application"])
        try:
            soldes, operations = client.soldes(compte["uid"]), client.operations(compte["uid"], depuis)
        except EnableBankingIndisponible as erreur:
            raise AccesIndisponible(str(erreur)) from erreur
        recu_le = datetime.now(tz=UTC).isoformat(timespec="seconds")
        corps = {"source": SOURCE, "masque": masque, "nom": compte.get("nom", ""), "devise": compte.get("devise", "EUR"),
                 "recu_le": recu_le, "soldes": _masquer(soldes), "operations": _masquer(operations)}  # fmt: skip
        return Reponse(
            f"{SOURCE}-{masque.lstrip('*')}-{recu_le[:10]}.json", json.dumps(corps, ensure_ascii=False).encode()
        )

    def reconnaitre(self, nom: str, contenu: bytes) -> Reconnaissance | None:  # noqa: ARG002 (signature du contrat)
        """Rendre le compte si le fichier est une réponse Enable Banking archivée par metabank."""
        if not contenu.lstrip().startswith(b"{"):
            return None
        try:
            corps = json.loads(contenu)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(corps, dict) or corps.get("source") != SOURCE:
            return None
        return Reconnaissance("BNP", "", str(corps.get("masque", "")))

    def lire(self, provenance: str, nom: str, contenu: bytes) -> Lot:
        """Rendre le lot : compte (type d'après le dossier), opérations comptabilisées, solde du jour de la réponse.

        Raises:
            LectureImpossible: dossier sans type de compte connu, ou réponse incomplète.
        """
        corps = json.loads(contenu)
        titulaire, morceaux = morceaux_provenance(provenance)
        type_compte = TYPES_PAR_PREFIXE.get(morceaux[0].upper(), "")
        if not type_compte:
            raise LectureImpossible(f"{provenance} : type de compte inconnu pour {nom}")
        banque = morceaux[1] if len(morceaux) > 1 else "BNP"
        masque = corps["masque"]
        cle = f"{banque}:{type_compte}:{masque}"
        compte = CompteLu(cle, titulaire, banque, type_compte, masque, corps.get("nom") or "Compte")
        operations = tuple(_operation(cle, o) for o in corps.get("operations", []) if o.get("status", "BOOK") == "BOOK")
        solde = _solde(cle, corps)
        return Lot(self.nom, (compte,), operations, (solde,) if solde else ())


def _operation(cle: str, o: dict) -> OperationLue:
    montant = Decimal(str(o["transaction_amount"]["amount"]))
    if o.get("credit_debit_indicator") == "DBIT":
        montant = -montant
    libelle = " ".join(o.get("remittance_information") or []) or str(
        (o.get("creditor") or o.get("debtor") or {}).get("name", "")
    )
    # Identifiant donné par la banque, stable d'une synchronisation à l'autre ; à défaut, empreinte des champs.
    stable = o.get("transaction_id") or o.get("entry_reference")
    if not stable:
        stable = hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()[:24]
    code = o.get("bank_transaction_code") or {}
    nature = str(code.get("description") or code.get("code") or "") if isinstance(code, dict) else str(code)
    return OperationLue(cle, f"eb:{stable}", date.fromisoformat(o["booking_date"][:10]), " ".join(libelle.split()),
                        montant, nature)  # fmt: skip


def _solde(cle: str, corps: dict) -> SoldeLu | None:
    soldes = {s.get("balance_type"): s for s in corps.get("soldes", [])}
    choisi = next((soldes[t] for t in TYPES_DE_SOLDE if t in soldes), None)
    if choisi is None:
        return None
    jour = choisi.get("reference_date") or corps["recu_le"]
    return SoldeLu(cle, date.fromisoformat(jour[:10]), Decimal(str(choisi["balance_amount"]["amount"])),
                   choisi["balance_amount"].get("currency", "EUR"))  # fmt: skip


CONNECTEUR = EnableBanking()

"""Classement des opérations bancaires : catégorie (« Alimentation ») et nature (dépense, revenu…). MODELE § 7.2.

Règles par mots du libellé, les règles personnelles de data/categories.json passant avant celles du code :
  {"regles": [{"motif": "/BEN [^/]*DUPONT", "categorie": "Virements entre mes comptes"}]}
« motif » est une expression régulière cherchée dans « TYPE SOUS-TYPE LIBELLÉ » en majuscules.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from metabank.banque.modele import Operation

FICHIER = "categories.json"
# Nature d'une catégorie : ce qu'elle pèse dans le budget. « interne » et « epargne » ne sont ni des revenus ni
# des dépenses : l'argent reste au foyer (autre compte, placement).
REVENU, DEPENSE, INTERNE, EPARGNE = "revenu", "depense", "interne", "epargne"
SALAIRES = "Salaires et revenus réguliers"
NATURES = {
    SALAIRES: REVENU,
    "Remboursements santé": REVENU,
    "Autres entrées": REVENU,
    "Virements entre mes comptes": INTERNE,
    "Épargne et placements": EPARGNE,
    "Frais bancaires": DEPENSE,
}
REGLES_PAR_DEFAUT: list[tuple[str, str]] = [
    (r"VIR CPTE A CPTE|REVOLUT", "Virements entre mes comptes"),
    (
        r"SURAVENIR|CARDIF|LINXEA|TRADE REPUBLIC|PLACEMENT.DIRECT|BOURSE DIRECT|\bLIVRET\b|\bLDDS?\b|\bPEA\b",
        "Épargne et placements",
    ),
    (
        r"^COMMISSIONS|^FRAIS\b|COTISATION A UNE OFFRE|\bAGIOS\b|FRAIS (DE )?TENUE|COMMISSION D.INTERVENTION|INTERETS DEBITEURS",
        "Frais bancaires",
    ),
    (r"CPAM|PRESTATIONS SANTE|MUTUELLE|\bMGEN\b|HARMONIE MUT", "Remboursements santé"),
    (r"DGFIP|IMPOT|TRESOR PUBLIC|FINANCES PUBLIQUES", "Impôts"),
    (r"BMW FINANCE|\bCITI\b|COFIDIS|CETELEM|SOFINCO|FRANFINANCE|\bDIAC\b|ECHEANCE PRET|\bPRET\b", "Crédits"),
    (r"ASSURANCE|\bAXA|\bMAIF\b|\bMACIF\b|MATMUT|ALLIANZ|GENERALI|GROUPAMA|\bMMA\b", "Assurances"),
    (r"\bEDF\b|ENGIE|TOTALENERGIES|VEOLIA|\bSAUR\b|EAU DU|\bENI\b|ENEDIS|GRDF", "Énergie et eau"),
    (
        (
            r"ORANGE|\bSFR\b|FREE (MOBILE|TELECOM)|BOUYGUES|NETFLIX|SPOTIFY|DEEZER|CANAL\+|DISNEY|APPLE\.COM|GOOGLE|"
            r"ANTHROPIC|OPENAI|MICROSOFT"
        ),
        "Télécom et abonnements",
    ),
    (r"CASTORAMA|LEROY MERLIN|BRICO|\bIKEA\b|CHAUFFAGE|\bBATI|JARDIN|PLOMB|ELECTRICI|MENUISERIE", "Maison et travaux"),
    (
        (
            r"CARREFOUR|LECLERC|INTERMARCHE|\bLIDL\b|AUCHAN|SUPER U|HYPER U|MONOPRIX|FRANPRIX|CASINO|PICARD|BIOCOOP|"
            r"GRAND FRAIS|BOULANG|KAYSER|\bMARCHE\b|VIVINO|\bNICOLAS\b|\bCAVE\b"
        ),
        "Alimentation",
    ),
    (
        r"RESTAU|PIZZA|CREPERIE|BRASSERIE|SUSHI|BURGER|MC ?DO|\bKFC\b|\bCAFE\b|BISTRO|SODEXO|DELIVEROO|UBER ?EATS",
        "Restaurants",
    ),
    (r"EXPEDIA|BOOKING|AIRBNB|HOTEL|ACCOR|\bIBIS\b|NOVOTEL|AIR FRANCE|EASYJET|RYANAIR", "Voyages"),
    (
        (
            r"\bSNCF\b|NAVIGO|\bRATP\b|\bUBR\*|\bUBER\b|BLABLACAR|\bTOTAL\b|\bESSO\b|\bSHELL\b|\bBP\b|PEAGE|AUTOROUTE|"
            r"\bAPRR\b|\bSANEF\b|PARKING|INDIGO"
        ),
        "Transports",
    ),
    (r"PHARMA|\bDR\b|DOCTEUR|MEDEC|OPHTA|RADIOLOG|CLINIQUE|HOPITAL|DENTI|\bLABO|KINE|OPTIC", "Santé"),
    (r"AMAZON|ALIEXPRESS|CDISCOUNT|\bFNAC\b|DARTY|ZALANDO|\bEBAY\b|\bTEMU\b|VINTED", "Achats en ligne"),
    (r"INSTANT GAMING|STEAM|PLAYSTATION|NINTENDO|PLAION|FIGURINE|CINEMA|PATHE|GAUMONT|DECATHLON|CULTURA", "Loisirs"),
    (r"RETRAIT", "Retraits d'espèces"),
]
EMETTEUR = re.compile(r"/DE (.+?)(?: /[A-Z]+ |$)")
MOIS_SALAIRE_MIN = 4
MONTANT_SALAIRE_MIN = 1000


@dataclass(frozen=True)
class OperationClassee:
    """Une opération avec sa catégorie et sa nature (revenu, depense, interne, epargne)."""

    operation: Operation
    categorie: str
    nature: str


def lire_regles(dossier: Path) -> list[tuple[str, str]]:
    """Rendre les règles personnelles de data/categories.json, ou [] sans fichier."""
    chemin = dossier / FICHIER
    if not chemin.exists():
        return []
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    return [(regle["motif"], regle["categorie"]) for regle in contenu.get("regles", [])]


def classer(operations: tuple[Operation, ...], regles_perso: list[tuple[str, str]]) -> list[OperationClassee]:
    """Rendre chaque opération avec sa catégorie : règles personnelles, salaires reconnus, puis règles du code."""
    regles = [(re.compile(motif, re.IGNORECASE), categorie) for motif, categorie in regles_perso + REGLES_PAR_DEFAUT]
    salaires = _emetteurs_reguliers(operations)
    classees = []
    for operation in operations:
        texte = f"{operation.type_banque} {operation.sous_type} {operation.libelle}".upper()
        categorie = next((c for motif, c in regles[: len(regles_perso)] if motif.search(texte)), None)
        if categorie is None and operation.montant > 0 and _emetteur(operation) in salaires:
            categorie = SALAIRES
        if categorie is None:
            categorie = next((c for motif, c in regles[len(regles_perso) :] if motif.search(texte)), None)
        if categorie is None:
            categorie = "Autres entrées" if operation.montant > 0 else "Autres dépenses"
        classees.append(OperationClassee(operation, categorie, _nature(categorie)))
    return classees


def _nature(categorie: str) -> str:
    """Rendre la nature d'une catégorie ; toute catégorie hors NATURES est une dépense.

    Un montant positif dans une catégorie de dépense (achat remboursé) diminue donc la dépense, il n'est pas un revenu.
    """
    return NATURES.get(categorie, DEPENSE)


def _emetteur(operation: Operation) -> str | None:
    trouve = EMETTEUR.search(operation.libelle)
    return trouve.group(1).strip() if trouve else None


def _emetteurs_reguliers(operations: tuple[Operation, ...]) -> set[str]:
    """Rendre les émetteurs de virements reçus d'au moins 1 000 € sur au moins 4 mois différents : les salaires."""
    mois_par_emetteur: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for operation in operations:
        emetteur = _emetteur(operation)
        if emetteur and operation.montant >= MONTANT_SALAIRE_MIN:
            mois_par_emetteur[emetteur].add((operation.jour.year, operation.jour.month))
    return {e for e, mois in mois_par_emetteur.items() if len(mois) >= MOIS_SALAIRE_MIN}


LONGUEUR_MOTIF_MAX = 200
LONGUEUR_CATEGORIE_MAX = 60
EXEMPLES_MAX = 5
# Ce qui change d'une facture à l'autre chez un même marchand : date de la facture, carte masquée (et ce qui la suit,
# le libellé étant tronqué à 60 caractères), chiffres.
BRUIT_DU_LIBELLE = re.compile(r"FACTURE CARTE DU \d{6}|\bCARTE\b.*$|PRLV SEPA|VIR SEPA (EMIS|RECU)|\d+")


class RegleInvalide(ValueError):
    """Règle refusée : motif vide, trop long ou qui n'est pas une expression régulière ; catégorie vide."""


def categories_connues(regles_perso: list[tuple[str, str]]) -> list[str]:
    """Rendre les catégories proposées : celles du code, des règles personnelles, et « Autres dépenses »."""
    noms = {c for _, c in REGLES_PAR_DEFAUT} | set(NATURES) | {c for _, c in regles_perso} | {"Autres dépenses"}
    return sorted(noms)


def motif_suggere(libelle: str) -> str:
    """Rendre un motif qui reconnaît ce marchand : ses trois premiers mots, sans date, carte ni chiffre."""
    mots = [m for m in BRUIT_DU_LIBELLE.sub(" ", libelle.upper()).split() if len(m) > 1][:3]
    return r"\s+".join(re.escape(m) for m in mots) or re.escape(libelle.strip().upper()[:30])


def essayer_motif(motif: str, operations: list[Operation]) -> dict:
    """Rendre ce que la règle classerait : nombre d'opérations, montant net (euros) et quelques libellés.

    Raises:
        RegleInvalide: motif vide, trop long ou invalide.
    """
    expression = _compiler(motif)
    trouvees = [o for o in operations if expression.search(f"{o.type_banque} {o.sous_type} {o.libelle}".upper())]
    return {
        "nombre": len(trouvees),
        "montant": float(sum((o.montant for o in trouvees), Decimal(0))),
        "exemples": sorted({o.libelle for o in trouvees})[:EXEMPLES_MAX],
    }


def ecrire_regles(dossier: Path, regles: list) -> list[dict]:
    """Rendre les règles personnelles validées après les avoir enregistrées dans data/categories.json (atomique).

    L'ordre compte : la première règle qui reconnaît une opération la classe.

    Raises:
        RegleInvalide: une règle est hors format ; rien n'est écrit.
    """
    if not isinstance(regles, list):
        raise RegleInvalide("liste de règles attendue")
    propres = []
    for regle in regles:
        if not isinstance(regle, dict):
            raise RegleInvalide("règle : objet attendu")
        motif, categorie = str(regle.get("motif") or "").strip(), str(regle.get("categorie") or "").strip()
        _compiler(motif)
        if not categorie or len(categorie) > LONGUEUR_CATEGORIE_MAX:
            raise RegleInvalide(f"{motif} : catégorie vide ou trop longue")
        propres.append({"motif": motif, "categorie": categorie})
    chemin = dossier / FICHIER
    contenu = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    temporaire = chemin.with_suffix(".json.tmp")
    temporaire.write_text(
        json.dumps({**contenu, "regles": propres}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporaire.replace(chemin)
    return propres


def _compiler(motif: str) -> re.Pattern:
    if not motif or len(motif) > LONGUEUR_MOTIF_MAX:
        raise RegleInvalide(f"motif vide ou de plus de {LONGUEUR_MOTIF_MAX} caractères")
    try:
        return re.compile(motif, re.IGNORECASE)
    except re.error as erreur:
        raise RegleInvalide(f"motif illisible ({erreur.msg}) : {motif}") from erreur

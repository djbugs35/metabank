"""Lecture de la « Situation de votre contrat au … » Suravenir (Vie Plus) : valeur et fonds à une date. MODELE § 2.3.

Document ponctuel, sans mouvements de l'année ni frais : il donne la valeur de chaque fonds, le total, et les cumuls
de versements et de rachats depuis l'origine. Montants en euros.
"""

import re
from datetime import date
from decimal import Decimal

from metabank.releves.modele import Distribution, Releve, Support
from metabank.releves.texte import MOTIF_ISIN, MOTIF_MONTANT, ErreurLecture, date_numerique, en_decimal

TITRE = re.compile(r"Situation de votre contrat au (\d{2}/\d{2}/\d{4})")
NUMERO = re.compile(r"N°\s*([A-Z0-9]{1,3}\s+\d{6,})\s+du")
SUPPORT = re.compile(
    rf"^\s*(?P<libelle>\S.*?\S)\s{{2,}}(?P<isin>{MOTIF_ISIN})\s+(?P<parts>{MOTIF_MONTANT})\s+(?P<vl>{MOTIF_MONTANT})\s+"
    rf"(?P<pru>{MOTIF_MONTANT})\s+(?P<pv>{MOTIF_MONTANT})\s?%\s+\d+\.\d+\s?%\s+(?P<montant>{MOTIF_MONTANT})\s*$"
)
TOTAL = re.compile(rf"^\s*TOTAL\s+({MOTIF_MONTANT})\s*$", re.MULTILINE)
COMPARTIMENT = re.compile(rf"\d+\s*-\s*Compartiment\s+\d+\s+({MOTIF_MONTANT})\s*€")
ECART_TOLERE = Decimal(1)
OPERATION = re.compile(rf"^\s*(\d\d/\d\d/(\d{{4}}))\s+(\S.*?)\s{{2,}}.*?({MOTIF_MONTANT})\s*$")
VERSEMENTS = ("VERSEMENT", "SOUSCRIPTION", "ADHESION")


def flux_de_l_annee(texte: str, annee: int) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Rendre (versé, rachats, frais) de l'année d'après l'historique des opérations, en euros. MODELE § 2.4.

    Tout vaut None quand le document n'imprime pas d'historique : l'année en cours ne se calcule pas.
    """
    verse = rachats = Decimal(0)
    frais = None
    historique = False
    for ligne in texte.splitlines():
        trouve = OPERATION.match(ligne)
        historique = historique or trouve is not None
        if not trouve or int(trouve.group(2)) != annee:
            continue
        nature, montant = trouve.group(3).upper(), abs(en_decimal(trouve.group(4)))
        if nature.startswith(VERSEMENTS):
            verse += montant
        elif nature.startswith("RACHAT"):
            rachats += montant
        elif nature.startswith(f"FRAIS ANNEE {annee}"):
            frais = (frais or Decimal(0)) + montant
    return (verse, rachats, frais) if historique else (None, None, None)


def lire_distributions(texte: str, supports: list[Support]) -> tuple[Distribution, ...]:
    """Rendre les coupons de l'historique, chacun rattaché au fonds que sa ligne nomme. MODELE § 13.1.

    La ligne porte « DISTRIBUTION », un nom court puis le libellé complet du fonds : c'est ce libellé qui désigne le
    support. Une ligne qui ne nomme aucun fonds détenu garde son texte en majuscules comme clé.
    """
    vues: dict[tuple[date, str, Decimal], None] = {}
    for ligne in texte.splitlines():
        trouve = OPERATION.match(ligne)
        if not trouve or not trouve.group(3).upper().startswith("DISTRIBUTION"):
            continue
        texte_ligne = " ".join(ligne.split()).upper()
        support = next((s for s in supports if s.libelle.upper() in texte_ligne), None)
        cle = (support.isin or support.libelle.upper()) if support else texte_ligne
        # Les pages répètent parfois une ligne : un même coupon (jour, fonds, montant) n'est compté qu'une fois.
        vues[(date_numerique(trouve.group(1)), cle, en_decimal(trouve.group(4)))] = None
    return tuple(Distribution(jour, cle, montant) for jour, cle, montant in vues)


def est_situation_suravenir(texte: str) -> bool:
    """Rendre vrai si le texte est une situation de contrat Suravenir (et non un relevé annuel)."""
    return "SURAVENIR" in texte.upper() and TITRE.search(texte) is not None and "Supports financiers" in texte


def _montant_apres(libelle: str, texte: str) -> Decimal | None:
    trouve = re.search(rf"{re.escape(libelle)}\s+({MOTIF_MONTANT})\s*€", texte)
    return en_decimal(trouve.group(1)) if trouve else None


def lire_situation_suravenir(texte: str, fichier: str = "", type_indique: str | None = None) -> Releve:
    """Rendre la situation lue : valeur totale, fonds, cumuls depuis l'origine, contrôles. MODELE § 2.3.

    Raises:
        ErreurLecture: date, numéro ou fonds introuvables.
    """
    titre, numero = TITRE.search(texte), NUMERO.search(texte)
    if not titre or not numero:
        raise ErreurLecture(f"{fichier} : date de situation ou numéro de contrat introuvable")
    lignes = texte.splitlines()
    rang = next(i for i, ligne in enumerate(lignes) if NUMERO.search(ligne))
    produit = next((ligne.strip() for ligne in reversed(lignes[:rang]) if ligne.strip()), "?").title()
    supports, vus = [], set()
    for ligne in lignes:
        trouve = SUPPORT.match(ligne)
        # Les pages répètent l'en-tête, jamais une ligne de fonds : chaque ISIN n'est compté qu'une fois.
        if trouve and trouve["isin"] not in vus:
            vus.add(trouve["isin"])
            supports.append(Support(" ".join(trouve["libelle"].split()), en_decimal(trouve["montant"]), trouve["isin"],
                                    en_decimal(trouve["parts"]), en_decimal(trouve["vl"]),
                                    en_decimal(trouve["pru"])))  # fmt: skip
    if not supports:
        raise ErreurLecture(f"{fichier} : aucun fonds lu dans la situation")
    total = TOTAL.search(texte)
    compartiments = {en_decimal(m) for m in COMPARTIMENT.findall(texte)}
    somme = sum((s.valeur for s in supports), Decimal(0))
    valeur = en_decimal(total.group(1)) if total else sum(compartiments, Decimal(0)) if compartiments else somme
    versements = _montant_apres("Cumul des versements bruts", texte)
    rachats = _montant_apres("Cumul des rachats bruts", texte)
    anomalies = _controles(
        valeur, somme, versements, rachats, _montant_apres("Performance (+/- value fiscale) en €", texte)
    )
    type_contrat = type_indique or ("per" if "RETRAITE" in produit.upper() else "assurance_vie")
    jour = date_numerique(titre.group(1))
    verse_annee, rachats_annee, frais_annee = flux_de_l_annee(texte, jour.year)
    return Releve("Suravenir", produit, numero.group(1), type_contrat, jour, valeur, tuple(supports),
                  versements_bruts_depuis_origine=versements, rachats_depuis_origine=rachats,
                  versements_annee_en_cours=verse_annee, rachats_annee_en_cours=rachats_annee,
                  frais_annee_en_cours=frais_annee, distributions=lire_distributions(texte, supports), anomalies=tuple(f"{fichier} : {a}" for a in anomalies),
                  fichier=fichier)  # fmt: skip


def _controles(valeur: Decimal, somme: Decimal, versements: Decimal | None, rachats: Decimal | None,
               performance: Decimal | None) -> list[str]:  # fmt: skip
    anomalies = []
    if abs(somme - valeur) > ECART_TOLERE:
        anomalies.append(f"somme des fonds {somme} € pour un total de {valeur} €")
    if versements is not None and performance is not None:
        gain = valeur - versements + (rachats or Decimal(0))
        if abs(gain - performance) > ECART_TOLERE:
            anomalies.append(f"gain recalculé {gain} € pour une performance annoncée de {performance} €")
    return anomalies

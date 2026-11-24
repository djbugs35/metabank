"""Fiche CSV d'un compte pour une année : le format unique que metabank relit. MODELE § 0.

Chaque lecteur de PDF (relevé annuel, situation…) écrit ce qu'il a lu dans « metabank-<année>.csv », rangé à côté
des PDF ; l'application ne lit plus que ces fiches. Format Excel français : séparateur « ; », virgule décimale, dates
JJ/MM/AAAA, UTF-8 avec BOM. Une ligne par chiffre lu ; la colonne « source » nomme le PDF.

Sortes de lignes (colonne « type ») :
- contrat : assureur, produit, numero, type_contrat (texte dans « libelle ») ;
- synthese : un chiffre de synthèse du document (valeur, cumul des versements, performance…, en euros) ;
- support : un fonds détenu (libellé, ISIN, parts, valeur de la part, prix de revient, montant) ;
- frais_support : un taux du tableau des frais d'un fonds (en points de pourcentage) ;
- operation : une ligne de l'historique (jour, nature imprimée, fonds nommé, montant) ;
- anomalie : une remarque du lecteur sur le PDF.
"""

import csv
import io
from collections import defaultdict
from dataclasses import fields, replace
from datetime import date
from decimal import Decimal, InvalidOperation

from metabank.releves.frais_supports import FraisSupport
from metabank.releves.modele import Frais, Mouvements, Operation, Releve, Support
from metabank.releves.operations import distributions_des_operations, flux_des_operations

COLONNES = ("type", "date", "rubrique", "libelle", "isin", "quantite", "prix", "prix_de_revient", "montant", "source")
ENTETE = ";".join(COLONNES)
# Marque d'ordre des octets : sans elle, Excel ouvre l'UTF-8 comme du Latin-1.
BOM = chr(0xFEFF)
# Espace fine insécable : Excel la met parfois entre les milliers.
ESPACE_FINE = chr(0x202F)
NOM = "metabank-{annee}.csv"
CONTRAT = ("assureur", "produit", "numero", "type_contrat")
# Chiffres de synthèse : (rubrique de la fiche, attribut du relevé), dans l'ordre où la fiche les écrit.
SYNTHESE = (
    ("valeur", "valeur"),
    ("valeur_au_1er_janvier", "valeur_precedente"),
    ("versements_annee", "versements_volontaires_annee"),
    ("cumul_versements", "versements_bruts_depuis_origine"),
    ("cumul_rachats", "rachats_depuis_origine"),
    ("performance_annoncee", "performance_annoncee"),
    ("primes_non_remboursees", "primes_non_remboursees"),
    ("taux_frais_fonds_euros", "taux_frais_fonds_euros"),
)


class FicheIllisible(ValueError):
    """Ligne de fiche dont un champ ne se lit pas : le message nomme la ligne et le champ."""


def _nombre(valeur: Decimal | None) -> str:
    return "" if valeur is None else format(valeur, "f").replace(".", ",")


def _jour(valeur: date) -> str:
    return valeur.strftime("%d/%m/%Y")


def lignes_du_releve(releve: Releve) -> list[list[str]]:
    """Rendre les lignes de fiche d'un relevé lu, dans les colonnes COLONNES."""
    jour, source = _jour(releve.date_arrete), releve.fichier

    def ligne(type_: str, quand: str = jour, **champs: str | None) -> list[str]:
        return [type_, quand, *(champs.get(c) or "" for c in COLONNES[2:-1]), source]

    lignes = [ligne("contrat", rubrique=rubrique, libelle=getattr(releve, rubrique)) for rubrique in CONTRAT]
    lignes += [ligne("synthese", rubrique=r, montant=_nombre(getattr(releve, a))) for r, a in SYNTHESE
               if getattr(releve, a) is not None]  # fmt: skip
    for nom, groupe in (("mouvements", releve.mouvements), ("frais", releve.frais)):
        if groupe is not None:
            lignes += [ligne("synthese", rubrique=f"{nom}.{f.name}", montant=_nombre(getattr(groupe, f.name)))
                       for f in fields(groupe)]  # fmt: skip
    lignes += [ligne("support", libelle=s.libelle, isin=s.isin, quantite=_nombre(s.parts), prix=_nombre(s.valeur_part),
                     prix_de_revient=_nombre(s.prix_de_revient), montant=_nombre(s.valeur)) for s in releve.supports]  # fmt: skip
    lignes += [ligne("frais_support", rubrique=f.name, isin=fs.isin, montant=_nombre(getattr(fs, f.name)))
               for fs in releve.frais_supports for f in fields(fs) if f.name != "isin"]  # fmt: skip
    lignes += [ligne("operation", _jour(o.jour), rubrique=o.nature, libelle=o.libelle, isin=o.isin, montant=_nombre(o.montant))
               for o in releve.operations]  # fmt: skip
    lignes += [ligne("anomalie", libelle=a) for a in releve.anomalies]
    return lignes


def ecrire_fiche(lignes: list[list[str]]) -> str:
    """Rendre le texte de la fiche : BOM, en-tête, puis les lignes."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\n")
    ecrivain.writerow(COLONNES)
    ecrivain.writerows(lignes)
    return BOM + sortie.getvalue()


def est_fiche(texte: str) -> bool:
    """Rendre vrai si le texte commence par l'en-tête des fiches metabank."""
    return texte.lstrip(BOM).startswith(ENTETE)


def sources_de_la_fiche(texte: str) -> set[str]:
    """Rendre les noms des PDF dont la fiche contient déjà les lignes."""
    return {ligne["source"] for ligne in csv.DictReader(io.StringIO(texte.lstrip(BOM)), delimiter=";")}


def lire_fiche(texte: str) -> list[Releve]:
    """Rendre un relevé par PDF source de la fiche, dans l'ordre des sources.

    Raises:
        FicheIllisible: date ou montant illisible (le message donne la ligne).
    """
    par_source: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for numero, ligne in enumerate(csv.DictReader(io.StringIO(texte.lstrip(BOM)), delimiter=";"), start=2):
        par_source[ligne["source"]].append((numero, ligne))
    return [_releve(source, lignes) for source, lignes in par_source.items()]


def _lire_nombre(numero: int, ligne: dict, champ: str) -> Decimal | None:
    brut = "".join((ligne.get(champ) or "").split()).replace(ESPACE_FINE, "").replace(",", ".")
    if not brut:
        return None
    try:
        return Decimal(brut)
    except InvalidOperation as erreur:
        raise FicheIllisible(f"ligne {numero} : {champ} illisible ({ligne.get(champ)!r})") from erreur


def _lire_jour(numero: int, ligne: dict) -> date:
    try:
        jour, mois, annee = (int(x) for x in ligne["date"].strip().split("/"))
        return date(annee, mois, jour)
    except (ValueError, AttributeError) as erreur:
        raise FicheIllisible(f"ligne {numero} : date illisible ({ligne.get('date')!r}), JJ/MM/AAAA attendu") from erreur


def _releve(source: str, lignes: list[tuple[int, dict]]) -> Releve:
    """Rendre le relevé d'une source ; versé de l'année en cours et coupons refaits depuis ses opérations."""
    par_type: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for numero, ligne in lignes:
        par_type[ligne["type"].strip()].append((numero, ligne))
    contrat = {ligne["rubrique"]: ligne["libelle"] for _, ligne in par_type["contrat"]}
    premiere = (par_type["contrat"] or lignes)[0]
    synthese = {ligne["rubrique"]: _lire_nombre(n, ligne, "montant") for n, ligne in par_type["synthese"]}

    def groupe(nom: str) -> dict[str, Decimal]:
        return {r.split(".", 1)[1]: v for r, v in synthese.items() if r.startswith(f"{nom}.") and v is not None}

    mouvements, frais = groupe("mouvements"), groupe("frais")
    supports = tuple(Support(ligne["libelle"], _lire_nombre(n, ligne, "montant") or Decimal(0), ligne["isin"] or None,
                             _lire_nombre(n, ligne, "quantite"), _lire_nombre(n, ligne, "prix"),
                             _lire_nombre(n, ligne, "prix_de_revient")) for n, ligne in par_type["support"])  # fmt: skip
    operations = tuple(Operation(_lire_jour(n, ligne), ligne["rubrique"], ligne["libelle"], ligne["isin"] or None,
                                 _lire_nombre(n, ligne, "montant") or Decimal(0))
                       for n, ligne in par_type["operation"])  # fmt: skip
    taux: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for n, ligne in par_type["frais_support"]:
        taux[ligne["isin"]][ligne["rubrique"]] = _lire_nombre(n, ligne, "montant") or Decimal(0)
    releve = Releve(
        assureur=contrat.get("assureur", ""), produit=contrat.get("produit", ""), numero=contrat.get("numero", ""),
        type_contrat=contrat.get("type_contrat", ""), date_arrete=_lire_jour(*premiere),
        valeur=synthese.get("valeur") or Decimal(0), supports=supports,
        mouvements=Mouvements(**mouvements) if mouvements else None, frais=Frais(**frais) if frais else None, frais_supports=tuple(FraisSupport(isin=i, **t) for i, t in taux.items()),
        operations=operations, anomalies=tuple(ligne["libelle"] for _, ligne in par_type["anomalie"]), fichier=source,
        valeur_precedente=synthese.get("valeur_au_1er_janvier"),
        versements_volontaires_annee=synthese.get("versements_annee"),
        versements_bruts_depuis_origine=synthese.get("cumul_versements"),
        rachats_depuis_origine=synthese.get("cumul_rachats"), performance_annoncee=synthese.get("performance_annoncee"),
        primes_non_remboursees=synthese.get("primes_non_remboursees"),
        taux_frais_fonds_euros=synthese.get("taux_frais_fonds_euros"),
    )  # fmt: skip
    if releve.est_annuel:
        return replace(releve, distributions=distributions_des_operations(operations))
    verse, rachats, frais_annee = flux_des_operations(operations, releve.date_arrete.year)
    return replace(releve, versements_annee_en_cours=verse, rachats_annee_en_cours=rachats,
                   frais_annee_en_cours=frais_annee, distributions=distributions_des_operations(operations))  # fmt: skip

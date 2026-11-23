"""Configuration saisie par le titulaire dans l'onglet Configuration : data/configuration.json.

Format :
  {"comptes": {"BNP:courant:****1234": {"titulaire": "Alice", "principal": "bnp_csv", "secours": "",
                                       "frequence_jours": 30}},
   "reglages": {"<connecteur>.<réglage>": "valeur"},
   "parametres": {"assistant_actif": true},
   "dossiers": {"depot": "/Users/alice/Documents/metabank"}}
« comptes » : le registre des comptes. Le titulaire saisi l'emporte sur celui déduit du dossier ; principal et
secours nomment les connecteurs qui le mettent à jour ; la fréquence attendue (en jours) colore le synoptique.
« reglages » : valeurs des réglages non secrets des connecteurs. Un secret n'est jamais écrit ici (coffre de la
machine, étape 4).
« classes » : classe choisie d'un support (clé = ISIN ou libellé) ; « cible » : part visée par classe, en %
(onglet Allocation, MODELE § 13).
« objectifs » : dépense mensuelle visée par catégorie, en euros (onglet Budget, MODELE § 7.13).
« dossiers » : dossier de dépôt surveillé (chemin absolu ; vide = data/depot/).
Saisie du titulaire, hors de la base : effacer data/metabank.db ne la perd pas.
"""

import json
import re
from collections.abc import Sequence
from pathlib import Path

from metabank.allocation import A_CLASSER, CLASSES
from metabank.connecteurs.contrat import Connecteur

FICHIER = "configuration.json"
TITULAIRE_VALIDE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' -]{0,39}$")
FREQUENCE_MAX_JOURS = 400
VALEUR_REGLAGE_MAX = 200
# imposition_commune : couple marié ou pacsé, pour l'abattement des assurances vie (MODELE § 11).
PARAMETRES_PAR_DEFAUT = {"assistant_actif": True, "imposition_commune": False}

# Fréquence de mise à jour attendue par défaut, en jours : un export mensuel des comptes courants, un relevé annuel
# des contrats et des livrets (intérêts de fin d'année), un export trimestriel suffit pour un prêt amortissable.
FREQUENCES_PAR_TYPE = {
    "courant": 30, "locatif": 30, "credit": 90,
    "livret_a": 365, "ldd": 365, "assurance_vie": 365, "per": 365, "perp": 365, "pea": 30, "cto": 30,
}  # fmt: skip


class ConfigurationInvalide(ValueError):
    """Configuration refusée : le message dit quel champ et pourquoi ; rien n'est écrit."""


def lire_configuration(dossier: Path) -> dict:
    """Rendre la configuration enregistrée, ses trois rubriques toujours présentes, paramètres par défaut compris."""
    chemin = dossier / FICHIER
    contenu = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    return {
        "comptes": dict(contenu.get("comptes", {})),
        "reglages": dict(contenu.get("reglages", {})),
        "parametres": {**PARAMETRES_PAR_DEFAUT, **contenu.get("parametres", {})},
        "dossiers": {"depot": "", **contenu.get("dossiers", {})},
        "objectifs": dict(contenu.get("objectifs", {})),
        "classes": dict(contenu.get("classes", {})),
        "cible": dict(contenu.get("cible", {})),
    }


def titulaires_saisis(configuration: dict) -> dict[str, str]:
    """Rendre {clé du compte : titulaire saisi}, pour les seuls comptes dont le titulaire a été corrigé."""
    return {cle: c["titulaire"] for cle, c in configuration["comptes"].items() if c.get("titulaire")}


def ecrire_configuration(
    dossier: Path, configuration: dict, connecteurs: Sequence[Connecteur], cles_comptes: set[str]
) -> dict:
    """Rendre la configuration validée après l'avoir enregistrée (écriture atomique).

    Args:
        cles_comptes: comptes connus de la base ; un compte inconnu est refusé plutôt que gardé sans effet.

    Raises:
        ConfigurationInvalide: compte, titulaire, connecteur, fréquence, réglage ou paramètre hors format.
    """
    propre = {
        "comptes": _comptes(_rubrique(configuration, "comptes"), connecteurs, cles_comptes),
        "reglages": _reglages(_rubrique(configuration, "reglages"), connecteurs),
        "parametres": _parametres(_rubrique(configuration, "parametres")),
        "dossiers": _dossiers(_rubrique(configuration, "dossiers"), dossier),
    }
    # Objectifs (onglet Budget), classes et cible (onglet Allocation) se saisissent ailleurs : absents de la saisie,
    # ils sont gardés tels quels.
    actuelle = lire_configuration(dossier)
    for nom, valider in (("objectifs", _objectifs), ("classes", _classes), ("cible", _cible)):
        propre[nom] = valider(_rubrique(configuration, nom)) if nom in configuration else actuelle[nom]
    _ecrire(dossier, propre)
    return lire_configuration(dossier)


def ecrire_objectifs(dossier: Path, objectifs: dict) -> dict:
    """Rendre les objectifs mensuels par catégorie (euros) validés, après les avoir enregistrés seuls.

    Raises:
        ConfigurationInvalide: catégorie vide ou trop longue, montant négatif ou trop grand ; rien n'est écrit.
    """
    if not isinstance(objectifs, dict):
        raise ConfigurationInvalide("objectifs : objet attendu")
    contenu = lire_configuration(dossier)
    contenu["objectifs"] = _objectifs(objectifs)
    _ecrire(dossier, contenu)
    return contenu["objectifs"]


def ecrire_allocation(dossier: Path, classes: dict, cible: dict) -> dict:
    """Rendre {"classes", "cible"} validés après les avoir enregistrés seuls (onglet Allocation). MODELE § 13.

    Raises:
        ConfigurationInvalide: classe inconnue, part hors de [0, 100] ou somme des parts différente de 100 %.
    """
    if not isinstance(classes, dict) or not isinstance(cible, dict):
        raise ConfigurationInvalide("classes et cible : objets attendus")
    contenu = lire_configuration(dossier)
    contenu["classes"], contenu["cible"] = _classes(classes), _cible(cible)
    _ecrire(dossier, contenu)
    return {"classes": contenu["classes"], "cible": contenu["cible"]}


def _ecrire(dossier: Path, contenu: dict) -> None:
    chemin = dossier / FICHIER
    temporaire = chemin.with_suffix(".json.tmp")
    temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporaire.replace(chemin)


def _rubrique(configuration: dict, nom: str) -> dict:
    valeur = configuration.get(nom)
    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise ConfigurationInvalide(f"{nom} : objet attendu")
    return valeur


def _comptes(comptes: dict, connecteurs: Sequence[Connecteur], cles_comptes: set[str]) -> dict:
    noms = {c.nom for c in connecteurs}
    propres = {}
    for cle, saisie in comptes.items():
        if cle not in cles_comptes:
            raise ConfigurationInvalide(f"compte inconnu : {cle}")
        if not isinstance(saisie, dict):
            raise ConfigurationInvalide(f"{cle} : objet attendu")
        titulaire = str(saisie.get("titulaire") or "").strip()
        if titulaire and not TITULAIRE_VALIDE.match(titulaire):
            raise ConfigurationInvalide(f"{cle} : prénom du titulaire invalide")
        acces = {r: str(saisie.get(r) or "") for r in ("principal", "secours")}
        inconnus = [n for n in acces.values() if n and n not in noms]
        if inconnus:
            raise ConfigurationInvalide(f"{cle} : connecteur inconnu {inconnus[0]}")
        if acces["secours"] and acces["secours"] == acces["principal"]:
            raise ConfigurationInvalide(f"{cle} : le secours doit différer de l'accès principal")
        propres[cle] = {
            "titulaire": titulaire,
            **acces,
            "frequence_jours": _frequence(cle, saisie.get("frequence_jours")),
        }
    return propres


def _frequence(cle: str, valeur: object) -> int | None:
    if valeur in (None, ""):
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, int) or not 1 <= valeur <= FREQUENCE_MAX_JOURS:
        raise ConfigurationInvalide(f"{cle} : fréquence attendue entre 1 et {FREQUENCE_MAX_JOURS} jours")
    return valeur


def _reglages(reglages: dict, connecteurs: Sequence[Connecteur]) -> dict:
    connus = {r.nom: r for c in connecteurs for r in c.reglages}
    propres = {}
    for nom, valeur in reglages.items():
        reglage = connus.get(nom)
        if reglage is None:
            raise ConfigurationInvalide(f"réglage inconnu : {nom}")
        texte = str(valeur or "").strip()
        if reglage.secret and texte:
            raise ConfigurationInvalide(f"{nom} : un secret va dans le coffre de la machine, jamais dans ce fichier")
        if len(texte) > VALEUR_REGLAGE_MAX:
            raise ConfigurationInvalide(f"{nom} : valeur trop longue")
        if texte:
            propres[nom] = texte
    return propres


def _parametres(parametres: dict) -> dict:
    propres = dict(PARAMETRES_PAR_DEFAUT)
    for nom, valeur in parametres.items():
        if nom not in PARAMETRES_PAR_DEFAUT:
            raise ConfigurationInvalide(f"paramètre inconnu : {nom}")
        if not isinstance(valeur, bool):
            raise ConfigurationInvalide(f"{nom} : vrai ou faux attendu")
        propres[nom] = valeur
    return propres


def _dossiers(dossiers: dict, dossier_data: Path) -> dict:
    inconnus = set(dossiers) - {"depot"}
    if inconnus:
        raise ConfigurationInvalide(f"dossier inconnu : {min(inconnus)}")
    depot = str(dossiers.get("depot") or "").strip()
    if depot:
        chemin = Path(depot).expanduser()
        if not chemin.is_absolute():
            raise ConfigurationInvalide("dossier de dépôt : chemin complet attendu (« /Users/… »)")
        if chemin.resolve().is_relative_to((dossier_data / "archives").resolve()):
            raise ConfigurationInvalide("dossier de dépôt : pas dans data/archives/, qui ne se modifie jamais")
    return {"depot": depot}


OBJECTIF_MAX = 1_000_000


def _objectifs(objectifs: dict) -> dict:
    propres = {}
    for categorie, montant in objectifs.items():
        nom = str(categorie).strip()
        if not nom or len(nom) > 60:
            raise ConfigurationInvalide("objectif : catégorie vide ou trop longue")
        if montant in (None, ""):
            continue
        if isinstance(montant, bool) or not isinstance(montant, int | float) or not 0 <= montant <= OBJECTIF_MAX:
            raise ConfigurationInvalide(f"{nom} : objectif entre 0 et {OBJECTIF_MAX} € par mois")
        propres[nom] = montant
    return propres


def _classes(classes: dict) -> dict:
    propres = {}
    for cle, classe in classes.items():
        if classe in (None, "", A_CLASSER):
            continue
        if classe not in CLASSES or not str(cle).strip():
            raise ConfigurationInvalide(f"classe inconnue : {classe}")
        propres[str(cle).strip()] = classe
    return propres


def _cible(cible: dict) -> dict:
    propres = {}
    for classe, part in cible.items():
        if part in (None, ""):
            continue
        if classe not in CLASSES or classe == A_CLASSER:
            raise ConfigurationInvalide(f"cible : classe inconnue {classe}")
        if isinstance(part, bool) or not isinstance(part, int | float) or not 0 <= part <= 100:
            raise ConfigurationInvalide(f"cible {classe} : part entre 0 et 100 %")
        propres[classe] = part
    if propres and abs(sum(propres.values()) - 100) > 0.5:
        raise ConfigurationInvalide(f"cible : la somme des parts fait {sum(propres.values()):g} %, pas 100 %")
    return propres

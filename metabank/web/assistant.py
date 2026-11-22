"""Questions à Claude depuis la page, par Claude Code installé sur le Mac (« claude -p »), sans clé d'API.

Ce qui part : les chiffres déjà calculés par metabank (montants, taux, fonds et leurs frais), les prénoms et les
noms des contrats ; jamais un numéro de contrat, un nom de fichier ni un relevé. Claude commente ces chiffres et
n'en calcule pas d'autres (CLAUDE.md). Il tourne dans un dossier temporaire vide, sans outil : il ne peut ni lire
data/ ni rien modifier.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

DELAI_SECONDES = 180
QUESTION_MAX = 2000
ECHANGES_MAX = 6
EMPLACEMENTS = ("~/.local/bin/claude", "~/.claude/local/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude")
OUTILS_INTERDITS = "Bash,Edit,Write,Read,Glob,Grep,NotebookEdit,WebFetch,WebSearch,Task,TodoWrite"
CONSIGNE = (
    "Tu es l'assistant de metabank, l'outil local qui suit le patrimoine financier d'un foyer. "
    "Réponds en français, simplement, en phrases courtes, pour quelqu'un qui n'est pas spécialiste. "
    "Appuie-toi uniquement sur les chiffres fournis ; ne calcule pas de nouveaux chiffres et n'en invente aucun : "
    "si un chiffre manque, dis-le. Donne toujours les montants en euros et en pourcentage quand ils sont fournis. "
    "Tu n'es pas conseiller financier : donne des éléments factuels pour décider, pas de recommandation "
    "personnalisée d'achat ou de vente."
)


class AssistantIndisponible(RuntimeError):
    """Claude Code est absent, a échoué ou n'a pas répondu à temps : le message dit quoi faire."""


def trouver_claude() -> str | None:
    """Rendre le chemin de la commande claude, ou None ; un lancement par double-clic n'a pas le PATH du terminal."""
    trouve = shutil.which("claude")
    if trouve:
        return trouve
    return next((str(Path(c).expanduser()) for c in EMPLACEMENTS if Path(c).expanduser().exists()), None)


def contexte(etat: dict) -> str:
    """Rendre le texte envoyé avec chaque question : les chiffres de toutes les vues et des fonds."""
    lignes = ["Chiffres calculés par metabank (montants en euros, taux en %) :"]
    for cle, patrimoine in etat.get("patrimoine", {}).items():
        qui = "Foyer" if cle == "foyer" else cle.removeprefix("p:")
        repartition = ", ".join(f"{f['famille']} {_e(f['montant'])} ({_p(f['part'])})" for f in patrimoine["familles"])
        lignes.append(f"- Patrimoine {qui} : {_e(patrimoine['total'])} = {repartition}")
    for vue in etat["vues"]:
        lignes.append(_ligne_vue(vue))
        lignes.extend(
            f"    {a['annee']} : versé {_e(a['verse'])}, gagné {_e(a['gain'])} ({_p(a['gain_taux'])}), "
            f"frais {_e(a['frais'])} ({_p(a['frais_taux'])})"
            for a in vue["annees"]
        )
    lignes.append("Fonds (dernier relevé annuel) : valeur, frais totaux par an, coût par an, performance nette :")
    lignes.extend(
        f"- {f['contrat']} · {f['fonds']} : {_e(f['valeur'])}, {_p(f['frais_totaux'])}, {_e(f['cout_annuel'])}, "
        f"{_p(f['performance_nette'])}"
        for f in etat["fonds"]
    )
    for compte in etat.get("banque", []):
        if compte["type"] != "courant":
            lignes.append(f"- {compte['court']} : solde {_e(compte['solde'])}, plafond {_e(compte['plafond'])}")
            lignes.extend(
                f"    intérêts {i['annee']} : {_e(i['interets'])} (taux obtenu {_p(i['taux'])}, taux réglementé moyen "
                f"{_p(i['taux_reglemente'])})"
                for i in compte["interets"]
                if i["interets"] is not None
            )
            continue
        lignes.append(
            f"- {compte['court']} : solde {_e(compte['solde'])}, solde moyen {_e(compte['solde_moyen'])}, "
            f"par mois : revenus {_e(compte['revenus_mois'])}, dépenses {_e(compte['depenses_mois'])} "
            f"({_p(compte['part_depenses'])} des revenus), épargne placée {_e(compte['epargne_mois'])} ; "
            f"frais bancaires {_e(compte['frais_an'])} par an ; argent qui dort {_e(compte['argent_qui_dort'])}"
        )
        lignes.extend(
            f"    dépenses {c['nom']} : {_e(c['montant'])} ({_p(c['part'])})" for c in compte["categories"][:8]
        )
    if etat["points"]:
        lignes.append("Points d'attention : " + " ; ".join(etat["points"]))
    lignes.append("Gagné = valeur moins versé, tous frais déjà déduits. Frais des fonds : estimés.")
    return "\n".join(lignes)


def _ligne_vue(vue: dict) -> str:
    frais = "inconnus" if vue["frais"] is None else f"{_e(vue['frais'])} ({_p(vue['frais_taux'])} du versé, "
    if vue["frais"] is not None:
        frais += f"{_p(vue['frais_par_an'])} par an)"
    return (
        f"- {vue['nom']} : versé {_e(vue['verse'])}, valeur {_e(vue['valeur'])}, gagné {_e(vue['gain'])} "
        f"({_p(vue['gain_taux'])} sur la période, {_p(vue['gain_par_an'])} par an), frais {frais}"
    )


def _e(montant: float | None) -> str:
    return "?" if montant is None else f"{montant:,.0f} €".replace(",", " ")


def _p(taux: float | None) -> str:
    return "?" if taux is None else f"{taux * 100:.1f} %".replace(".", ",")


def demander(question: str, historique: list[dict], etat: dict) -> str:
    """Rendre la réponse de Claude à la question, avec les chiffres et les derniers échanges en contexte.

    Raises:
        AssistantIndisponible: commande claude introuvable, en erreur ou trop lente.
        ValueError: question vide ou trop longue.
    """
    question = question.strip()
    if not question or len(question) > QUESTION_MAX:
        raise ValueError(f"question vide ou de plus de {QUESTION_MAX} caractères")
    claude = trouver_claude()
    if claude is None:
        raise AssistantIndisponible("Claude Code n'est pas installé sur ce Mac (commande « claude » introuvable).")
    echanges = "".join(
        f"\nQuestion précédente : {e.get('question', '')}\nRéponse précédente : {e.get('reponse', '')}\n"
        for e in historique[-ECHANGES_MAX:]
    )
    message = f"{contexte(etat)}\n{echanges}\nQuestion : {question}"
    commande = [claude, "-p", "--output-format", "text", "--append-system-prompt", CONSIGNE,
                "--disallowedTools", OUTILS_INTERDITS]  # fmt: skip
    with tempfile.TemporaryDirectory() as vide:
        try:
            resultat = subprocess.run(commande, input=message, capture_output=True, text=True, cwd=vide,
                                      timeout=DELAI_SECONDES, check=False)  # fmt: skip
        except subprocess.TimeoutExpired as erreur:
            raise AssistantIndisponible(f"pas de réponse en {DELAI_SECONDES} s, réessayez.") from erreur
    if resultat.returncode != 0 or not resultat.stdout.strip():
        detail = (resultat.stderr or resultat.stdout).strip().splitlines()[-1:] or ["sans message"]
        raise AssistantIndisponible(f"Claude Code a échoué : {detail[0][:300]}")
    return resultat.stdout.strip()

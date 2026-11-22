"""Tableau de bord du patrimoine : une page HTML autonome, générée en local (aucune ressource en ligne).

Trois niveaux avec les mêmes chiffres et les mêmes graphiques : le foyer, chaque personne, chaque contrat.
Palette : catégorielle de référence (skill dataviz), une version claire et une sombre.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from html import escape

from metabank.bilan import BilanContrat
from metabank.frais import AnalyseFrais
from metabank.frais_historique import HistoriqueFrais
from metabank.graphiques import Serie, histogramme
from metabank.rapport import LIBELLES_TYPES, euros, pourcent
from metabank.rapport_frais import points
from metabank.synthese import AnneeSynthese, Synthese, synthetiser

ZERO = Decimal(0)


@dataclass(frozen=True)
class Tableau:
    """Contenu du tableau de bord, prêt à mettre en page."""

    bilans: list[BilanContrat]
    analyses: list[AnalyseFrais]
    genere_le: date
    historiques: list[HistoriqueFrais] = field(default_factory=list)


def generer_html(tableau: Tableau) -> str:
    """Rendre la page HTML complète : foyer, puis chaque personne, puis chaque contrat, puis le détail."""
    b, h = tableau.bilans, tableau.historiques
    blocs = [_bloc(synthetiser("Foyer", b, h), "h2")]
    blocs.extend(
        _bloc(synthetiser(titulaire, [x for x in b if x.titulaire == titulaire], h), "h2")
        for titulaire in sorted({bilan.titulaire for bilan in b})
    )
    contrats = "".join(
        f'<details class="contrat"><summary>{escape(_nom(bilan))} — {euros(bilan.valeur)}</summary>'
        f"{_bloc(synthetiser(_nom(bilan), [bilan], h), None)}</details>"
        for bilan in sorted(b, key=lambda x: (x.titulaire, -x.valeur))
    )
    blocs.append(f'<div class="bloc"><h2>Par contrat</h2>{contrats}</div>')
    blocs.append(_section("Les supports, du plus coûteux au moins coûteux", _table_supports(tableau.analyses)))
    blocs.append(_section("Points d'attention", _points_attention(tableau)))
    return GABARIT.format(date=f"{tableau.genere_le:%d/%m/%Y}", corps="\n".join(blocs))


def _nom(bilan: BilanContrat) -> str:
    type_ = LIBELLES_TYPES.get(bilan.type_contrat, bilan.type_contrat)
    return f"{bilan.titulaire} · {type_} {bilan.produit} ({bilan.assureur})"


def _section(titre: str, contenu: str) -> str:
    return f"<section><h2>{escape(titre)}</h2>{contenu}</section>"


def _bloc(s: Synthese, niveau_titre: str | None) -> str:
    """Rendre les tuiles et les trois graphiques d'un ensemble de contrats."""
    titre = f"<{niveau_titre}>{escape(s.nom)}</{niveau_titre}>" if niveau_titre else ""
    return f'<div class="bloc">{titre}{_tuiles(s)}{_graphiques(s)}{_notes(s)}</div>'


def _tuiles(s: Synthese) -> str:
    gain_pct = s.gain / s.verse if s.verse else None
    tuiles = [
        ("Valeur", euros(s.valeur), ""),
        ("Versé", euros(s.verse), ""),
        ("Gain", euros(s.gain), f"{pourcent(gain_pct)} du versé" if gain_pct is not None else ""),
        (
            "Rentabilité annualisée",
            pourcent(s.rendement_annualise),
            "⚠ versements incertains" if s.versements_incertains else "par an depuis l'ouverture",
        ),
        (
            ("Frais payés", euros(s.frais_cumules), "depuis l'ouverture, fonds compris")
            if s.annees
            else ("Frais payés", "—", "inconnus : relevé de situation seul")
        ),
    ]
    contenu = "".join(
        f'<div class="tuile"><div class="etiquette">{escape(e)}</div><div class="valeur">{escape(v)}</div>'
        f'<div class="note">{escape(n)}</div></div>'
        for e, v, n in tuiles
    )
    return f'<div class="tuiles">{contenu}</div>'


def _graphiques(s: Synthese) -> str:
    if not s.annees:
        return "<p class='note'>Relevé de situation seul : pas d'historique année par année.</p>"
    annees = [a.annee for a in s.annees]
    versements = histogramme(
        "Versements par année", annees, [Serie("serie-1", "Versé", [a.verse for a in s.annees])], euros
    )
    rentabilite = histogramme(
        "Rentabilité par année (après frais)",
        annees,
        [Serie("serie-3", "Rentabilité", [a.rendement for a in s.annees])],
        pourcent,
        etiquettes=[_etiquette_rentabilite(a) for a in s.annees],
        infos=[_info_rentabilite(a) for a in s.annees],
    )
    frais = histogramme(
        "Frais par année",
        annees,
        [
            Serie("serie-1", "Frais du contrat (relevé)", [a.frais_releve for a in s.annees]),
            Serie("serie-2", "Frais des fonds (estimés)", [a.frais_fonds for a in s.annees]),
        ],
        euros,
    )
    return f'<div class="graphiques">{versements}{rentabilite}{frais}</div>'


def _etiquette_rentabilite(a: AnneeSynthese) -> list[str]:
    """Rendre « ≈ 8,2 % » ou « 3,3 % · 5 mois », puis le gain exact en euros."""
    prefixe = "≈ " if a.approximatif else ""
    duree = f" · {a.duree_mois} mois" if a.duree_mois else ""
    signe = "+" if a.gain >= 0 else ""
    return [f"{prefixe}{pourcent(a.rendement)}{duree}", f"{signe}{euros(a.gain)}"]


def _info_rentabilite(a: AnneeSynthese) -> str:
    texte = f"{a.annee} : gain {euros(a.gain)}, rentabilité {pourcent(a.rendement)}"
    if a.duree_mois:
        texte += f" sur {a.duree_mois} mois de placement (année d'ouverture)"
    if a.approximatif:
        texte += (
            f" ; entre {pourcent(a.rendement_min)} (versements en janvier) et {pourcent(a.rendement_max)} "
            "(versements en décembre) : les relevés ne datent pas les versements"
        )
    return texte


def _notes(s: Synthese) -> str:
    notes = []
    if any(a.approximatif for a in s.annees):
        notes.append(
            "≈ : les versements de l'année sont importants et les relevés ne les datent pas ; rentabilité calculée "
            "avec des versements en milieu d'année (fourchette au survol). Le gain en euros, lui, est exact."
        )
    if any(a.duree_mois for a in s.annees):
        notes.append("Année d'ouverture : rentabilité réelle sur la durée de placement indiquée, pas sur un an.")
    if s.sans_historique and s.annees:
        notes.append(
            "Valeur, versé et gain incluent "
            + ", ".join(s.sans_historique)
            + " (relevé de situation seul) ; graphiques et frais non."
        )
    if s.situations_dans_rendement:
        notes.append(
            "Rentabilité annualisée : pour "
            + ", ".join(s.situations_dans_rendement)
            + ", tout le versé est supposé placé à l'ouverture (les dates des versements sont inconnues) ;"
            " c'est la rentabilité la plus basse possible."
        )
    if s.versements_incertains:
        notes.append(
            "⚠ Les relevés donnent deux montants différents pour les versements PER d'une année (voir points "
            "d'attention) : la rentabilité affichée retient le plus petit et peut donc être surestimée."
        )
    return "".join(f"<p class='note'>{escape(n)}</p>" for n in notes)


def _table_supports(analyses: list[AnalyseFrais]) -> str:
    lignes = [(a, l) for a in analyses for l in a.lignes]
    lignes.sort(key=lambda al: al[1].cout_annuel or ZERO, reverse=True)
    corps = "".join(
        f"<tr><td>{escape(l.libelle)}</td><td>{escape(a.titulaire)} · {escape(a.produit)}</td>"
        f'<td class="n">{euros(l.valeur)}</td><td class="n">{points(l.frais_support)}</td>'
        f'<td class="n">{points(l.retrocessions)}</td><td class="n">{points(l.frais_totaux)}</td>'
        f'<td class="n">{euros(l.cout_annuel)}</td><td class="n">{points(l.performance_finale)}</td></tr>'
        for a, l in lignes
    )
    entete = ("<tr><th>Support</th><th>Contrat</th><th>Valeur</th><th>Frais du fonds</th><th>dont rétro.</th>"
              "<th>Frais totaux</th><th>Coût/an</th><th>Perf. nette année</th></tr>")  # fmt: skip
    return f'<div class="defile"><table><thead>{entete}</thead><tbody>{corps}</tbody></table></div>'


def _points_attention(tableau: Tableau) -> str:
    points_ = [f"{b.titulaire} · {b.produit} : {a.split(' : ', 1)[-1]}" for b in tableau.bilans for a in b.anomalies]
    points_ += [
        f"{b.titulaire} · {b.produit} : relevé de situation seul, frais et historique inconnus"
        for b in tableau.bilans
        if not b.annees
    ]
    if not points_:
        return "<p>Aucun.</p>"
    return "<ul>" + "".join(f"<li>{escape(p)}</li>" for p in points_) + "</ul>"


GABARIT = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Patrimoine du foyer</title>
<style>
:root {{ color-scheme: light; --fond:#f6f5f2; --surface:#fcfcfb; --texte:#0b0b0b; --texte-2:#52514e; --trait:#dcdad3;
  --serie-1:#2a78d6; --serie-2:#eb6834; --serie-3:#1baf7a; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark; --fond:#121211;
  --surface:#1a1a19; --texte:#f0efec; --texte-2:#c3c2b7; --trait:#3a3936; --serie-1:#3987e5; --serie-2:#d95926; --serie-3:#199e70; }} }}
:root[data-theme="dark"] {{ color-scheme: dark; --fond:#121211; --surface:#1a1a19; --texte:#f0efec; --texte-2:#c3c2b7;
  --trait:#3a3936; --serie-1:#3987e5; --serie-2:#d95926; --serie-3:#199e70; }}
body {{ margin:0; background:var(--fond); color:var(--texte); font:15px/1.5 -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:980px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:26px; margin:0 0 4px; }} h2 {{ font-size:17px; margin:0 0 12px; }}
.sous-titre, .note {{ color:var(--texte-2); font-size:13px; }}
section {{ background:var(--surface); border:1px solid var(--trait); border-radius:12px; padding:18px; margin-top:16px; }}
.tuiles {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; background:none;
  border:0; padding:0; }}
.tuile {{ background:var(--surface); border:1px solid var(--trait); border-radius:12px; padding:14px 16px; }}
.etiquette {{ color:var(--texte-2); font-size:13px; }} .valeur {{ font-size:26px; font-weight:650; }}
svg {{ width:100%; height:auto; display:block; }}
.serie-1 {{ fill:var(--serie-1); stroke:var(--serie-1); }} .serie-2 {{ fill:var(--serie-2); stroke:var(--serie-2); }}
rect.serie-1, rect.serie-2 {{ stroke:none; }}
.ligne {{ fill:none !important; stroke-width:2; }} .point {{ stroke:var(--surface) !important; stroke-width:2; }}
.axe {{ stroke:var(--trait); }} .graduation, .libelle {{ fill:var(--texte-2); font-size:12px; }}
.valeur-barre {{ fill:var(--texte); font-size:12px; }}
.legende {{ display:flex; gap:4px 12px; flex-wrap:wrap; font-size:12px; color:var(--texte-2); margin-bottom:8px; }}
.pastille {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; }}
i.serie-1 {{ background:var(--serie-1); }} i.serie-2 {{ background:var(--serie-2); }}
.defile {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th, td {{ padding:6px 8px; border-bottom:1px solid var(--trait); text-align:left; white-space:nowrap; }}
th {{ color:var(--texte-2); font-weight:600; }} td.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
tr.total td {{ font-weight:650; }}
.bloc {{ margin-top:16px; }} .bloc > h2 {{ font-size:20px; margin:28px 0 8px; }}
.graphiques {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:12px; }}
figure.graphique {{ margin:0; background:var(--surface); border:1px solid var(--trait); border-radius:12px; padding:12px 14px; }}
figcaption {{ font-weight:600; font-size:14px; margin-bottom:6px; }}
.serie-3 {{ fill:var(--serie-3); }} i.serie-3 {{ background:var(--serie-3); }}
.tuiles .tuile .valeur {{ font-size:22px; }}
details.contrat {{ background:var(--surface); border:1px solid var(--trait); border-radius:12px; padding:12px 16px; margin-top:10px; }}
details.contrat summary {{ cursor:pointer; font-weight:600; }}
ul {{ margin:0; padding-left:20px; }} li {{ margin:4px 0; }}
</style></head>
<body><main>
<h1>Patrimoine du foyer</h1>
<div class="sous-titre">Généré le {date} par metabank, à partir des relevés de data/. Données locales, rien n'est envoyé.
Survoler un graphique pour le détail.</div>
{corps}
<p class="note">Rendements estimés (versements supposés en milieu d'année) ; frais annuels estimés sur la valeur au
31/12. Formules : docs/MODELE.md. Éléments d'aide à la décision, pas un conseil financier.</p>
</main></body></html>
"""

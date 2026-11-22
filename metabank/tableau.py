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
from metabank.graphiques import Serie, barres_groupees
from metabank.rapport import LIBELLES_TYPES, euros
from metabank.rapport_frais import points
from metabank.synthese import Synthese, synthetiser

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
    foyer = synthetiser("Foyer", b, h)
    blocs = [_bloc(foyer, "h2", foyer)]
    blocs.extend(
        _bloc(synthetiser(titulaire, [x for x in b if x.titulaire == titulaire], h), "h2", foyer)
        for titulaire in sorted({bilan.titulaire for bilan in b})
    )
    contrats = "".join(
        f'<details class="contrat"><summary>{escape(_nom(bilan))} — {euros(bilan.valeur)}</summary>'
        f"{_bloc(synthetiser(_nom(bilan), [bilan], h), None, foyer)}</details>"
        for bilan in sorted(b, key=lambda x: (x.titulaire, -x.valeur))
    )
    blocs.append(f'<div class="bloc"><h2>Par contrat</h2>{contrats}</div>')
    blocs.append(
        f'<details class="contrat"><summary>Détail des fonds, du plus coûteux au moins coûteux</summary>'
        f"{_table_supports(tableau.analyses)}</details>"
    )
    blocs.append(_section("Points d'attention", _points_attention(tableau)))
    return GABARIT.format(date=f"{tableau.genere_le:%d/%m/%Y}", corps="\n".join(blocs))


def _nom(bilan: BilanContrat) -> str:
    type_ = LIBELLES_TYPES.get(bilan.type_contrat, bilan.type_contrat)
    return f"{bilan.titulaire} · {type_} {bilan.produit} ({bilan.assureur})"


def _section(titre: str, contenu: str) -> str:
    return f"<section><h2>{escape(titre)}</h2>{contenu}</section>"


def _bloc(s: Synthese, niveau_titre: str | None, foyer: Synthese) -> str:
    """Rendre les tuiles et le graphique d'un ensemble de contrats."""
    titre = f"<{niveau_titre}>{escape(s.nom)}</{niveau_titre}>" if niveau_titre else ""
    return f'<div class="bloc">{titre}{_tuiles(s, foyer)}{_graphiques(s)}{_notes(s)}</div>'


def _part(montant: Decimal, total: Decimal) -> str:
    return f"{_signe(montant / total * 100, False)} %" if total else "—"


def _tuiles(s: Synthese, foyer: Synthese) -> str:
    """Rendre les quatre chiffres de la période, chacun en euros et en pourcentage."""
    gagne_pct, gagne_note = "—", ""
    if s.verse:
        gagne_pct = f"{_signe(s.gain / s.verse * 100)} %"
        gagne_note = "du versé, sur toute la période"
        if s.rendement_annualise is not None:
            gagne_note += f" ; soit {_signe(s.rendement_annualise * 100)} % par an"
    verse_suivi = sum((a.verse for a in s.annees), ZERO)
    if s.annees and verse_suivi:
        note = "du versé des contrats à relevés annuels" if s.sans_historique else "du versé, sur toute la période"
        if s.frais_par_an is not None:
            note += f" ; soit {_signe(s.frais_par_an * 100, False)} % par an des sommes placées"
        frais = (euros(s.frais_cumules), _part(s.frais_cumules, verse_suivi), note)
    else:
        frais = ("—", "—", "inconnus (relevé de situation seul)")
    tuiles = [
        ("Versé", euros(s.verse), _part(s.verse, foyer.verse), "du versé du foyer"),
        ("Valeur aujourd'hui", euros(s.valeur), _part(s.valeur, foyer.valeur), "du patrimoine du foyer"),
        ("Gagné, frais déduits", f"{'+' if s.gain >= 0 else ''}{euros(s.gain)}", gagne_pct, gagne_note),
        ("Frais payés", *frais),
    ]
    contenu = "".join(
        f'<div class="tuile"><div class="etiquette">{escape(e)}</div><div class="valeur">{escape(v)}</div>'
        f'<div class="pct">{escape(p)}</div><div class="note">{escape(n)}</div></div>'
        for e, v, p, n in tuiles
    )
    return f'<div class="tuiles">{contenu}</div>'


def _signe(nombre: Decimal, avec_plus: bool = True) -> str:
    texte = f"{nombre:.1f}".replace(".", ",")
    return f"+{texte}" if avec_plus and nombre >= 0 else texte


def _graphiques(s: Synthese) -> str:
    if not s.annees:
        return ""
    annees = [a.annee for a in s.annees]
    return barres_groupees(
        "Gagné et frais payés chaque année (en % des sommes placées dans l'année)",
        annees,
        [
            Serie(
                "serie-3", "Gagné (frais déduits)", [a.gain for a in s.annees], [_pct(a.rendement) for a in s.annees]
            ),
            Serie(
                "serie-2",
                "Frais payés",
                [a.frais for a in s.annees],
                [_pct(a.rendement_frais, False) for a in s.annees],
            ),
        ],
        euros,
    )


def _pct(taux: Decimal | None, avec_plus: bool = True) -> str:
    return "" if taux is None else f"{_signe(taux * 100, avec_plus)} %"


def _notes(s: Synthese) -> str:
    notes = []
    if s.sans_historique and s.annees:
        notes.append("Le graphique ne montre pas " + ", ".join(s.sans_historique) + " : pas de relevé année par année.")
    if s.versements_incertains:
        notes.append("⚠ PER : les relevés donnent deux montants de versements pour 2024 ; le gain peut être surestimé.")
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
.tuiles .tuile .valeur {{ font-size:22px; }} .pct {{ font-size:17px; font-weight:600; }}
.valeur-barre .sous {{ fill:var(--texte-2); font-size:11px; }}
details.contrat {{ background:var(--surface); border:1px solid var(--trait); border-radius:12px; padding:12px 16px; margin-top:10px; }}
details.contrat summary {{ cursor:pointer; font-weight:600; }}
ul {{ margin:0; padding-left:20px; }} li {{ margin:4px 0; }}
</style></head>
<body><main>
<h1>Patrimoine du foyer</h1>
<div class="sous-titre">Généré le {date} par metabank, à partir des relevés de data/. Données locales, rien n'est envoyé.
Gagné : valeur aujourd'hui moins versé, tous frais déjà déduits.</div>
{corps}
<p class="note">Frais : ceux du relevé (exacts) et ceux des fonds, déjà déduits de leur cours (estimés). Pourcentages par an : moyenne annuelle
depuis l'ouverture ; pour l'année d'ouverture, sur la durée réellement placée. Formules : docs/MODELE.md. Éléments d'aide à la décision, pas un conseil financier.</p>
</main></body></html>
"""

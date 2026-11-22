// Mise en forme partagée par l'application et le rapport PDF : mêmes chiffres, mêmes libellés, même présentation.
import { echapper } from "./graphiques.js";

const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
export const euros = (v) => (v === null || v === undefined ? "—" : `${nombre.format(v)} €`);
export const eurosSignes = (v) => (v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${euros(v)}`);
export const pct = (t, signe = false) =>
  t === null || t === undefined ? "—" : `${signe && t >= 0 ? "+" : ""}${(t * 100).toFixed(1).replace(".", ",")} %`;

// Les quatre chiffres de la période d'une vue, chacun en euros et en pourcentage.
export function tuilesHtml(vue) {
  const fraisNote = vue.frais === null
    ? "inconnus (relevé de situation seul)"
    : `${vue.frais_sur_partie ? "du versé des contrats à relevés annuels" : "du versé, sur toute la période"} ; soit ${pct(vue.frais_par_an)} par an des sommes placées`;
  const tuiles = [
    ["Versé", euros(vue.verse), pct(vue.part_verse), "du versé du foyer"],
    ["Valeur aujourd'hui", euros(vue.valeur), pct(vue.part_valeur), "du patrimoine du foyer"],
    ["Gagné, frais déduits", eurosSignes(vue.gain), pct(vue.gain_taux, true),
      `du versé, sur toute la période${vue.gain_par_an === null ? "" : ` ; soit ${pct(vue.gain_par_an, true)} par an`}`],
    ["Frais payés", euros(vue.frais), pct(vue.frais_taux), fraisNote],
  ];
  return tuiles
    .map(([e, v, p, n]) => `<div class="tuile"><div class="etiquette">${echapper(e)}</div><div class="valeur">${echapper(v)}</div>
      <div class="pct">${echapper(p)}</div><div class="note">${echapper(n)}</div></div>`)
    .join("");
}

// Séries du graphique « gagné et frais payés chaque année ».
export const seriesAnnees = (annees) => [
  { classe: "serie-3", nom: "Gagné (frais déduits)", valeurs: annees.map((a) => a.gain), sous: annees.map((a) => pct(a.gain_taux, true)) },
  { classe: "serie-2", nom: "Frais payés", valeurs: annees.map((a) => a.frais), sous: annees.map((a) => pct(a.frais_taux)) },
];

export function tableAnneesHtml(annees) {
  return `<thead><tr><th>Année</th><th class="n">Versé</th><th class="n">Gagné</th><th class="n">Gagné %</th>
    <th class="n">Frais</th><th class="n">Frais %</th><th class="n">Sommes placées</th></tr></thead><tbody>${annees
      .map((a) => `<tr><td>${a.annee}</td><td class="n">${euros(a.verse)}</td><td class="n">${eurosSignes(a.gain)}</td>
        <td class="n">${pct(a.gain_taux, true)}</td><td class="n">${euros(a.frais)}</td><td class="n">${pct(a.frais_taux)}</td>
        <td class="n">${euros(a.capital)}</td></tr>`)
      .join("")}</tbody>`;
}

// Fonds d'une vue : tous pour le foyer, ceux de la personne, ou ceux du contrat.
export const fondsDeVue = (etat, vue) =>
  etat.fonds.filter((f) =>
    vue.niveau === "foyer" ? true : vue.niveau === "personne" ? f.contrat.startsWith(`${vue.nom} · `) : f.contrat === vue.court,
  );

export function tableFondsHtml(fonds) {
  return `<thead><tr><th>Fonds</th><th>Contrat</th><th class="n">Valeur</th><th class="n">Frais du fonds</th>
    <th class="n">dont rétro.</th><th class="n">Frais totaux</th><th class="n">Coût / an</th><th class="n">Perf. nette</th></tr></thead><tbody>${fonds
      .map((f) => `<tr><td>${echapper(f.fonds)}</td><td>${echapper(f.contrat)}</td><td class="n">${euros(f.valeur)}</td>
        <td class="n">${pct(f.frais_fonds)}</td><td class="n">${pct(f.retrocessions)}</td><td class="n">${pct(f.frais_totaux)}</td>
        <td class="n">${euros(f.cout_annuel)}</td><td class="n">${pct(f.performance_nette, true)}</td></tr>`)
      .join("") || `<tr><td colspan="8">Aucun fonds détaillé (relevé de situation seul).</td></tr>`}</tbody>`;
}

export const noteSansHistorique = (vue) =>
  vue.sans_historique.length && vue.annees.length
    ? `Les années ne comprennent pas ${vue.sans_historique.join(", ")} : pas de relevé année par année.`
    : "";

export const MENTION =
  "Gagné : valeur aujourd'hui moins versé, tous frais déjà déduits. Pourcentages de l'année : par rapport aux sommes " +
  "placées dans l'année. Par an : moyenne annuelle depuis l'ouverture. Frais des fonds : estimés. Éléments d'aide à la " +
  "décision, pas un conseil financier.";

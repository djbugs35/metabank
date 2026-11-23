// Rapport à enregistrer en PDF : une page A4 par vue cochée dans l'application (/rapport?vues=foyer,p:Aude&fonds=1).
import { barresGroupees, echapper } from "./graphiques.js";
import {
  MENTION, creditsDeVue, creditsHtml, epargneHtml, euros, fondsDeVue, livretsDeVue, livretsHtml, noteSansHistorique, patrimoineHtml, seriesAnnees,
  pct, reperesHtml, tableAnneesHtml, tableFondsHtml, tuilesHtml,
} from "./rendu.js";

const options = new URLSearchParams(location.search);
const ids = (options.get("vues") || "foyer").split(",");
const avec = (option) => options.get(option) === "1";

// Sans les prénoms : « Personne 1 », « Personne 2 »… partout où un prénom apparaît dans un libellé.
function anonymiser(etat) {
  const prenoms = etat.vues.filter((v) => v.niveau === "personne").map((v) => v.nom);
  const remplacer = (texte) =>
    prenoms.reduce((t, prenom, rang) => t.replaceAll(prenom, `Personne ${rang + 1}`), String(texte ?? ""));
  return {
    ...etat,
    vues: etat.vues.map((v) => ({
      ...v, nom: remplacer(v.nom), court: v.court && remplacer(v.court), sans_historique: v.sans_historique.map(remplacer),
    })),
    fonds: etat.fonds.map((f) => ({ ...f, contrat: remplacer(f.contrat) })),
    points: etat.points.map(remplacer),
    credits: (etat.credits ?? []).map((c) => ({ ...c, nom: remplacer(c.nom), titulaire: remplacer(c.titulaire) })),
    banque: (etat.banque ?? []).map((c) => ({ ...c, nom: remplacer(c.nom), court: remplacer(c.court), titulaire: remplacer(c.titulaire) })),
    patrimoine: Object.fromEntries(Object.entries(etat.patrimoine ?? {}).map(([cle, p]) => [cle, {
      ...p, lignes: p.lignes.map((l) => ({ ...l, nom: remplacer(l.nom), titulaire: remplacer(l.titulaire) })),
    }])),
  };
}

function pageVue(etat, vue, rang) {
  const section = document.createElement("section");
  section.className = "page-vue";
  const note = noteSansHistorique(vue);
  const fonds = avec("fonds") ? fondsDeVue(etat, vue) : [];
  const patrimoine = etat.patrimoine?.[vue.id];
  const livrets = vue.niveau === "contrat" ? [] : livretsDeVue(etat, vue);
  const avecPlacements = vue.verse > 0 || vue.valeur > 0;
  section.innerHTML = `<h2>${echapper(vue.nom)}</h2>
    ${patrimoine ? `<h3>Patrimoine</h3>${patrimoineHtml(patrimoine, { sansNumero: true })}` : ""}
    ${livrets.length ? `<h3>Épargne disponible : livrets</h3>${etat.epargne?.[vue.id] ? epargneHtml(etat.epargne[vue.id]) : ""}
      ${livretsHtml(livrets, { sansNumero: true })}` : ""}
    ${(vue.niveau !== "contrat" && creditsDeVue(etat, vue).length) ? `<h3>Crédits immobiliers</h3>${creditsHtml(creditsDeVue(etat, vue), etat.synthese_credits, patrimoine?.part_credits, { sansNumero: true })}` : ""}
    ${avecPlacements ? `<h3>${vue.niveau === "contrat" ? "Ce contrat" : "Placements : assurance vie, PER, PERP"}</h3>
    <div class="tuiles">${tuilesHtml(vue)}</div>` : ""}
    ${vue.annees.length && avecPlacements ? `<figure id="graphique-${rang}"></figure><table>${tableAnneesHtml(vue.annees)}</table>` : ""}
    ${note ? `<p class="note">${echapper(note)}</p>` : ""}
    ${fonds.length ? `<h3>Fonds, du plus coûteux au moins coûteux</h3><table class="fonds">${tableFondsHtml(fonds)}</table>` : ""}`;
  return section;
}

// Questions factuelles à poser à l'assureur ou au conseiller : des faits à obtenir, pas des décisions à prendre.
const QUESTIONS = [
  "Quels sont les frais de gestion du contrat et les frais d'arbitrage, et peuvent-ils être réduits ?",
  "Quelle part des frais des fonds vous est reversée (rétrocessions), fonds par fonds ?",
  "Ce contrat propose-t-il, dans les mêmes classes d'actifs, des fonds aux frais plus bas (fonds indiciels, ETF) ?",
  "Quel taux le fonds en euros sert-il cette année, et sous quelles conditions (part d'unités de compte, bonus) ?",
  "Les produits structurés détenus : échéance, conditions de remboursement, risque sur le capital ?",
];

// Fiche de rendez-vous d'un contrat (option « rdv ») : frais, rendements face aux repères, répartition, fonds les plus
// chers, échéances et questions. Tous les chiffres viennent de l'API.
function ficheRendezVous(etat, brut, vue, allocation) {
  const contrat = brut.contrats.find((c) => `c:${c.cle}` === vue.id);
  if (!contrat) return null;
  const memeContrat = (titulaire, nom) => titulaire === contrat.titulaire && nom.startsWith(contrat.produit);
  const repartition = allocation.par_contrat.find((p) => memeContrat(p.titulaire, p.contrat));
  const chers = allocation.positions.filter((p) => memeContrat(p.titulaire, p.contrat) && p.frais_totaux !== null)
    .sort((a, b) => b.frais_totaux - a.frais_totaux).slice(0, 5);
  const echeances = brut.echeances.filter((e) => memeContrat(e.titulaire, e.contrat));
  const section = document.createElement("section");
  section.className = "page-vue";
  section.innerHTML = `<h2>Préparer un rendez-vous : ${echapper(vue.nom)}</h2>
    <h3>Frais</h3><p>Frais annuels estimés : ${contrat.taux_frais === null ? "inconnus" : `${pct(contrat.taux_frais)} de l'encours, soit ${euros(contrat.cout_frais_annuel)} par an`}${
      contrat.retrocessions_annuelles ? `, dont ${euros(contrat.retrocessions_annuelles)} reversés à l'assureur et au distributeur` : ""}.
      ${contrat.taux_frais_fonds_moins_chers === null ? "" : `Avec des fonds à 0,20 % de frais : ${pct(contrat.taux_frais_fonds_moins_chers)}.`}</p>
    ${vue.annees.some((a) => etat.reperes?.[a.annee]) ? `<h3>Rendement face aux repères publics</h3><table>${reperesHtml(vue.annees, etat.reperes)}</table>` : ""}
    ${repartition ? `<h3>Répartition</h3><table><thead><tr><th>Classe</th><th class="n">Montant</th><th class="n">Part</th></tr></thead><tbody>${repartition.classes
      .map((c) => `<tr><td>${echapper(c.classe)}</td><td class="n">${euros(c.montant)}</td><td class="n">${pct(c.part)}</td></tr>`).join("")}</tbody></table>` : ""}
    ${chers.length ? `<h3>Fonds les plus chers</h3><table><thead><tr><th>Fonds</th><th class="n">Valeur</th><th class="n">Frais totaux</th></tr></thead><tbody>${chers
      .map((p) => `<tr><td>${echapper(p.libelle)}</td><td class="n">${euros(p.valeur)}</td><td class="n">${pct(p.frais_totaux / 100)}</td></tr>`).join("")}</tbody></table>` : ""}
    ${echeances.length ? `<h3>Échéances</h3><ul>${echeances.map((e) => `<li>${echapper(e.quoi)} : ${e.jour ? new Date(e.jour).toLocaleDateString("fr-FR") : "date à saisir"}</li>`).join("")}</ul>` : ""}
    <h3>Questions à poser</h3><ul>${QUESTIONS.map((q) => `<li>${echapper(q)}</li>`).join("")}</ul>`;
  return section;
}

async function construire() {
  const reponse = await fetch("/api/etat");
  const brut = await reponse.json();
  const etat = avec("noms") ? brut : anonymiser(brut);
  const vues = ids.map((id) => etat.vues.find((v) => v.id === id)).filter(Boolean);
  const date = new Date().toLocaleDateString("fr-FR");
  const titre = vues.length === 1 ? vues[0].nom : "Patrimoine";
  document.title = `Synthèse ${titre} - ${new Date().toISOString().slice(0, 10)}`;
  const rapport = document.getElementById("rapport");
  rapport.innerHTML = `<header class="entete-rapport"><h1>Synthèse patrimoniale</h1>
    <p class="discret">${echapper(vues.map((v) => v.nom).join(" · "))} — au ${date}, d'après les derniers relevés.</p></header>`;
  const allocation = avec("rdv") ? await (await fetch("/api/allocation")).json() : null;
  vues.forEach((vue, rang) => {
    rapport.append(pageVue(etat, vue, rang));
    const fiche = allocation && vue.niveau === "contrat" ? ficheRendezVous(etat, brut, vue, allocation) : null;
    if (fiche) rapport.append(fiche);
    if (vue.annees.length && (vue.verse > 0 || vue.valeur > 0)) {
      barresGroupees(document.getElementById(`graphique-${rang}`), {
        titre: "Gagné et frais payés chaque année", annees: vue.annees.map((a) => a.annee),
        series: seriesAnnees(vue.annees), formater: euros,
      });
    }
  });
  // Seuls les points des contrats couverts par les vues choisies : un PDF envoyé ne parle pas des autres.
  const prefixes = vues.map((v) => (v.niveau === "foyer" ? "" : v.niveau === "personne" ? `${v.nom} · ` : v.court));
  const points = etat.points.filter((p) => prefixes.some((prefixe) => p.startsWith(prefixe)));
  if (avec("points") && points.length) {
    const bloc = document.createElement("section");
    bloc.className = "page-points";
    bloc.innerHTML = `<h2>Points d'attention</h2><ul>${points.map((p) => `<li>${echapper(p)}</li>`).join("")}</ul>`;
    rapport.append(bloc);
  }
  rapport.insertAdjacentHTML("beforeend", `<p class="note mention">${echapper(MENTION)} Document généré par metabank le ${date}.</p>`);
}

document.getElementById("imprimer").addEventListener("click", () => window.print());
construire();

// metabank : page unique. Les chiffres viennent tous de l'API (code Python testé) ; ici, on ne fait que les montrer.
import { afficherComptes } from "./comptes.js";
import { afficherConfiguration, preparerConfiguration } from "./configuration.js";
import { afficherAllocation, preparerAllocation } from "./allocation.js";
import { preparerBudget } from "./budget.js";
import { afficherGraphiques } from "./graphiques_tableau.js";
import { afficherRetraite, preparerRetraite } from "./retraite.js";
import { afficherRevue, preparerRevue } from "./revue.js";
import { afficherCreditsSimulation, preparerCreditsSimulation } from "./credits.js";
import { afficherRegles, preparerRegles } from "./regles.js";
import { afficherSynoptique, preparerSynoptique } from "./synoptique.js";
import { barresEmpilees, barresGroupees, courbes, echapper } from "./graphiques.js";
import {
  anneeLibelle, creditsDeVue, creditsHtml, epargneHtml, euros, eurosSignes, fondsDeVue, livretsDeVue, livretsHtml, noteSansHistorique, patrimoineHtml, pct,
  reperesHtml, tableFondsHtml, tuilesHtml,
} from "./rendu.js";

const $ = (id) => document.getElementById(id);

let etat = null;
let vueChoisie = "foyer";
let anneesChoisies = null;
let ligneChoisie = null;

async function appeler(chemin, options = {}) {
  const reponse = await fetch(chemin, options);
  const donnees = await reponse.json();
  if (!reponse.ok) throw new Error(donnees.erreur || `erreur ${reponse.status}`);
  return donnees;
}
const envoyerJson = (chemin, corps) =>
  appeler(chemin, { method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" }, body: JSON.stringify(corps) });

async function charger() {
  $("chargement").classList.remove("cache");
  $("chargement").textContent = "Lecture des relevés…";
  try {
    etat = await appeler("/api/etat");
  } catch (erreur) {
    $("chargement").textContent = `Impossible de lire les données : ${erreur.message}`;
    return;
  }
  $("chargement").classList.add("cache");
  if (!etat.vues.some((v) => v.id === vueChoisie)) vueChoisie = "foyer";
  afficherTableau();
  if ($("export-vues").children.length) preparerExport();
  afficherComptes(etat);
  afficherCreditsSimulation(etat);
  afficherRetraite(etat);
  afficherReleves();
  afficherCorrections();
  afficherBiens();
  preparerSimulation();
  preparerAssistant();
}

// ---------- Onglets ----------
// Onglets par catégorie : ils suivent la vue choisie (foyer, personne) ; seul « Placements » descend au contrat.
const ONGLETS_DE_VUE = ["tableau", "onglet-placements", "onglet-epargne", "onglet-credits", "onglet-locatif"];
let ongletOuvert = "tableau";

function ouvrirOnglet(id) {
  document.querySelector(`nav [data-onglet="${id}"]`)?.click();
}

document.querySelectorAll("nav [data-onglet]").forEach((bouton) =>
  bouton.addEventListener("click", () => {
    ongletOuvert = bouton.dataset.onglet;
    document.querySelectorAll("nav [data-onglet]").forEach((b) => b.setAttribute("aria-selected", String(b === bouton)));
    document.querySelectorAll("[data-panneau]").forEach((p) => p.classList.toggle("cache", p.id !== bouton.dataset.onglet));
    $("entete-vues").classList.toggle("cache", !ONGLETS_DE_VUE.includes(ongletOuvert));
    const vue = etat?.vues.find((v) => v.id === vueChoisie);
    if (ONGLETS_DE_VUE.includes(ongletOuvert) && ongletOuvert !== "onglet-placements" && vue?.niveau === "contrat") choisirVue(vue.parent);
    else if (etat) afficherTableau();
    if (bouton.dataset.onglet === "simulation") simuler();
    if (bouton.dataset.onglet === "comptes") afficherRegles().catch((e) => { $("regles-liste").textContent = e.message; });
    if (bouton.dataset.onglet === "revue") afficherRevue().catch((e) => { $("revue-actions").textContent = e.message; });
    if (bouton.dataset.onglet === "allocation") afficherAllocation().catch((e) => { $("alloc-alertes").textContent = e.message; });
    if (bouton.dataset.onglet === "synoptique") afficherSynoptique().catch((e) => { $("synoptique-comptes").textContent = e.message; });
    if (bouton.dataset.onglet === "configuration") afficherConfiguration().catch((e) => { $("etat-configuration").textContent = e.message; });
  }),
);

// ---------- Tableau de bord ----------
function puce(texte, actif, action) {
  const b = document.createElement("button");
  b.className = "puce";
  b.textContent = texte;
  b.setAttribute("aria-pressed", String(actif));
  b.addEventListener("click", action);
  return b;
}

function choisirVue(id) {
  vueChoisie = id;
  anneesChoisies = null;
  ligneChoisie = null;
  afficherTableau();
}

function afficherTableau() {
  const vue = etat.vues.find((v) => v.id === vueChoisie);
  const personne = vue.niveau === "contrat" ? vue.parent : vue.niveau === "personne" ? vue.id : null;
  const niveaux = $("choix-niveau");
  niveaux.replaceChildren(
    ...etat.vues.filter((v) => v.niveau !== "contrat").map((v) => puce(v.nom, v.id === personne || v.id === vueChoisie, () => choisirVue(v.id))),
  );
  const contrats = $("choix-contrat");
  contrats.replaceChildren(
    ...(personne ? etat.vues.filter((v) => v.parent === personne) : []).map((v) =>
      puce(v.nom.split(" · ").slice(1).join(" · "), v.id === vueChoisie, () => choisirVue(v.id === vueChoisie ? personne : v.id)),
    ),
  );
  $("titre-vue").textContent = vue.nom;
  contrats.classList.toggle("cache", ongletOuvert !== "onglet-placements");
  const patrimoine = etat.patrimoine?.[vue.id];
  $("bloc-patrimoine").classList.toggle("cache", !patrimoine);
  if (patrimoine) {
    $("patrimoine").innerHTML = patrimoineHtml(patrimoine, { onglets: { ...ONGLETS_DES_FAMILLES, ...(etat.locatif ? {} : { Immobilier: null }) }, comptesReplies: true });
    $("patrimoine").querySelectorAll("[data-aller]").forEach((t) => t.addEventListener("click", () => ouvrirOnglet(t.dataset.aller)));
    afficherHistorique(etat.historique?.[vue.id] ?? { points: [], reportes: [] }, patrimoine);
  }
  const avecPlacements = vue.verse > 0 || vue.valeur > 0;
  for (const id of ["titre-placements", "tuiles", "bloc-progression", "bloc-annees", "notes"]) $(id).classList.toggle("cache", !avecPlacements);
  $("titre-placements").textContent = vue.niveau === "contrat" ? "Ce contrat" : "Placements : assurance vie, PER, PERP";
  const livrets = vue.niveau === "contrat" ? [] : livretsDeVue(etat, vue);
  $("bloc-livrets").classList.toggle("cache", !livrets.length);
  if (livrets.length) $("livrets").innerHTML = livretsHtml(livrets);
  const credits = vue.niveau === "contrat" ? [] : creditsDeVue(etat, vue);
  $("bloc-credits").classList.toggle("cache", !credits.length);
  if (credits.length) $("credits").innerHTML = creditsHtml(credits, etat.synthese_credits, patrimoine?.part_credits);
  const epargne = etat.epargne?.[vue.id];
  $("epargne").innerHTML = epargne && livrets.length ? epargneHtml(epargne) : "";
  afficherLocatif(vue);
  afficherEcheances(vue);
  afficherTuiles(vue);
  afficherProgression(vue);
  afficherAnnees(vue);
  afficherReperes(vue);
  afficherGraphiques(etat, vue);
  afficherNotes(vue);
  afficherFonds(vue);
  $("points").innerHTML = etat.points.length ? `<ul>${etat.points.map((p) => `<li>${echapper(p)}</li>`).join("")}</ul>` : "<p>Aucun.</p>";
  marquerOngletsVides();
}

// Famille du patrimoine -> onglet qui la détaille (tuiles cliquables du tableau de bord).
const ONGLETS_DES_FAMILLES = { "Placements": "onglet-placements", "Épargne disponible": "onglet-epargne",
  "Comptes courants": "comptes", "Immobilier": "onglet-locatif", "Crédits restant dus": "onglet-credits" };

// Onglet d'une catégorie absente du foyer : masqué ; vide pour la vue choisie : une phrase le dit.
function marquerOngletsVides() {
  const foyer = etat.vues.find((v) => v.niveau === "foyer");
  const presents = { "onglet-placements": foyer.verse > 0 || foyer.valeur > 0,
    "onglet-epargne": livretsDeVue(etat, foyer).length > 0, "onglet-credits": creditsDeVue(etat, foyer).length > 0,
    "onglet-locatif": Boolean(etat.locatif) };
  for (const [onglet, present] of Object.entries(presents)) {
    document.querySelector(`nav [data-onglet="${onglet}"]`).classList.toggle("cache", !present);
    const section = $(onglet);
    const visibles = [...section.children].filter((e) => !e.classList.contains("cache") && !e.classList.contains("vide") && e.id !== "choix-contrat");
    let vide = section.querySelector(".vide");
    if (!vide) {
      vide = document.createElement("p");
      vide.className = "discret vide";
      vide.textContent = "Rien à afficher pour cette vue : choisissez le foyer ou une autre personne.";
      section.append(vide);
    }
    vide.classList.toggle("cache", visibles.length > 0);
  }
}

const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const moisDe = (iso) => `${MOIS_COURTS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(2, 4)}`;

// Courbe du patrimoine sur 13 mois ; le net n'est tracé que là où le tableau l'affiche (biens saisis ou aucun crédit).
function afficherHistorique({ points, reportes }, patrimoine) {
  const figure = $("patrimoine-historique");
  $("patrimoine-reportes").textContent = reportes.length
    ? `Comptés à leur première valeur connue avant leur premier relevé ou export : ${reportes.join(", ")}.` : "";
  figure.parentElement.classList.toggle("cache", points.length < 2);
  if (points.length < 2) return;
  const avecCredits = points.some((p) => p.credits > 0);
  const series = [{ classe: "serie-1", nom: "Actifs", valeurs: points.map((p) => p.actifs) }];
  if (avecCredits) series.push({ classe: "serie-2", nom: "Crédits", valeurs: points.map((p) => p.credits) });
  if (!patrimoine.credits_sans_bien) series.push({ classe: "serie-3", nom: "Patrimoine net", valeurs: points.map((p) => p.net) });
  courbes(figure, {
    titre: "Patrimoine en fin de mois",
    abscisses: points.map((p) => p.jour),
    legendeX: moisDe,
    series,
    formater: euros,
    survol: (rang) => {
      const p = points[rang];
      $("patrimoine-historique-infobulle").textContent = rang === null ? "" : `${moisDe(p.jour)} : actifs ${euros(p.actifs)}`
        + (avecCredits ? `, crédits ${euros(p.credits)}` : "") + (patrimoine.credits_sans_bien ? "" : `, net ${euros(p.net)}`);
    },
  });
}

// Échéances (MODELE § 11) : toutes au foyer, celles de la personne (et du foyer) sinon.
function afficherEcheances(vue) {
  const titulaire = vue.niveau === "foyer" ? null : vue.niveau === "personne" ? vue.nom : vue.parent?.slice(2);
  const liste = (etat.echeances ?? []).filter((e) => !titulaire || e.titulaire === titulaire || e.titulaire === "Foyer");
  $("bloc-echeances").classList.toggle("cache", !liste.length);
  const aujourdhui = new Date().toISOString().slice(0, 10);
  $("echeances").innerHTML = liste.map((e) => {
    const quand = e.jour === null ? "date à saisir" : `${e.jour <= aujourdhui ? "atteint le" : "le"} ${new Date(e.jour).toLocaleDateString("fr-FR")}`;
    return `<li><strong>${echapper(e.quoi)}</strong>, ${quand} : ${echapper(e.titulaire)} · ${echapper(e.contrat)}<br><span class="note">${echapper(e.detail)}</span></li>`;
  }).join("");
}

// Bien locatif (MODELE § 7.12) : au foyer et à la personne qui en tient le compte.
function afficherLocatif(vue) {
  const b = etat.locatif;
  const visible = Boolean(b) && (vue.niveau === "foyer" || (vue.niveau === "personne" && b.titulaires.includes(vue.nom)));
  $("bloc-locatif").classList.toggle("cache", !visible);
  if (!visible) return;
  const tuile = (etiquette, valeur, taux, note) => `<div class="tuile"><div class="etiquette">${etiquette}</div>
    <div class="valeur">${valeur}</div>${taux === null || taux === undefined ? "" : `<div class="pct">${pct(taux, true)}</div>`}<div class="note">${note}</div></div>`;
  const sansValeur = "saisissez la valeur du bien dans Corrections";
  $("locatif").innerHTML = `<div class="tuiles">${[
    tuile("Loyers par an", euros(b.loyers), b.rendement_brut, b.valeur ? "rendement brut, de la valeur du bien" : sansValeur),
    tuile("Charges par an", euros(b.charges), b.rendement_net, b.valeur ? "rendement net de charges" : "hors mensualités du prêt"),
    tuile("Intérêts d'emprunt, 12 mois", b.interets === null ? "—" : euros(b.interets), b.rendement_apres_interets,
      b.interets === null ? "crédit du bien non retrouvé" : "rendement après intérêts"),
    tuile("Trésorerie par mois", eurosSignes(b.tresorerie_mensuelle), null,
      `loyers − charges − mensualités (${euros(b.echeances)} par an) ; sur ${b.mois_couverts} mois d'exports`),
  ].join("")}</div>`;
}

function afficherTuiles(vue) {
  $("tuiles").innerHTML = tuilesHtml(vue);
}

// Rendement de chaque année face aux repères publics (MODELE § 10) ; écart en points sous le rendement.
function afficherReperes(vue) {
  const annees = vue.annees.filter((a) => etat.reperes?.[a.annee]);
  $("bloc-reperes").classList.toggle("cache", !annees.length);
  $("table-reperes").innerHTML = reperesHtml(annees, etat.reperes);
}

// Valeur des placements fin d'année par fin d'année, versé net et gagné cumulés (MODELE § 6.4).
function afficherProgression(vue) {
  const p = vue.progression ?? [];
  $("bloc-progression").classList.toggle("cache", !p.length || $("tuiles").classList.contains("cache"));
  if (!p.length) return;
  const fin = (x) => (x.en_cours_au ? `${x.annee} (au ${x.en_cours_au.slice(8, 10)}/${x.en_cours_au.slice(5, 7)})` : `fin ${x.annee}`);
  // Dernière colonne : les tuiles, tous contrats (situations seules comprises) ; mêmes chiffres que « Versé » et « Valeur ».
  const tous = { valeur: vue.valeur, verse: vue.verse, gain: vue.gain };
  barresEmpilees($("graphique-progression"), {
    titre: "Valeur des placements en fin d'année, et variation de l'année",
    abscisses: [...p.map(fin), "Aujourd'hui, tous contrats"],
    parts: [
      { classe: "serie-1", nom: "Versé net cumulé", valeurs: [...p.map((x) => x.verse_cumule), tous.verse] },
      { classe: "serie-3", classeNegative: "serie-2", nom: "Gagné cumulé", nomNegatif: "Perdu cumulé", valeurs: [...p.map((x) => x.gain_cumule), tous.gain] },
    ],
    totaux: [...p.map((x) => x.valeur), tous.valeur],
    sous: [...p.map((x) => `${eurosSignes(x.variation)} sur l'année`),
      vue.valeur_sans_historique ? `dont ${euros(vue.valeur_sans_historique)} sans historique` : "= tuiles"],
    formater: euros,
    survol: (rang) => {
      const x = rang === null ? null : p[rang];
      $("infobulle-progression").textContent = x
        ? `${fin(x)} : valeur ${euros(x.valeur)} · variation ${eurosSignes(x.variation)} = versé net ${eurosSignes(x.verse_net_annee)} + gagné ${eurosSignes(x.gain_annee)} · depuis le début : versé net ${euros(x.verse_cumule)}, gagné ${eurosSignes(x.gain_cumule)}`
        : rang === p.length ? `Aujourd'hui, tous contrats : valeur ${euros(tous.valeur)} · versé ${euros(tous.verse)} (lu sur les documents) · gagné ${eurosSignes(tous.gain)}` : "";
    },
  });
  const notes = [];
  if (vue.sans_historique.length) notes.push(`Fins d'année : contrats à relevés annuels seulement ; sans historique annuel, ${vue.sans_historique.join(", ")} n'apparaissent que dans la dernière colonne.`);
  if (vue.ecart_verse !== null && vue.ecart_verse !== undefined) notes.push(`Les fins d'année suivent les mouvements de chaque année ; le versé lu sur les documents en diffère de ${eurosSignes(vue.ecart_verse)} (voir « Versé »).`);
  $("note-progression").textContent = notes.join(" ");
}

// Tableau par contrat (MODELE § 6.5) : versé, gain hors frais et frais de chaque année choisie, puis leur cumul ;
// lignes des contrats, cumul par personne, total. Le graphique montre la ligne cliquée (le total d'abord).
// « +8,1 k€ » : étiquettes courtes, trois barres par année tiennent sans se chevaucher.
const kiloEuros = (v) => `${v >= 0 ? "+" : "−"}${Math.abs(v) >= 1000 ? `${(Math.abs(v) / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k€` : euros(Math.abs(v))}`;
const CHAMPS_TABLEAU = [["verse", "Versé"], ["gain_avant_frais", "Gain hors frais"], ["frais", "Frais"], ["valeur", "Valeur"]];

function afficherTableauContrats(vue, annees) {
  const lignes = vue.tableau ?? [];
  if (!lignes.length) return;
  const choisie = lignes.find((l) => l.nom === ligneChoisie) ?? lignes[lignes.length - 1];
  const cellule = (v, champ) => `<td class="n">${v === undefined || v === null ? "—" : ["verse", "frais", "valeur", "ecart"].includes(champ) ? euros(v) : eurosSignes(v)}</td>`;
  // Depuis l'ouverture (MODELE § 6.5) : versé et gagné du document ; gain hors frais − frais − écart = gagné.
  const DEPUIS = [["verse", "Versé (document)"], ["gain_avant_frais", "Gain hors frais"], ["frais", "Frais"],
    ["ecart", "Écart de versé"], ["gain", "Gagné"], ["valeur", "Valeur aujourd'hui"]];
  const vide = (l) => !Object.keys(l.annees).length;
  $("table-annees").innerHTML = `<thead><tr><th rowspan="2">Contrat</th>${annees.map((a) => `<th colspan="4" class="n">${echapper(anneeLibelle(a))}</th>`).join("")}
      <th colspan="6" class="n">Depuis l'ouverture</th></tr>
    <tr>${annees.map(() => CHAMPS_TABLEAU.map(([, titre]) => `<th class="n">${titre}</th>`).join("")).join("")}${DEPUIS.map(([, titre]) => `<th class="n">${titre}</th>`).join("")}</tr></thead>
    <tbody>${lignes.map((l) => `<tr class="cliquable ligne-${l.niveau}${l === choisie ? " ligne-choisie" : ""}" data-ligne="${echapper(l.nom)}">
      <td>${echapper(l.nom)}</td>${annees.map((a) => CHAMPS_TABLEAU.map(([champ]) => cellule(l.annees[a.annee]?.[champ], champ)).join("")).join("")}
      ${DEPUIS.map(([champ]) => cellule(champ === "ecart" && !l.depuis_ouverture.ecart ? null : l.depuis_ouverture[champ], champ)).join("")}</tr>`).join("")}</tbody>`;
  $("table-annees").querySelectorAll("tr[data-ligne]").forEach((tr) => tr.addEventListener("click", () => {
    if (vide(lignes.find((l) => l.nom === tr.dataset.ligne))) return;
    ligneChoisie = tr.dataset.ligne;
    afficherTableauContrats(vue, annees);
  }));
  const chiffres = annees.map((a) => choisie.annees[a.annee] ?? null);
  barresGroupees($("graphique-annees"), {
    titre: `${choisie.nom} : gain hors frais, frais et gagné net, année par année`,
    annees: annees.map((a) => anneeLibelle(a)),
    series: [
      { classe: "serie-1", nom: "Gain hors frais", valeurs: chiffres.map((c) => c?.gain_avant_frais ?? null) },
      { classe: "serie-2", nom: "Frais", valeurs: chiffres.map((c) => (c ? -c.frais : null)) },
      { classe: "serie-3", nom: "Gagné net (frais déduits)", valeurs: chiffres.map((c) => c?.gain ?? null) },
    ],
    formater: kiloEuros,
    largeur: 960,
    survol: (rang) => {
      const c = rang === null ? null : chiffres[rang];
      $("infobulle-annees").textContent = c
        ? `${anneeLibelle(annees[rang])} : versé ${euros(c.verse)} · gain hors frais ${eurosSignes(c.gain_avant_frais)} − frais ${euros(c.frais)} = gagné net ${eurosSignes(c.gain)}`
        : "Cliquez une ligne du tableau pour la voir ici.";
    },
  });
  $("infobulle-annees").textContent = "Cliquez une ligne du tableau pour la voir ici.";
  $("rapprochement").textContent = lignes.some((l) => l.depuis_ouverture.ecart)
    ? "Écart de versé : ce que le document compte en plus des versements lus dans les mouvements de chaque année, "
      + "par exemple un transfert entrant compté pour les versements faits sur l'ancien contrat. Gagné = valeur − versé du document."
    : "";
}

function afficherAnnees(vue) {
  const bloc = $("bloc-annees");
  bloc.classList.toggle("cache", !vue.annees.length || $("tuiles").classList.contains("cache"));
  if (!vue.annees.length) return;
  anneesChoisies ??= new Set(vue.annees.map((a) => a.annee));
  const choix = $("choix-annees");
  choix.replaceChildren(choix.firstElementChild, ...vue.annees.map((a) => puce(String(a.annee), anneesChoisies.has(a.annee), () => {
    if (anneesChoisies.has(a.annee) && anneesChoisies.size > 1) anneesChoisies.delete(a.annee);
    else anneesChoisies.add(a.annee);
    afficherAnnees(vue);
  })));
  const annees = vue.annees.filter((a) => anneesChoisies.has(a.annee));
  const somme = (cle) => annees.reduce((t, a) => t + (a[cle] ?? 0), 0);
  const capital = somme("capital");
  const periode = annees.length === 1 ? `En ${annees[0].annee}` : `Sur ${annees.map((a) => a.annee).join(", ")}`;
  $("selection").innerHTML = `${periode} : <strong>gagné ${eurosSignes(somme("gain"))}</strong>
    (${pct(capital ? somme("gain") / capital : null, true)} des sommes placées),
    <strong>frais ${euros(somme("frais"))}</strong> (${pct(capital ? somme("frais") / capital : null)}),
    versé ${euros(somme("verse"))}.`;
  afficherTableauContrats(vue, annees);
}

function afficherNotes(vue) {
  const note = noteSansHistorique(vue);
  $("notes").innerHTML = note ? `<p class="note">${echapper(note)}</p>` : "";
}

function afficherFonds(vue) {
  $("table-fonds").innerHTML = tableFondsHtml(fondsDeVue(etat, vue));
}

// ---------- Export PDF ----------
// Le rapport s'ouvre dans un nouvel onglet, au format A4 ; « Enregistrer au format PDF » du navigateur fait le fichier.
function preparerExport() {
  const liste = $("export-vues");
  const cochees = new Set([...liste.querySelectorAll("input:checked")].map((i) => i.value));
  if (!cochees.size) cochees.add(vueChoisie);
  liste.innerHTML = etat.vues
    .map((v) => `<label class="${v.niveau}"><input type="checkbox" value="${echapper(v.id)}" ${cochees.has(v.id) ? "checked" : ""}> ${echapper(v.nom)}</label>`)
    .join("");
}

$("exporter").addEventListener("click", () => {
  const panneau = $("panneau-export");
  panneau.classList.toggle("cache");
  if (!panneau.classList.contains("cache")) {
    $("export-vues").querySelectorAll("input").forEach((i) => { i.checked = i.value === vueChoisie; });
    preparerExport();
  }
});

$("creer-pdf").addEventListener("click", () => {
  const vues = [...$("export-vues").querySelectorAll("input:checked")].map((i) => i.value);
  if (!vues.length) {
    $("etat-export").textContent = "Cochez au moins une vue.";
    return;
  }
  $("etat-export").textContent = "";
  const options = new URLSearchParams({ vues: vues.join(",") });
  for (const option of ["fonds", "points", "noms", "rdv"]) if ($(`export-${option}`).checked) options.set(option, "1");
  window.open(`/rapport?${options}`, "_blank");
});

// ---------- Relevés ----------
function afficherReleves() {
  const choix = $("depot-titulaire");
  const actuel = choix.value;
  choix.innerHTML = [`<option value="auto">Reconnaître le compte</option>`, ...etat.titulaires.map((t) => `<option>${echapper(t)}</option>`),
    `<option value="">Nouveau titulaire…</option>`].join("");
  if (actuel !== undefined && [...choix.options].some((o) => o.value === actuel)) choix.value = actuel;
  $("champ-nouveau").classList.toggle("cache", choix.value !== "");
  $("depot-surveille").textContent = `Dossier surveillé : ${etat.dossier_depot} (onglet Configuration).`;
  $("table-contrats").innerHTML = `<thead><tr><th>Contrat</th><th>N°</th><th>Années</th><th>Dernier relevé</th><th class="n">Valeur</th></tr></thead><tbody>${etat.contrats
    .map((c) => `<tr><td>${echapper(c.nom)}</td><td>${echapper(c.numero_masque)}</td><td>${c.annees.join(", ") || "situation"}</td>
      <td>${new Date(c.date_valeur).toLocaleDateString("fr-FR")}</td><td class="n">${euros(c.valeur)}</td></tr>`)
    .join("")}</tbody>`;
  $("bloc-erreurs").innerHTML = etat.erreurs.length
    ? `<h2>Fichiers non lus</h2><ul>${etat.erreurs.map((e) => `<li class="ko">${echapper(e)}</li>`).join("")}</ul>`
    : `<p class="discret">Tous les PDF de data/ ont été lus.</p>`;
}

$("depot-titulaire").addEventListener("change", () => $("champ-nouveau").classList.toggle("cache", $("depot-titulaire").value !== ""));

async function deposer(fichiers) {
  const choix = $("depot-titulaire").value;
  const titulaire = choix === "auto" ? "" : choix || $("depot-nouveau").value.trim();
  const resultats = $("depot-resultats");
  if (choix !== "auto" && !titulaire) {
    resultats.innerHTML = `<li class="ko">Indiquez d'abord le titulaire.</li>`;
    return;
  }
  for (const fichier of fichiers) {
    const ligne = document.createElement("li");
    ligne.textContent = `${fichier.name} : lecture…`;
    resultats.prepend(ligne);
    try {
      const r = await appeler("/api/releves", {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream", "X-Metabank": "1",
          "X-Titulaire": encodeURIComponent(titulaire), "X-Nom-Fichier": encodeURIComponent(fichier.name) },
        body: fichier,
      });
      ligne.className = "ok";
      const precision = r.date ? ` (${r.assureur}, ${r.annuel ? "relevé annuel" : "situation"} au ${new Date(r.date).toLocaleDateString("fr-FR")})` : "";
      ligne.textContent = `${fichier.name} : ${r.deja_present ? "déjà présent" : "rangé"} dans ${r.chemin}${precision}`;
    } catch (erreur) {
      ligne.className = "ko";
      ligne.textContent = `${fichier.name} : refusé, ${erreur.message}`;
    }
  }
  await charger();
}

const zone = $("zone-depot");
zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("survol"); });
zone.addEventListener("dragleave", () => zone.classList.remove("survol"));
zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("survol"); deposer([...e.dataTransfer.files]); });
$("depot-fichiers").addEventListener("change", (e) => { deposer([...e.target.files]); e.target.value = ""; });

// ---------- Corrections ----------
function afficherCorrections() {
  const c = etat.corrections;
  $("liste-corrections").innerHTML = etat.contrats
    .map((contrat) => {
      const verifiees = new Set(c.versements_verifies[contrat.cle] ?? []);
      const annees = contrat.annees.length
        ? `<div class="champ"><span>Versements vérifiés sur mes virements</span><div class="annees-verifiees">${contrat.annees
            .map((a) => `<label><input type="checkbox" data-verifie="${echapper(contrat.cle)}" value="${a}" ${verifiees.has(a) ? "checked" : ""}> ${a}</label>`)
            .join("")}</div></div>`
        : "";
      return `<div class="carte"><strong>${echapper(contrat.nom)}</strong> <span class="discret">${echapper(contrat.numero_masque)}</span>
        <div class="champs"><label class="champ">Date d'ouverture
          <input type="date" data-ouverture="${echapper(contrat.cle)}" value="${echapper(c.ouvertures[contrat.cle] ?? "")}"></label>${annees}</div></div>`;
    })
    .join("");
}

function afficherBiens() {
  const biens = etat.corrections.biens ?? {};
  const defaut = (c) => (/locatif/i.test(c.nom) ? "Bien locatif" : "Résidence principale");
  $("liste-biens").innerHTML = (etat.credits ?? []).map((c) => `<div class="carte"><strong>${echapper(c.nom)}</strong>
    <div class="champs"><label class="champ">Bien financé
      <input data-bien-nom="${echapper(c.cle)}" maxlength="60" value="${echapper(biens[c.cle]?.nom ?? defaut(c))}"></label>
    <label class="champ">Valeur estimée aujourd'hui (€)
      <input type="number" min="0" step="1000" data-bien-valeur="${echapper(c.cle)}" value="${biens[c.cle]?.valeur ?? ""}"></label></div></div>`).join("")
    || `<p class="discret">Aucun crédit.</p>`;
}

$("enregistrer-corrections").addEventListener("click", async () => {
  const ouvertures = Object.fromEntries([...document.querySelectorAll("[data-ouverture]")].map((i) => [i.dataset.ouverture, i.value]));
  const verifies = {};
  document.querySelectorAll("[data-verifie]").forEach((i) => {
    verifies[i.dataset.verifie] ??= [];
    if (i.checked) verifies[i.dataset.verifie].push(Number(i.value));
  });
  const etatCorrections = $("etat-corrections");
  try {
    const biens = {};
    document.querySelectorAll("[data-bien-valeur]").forEach((i) => {
      const cle = i.dataset.bienValeur;
      biens[cle] = { nom: document.querySelector(`[data-bien-nom="${cle}"]`).value, valeur: i.value === "" ? null : Number(i.value) };
    });
    await envoyerJson("/api/corrections", { ouvertures, versements_verifies: verifies, biens });
    etatCorrections.className = "ok";
    etatCorrections.textContent = "Enregistré ; chiffres recalculés.";
    await charger();
  } catch (erreur) {
    etatCorrections.className = "ko";
    etatCorrections.textContent = `Non enregistré : ${erreur.message}`;
  }
});

// ---------- Simulation ----------
const CURSEURS = [
  ["rendement_brut", "Rendement avant frais", 0, 12, 0.1, "% par an"],
  ["frais_actuels", "Frais actuels", 0, 5, 0.05, "% par an"],
  ["frais_vises", "Frais visés", 0, 5, 0.05, "% par an"],
  ["horizon", "Durée", 1, 40, 1, "ans"],
];

function preparerSimulation() {
  const choix = $("sim-contrat");
  const actuel = choix.value;
  const avecFrais = etat.contrats.filter((c) => c.taux_frais !== null);
  choix.innerHTML = avecFrais.map((c) => `<option value="${echapper(c.cle)}">${echapper(c.nom)}</option>`).join("") + `<option value="">Montant libre</option>`;
  if ([...choix.options].some((o) => o.value === actuel)) choix.value = actuel;
  if (!$("sim-curseurs").children.length) {
    $("sim-curseurs").innerHTML = CURSEURS.map(([cle, nom, min, max, pas, unite]) => `<div class="champ"><span>${nom}</span>
      <div class="ligne"><input type="range" id="sim-${cle}-r" min="${min}" max="${max}" step="${pas}">
      <input type="number" id="sim-${cle}" min="${min}" max="${max}" step="${pas}"> <span>${unite}</span></div></div>`).join("");
    CURSEURS.forEach(([cle]) => {
      $(`sim-${cle}-r`).addEventListener("input", (e) => { $(`sim-${cle}`).value = e.target.value; simulerPlusTard(); });
      $(`sim-${cle}`).addEventListener("input", (e) => { $(`sim-${cle}-r`).value = e.target.value; simulerPlusTard(); });
    });
    $("sim-valeur").addEventListener("input", simulerPlusTard);
    choix.addEventListener("change", () => { remplirSimulation(); simuler(); });
    remplirSimulation();
  }
}

function regler(cle, valeur) {
  $(`sim-${cle}`).value = valeur;
  $(`sim-${cle}-r`).value = valeur;
}

function remplirSimulation() {
  const contrat = etat.contrats.find((c) => c.cle === $("sim-contrat").value);
  $("sim-valeur").value = Math.round(contrat?.encours_frais_connus ?? 100000);
  regler("rendement_brut", 5);
  regler("frais_actuels", contrat ? +(contrat.taux_frais * 100).toFixed(2) : 2.5);
  regler("frais_vises", contrat?.taux_frais_fonds_moins_chers != null ? +(contrat.taux_frais_fonds_moins_chers * 100).toFixed(2) : 1);
  regler("horizon", 15);
}

let minuterie = null;
function simulerPlusTard() {
  clearTimeout(minuterie);
  minuterie = setTimeout(simuler, 250);
}

async function simuler() {
  if (!etat || $("simulation").classList.contains("cache")) return;
  const parametres = {
    valeur: Number($("sim-valeur").value),
    rendement_brut: Number($("sim-rendement_brut").value),
    frais_actuels: Number($("sim-frais_actuels").value),
    frais_vises: Number($("sim-frais_vises").value),
    horizon: Math.round(Number($("sim-horizon").value)),
  };
  let r;
  try {
    r = await envoyerJson("/api/simulation", parametres);
  } catch (erreur) {
    $("sim-tuiles").innerHTML = `<p class="ko">${echapper(erreur.message)}</p>`;
    return;
  }
  const fin = r.annees.length - 1;
  const gainActuel = r.frais_actuels[fin] - parametres.valeur, gainVise = r.frais_vises[fin] - parametres.valeur;
  const tuiles = [
    [`Dans ${parametres.horizon} ans, frais actuels`, euros(r.frais_actuels[fin]), pct(parametres.valeur ? gainActuel / parametres.valeur : null, true), `gagné ${eurosSignes(gainActuel)}`],
    [`Dans ${parametres.horizon} ans, frais visés`, euros(r.frais_vises[fin]), pct(parametres.valeur ? gainVise / parametres.valeur : null, true), `gagné ${eurosSignes(gainVise)}`],
    ["Différence", eurosSignes(r.ecart), pct(r.ecart_taux, true), "de plus avec les frais visés"],
    ["Frais payés sur la durée, frais visés", euros(r.frais_payes_vises),
      pct(r.frais_payes_actuels ? (r.frais_payes_vises - r.frais_payes_actuels) / r.frais_payes_actuels : null, true),
      `contre ${euros(r.frais_payes_actuels)} avec les frais actuels`],
  ];
  $("sim-tuiles").innerHTML = tuiles
    .map(([e, v, p, n]) => `<div class="tuile"><div class="etiquette">${echapper(e)}</div><div class="valeur">${echapper(v)}</div>
      <div class="pct">${echapper(p)}</div><div class="note">${echapper(n)}</div></div>`)
    .join("");
  courbes($("sim-graphique"), {
    titre: "Valeur du contrat, année après année",
    abscisses: r.annees,
    legendeX: (a) => (a === 0 ? "auj." : `${a} an${a > 1 ? "s" : ""}`),
    series: [
      { classe: "serie-2", nom: `Frais actuels (${pct(parametres.frais_actuels / 100)})`, valeurs: r.frais_actuels },
      { classe: "serie-3", nom: `Frais visés (${pct(parametres.frais_vises / 100)})`, valeurs: r.frais_vises },
    ],
    formater: euros,
    survol: (rang) => {
      $("sim-infobulle").textContent = rang === null ? ""
        : `Après ${rang} an${rang > 1 ? "s" : ""} : ${euros(r.frais_actuels[rang])} avec les frais actuels, ${euros(r.frais_vises[rang])} avec les frais visés (écart ${eurosSignes(r.frais_vises[rang] - r.frais_actuels[rang])})`;
    },
  });
}

// ---------- Assistant ----------
const SUGGESTIONS = [
  "Quel contrat me coûte le plus en frais, en euros et en % ?",
  "Mes frais sont-ils élevés par rapport à ce que je gagne ?",
  "Quels fonds pèsent le plus dans mes frais ?",
  "Explique-moi simplement ma rentabilité par an.",
];
const historique = [];

function preparerAssistant() {
  $("assistant-absent").classList.toggle("cache", etat.assistant_disponible);
  $("envoyer").disabled = !etat.assistant_disponible;
  if (!$("suggestions").children.length) {
    $("suggestions").replaceChildren(...SUGGESTIONS.map((s) => puce(s, false, () => { $("question").value = s; $("question").focus(); })));
  }
}

$("envoyer").addEventListener("click", async () => {
  const question = $("question").value.trim();
  if (!question) return;
  const fil = $("conversation");
  fil.insertAdjacentHTML("beforeend", `<div class="message vous">${echapper(question)}</div>`);
  const attente = document.createElement("div");
  attente.className = "message discret";
  attente.textContent = "Claude réfléchit… (jusqu'à une minute)";
  fil.append(attente);
  $("envoyer").disabled = true;
  $("question").value = "";
  try {
    const r = await envoyerJson("/api/assistant", { question, historique });
    attente.className = "message";
    attente.textContent = r.reponse;
    historique.push({ question, reponse: r.reponse });
  } catch (erreur) {
    attente.className = "message ko";
    attente.textContent = erreur.message;
  } finally {
    $("envoyer").disabled = !etat.assistant_disponible;
  }
});

document.querySelector("#assistant details").addEventListener("toggle", async (e) => {
  if (!e.target.open) return;
  $("contexte").textContent = await (await fetch("/api/assistant/contexte")).text();
});

preparerConfiguration(charger);
preparerRegles(charger);
preparerCreditsSimulation();
preparerBudget(charger);
preparerRetraite();
preparerAllocation();
preparerRevue();
preparerSynoptique(charger);
charger();

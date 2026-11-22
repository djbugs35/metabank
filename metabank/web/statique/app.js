// metabank : page unique. Les chiffres viennent tous de l'API (code Python testé) ; ici, on ne fait que les montrer.
import { barresGroupees, courbes, echapper } from "./graphiques.js";

const $ = (id) => document.getElementById(id);
const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const euros = (v) => (v === null || v === undefined ? "—" : `${nombre.format(v)} €`);
const eurosSignes = (v) => (v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${euros(v)}`);
const pct = (t, signe = false) =>
  t === null || t === undefined ? "—" : `${signe && t >= 0 ? "+" : ""}${(t * 100).toFixed(1).replace(".", ",")} %`;

let etat = null;
let vueChoisie = "foyer";
let anneesChoisies = null;

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
  afficherReleves();
  afficherCorrections();
  preparerSimulation();
  preparerAssistant();
}

// ---------- Onglets ----------
document.querySelectorAll("nav [data-onglet]").forEach((bouton) =>
  bouton.addEventListener("click", () => {
    document.querySelectorAll("nav [data-onglet]").forEach((b) => b.setAttribute("aria-selected", String(b === bouton)));
    document.querySelectorAll("[data-panneau]").forEach((p) => p.classList.toggle("cache", p.id !== bouton.dataset.onglet));
    if (bouton.dataset.onglet === "simulation") simuler();
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
  afficherTuiles(vue);
  afficherAnnees(vue);
  afficherNotes(vue);
  afficherFonds(vue);
  $("points").innerHTML = etat.points.length ? `<ul>${etat.points.map((p) => `<li>${echapper(p)}</li>`).join("")}</ul>` : "<p>Aucun.</p>";
}

function afficherTuiles(vue) {
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
  $("tuiles").innerHTML = tuiles
    .map(([e, v, p, n]) => `<div class="tuile"><div class="etiquette">${echapper(e)}</div><div class="valeur">${echapper(v)}</div>
      <div class="pct">${echapper(p)}</div><div class="note">${echapper(n)}</div></div>`)
    .join("");
}

function afficherAnnees(vue) {
  const bloc = $("bloc-annees");
  bloc.classList.toggle("cache", !vue.annees.length);
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
  barresGroupees($("graphique-annees"), {
    titre: "Gagné et frais payés chaque année",
    annees: annees.map((a) => a.annee),
    series: [
      { classe: "serie-3", nom: "Gagné (frais déduits)", valeurs: annees.map((a) => a.gain), sous: annees.map((a) => pct(a.gain_taux, true)) },
      { classe: "serie-2", nom: "Frais payés", valeurs: annees.map((a) => a.frais), sous: annees.map((a) => pct(a.frais_taux)) },
    ],
    formater: euros,
    survol: (rang) => {
      const a = rang === null ? null : annees[rang];
      $("infobulle-annees").textContent = a
        ? `${a.annee} : versé ${euros(a.verse)} · gagné ${eurosSignes(a.gain)} (${pct(a.gain_taux, true)}) · frais ${euros(a.frais)} (${pct(a.frais_taux)}) · sommes placées ${euros(a.capital)}`
        : "";
    },
  });
  $("table-annees").innerHTML = `<thead><tr><th>Année</th><th class="n">Versé</th><th class="n">Gagné</th><th class="n">Gagné %</th>
    <th class="n">Frais</th><th class="n">Frais %</th><th class="n">Sommes placées</th></tr></thead><tbody>${annees
      .map((a) => `<tr><td>${a.annee}</td><td class="n">${euros(a.verse)}</td><td class="n">${eurosSignes(a.gain)}</td>
        <td class="n">${pct(a.gain_taux, true)}</td><td class="n">${euros(a.frais)}</td><td class="n">${pct(a.frais_taux)}</td>
        <td class="n">${euros(a.capital)}</td></tr>`)
      .join("")}</tbody>`;
}

function afficherNotes(vue) {
  const notes = [];
  if (vue.sans_historique.length && vue.annees.length) {
    notes.push(`Les années ne comprennent pas ${vue.sans_historique.join(", ")} : pas de relevé année par année.`);
  }
  $("notes").innerHTML = notes.map((n) => `<p class="note">${echapper(n)}</p>`).join("");
}

function afficherFonds(vue) {
  const fonds = etat.fonds.filter((f) =>
    vue.niveau === "foyer" ? true : vue.niveau === "personne" ? f.contrat.startsWith(`${vue.nom} · `) : f.contrat === vue.court,
  );
  $("table-fonds").innerHTML = `<thead><tr><th>Fonds</th><th>Contrat</th><th class="n">Valeur</th><th class="n">Frais du fonds</th>
    <th class="n">dont rétro.</th><th class="n">Frais totaux</th><th class="n">Coût / an</th><th class="n">Perf. nette</th></tr></thead><tbody>${fonds
      .map((f) => `<tr><td>${echapper(f.fonds)}</td><td>${echapper(f.contrat)}</td><td class="n">${euros(f.valeur)}</td>
        <td class="n">${pct(f.frais_fonds)}</td><td class="n">${pct(f.retrocessions)}</td><td class="n">${pct(f.frais_totaux)}</td>
        <td class="n">${euros(f.cout_annuel)}</td><td class="n">${pct(f.performance_nette, true)}</td></tr>`)
      .join("") || `<tr><td colspan="8">Aucun fonds détaillé (relevé de situation seul).</td></tr>`}</tbody>`;
}

// ---------- Relevés ----------
function afficherReleves() {
  const choix = $("depot-titulaire");
  const actuel = choix.value;
  choix.innerHTML = [...etat.titulaires.map((t) => `<option>${echapper(t)}</option>`), `<option value="">Nouveau titulaire…</option>`].join("");
  if (actuel !== undefined && [...choix.options].some((o) => o.value === actuel)) choix.value = actuel;
  $("champ-nouveau").classList.toggle("cache", choix.value !== "");
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
  const titulaire = $("depot-titulaire").value || $("depot-nouveau").value.trim();
  const resultats = $("depot-resultats");
  if (!titulaire) {
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
      ligne.textContent = `${fichier.name} : ${r.deja_present ? "déjà présent" : "rangé"} dans ${r.chemin}
        (${r.assureur}, ${r.annuel ? "relevé annuel" : "situation"} au ${new Date(r.date).toLocaleDateString("fr-FR")})`;
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

$("enregistrer-corrections").addEventListener("click", async () => {
  const ouvertures = Object.fromEntries([...document.querySelectorAll("[data-ouverture]")].map((i) => [i.dataset.ouverture, i.value]));
  const verifies = {};
  document.querySelectorAll("[data-verifie]").forEach((i) => {
    verifies[i.dataset.verifie] ??= [];
    if (i.checked) verifies[i.dataset.verifie].push(Number(i.value));
  });
  const etatCorrections = $("etat-corrections");
  try {
    await envoyerJson("/api/corrections", { ouvertures, versements_verifies: verifies });
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

charger();

// Crédits : tableau d'amortissement et « rembourser ou placer » (calculés en Python, MODELE § 7.11).
import { echapper } from "./graphiques.js";
import { euros } from "./rendu.js";

const $ = (id) => document.getElementById(id);
let credits = [];

function afficherEcheancier() {
  const credit = credits.find((c) => c.cle === $("sim-credit").value);
  $("sim-credit-echeancier").innerHTML = credit?.echeancier.length
    ? `<thead><tr><th>Année</th><th class="n">Intérêts</th><th class="n">Capital remboursé</th><th class="n">Restant dû fin d'année</th></tr></thead><tbody>${credit.echeancier
        .map((a) => `<tr><td>${a.annee}</td><td class="n">${euros(a.interets)}</td><td class="n">${euros(a.capital)}</td><td class="n">${euros(a.restant)}</td></tr>`)
        .join("")}</tbody>`
    : "";
}

export function afficherCreditsSimulation(etat) {
  credits = etat.credits ?? [];
  const actuel = $("sim-credit").value;
  $("sim-credit").innerHTML = credits.map((c) => `<option value="${echapper(c.cle)}">${echapper(c.nom)}</option>`).join("");
  if (credits.some((c) => c.cle === actuel)) $("sim-credit").value = actuel;
  afficherEcheancier();
}

export function preparerCreditsSimulation() {
  $("sim-credit").addEventListener("change", afficherEcheancier);
  $("sim-credit-comparer").addEventListener("click", async () => {
    const sortie = $("sim-credit-resultat");
    const reponse = await fetch("/api/credits/simulation", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" },
      body: JSON.stringify({ cle: $("sim-credit").value, montant: $("sim-credit-montant").value, rendement: $("sim-credit-rendement").value }),
    });
    const r = await reponse.json();
    if (!reponse.ok) {
      sortie.innerHTML = `<p class="ko">${echapper(r.erreur)}</p>`;
      return;
    }
    const mieux = r.ecart >= 0 ? "rembourser" : "placer";
    const tuile = (etiquette, valeur, note) =>
      `<div class="tuile"><div class="etiquette">${etiquette}</div><div class="valeur">${valeur}</div><div class="note">${note}</div></div>`;
    sortie.innerHTML = `<div class="tuiles">${[
      tuile("Intérêts économisés", euros(r.interets_economises), `fin avancée de ${r.mois_gagnes} mois`),
      tuile("Indemnités, au plus", euros(r.indemnites_max), "plafond légal"),
      tuile(`Avantage à ${mieux}`, euros(Math.abs(r.ecart)),
        `à la fin actuelle du prêt ; rembourser : ${euros(r.patrimoine_si_rembourse)}, placer : ${euros(r.patrimoine_si_place)}`),
    ].join("")}</div>`;
  });
}

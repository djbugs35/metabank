// Budget d'un compte courant : abonnements, objectifs, d'une année sur l'autre (calculés en Python, MODELE § 7.13).
import { echapper } from "./graphiques.js";
import { euros, eurosSignes } from "./rendu.js";

const $ = (id) => document.getElementById(id);

export function afficherBudget(c) {
  const depasses = c.objectifs.filter((o) => o.depasse);
  $("compte-depassements").innerHTML = depasses.length
    ? `<div class="carte"><strong class="ko">Objectif dépassé</strong> ${depasses
        .map((o) => `${echapper(o.categorie)} : ${euros(o.depense_mois)} en ${o.mois}, pour ${euros(o.objectif)} visés`).join(" ; ")}</div>`
    : "";
  $("compte-abonnements").innerHTML = `<thead><tr><th>Marchand</th><th>Catégorie</th><th class="n">Montant habituel</th><th class="n">Mois</th><th class="n">Sur 12 mois</th></tr></thead><tbody>${c.abonnements
    .map((a) => `<tr><td>${echapper(a.marchand)}</td><td>${echapper(a.categorie)}</td><td class="n">${euros(a.montant)}</td><td class="n">${a.mois}</td><td class="n">${euros(a.cout_12_mois)}</td></tr>`)
    .join("") || "<tr><td colspan='5'>Aucune dépense régulière repérée.</td></tr>"}</tbody>`;
  const objectifs = Object.fromEntries(c.objectifs.map((o) => [o.categorie, o]));
  $("compte-objectifs").innerHTML = `<thead><tr><th>Catégorie</th><th class="n">Objectif par mois (€)</th><th class="n">Dernier mois complet</th><th class="n">Moyenne 3 mois</th></tr></thead><tbody>${c.categories_budget
    .map((nom) => {
      const o = objectifs[nom];
      return `<tr><td>${echapper(nom)}</td><td class="n"><input type="number" min="0" step="10" data-objectif="${echapper(nom)}" value="${o?.objectif ?? ""}"></td>
        <td class="n ${o?.depasse ? "ko" : ""}">${o ? euros(o.depense_mois) : "—"}</td><td class="n">${o ? euros(o.moyenne_3_mois) : "—"}</td></tr>`;
    }).join("")}</tbody>`;
  $("compte-comparaison").innerHTML = c.comparaison.length
    ? `<thead><tr><th>Catégorie</th><th class="n">12 derniers mois</th><th class="n">12 mois précédents</th><th class="n">Écart</th></tr></thead><tbody>${c.comparaison
        .map((l) => `<tr><td>${echapper(l.categorie)}</td><td class="n">${euros(l.derniers_12)}</td><td class="n">${l.precedents_12 === null ? "—" : euros(l.precedents_12)}</td>
          <td class="n">${l.precedents_12 === null ? "—" : eurosSignes(l.derniers_12 - l.precedents_12)}</td></tr>`).join("")}</tbody>`
    : `<tbody><tr><td class="discret">Il faut au moins 12 mois complets d'exports ; la colonne précédente demande 24 mois.</td></tr></tbody>`;
}

export function preparerBudget(recharger) {
  $("enregistrer-objectifs").addEventListener("click", async () => {
    const objectifs = {};
    document.querySelectorAll("[data-objectif]").forEach((i) => { if (i.value !== "") objectifs[i.dataset.objectif] = Number(i.value); });
    const message = $("etat-objectifs");
    const reponse = await fetch("/api/objectifs", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" }, body: JSON.stringify({ objectifs }),
    });
    const r = await reponse.json();
    message.className = reponse.ok ? "ok" : "ko";
    message.textContent = reponse.ok ? "Enregistré ; chiffres recalculés." : `Non enregistré : ${r.erreur}`;
    if (reponse.ok) await recharger();
  });
}

// Règles de classement des dépenses : proposer, tester, enregistrer, retirer. Validation en Python (categories.py).
import { echapper } from "./graphiques.js";
import { euros } from "./rendu.js";

const $ = (id) => document.getElementById(id);
let regles = [];
let categories = [];
let recharge = async () => {};

// Chaque dépense non classée a une liste « Ranger dans… » : choisir une catégorie crée la règle proposée (motif du
// marchand) et range d'un coup toutes ses dépenses.
export function remplirRangements() {
  document.querySelectorAll("select.ranger").forEach((s) => {
    s.innerHTML = `<option value="">Ranger dans…</option>${categories.map((c) => `<option>${echapper(c)}</option>`).join("")}`;
  });
}

async function appeler(chemin, corps) {
  const options = corps === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" }, body: JSON.stringify(corps),
  };
  const reponse = await fetch(chemin, options);
  const donnees = await reponse.json();
  if (!reponse.ok) throw new Error(donnees.erreur || `erreur ${reponse.status}`);
  return donnees;
}

function montrer(etat) {
  regles = etat.regles;
  categories = etat.categories.filter((c) => c !== "Autres dépenses");
  remplirRangements();
  $("regle-categories").innerHTML = etat.categories.map((c) => `<option value="${echapper(c)}">`).join("");
  $("regles-liste").innerHTML = regles.length
    ? `<table><thead><tr><th>Motif</th><th>Catégorie</th><th></th></tr></thead><tbody>${regles
        .map((r, rang) => `<tr><td><code>${echapper(r.motif)}</code></td><td>${echapper(r.categorie)}</td>
          <td><button class="puce" data-retirer="${rang}">Retirer</button></td></tr>`).join("")}</tbody></table>`
    : `<p class="discret">Aucune règle personnelle : seules celles de metabank s'appliquent.</p>`;
}

function dire(texte, classe = "") {
  $("regle-resultat").className = classe;
  $("regle-resultat").textContent = texte;
}

async function enregistrer(nouvelles, recharger) {
  try {
    montrer(await appeler("/api/regles", { regles: nouvelles }));
    dire("Enregistré ; chiffres recalculés.", "ok");
    await recharger();
  } catch (erreur) {
    dire(`Non enregistré : ${erreur.message}`, "ko");
  }
}

export async function afficherRegles() {
  montrer(await appeler("/api/regles"));
}

export function preparerRegles(recharger) {
  recharge = recharger;
  $("compte-non-classees").addEventListener("change", (e) => {
    const liste = e.target.closest("select.ranger");
    if (liste?.value) enregistrer([{ motif: liste.dataset.motif, categorie: liste.value }, ...regles], recharge);
  });
  $("compte-non-classees").addEventListener("click", (e) => {
    const bouton = e.target.closest("[data-classer]");
    if (!bouton) return;
    $("regle-motif").value = bouton.dataset.classer;
    $("regle-categorie").focus();
    dire("");
  });
  $("regle-tester").addEventListener("click", async () => {
    try {
      const r = await appeler("/api/regles/test", { motif: $("regle-motif").value });
      dire(`${r.nombre} opération${r.nombre > 1 ? "s" : ""}, ${euros(r.montant)}${r.exemples.length ? ` : ${r.exemples.join(" ; ")}` : ""}`);
    } catch (erreur) {
      dire(erreur.message, "ko");
    }
  });
  $("regle-enregistrer").addEventListener("click", () =>
    enregistrer([{ motif: $("regle-motif").value.trim(), categorie: $("regle-categorie").value.trim() }, ...regles], recharger));
  $("regles-liste").addEventListener("click", (e) => {
    const bouton = e.target.closest("[data-retirer]");
    if (bouton) enregistrer(regles.filter((_, rang) => rang !== Number(bouton.dataset.retirer)), recharger);
  });
}

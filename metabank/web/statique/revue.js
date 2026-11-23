// Onglet « Revue du mois » : liste d'actions calculée en Python (metabank/revue.py) ; ici, l'affichage.
import { echapper } from "./graphiques.js";

const $ = (id) => document.getElementById(id);

export async function afficherRevue() {
  const reponse = await fetch("/api/revue");
  const r = await reponse.json();
  if (!reponse.ok) throw new Error(r.erreur || `erreur ${reponse.status}`);
  const [annee, mois] = r.mois.split("-");
  $("revue-titre").textContent = `Revue de ${new Date(Number(annee), Number(mois) - 1, 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`;
  $("revue-actions").innerHTML = r.actions.length
    ? r.sujets.map((sujet) => {
        const actions = r.actions.filter((a) => a.sujet === sujet);
        return actions.length ? `<div class="carte"><h2>${echapper(sujet)}</h2><ul>${actions
          .map((a) => `<li>${echapper(a.texte)}${a.detail ? `<br><span class="note">${echapper(a.detail)}</span>` : ""}</li>`).join("")}</ul></div>` : "";
      }).join("")
    : `<div class="carte"><p>Rien à signaler ce mois-ci.</p></div>`;
}

export function preparerRevue() {
  $("revue-imprimer").addEventListener("click", () => window.print());
}

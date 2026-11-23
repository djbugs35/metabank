// Projection retraite : trois scénarios calculés en Python (MODELE § 12) ; ici, la saisie et l'affichage.
import { echapper } from "./graphiques.js";
import { euros, pct } from "./rendu.js";

const $ = (id) => document.getElementById(id);

export function afficherRetraite(etat) {
  const personnes = etat.vues.filter((v) => v.niveau === "personne").map((v) => v.nom);
  const actuel = $("ret-titulaire").value;
  $("ret-titulaire").innerHTML = personnes.map((p) => `<option>${echapper(p)}</option>`).join("");
  if (personnes.includes(actuel)) $("ret-titulaire").value = actuel;
}

export function preparerRetraite() {
  $("ret-calculer").addEventListener("click", async () => {
    const saisie = {
      titulaire: $("ret-titulaire").value, annee_depart: $("ret-annee").value, versement: $("ret-versement").value,
      inflation: $("ret-inflation").value, duree_retrait: $("ret-duree").value,
      rendements: [$("ret-r1").value, $("ret-r2").value, $("ret-r3").value], inclure_av: $("ret-av").checked,
    };
    const reponse = await fetch("/api/retraite", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" }, body: JSON.stringify(saisie),
    });
    const r = await reponse.json();
    if (!reponse.ok) {
      $("ret-resultat").innerHTML = `<p class="ko">${echapper(r.erreur)}</p>`;
      return;
    }
    $("ret-resultat").innerHTML = `<p class="discret">Aujourd'hui : ${euros(r.capital_actuel)} sur ${r.contrats.map(echapper).join(", ")} ;
      départ dans ${Math.floor(r.mois / 12)} ans et ${r.mois % 12} mois.</p>
      <div class="defile"><table><thead><tr><th>Rendement net</th><th class="n">Capital au départ</th><th class="n">En euros d'aujourd'hui</th>
        <th class="n">Retrait mensuel possible</th></tr></thead><tbody>${r.scenarios
        .map((s) => `<tr><td>${pct(s.rendement)} par an</td><td class="n">${euros(s.capital)}</td><td class="n">${euros(s.capital_reel)}</td>
          <td class="n">${euros(s.retrait_mensuel)}</td></tr>`).join("")}</tbody></table></div>`;
  });
}

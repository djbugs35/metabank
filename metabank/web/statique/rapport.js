// Rapport à enregistrer en PDF : une page A4 par vue cochée dans l'application (/rapport?vues=foyer,p:Aude&fonds=1).
import { barresGroupees, echapper } from "./graphiques.js";
import {
  MENTION, fondsDeVue, noteSansHistorique, seriesAnnees, euros, tableAnneesHtml, tableFondsHtml, tuilesHtml,
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
  };
}

function pageVue(etat, vue, rang) {
  const section = document.createElement("section");
  section.className = "page-vue";
  const note = noteSansHistorique(vue);
  const fonds = avec("fonds") ? fondsDeVue(etat, vue) : [];
  section.innerHTML = `<h2>${echapper(vue.nom)}</h2>
    <div class="tuiles">${tuilesHtml(vue)}</div>
    ${vue.annees.length ? `<figure id="graphique-${rang}"></figure><table>${tableAnneesHtml(vue.annees)}</table>` : ""}
    ${note ? `<p class="note">${echapper(note)}</p>` : ""}
    ${fonds.length ? `<h3>Fonds, du plus coûteux au moins coûteux</h3><table class="fonds">${tableFondsHtml(fonds)}</table>` : ""}`;
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
  vues.forEach((vue, rang) => {
    rapport.append(pageVue(etat, vue, rang));
    if (vue.annees.length) {
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

// Declencheur : reveille GitHub Actions a heure fixe.
//
// Cloudflare Workers ont un ordonnanceur integre, les Cron Triggers : a l heure
// dite, la plateforme appelle scheduled() sans qu aucune requete n arrive. Un
// Worker suffit donc a remplacer le planificateur de GitHub, dont les
// declenchements sont irreguliers.
//
// Le handler fetch() ne sert qu au diagnostic et, si JETON_MANUEL est
// configure, a un declenchement a la demande.

const API = "https://api.github.com";

export default {
  async scheduled(controleur, env, ctx) {
    // waitUntil : la reponse n existe pas ici, il faut prolonger l execution
    // jusqu a la fin du fetch sortant.
    ctx.waitUntil(declencher(env, "cron " + (controleur.cron || "")));
  },

  async fetch(requete, env) {
    const url = new URL(requete.url);

    if (url.pathname === "/declencher") {
      const fourni = requete.headers.get("x-jeton") || "";
      // Sans jeton configure, le declenchement manuel reste ferme : l URL du
      // Worker est publique, n importe qui pourrait sinon lancer des collectes.
      if (!env.JETON_MANUEL || fourni !== env.JETON_MANUEL) {
        return new Response("refuse\n", { status: 401 });
      }
      const resultat = await declencher(env, "manuel");
      return new Response(JSON.stringify(resultat) + "\n", {
        status: resultat.ok ? 200 : 502,
        headers: { "content-type": "application/json; charset=utf-8" },
      });
    }

    return new Response(
      "declencheur handball\n\n" +
      "Le cron lance la collecte seul, aux heures prevues par wrangler.toml.\n" +
      "Declenchement manuel : GET /declencher avec l en-tete x-jeton.\n",
      { headers: { "content-type": "text/plain; charset=utf-8" } }
    );
  },
};

async function declencher(env, origine) {
  if (!env.GITHUB_TOKEN) {
    console.error("GITHUB_TOKEN absent : secret a creer dans les reglages du Worker");
    return { ok: false, erreur: "GITHUB_TOKEN absent" };
  }

  const depot = env.DEPOT || "christophebelliere/handball";
  const flux = env.FLUX || "collecte.yml";
  const branche = env.BRANCHE || "main";

  let reponse;
  try {
    reponse = await fetch(
      `${API}/repos/${depot}/actions/workflows/${flux}/dispatches`,
      {
        method: "POST",
        headers: {
          authorization: `Bearer ${env.GITHUB_TOKEN}`,
          accept: "application/vnd.github+json",
          "x-github-api-version": "2022-11-28",
          "content-type": "application/json",
          "user-agent": "declencheur-handball",
        },
        // forcer="false" : le workflow garde son garde-fou de fraicheur, un
        // declenchement en double ne relance donc pas la collecte pour rien.
        body: JSON.stringify({ ref: branche, inputs: { forcer: "false" } }),
      }
    );
  } catch (erreur) {
    console.error("appel GitHub impossible", origine, erreur);
    return { ok: false, erreur: String(erreur) };
  }

  const detail = reponse.status === 204 ? "" : (await reponse.text()).slice(0, 300);
  console.log(origine, "->", reponse.status, detail);
  return { ok: reponse.status === 204, statut: reponse.status, detail };
}

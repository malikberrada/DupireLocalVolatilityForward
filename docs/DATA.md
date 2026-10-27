# Données, collecte et provenance

Les chaînes brutes sont des archives réelles Yahoo reçues par `yfinance.Ticker.option_chain`. Elles contiennent les calls, puts, informations de sous-jacent et heures de requête. La liste exhaustive des échéances, nombres de contrats, tailles et empreintes est dans `data/manifest.json`.

| ID | Début de collecte UTC, le 26 octobre 2026 | Utilisation |
|---|---|---|
| `attempt_01` | 19:31:29 | Rejeu du premier instantané d’origine |
| `attempt_02` | 19:31:59 | Rejeu du deuxième instantané d’origine |
| `attempt_03` | 19:32:31 | Entrée principale du critère conjoint et de l’audit de traçabilité |
| `live_capture` | 20:09:06 | Capture ultérieure du même jour, archivée dans les validations d’origine |

Une copie incluse au dépôt et un téléchargement GitHub à SHA complet donnent les mêmes octets. Le fournisseur ne propose pas ici un mécanisme de rejeu historique des bid/ask : les appels actuels `option_chain` sont archivés comme de **nouvelles données**, sans remplacer ces quatre instantanés.

## Chaîne de traitement

1. Le collecteur enregistre le protocole avant téléchargement : symbole `^SPX`, racine `SPXW`, fenêtre de strikes 95 %–105 % du spot, strikes multiples de 50, échéances de 14 à 180 jours, six dates demandées au maximum. Le spot sert à la sélection, jamais comme forward estimé.
2. Toutes les chaînes reçues restent dans `raw_snapshot.json`. La sélection et les motifs d’exclusion sont enregistrés ; les bid/ask retenus sont inchangés. Une règle fixe pendant un rejeu ne prouve pas rétrospectivement qu’elle a été choisie avant les prix lors du développement.
3. Les courbes nominales forward/discount sont estimées par la parité call-put. Elles ne sont pas remplacées par des taux ou dividendes inventés.
4. La normalisation des calls et puts conserve 121 intervalles sur la grille retenue. La monotonie, les pentes, la convexité et les boîtes sont vérifiées exactement sur les coordonnées rationnelles déclarées.
5. Le lanceur historique certifie séparément forward et backward. Le parcours `scripts/reproduce.py` ajoute le critère **conjoint** et vérifie un seul témoin satisfaisant les deux systèmes.

Les garanties sont conditionnelles aux courbes nominales, à la sélection et aux bornes 5 %–100 % annualisées. Les horodatages de récupération/`lastTradeDate` ne sont pas des heures certifiées du bid/ask. Le parcours ne démontre pas une absence d’arbitrage de tous les contrats bruts ni la robustesse à toute l’incertitude sur les courbes.

Le calendrier de collecte intégré couvre 2026–2028. La collecte actuelle respecte les séances régulières prévues et refuse une séance fermée. Cette garde n’est pas une détection des suspensions de marché. Sources techniques du projet : [yfinance](https://github.com/ranaroussi/yfinance), [horaires Cboe](https://www.cboe.com/about/hours/us-options).

## Articles bibliographiques

`data/papers_manifest.json` conserve les URLs et empreintes des sept fichiers PDF du dossier d’origine, dont les six textes indexés pour les 18 corrections. Aucun PDF tiers n’est nécessaire à la reproduction numérique principale. `python scripts/download_data.py papers --id BR2016` télécharge une version précise, avec contrôle d’empreinte ; une page HTML, un refus d’accès ou une version modifiée provoquent un échec explicite. Le script ne contourne pas les restrictions d’accès.

Les lectures corrigées dans `reference/readings/` restent en attente de validation. Les empreintes et arguments mathématiques peuvent être vérifiés localement ; récupérer un article n’établit ni sa bonne interprétation, ni une priorité scientifique.

## Conditions des tiers

La licence MIT du dépôt s’applique au code de l’auteur. Les données Yahoo sont conservées comme entrées de recherche et ne sont pas déclarées sous licence MIT ; les conditions de Yahoo et des ayants droit restent applicables. Les articles appartiennent à leurs auteurs/éditeurs. Les instantanés ne contiennent pas de clés d’API ni de cookies d’authentification et le collecteur ne les demande pas.

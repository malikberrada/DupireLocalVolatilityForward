# Diagnostic et collecte Yahoo — 0.1.4

La version 0.1.4 ajoute des diagnostics et une sélection d'échéances. Elle ne
reconstitue aucun bid/ask absent, ne remplace aucun zéro par `lastPrice` et ne
modifie pas les règles d'estimation ni la signification des certificats 0.1.3.

## Diagnostic d'un instantané enregistré

```powershell
python -u -m dupire_joint diagnose-snapshot `
  --snapshot .\runs\yahoo_snapshot\snapshot.json `
  --check-parity `
  --out .\runs\yahoo_diagnostic
```

`snapshot.quality.json` fournit, par racine et échéance, les nombres de calls,
puts, livres entièrement nuls, livres valides et strikes appariés. Le test de
parité optionnel vérifie aussi les bandes exactes. Un nombre suffisant de
paires ne garantit pas que leurs bandes sont compatibles. Aucun compte de
livres ne démontre la faisabilité d'une surface Dupire.

`estimate-curves` écrit maintenant `input_quality.json` et affiche le résultat
de chaque échéance, y compris le motif des rejets. Les anciens certificats
de courbes restent revérifiables : le cœur de l'estimateur est inchangé.

## Nouvelle collecte

```powershell
python -u -m dupire_joint snapshot `
  --symbols "^SPX,^XSP" `
  --expiry-selection spread `
  --min-days 7 --max-days 365 `
  --max-expiries 24 --rps 0.5 --retries 3 `
  --require-matched-pairs 3 `
  --out .\runs\yahoo_snapshot_v014
```

`spread` répartit au plus 24 échéances par symbole sur l'ensemble des dates
proposées dans la fenêtre, en conservant la première et la dernière. Cette
sélection dépend des dates, avant toute consultation des prix. Elle ne choisit
pas les résultats les plus favorables. La sélection historique des premières
dates reste `front`, valeur par défaut pour les anciennes commandes.

Les bornes du téléchargement portent sur des jours calendaires depuis le jour
UTC de collecte. L'estimation applique ensuite ses propres bornes ACT/365F
jusqu'au fixing, comme dans la version 0.1.3. Les échéances retenues et le
nombre de dates disponibles sont conservés dans `snapshot.json`.

Le téléchargement archive les données et écrit `snapshot.quality.json`.
`--require-matched-pairs 3` retourne le code 3 si aucune racine/échéance n'a
trois strikes call-put avec deux livres valides. Les données restent disponibles
pour l'audit. Cette condition est nécessaire à la configuration d'estimation
par défaut ; elle ne garantit ni la parité ni la calibration. Le seuil ne
compte pas des contrats de racines ou d'échéances différentes ensemble.

## Résultat sur l'archive utilisateur auditée

L'instantané fourni a été collecté le 25 octobre 2026, entre
16:29:09.843070 et 16:30:57.750179 UTC. Les résultats sont :

| Racine | Contrats | Livres bid=ask=0 | Livres valides | Strikes appariés valides |
| --- | ---: | ---: | ---: | ---: |
| SPXW | 6974 | 6900 | 72 | 0 |
| SPX | 560 | 521 | 38 | 0 |
| XSP | 4203 | 4064 | 138 | 4 |

Les quatre paires XSP appartiennent au 20 novembre 2026. Elles n'ont pas de
facteur d'actualisation commun compatible : certaines bandes imposent
D >= 13377/13250, d'autres D <= 15667/16500. La première borne dépasse la
seconde. L'échec ne provient donc pas d'une tolérance numérique du solveur.

Les racines et l'appariement sont corrects pour cette archive. Pour SPXW,
écarter le livre croisé ne ferait apparaître aucune paire. L'archive ne
permet pas de produire les courbes requises pour la normalisation demandée.
Les dates `lastTradeDate` des rares contrats XSP appariés datent de mai à
septembre ; ce sont des dates de transactions, pas des horodatages bid/ask.
Le fait que la collecte soit un dimanche ne prouve pas la cause des zéros.

Une nouvelle collecte sur un horizon plus large peut fournir de meilleurs
livres, sans garantie. Si les livres restent absents ou incohérents, une
validation sur ces données Yahoo reste impossible dans ce cadre. Le patch
ne change pas de fournisseur ni de famille d'instruments implicitement.

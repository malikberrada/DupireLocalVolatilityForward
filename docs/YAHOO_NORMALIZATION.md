# Normalisation Yahoo par parité call-put — version 0.1.3

`estimate-curves` calcule les courbes depuis un instantané enregistré.
`verify-curves` reconstruit leurs ensembles admissibles et leurs bornes.
Le chemin manuel `normalize` et la construction 0.1.2 restent disponibles.
Aucun taux courant ou spot de remplacement n'est utilisé dans l'estimation.

## Commandes PowerShell

Dans `.venv312` actif, après installation du patch :

```powershell
python -u -m dupire_joint snapshot `
  --symbols "^SPX,^XSP" --max-expiries 24 --rps 0.5 --retries 3 `
  --out .\runs\yahoo_snapshot

python -u -m dupire_joint estimate-curves `
  --snapshot .\runs\yahoo_snapshot\snapshot.json `
  --symbol "^SPX" --root SPXW `
  --min-days 7 --max-days 365 `
  --allow-partial --normalize `
  --out .\runs\yahoo_SPXW_normalise

python -u -m dupire_joint verify-curves `
  --snapshot .\runs\yahoo_snapshot\snapshot.json `
  --curves .\runs\yahoo_SPXW_normalise\curves_estimees.csv `
  --out .\runs\yahoo_SPXW_verification
```

Pour XSP, sélectionner `--symbol "^XSP" --root XSP` dans un autre dossier.
La fenêtre de 7 à 365 jours est explicite et consignée. La maturité est
ACT/365F entre le temps de référence et le fixing prévu de l'indice.
Au moins trois strikes call/put appariés sont exigés par défaut ; le seuil
peut être ramené explicitement à deux. Un seul strike n'identifie pas F,D.
`--max-pairs 2000` et `--time-limit 120` bornent le calcul par échéance.
Un dépassement est un refus de calcul, sans conclusion d'infaisabilité.

Sans `--allow-partial`, toute échéance sélectionnée rejetée bloque la
normalisation avec le code de sortie 3. Avec cette option, seules les
échéances acceptées sont exportées, les autres restant dans le rapport.
Une absence totale de courbes acceptées produit toujours le code 3.
Une relance dans le même dossier déplace les anciens exports dans
`previous_exports` : un échec ne laisse pas un ancien `quotes.csv` à la
place des nouvelles données attendues. Le suivi de démarrage reste actif.

## Fichiers produits

| Fichier | Contenu |
| --- | --- |
| `curves_estimees.csv` | Huit colonnes attendues, plus provenance et nom du certificat |
| `curves_estimees.csv.uncertainty.json` | Polygones exacts, courbes nominales, bornes, horaires et exclusions |
| `estimation.json` | Bilan et chemins des résultats |
| `quotes.csv` | Calls normalisés avec la courbe nominale, pour `solve` et `construct` |
| `quotes.csv.uncertainty.csv` | Enveloppes de temps, strike normalisé, bid et ask |
| `quotes.csv.metadata.json` | Périmètre et hypothèses de normalisation |

La vérification rationnelle de courbes **estimées** n'est pas une validation
externe des cotations. Conserver le CSV et son fichier `.uncertainty.json`
ensemble. `normalize` reconnaît ce dernier et propage l'incertitude. Un CSV
portant la provenance `estimated_call_put_intervals` est refusé s'il manque.

## Estimation avec les fourchettes observées

Pour une même racine et une même échéance, poser A=DF. Pour chaque strike K :

\[
L=C_{bid}-P_{ask}\le A-DK\le C_{ask}-P_{bid}=U.
\]

L'ensemble admissible est l'intersection de ces bandes avec A>=0,D>=0.
Le code utilise des rationnels exacts sur les représentations décimales JSON.
Il ne fait pas de régression sur les milieux et ne présuppose aucun taux.
Les strikes et dates des identifiants OCC sont vérifiés. Les racines SPX,
SPXW et XSP restent séparées. Les livres absents, non finis ou sans ask
positif sont exclus et listés, comme les strikes non appariés. Les doublons
contradictoires, contrats incohérents et livres croisés rejettent l'échéance.
Aucune fourchette n'est élargie, aucun outlier n'est retiré automatiquement.

Les deux strikes extrêmes k0<kn impliquent :

\[
\frac{L_0-U_n}{k_n-k_0}\le D\le
\frac{U_0-L_n}{k_n-k_0}.
\]

Après intersection avec D>=0, ces bornes et la première bande donnent une
boîte finie en (A,D) contenant toutes les solutions positives. Le code la
découpe exactement par toutes les bandes. Les segments et points sont
conservés. Un ensemble vide est signalé. Si la fermeture touche A=0 ou D=0,
la normalisation est refusée comme insuffisamment identifiée. Sinon la
moyenne des sommets fournit un choix nominal déterministe admissible.

Les extrema de A et D sont atteints aux sommets. Ceux de F=A/D le sont aussi
car D>0. `verify-curves` repart du snapshot original, reconstruit les bandes,
leurs intersections et leurs bornes, puis vérifie les empreintes et le CSV.
Une empreinte lie des fichiers ; elle n'authentifie pas une donnée externe.

## Propagation des incertitudes

Les transformations d'un call brut sont :

\[
x=KD/A,\qquad bid_{norm}=C_{bid}/A,\qquad ask_{norm}=C_{ask}/A.
\]

Leurs extrema sont calculés sur le même polygone (A,D), sans combiner des
bornes indépendantes de F et D. Les colonnes sont `time_lower/upper`,
`x_lower/upper`, `bid_lower/upper`, `ask_lower/upper` et les versions `_exact`.
Les bornes binary64 sont arrondies vers l'extérieur. Les rationnels exacts
permettent de retrouver les bornes sans arrondi.

Ce sont des **enveloppes marginales déterministes**, pas des intervalles de
confiance. Le polygone conserve la dépendance commune de toutes les options
d'une échéance. Les intervalles de strikes ne forment pas une grille fixe à
fournir directement à `construct`. Les fourchettes de `quotes.csv` sont celles
de la courbe nominale ; les enveloppes ne les élargissent pas. Un certificat
sur cette courbe ne démontre pas la faisabilité pour toutes les courbes du
polygone. Les métadonnées portent `robust_calibration_certified: false`.

## Horaires et calendrier

Les conventions sont SPX=AM, SPXW=PM, XSP=PM. Le calendrier embarqué couvre
2026-2028, avec les fermetures et clôtures anticipées publiées par NYSE.
Les PM utilisent la clôture prévue des actions sous-jacentes (16h ou 13h à
New York), pas la fin de négociation des options non expirantes. `zoneinfo`
gère les conversions UTC et le changement d'heure. Sous Windows, si la base
est absente : `python -m pip install tzdata`.

Le temps de référence par défaut est le milieu de la fenêtre globale de
récupération. L'enveloppe temporelle utilise ses deux extrémités ; elle ne
borne pas l'ancienneté réelle du bid/ask. `lastTradeDate` n'est jamais utilisé
comme horodatage bid/ask. `--asof 2026-10-26T14:00:00Z` permet de fixer une
autre référence explicitement enregistrée.

Pour SPX AM, 09h30 est une référence d'ouverture prévue : le SET réel utilise
les ouvertures des composantes et sa publication n'est pas garantie à cet
instant précis. Cette hypothèse est explicite dans le rapport. T vise le
fixing, tandis que le paiement peut intervenir le jour ouvré suivant. D est
inféré de la parité des contrats, sans taux de remplacement exp(-r*T).

Un fixing hors calendrier, un jour de fermeture ou une fermeture exceptionnelle
demande un fichier `--settlements CHEMIN.csv` avec les colonnes :

```csv
symbol,root,expiry,fixing_utc,settlement,source
```

Chaque ligne renseigne l'instant avec fuseau, AM/PM et une source. La date
d'expiration n'est jamais déplacée automatiquement. Le calendrier annoncé
reste conditionnel à l'absence de changements ultérieurs.

## Utiliser les calls normalisés

```powershell
python -u -m dupire_joint construct `
  --quotes .\runs\yahoo_SPXW_normalise\quotes.csv `
  --degree-time 4 --degree-space 10 `
  --sigma-min 0.05 --sigma-max 1.00 `
  --variance-buffer 0.001 --gamma-floor 0.01 `
  --device cuda --threads 10 `
  --out .\runs\constructive_yahoo
```

Ce sont des paramètres exploratoires, sans garantie de succès. La fenêtre de
strikes, les fourchettes et les bornes locales restent à justifier. Au moins
deux échéances acceptées sont nécessaires. Les unions de strikes normalisés
peuvent être grandes ; les budgets de la commande `construct` s'appliquent.

## Sources primaires

- Cboe, racines, AM/PM, style européen, fixing et paiement XSP :
  https://cdn.cboe.com/resources/xsp/XSP_Options_Fact_Sheet.pdf
- NYSE/ICE, calendrier 2026-2028 et clôtures anticipées :
  https://ir.theice.com/press/news-details/2025/NYSE-Group-Announces-2026-2027-and-2028-Holiday-and-Early-Closings-Calendar/
- yfinance, données `option_chain` :
  https://github.com/ranaroussi/yfinance/blob/main/yfinance/ticker.py

La validation jointe utilise des instantanés synthétiques et des cas
incohérents. Elle ne constitue pas un essai de cotations Yahoo en direct.

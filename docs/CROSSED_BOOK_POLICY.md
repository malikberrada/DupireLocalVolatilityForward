# Livres croisés : rejet strict ou exclusion explicite — 0.1.5

Le mode historique rejette toute une échéance dès qu'un livre de cette racine
présente bid>ask, même si ce contrat n'appartient à aucune paire call-put.
Cela peut empêcher le calcul de la parité sur les autres livres valides.
La version 0.1.5 ajoute une politique explicite, sans élargir les fourchettes.

## Deux modes

- `--crossed-policy reject` : comportement historique, conservé par défaut.
- `--crossed-policy exclude` : exclut uniquement les livres croisés de
  l'appariement et enregistre contrat, bid, ask et motif. L'autre membre de
  leur éventuelle paire devient non apparié ; aucun prix n'est reconstruit.

Les contrats incohérents, erreurs de strike/date/type et doublons contradictoires
continuent à rejeter l'échéance. Les livres nuls ou non finis restent exclus
et consignés comme dans 0.1.3. Aucun livre valide n'est supprimé parce qu'il
rend la parité infaisable : les bandes de tous les livres valides appariés
sont utilisées ensemble. Si leur intersection est vide, le résultat reste
`empty_parity_set`. Il n'y a ni régression sur les milieux ni remplacement
par `lastPrice`, ni modification du seuil de tolérance.

## Tester le nouvel instantané déjà téléchargé

```powershell
python -u -m dupire_joint diagnose-snapshot `
  --snapshot .\runs\yahoo_snapshot_v014\snapshot.json `
  --check-parity --crossed-policy exclude `
  --out .\runs\yahoo_quality_v015_exclude
```

Le rapport conserve les comptes bruts, les livres exclus et les états de
parité après cette exclusion. La présence de trois paires n'est toujours pas
une garantie de compatibilité ni de calibration. Les dates, racines et
échéances restent séparées.

Pour estimer XSP puis normaliser :

```powershell
python -u -m dupire_joint estimate-curves `
  --snapshot .\runs\yahoo_snapshot_v014\snapshot.json `
  --symbol "^XSP" --root XSP `
  --min-days 7 --max-days 365 `
  --crossed-policy exclude `
  --allow-partial --normalize `
  --out .\runs\yahoo_XSP_normalise_v015
```

Pour SPXW, utiliser `--symbol "^SPX" --root SPXW` et un autre dossier.
Au moins deux échéances acceptées sont nécessaires à `construct` ; une courbe
d'une seule échéance ne suffit pas. Les degrés et bornes locales de la
construction doivent toujours être justifiés pour les données retenues.

## Certificat, données et portée

Le certificat sauvegarde `settings.crossed_policy` et les exclusions par
échéance. `verify-curves` recalcule la même sélection sur le snapshot brut,
lié par SHA-256, puis toutes les contraintes et les bornes exactes. Changer
la politique d'un certificat sans le recalculer fait échouer sa vérification
lorsque les résultats changent. Les anciens certificats sans ce champ sont
interprétés selon la politique historique `reject`.

La normalisation exporte les calls valides des échéances acceptées et journalise
chaque call omis. Les métadonnées indiquent la politique et
`original_snapshot_all_quotes_certified: false`. Un certificat sur ces prix
concerne le jeu retenu après exclusion ; il ne valide pas les livres croisés
du snapshot original, ni leur simultanéité. Les enveloppes d'incertitude en
coordonnées ne démontrent toujours pas une calibration robuste pour toutes
les courbes admissibles.

## Lecture du rapport utilisateur collecté à 17:05 UTC

Le fichier fourni contient 50 groupes racine/échéance : 42 ont un nombre de
paires inférieur à trois, et huit sont rejetés par le contrôle des livres
croisés. Aucun rejet de ces huit groupes ne porte le motif `empty_parity_set`.
Il ne permet donc pas de conclure que leurs paires valides sont incompatibles.

Les candidats disposant d'au moins trois paires valides sont :

| Racine | Échéance | Paires valides |
| --- | --- | ---: |
| SPXW | 2027-03-31 | 5 |
| XSP | 2027-02-19 | 8 |
| XSP | 2027-03-19 | 16 |
| XSP | 2027-05-21 | 3 |
| XSP | 2027-06-17 | 28 |
| XSP | 2027-08-20 | 10 |

XSP dispose aussi de deux paires sur chacune des dates 2026-12-18 et
2027-01-29, insuffisantes pour la configuration par défaut. SPX ne fournit
qu'une seule paire dans son groupe le mieux renseigné.

Le fichier `snapshot.quality.json` contient un résumé, pas les bid/ask de
toutes ces paires. Leur intersection après exclusion n'a donc pas pu être
calculée ici sur cette nouvelle collecte. Le patch permet de la calculer
localement depuis `snapshot.json`. Les tests et exemples joints ne sont pas
présentés comme un résultat positif sur ces nouvelles cotations Yahoo.

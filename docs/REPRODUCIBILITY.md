# Reproduction et critères de réussite

Le point d’entrée est `python scripts/reproduce.py`. Toutes les commandes utilisent le même `sys.executable`, y compris dans les sous-processus. Les paramètres principaux sont versionnés dans `config/reproduction.json`.

| Profil | Travail exécuté |
|---|---|
| `proofs` | Reconstruit le nouveau dual depuis les contraintes ; exporte les preuves rédigées et contrôle les identités/certificats rationnels |
| `market` | Rejoue un instantané brut, reconstruit sélection/courbes/grille, résout les deux schémas puis leur intersection avec un témoin commun |
| `core` | Preuves, certificat polynomial d’origine et nouvel ajustement, marché `attempt_03`, traçabilité complète, exemples discriminants et vérification des archives numériques |
| `study` | Revérifie les preuves archivées puis recalcule les 12 cas avec leurs CSV originaux, sur trois niveaux |
| `all` | `core`, les quatre instantanés du 26 octobre et les 12 cas recalculés |

Exemple :

```powershell
& $PyDupire scripts/reproduce.py --profile market --snapshot live_capture --out runs/rejeu_capture
```

`live_capture` est le nom d’un **instantané historique**, collecté le 26 octobre à 20:09 UTC. Il ne déclenche aucun téléchargement actuel.

Le parcours marché vérifie le statut exact, le nombre d’observations, la géométrie reconstruite et son identité avec l’original. Le critère `joint` produit un unique vecteur rationnel, contrairement aux deux témoins distincts du lanceur historique `valider_yahoo.py`. Le script d’audit relie ce certificat jusqu’aux lignes bid/ask brutes.

Chaque échec donne un code de sortie non nul, un `summary.json` avec `status: failed` et un journal précis. Un dossier de sortie non vide est refusé. Les entrées figées ne sont jamais écrasées. Les données téléchargées ne sont publiées à leur chemin final qu’après contrôle de taille et de SHA-256.

## Ce qui est reproduit exactement

Les octets bruts, les observations originales, les contraintes rationnelles, les marges des certificats duals et les identités algébriques décrites sont contrôlés exactement. Une empreinte lie des octets ; elle n’authentifie pas Yahoo.

Le nouvel ajustement polynomial retrouve la conclusion certifiée avec des paramètres décimaux exacts 0.18 et 0.22. Le témoin d’origine utilisait des bornes enregistrées en rationnels issus de binary64 : il est conservé et vérifié séparément, sans lui substituer les paramètres décimaux du nouvel ajustement.

Les fichiers `.npz`, les témoins numériques et les rapports de l’étude d’origine restent dans `reference/study/`. Leur environnement d’origine est enregistré dans chaque `report.json`. Le verrou actuel ne prétend pas reconstituer cet ancien environnement CUDA. Le recalcul utilise leurs **CSV originaux**, ce qui préserve les entrées malgré les différences d’arrondi entre générateurs CPU et GPU. Les temps, bases du solveur et décisions numériques indéterminées peuvent varier ; les nouveaux résultats sont conservés pour comparaison. Les témoins primaux de cette étude sont contrôlés numériquement ; leurs certificats duals portent sur les LP binary64 enregistrés.

Le profil `all`/`study` produit aussi `study_comparison.json` et exige les mêmes 108 modèles LP et conclusions. Dans l’environnement verrouillé testé, les 32 conclusions numériques positives, 70 négatives certifiées et 6 indéterminées sont retrouvées. Si un autre environnement les modifie, le parcours s’arrête et conserve le détail de l’écart ; il ne transforme pas cet écart en reproduction réussie.

Les 12 cas ne sont pas douze journées de marché : ce sont des expériences synthétiques BS/discrètes/perturbées/Heston. Les quatre instantanés Yahoo concernent une seule journée. Les profils de reproduction n’effectuent aucun appel Ollama et ne convertissent jamais les annotations bibliographiques en lectures acceptées.

## Autres commandes

```powershell
# Contrôler un nouveau dossier Yahoo terminé, sans résolution ni réseau
& $PyDupire valider_yahoo.py --verify runs/nouveau_marche

# Contrôler uniquement les preuves archivées de l’étude
& $PyDupire scripts/verify_reference.py

# Recalcul synthétique depuis la graine (en plus des CSV originaux archivés)
& $PyDupire -m dupire_joint study --device cpu --seed 20261025 --cases 12 --families bs,discrete,corrupt,heston --nt 5 --nx 25 --stagger --levels 0,1,2 --relax --threads 2 --out runs/etude_generee

# Recompiler la note si pdflatex est installé
& $PyDupire -I -S analyse_dependances/generer_dependances.py --out runs/preuves_pdf --compile-pdf
```

Sans `--compile-pdf`, le PDF joint est copié ; les certificats et calculs rationnels sont bien recalculés. Les textes de preuves générales sont exportés depuis le LaTeX rédigé, sans prétendre à une démonstration formelle automatique.

## Nettoyage de l’archive d’origine

La racine de l’archive contenait un moteur 0.1.1 et un second arbre `source/` en 0.1.6. Le présent dépôt prend **l’arbre 0.1.6**, identique aux modules Python de la roue 0.1.6 fournie. Les anciens correctifs, sauvegardes, roues, archives imbriquées, caches Python et exécutions intermédiaires ont été écartés. Les données/certificats de référence utiles et les tests existants ont été conservés. Les entrées exactes des dossiers scellés restent inchangées et protégées contre la conversion des fins de ligne par `.gitattributes`.

Les profils se lancent depuis un checkout ou une archive source complète ; la roue du moteur seule ne contient pas les données de recherche et les scripts d’audit.

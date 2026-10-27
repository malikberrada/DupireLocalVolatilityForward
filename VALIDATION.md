# Validation du 27 octobre 2026

Les vérifications ont été exécutées dans un nouvel environnement virtuel Python **3.12.14**, sous Linux, avec les versions exactes de `requirements-lock.txt`. Le moteur a été installé depuis les sources de ce dépôt. Aucun paquet de l’environnement utilisateur n’a été utilisé. La livraison ZIP a ensuite été extraite dans un autre dossier, réinstallée dans un second environnement virtuel indépendant puis contrôlée : les 315 tests et les 16 étapes du parcours principal passent également après extraction.

| Contrôle | Résultat |
|---|---|
| Tests du moteur, collecteur, téléchargements et audits | **315 réussites, 3 tests optionnels ignorés** |
| Profil `core` | Réussi : preuves, ajustement polynomial, rejeu brut, courbes, deux schémas et critère conjoint, traçabilité |
| Profil `all` | Réussi : quatre instantanés historiques et douze cas d’étude recalculés |
| Comparaison de l’étude | **108/108 modèles LP et conclusions identiques** |
| Preuves archivées de l’étude | 70 certificats duals exacts et 32 témoins primaux numériques revérifiés ; 6 résultats indéterminés conservés |
| Nouveau certificat dual | 10 termes, marge exacte `4739/384000000` |
| Séparation robuste aux spreads | Écart exact `1153/128000000` |
| Construction polynomiale | Certificat d’origine vérifié ; nouvel ajustement certifié au niveau garanti 2 |
| Construction pip | Roue Python et distribution source construites avec succès, sans CMake |
| Dépendances installées | `pip check` ne trouve aucune incompatibilité |
| Dépendances Windows Python 3.12 x64 | Toutes les roues du verrou ont été résolues et téléchargées |

Les trois tests ignorés dépendent de l’API de partage de fichiers native Windows, de PyTorch ou d’un GPU CUDA. **L’exécution native Windows et CUDA n’a pas été réalisée ici.** Le workflow GitHub Actions prépare les tests CPU sur Ubuntu et Windows ; son exécution distante nécessite la publication du dépôt.

Un test de téléchargement Yahoo réel le 27 octobre 2026, de **14:12:10 à 14:12:29 UTC**, a reçu six chaînes sans erreur réseau. La collecte a ensuite été rejetée pour incohérence de parité/qualité sur certaines échéances. Le code de sortie non nul et la conservation des tentatives sont attendus dans ce cas ; aucune réussite mathématique n’a été déclarée pour cette nouvelle collecte. Ces nouvelles données ne remplacent pas les quatre entrées historiques du dépôt.

La route de téléchargement des données figées par GitHub est couverte par des tests de contrôle des octets, des URLs à commit complet et du refus des contenus modifiés. Le dépôt distant n’étant pas encore publié, cette route n’a pas été exercée contre une URL de ce nouveau dépôt. Les mêmes données sont présentes dans l’archive livrée et ont été rejouées intégralement.

Les reçus lisibles par programme sont dans `validation/` : environnement, tests, parcours principal/complet, comparaison détaillée de l’étude et acquisition actuelle. Les preuves de référence inchangées sont dans `reference/`. Les commandes complètes et journaux sont régénérés dans `runs/` à chaque exécution.

La validation des calculs ne certifie pas une priorité scientifique, une extension continue ou une synchronisation des bid/ask.

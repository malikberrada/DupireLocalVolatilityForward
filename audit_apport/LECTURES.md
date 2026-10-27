# Compléter les lectures et analyses — 0.5.3

## Corriger les arguments du cahier v052

Les 18 brouillons ont été produits ; leur réussite structurelle n’est pas une
validation des arguments. La version 0.5.3 fournit une révision documentée de
ces analyses. Utiliser `rectifier_lectures.py --workbook ... --campaign ...
--out ...` comme indiqué dans le README. Aucun nouvel appel Ollama n’est requis.

Le dossier de sortie contient `lectures_corrigees.json`, l’entrée initiale,
les changements par champ, les liaisons aux sources et
`verification_bibliographique.md`. C’est ce nouveau cahier qu’il faut copier
hors du dossier scellé pour une lecture et une déclaration ultérieures.
Ne pas écraser le cahier ni les reçus dans `analyses_bibliographiques_v052`.

La révision retire la référence circulaire dans ZHANG/C3 et les qualifications
erronées de nécessité de C1. Elle établit une dérivation de la composante seuil
C3 depuis les contraintes BR et précise l’obstacle à une application littérale
du lemme S0.2 à toute la classe C1. Les autres dérivabilités restent ouvertes.
Le rapport explique la portée de chaque conclusion ; aucune lecture intégrale
ni validation du lecteur ne sont enregistrées automatiquement.

## Reprendre les six comparaisons manquantes

L’exécution 0.5.1 jointe a produit huit nouveaux brouillons et repris les quatre
anciens : **12 au total**, sans lecture acceptée automatiquement. Le cahier
confirme deux C1, cinq C2 et cinq C3. Les six paires encore en échec sont :

| Paire | Dernière catégorie indiquée par le journal console |
|---|---|
| SANOS2026_C1 | invalid_analysis_schema |
| CCD2020_C1 | incomplete_hypothesis_coverage |
| ZHANG2025_C1 | invalid_analysis_schema |
| ZHANG2025_C2 | invalid_analysis_schema |
| ZHANG2025_C3 | incomplete_hypothesis_coverage |
| FH2015_C1 | invalid_analysis_schema |

Le détail du champ rejeté n’est pas dans ces deux pièces jointes. Le lire dans
`analysis_log.json` et les fichiers `diagnostics/*.response.json` du dossier
0.5.1. Il n’y a pas de troncature signalée dans le journal console fourni.
Ce constat ne remplace pas l’examen des réponses d’Ollama.

Après extraction du correctif :

```powershell
python -u .\audit_apport\completer_lectures.py analyser `
  --campaign .\runs\lectures_bibliographiques_v050 `
  --model 'qwen3.5:35b' `
  --resume .\runs\analyses_bibliographiques_v051 `
  --axes-per-call 1 --retries 2 `
  --out .\runs\analyses_bibliographiques_v052
```

Le programme vérifie les empreintes de la même campagne, copie les douze
fichiers de brouillons réussis sans les réécrire et relance les six paires
manquantes. Les cahiers ou dossiers scellés ne doivent pas être modifiés avant
la reprise. Un nouveau dossier de sortie est nécessaire à chaque exécution.

Les six paires totalisent **69 axes**. Avec `--axes-per-call 1`, chaque axe a
son propre appel ; les échecs peuvent provoquer jusqu’à deux essais
supplémentaires. Le projet et les passages antérieurs accompagnent chaque
appel, avec leurs rôles respectifs. Le serveur doit déjà disposer du modèle.

Le schéma 0.5.2 utilise une propriété obligatoire par identifiant d’axe,
également présentée au modèle dans le prompt. Le décodage ne fait que
convertir cet objet en la liste habituelle du cahier, dans l’ordre attendu.
Il ne complète aucun contenu manquant. Un ancien format en liste reste
accepté si sa couverture exacte et tous ses champs sont valides. Les clés
JSON dupliquées sont refusées plutôt qu’écrasées silencieusement.

Les valeurs par défaut restent `--num-predict 8000`, `--thinking off`,
`--axes-per-call 7`, `--retries 1`. Un lot multi-axes rejeté après ces essais
est repris automatiquement par appels individuels, avec les mêmes contrôles.
Un problème de connexion ne multiplie pas les appels par hypothèse.
Une divergence entre les conclusions des appels reste `unresolved`.

Pour consulter le diagnostic après exécution :

```powershell
python -u .\audit_apport\completer_lectures.py diagnostiquer `
  --workbook .\runs\analyses_bibliographiques_v052\lectures_a_valider.json `
  --analysis-dir .\runs\analyses_bibliographiques_v052
```

Les nouvelles catégories précisent notamment les champs vides, les relations
inconnues, les références manquantes et les identifiants incohérents.
Les messages et `details.path` identifient le champ rejeté. Les diagnostics
conservent la réponse finale, `done_reason`, les compteurs de tokens et les
réglages ; le raisonnement privé du modèle n’est pas enregistré.
Les réponses tronquées, JSON incomplets, citations inventées et demandes
d’outils restent refusés. Un éventuel bloc Markdown unique entourant un JSON
complet peut être retiré, en le signalant dans le reçu.

L’ancien tableau homogène imposait le nombre d’entrées, mais ses contraintes
n’interdisaient pas la répétition d’un identifiant d’axe. C’est une faiblesse
reproductible du schéma, cohérente avec la catégorie de couverture observée.
Sans les réponses originales, on ne peut pas affirmer que la duplication
était la cause précise des deux échecs de couverture du journal.
La documentation officielle [Ollama : sorties structurées](https://docs.ollama.com/capabilities/structured-outputs)
décrit le schéma dans `format` et recommande aussi de l’inclure dans le prompt.

Les **19 comparaisons sans source** restent à documenter à l’étape suivante
de récupération des textes. Une exécution partielle renvoie le code de sortie
2 tout en conservant ses résultats utilisables. Les brouillons obtenus sont
à contrôler, corriger et déclarer après lecture ; leur présence ne certifie
pas la priorité scientifique. La différence de cadre ou l’absence d’une
formule identique ne suffit pas à exclure un corollaire ou une adaptation.

## Préparer une nouvelle campagne

Ce module reprend le dossier `priorite_bibliographique_v040` déjà vérifié.
Il récupère les textes accessibles, conserve leurs octets, extrait les pages,
prépare les comparaisons C1–C3 et intègre des lectures explicitement déclarées.
Il conserve les lacunes quand un document manque. Une analyse de modèle reste
un brouillon à contrôler dans le texte source, particulièrement pour les équations.

## 1. Installer l’extracteur PDF et préparer les textes

Depuis le dossier du projet, dans `.venv312` :

```powershell
python -m pip install -r .\audit_apport\requirements_lectures.txt

python -u .\audit_apport\completer_lectures.py preparer `
  --priority-dir .\runs\priorite_bibliographique_v040 `
  --telecharger --decouvrir --workers 2 `
  --out .\runs\lectures_bibliographiques_v050
```

`--telecharger` essaie les routes publiques nommées dans
`bibliography/source_routes.json`. `--decouvrir` consulte aussi les liens de
texte intégral Crossref après échec des routes connues. Aucun compte payant,
message aux auteurs ou contournement d’accès n’est effectué.
Le script affiche l’avancement par travail et consigne les erreurs sans les
convertir en lectures accomplies.

Pour un PDF obtenu par ta bibliothèque ou l’auteur, l’ajouter à la même commande
de préparation, dans un nouveau dossier de sortie :

```powershell
python -u .\audit_apport\completer_lectures.py preparer `
  --priority-dir .\runs\priorite_bibliographique_v040 `
  --source 'KKT2024=C:\Articles\KKT2024.pdf' `
  --source 'KUNDU2017=C:\Articles\These_Kundu.pdf' `
  --telecharger --decouvrir `
  --out .\runs\lectures_avec_textes_complets
```

Une nouvelle URL publique peut être ajoutée avec `--url 'WORK_ID=https://...'`.
Sans `--telecharger`, seuls les fichiers locaux ou déjà joints au dossier sont lus.
Le CV institutionnel de Tomar n’est jamais téléchargé comme s’il s’agissait de la thèse.
Les pages éditeur contenant un aperçu, un résumé ou une barrière d’accès sont
signalées. Un PDF extrait reste un candidat dont l’identité, la version et
l’étendue doivent être contrôlées : un PDF d’une seule page peut être un aperçu.

Les sorties sont :

- `documents.json` : succès, échecs, empreintes et contrôle indicatif du titre ;
- `documents/WORK_ID/pages.json` : toutes les pages et lignes extraites ;
- `tasks.json` : les 37 comparaisons, avec hypothèses et passages candidats ;
- `lectures.md` : les textes récupérés et les lacunes ;
- `lectures_a_valider.json` : le cahier de lecture à compléter.

Les localisateurs utilisent les **pages physiques du PDF**, à compter de 1,
et non les numéros imprimés. Pour HTML/texte, les pages sont explicitement
des blocs virtuels de 80 lignes. Les scans sans texte demandent un traitement
OCR externe ; le module ne simule pas leur lecture. Les erreurs d’extraction
restent enregistrées.

## 2. Produire les brouillons d’analyse avec Ollama, si souhaité

Cette étape est facultative. Elle utilise un serveur Ollama **local**, avec un
modèle déjà installé ; aucun service distant ni téléchargement de modèle n’est
déclenché par le module. Exemple, si `qwen3.5:35b` est disponible :

```powershell
python -u .\audit_apport\completer_lectures.py analyser `
  --campaign .\runs\lectures_bibliographiques_v050 `
  --model 'qwen3.5:35b' `
  --out .\runs\analyses_bibliographiques_v050
```

Pour commencer par une comparaison :

```powershell
python -u .\audit_apport\completer_lectures.py analyser `
  --campaign .\runs\lectures_bibliographiques_v050 `
  --model 'qwen3.5:35b' --pair CARR2014_C1 --max-pairs 1 `
  --out .\runs\analyse_carr_c1
```

Le schéma impose, pour chaque paire travail/revendication, puis dans chaque lot :

1. toutes les hypothèses de la revendication concernée (14 pour C1, 6 pour C2, 7 pour C3) ;
2. les hypothèses et la conclusion du résultat antérieur, avec les quantificateurs ;
3. une analyse de spécialisation directe et ses limites ;
4. des identifiants de passages présents dans le texte réellement fourni.

Le programme refuse les passages inventés, les hypothèses omises, les sorties
tronquées et les demandes d’outils. Il peut vérifier l’existence d’un passage,
pas la justesse de l’interprétation du modèle. La sélection fournit jusqu’à dix
blocs pertinents par comparaison ; elle ne représente pas une lecture de tout
l’article. Un passage absent de la sélection n’est jamais réputé absent du texte.

Les résultats arrivent dans `WORK_ID_Cn.draft.json`, `analysis_log.json` et
`lectures_a_valider.json`. Le cahier est sauvegardé après chaque comparaison.
Un serveur indisponible produit un échec explicite ; aucune comparaison n’est
acceptée automatiquement. Si toutes les analyses échouent, le processus sort
avec le code 2.

## 3. Contrôler et déclarer les lectures

Copier le cahier hors du dossier scellé avant de le modifier :

```powershell
Copy-Item .\runs\analyses_bibliographiques_v050\lectures_a_valider.json `
  .\runs\mes_lectures.json
```

Sans Ollama, partir du cahier produit à l’étape 1. Pour chaque source effectivement
lue, renseigner `reviewer`, `review_date`, `version_id`, `identity_confirmed`
et `pages_reviewed`. Contrôler puis corriger les champs `analysis` de chaque
revendication ; les hypothèses et références doivent refléter la lecture effectuée.
Les références peuvent viser tous les blocs de l’index, au-delà de la sélection
initiale. Le format des IDs est `p0001:l0001-0016`.

Après ce contrôle, une comparaison peut être déclarée par commande :

```powershell
python -u .\audit_apport\completer_lectures.py valider `
  --campaign .\runs\lectures_bibliographiques_v050 `
  --workbook .\runs\mes_lectures.json `
  --work-id CARR2014 --claim C1 `
  --reviewer 'Abdelmalik Berrada' --date 2026-10-27 `
  --pages '27-30' --scope selected_statement --identity-confirmed `
  --out .\runs\mes_lectures_carr_validees.json
```

**Adapter la date et les pages à la lecture réellement effectuée.** La commande
ne modifie que la décision nommée. Elle contrôle aussi que les passages cités
se trouvent sur les pages déclarées lues. Pour plusieurs décisions, utiliser
successivement le dernier cahier obtenu, ou modifier explicitement leurs
`decision` en `accepted` dans le cahier.

`selected_statement` convient à une lecture ciblée. `full_work` exige toutes
les pages déclarées lues, `full_text_extent_confirmed: true`, chaque hypothèse
résolue et une analyse de dérivabilité renseignée. La commande correspondante
demande aussi `--extent-confirmed`. La couverture des pages est une déclaration
du lecteur, pas une preuve automatique de lecture ou de vérité du théorème.

Si la version effectivement lue diffère du registre, indiquer son identifiant
exact. Sa date publique reste inconnue tant qu’un événement sourcé ne la relie
pas à cette version. Le champ facultatif `public_version_event` peut documenter
ce lien après contrôle de la notice primaire, par exemple :

```json
{
  "id": "primary_record_checked_v2",
  "kind": "arxiv_submitted",
  "date_parts": [2014, 1, 31],
  "version_id": "arxiv-v2",
  "evidence_url": "https://arxiv.org/abs/1308.2326v2",
  "locator": "Submission history [v2]"
}
```

Ne pas recopier cet exemple comme date d’un autre travail. Ne pas dater une
version récente par le premier dépôt d’un autre fichier.

## 4. Intégrer les analyses validées et revérifier

```powershell
python -u .\audit_apport\completer_lectures.py exporter `
  --campaign .\runs\lectures_bibliographiques_v050 `
  --workbook .\runs\mes_lectures_carr_validees.json `
  --out .\runs\priorite_bibliographique_v050

python -u .\audit_apport\priorite_bibliographique.py `
  --verify .\runs\priorite_bibliographique_v050
```

L’export reprend les preuves mathématiques et la référence publique du projet
déjà présentes. Il joint automatiquement les sources exactes des décisions
acceptées, leurs pages/lignes et les annotations par hypothèse. Une comparaison
ciblée améliore le dossier tout en laissant ouverte l’exclusion du texte entier.
Les autres lectures manquantes restent ouvertes.

Si la lecture est postérieure à l’arrêté du registre, ajouter à `exporter`
`--as-of YYYY-MM-DD`. Pour intégrer une référence publique nouvelle du projet,
ajouter `--project-record chemin.json --project-source article_public.pdf`.
Le modèle de notice publique de la version 0.4 reste applicable.

Pour vérifier le dossier de lecture, avec une nouvelle extraction des pages :

```powershell
python -u .\audit_apport\completer_lectures.py verifier `
  --campaign .\runs\lectures_bibliographiques_v050 --reextraire
```

La relecture ordinaire contrôle les octets, empreintes, passages et décisions
sans réseau ni modèle. `--reextraire` compare en plus une nouvelle extraction
du PDF ; un changement de version de l’extracteur peut demander un contrôle.
`scientific_priority_certified` demeure `false` : la conclusion bibliographique
reste limitée aux textes et annotations effectivement documentés.

## Validation livrée

Les tests comprennent des PDF synthétiques, des aperçus, des sources manquantes,
des références inventées, des hypothèses omises, les approbations ciblées et
les exports partiels/complets. Les cas positifs utilisent des publications
fictives explicitement signalées. Le contrat Ollama est testé avec des réponses
simulées ; aucun grand modèle n’a été exécuté dans l’environnement de livraison.
Un essai réel de récupération et d’extraction du corpus est résumé dans
`validation/reading_retrieval.json`. Les PDF de tiers ne sont pas redistribués.

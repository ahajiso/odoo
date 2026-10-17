# Validation locale — 17/10/2026

Base isolée : `artdubati_test_oneoff_parity_v2_local`, **122 modules**, mêmes noms
et versions que l'inventaire serveur reçu, sauf les deux versions proposées.
Aucune mise à jour, approbation ni réception dans la base distante pendant cette
vérification. Il s'agit de données synthétiques locales, pas d'une copie métier.

## Plateforme reproduite

- Image serveur reçue : sha256:706e891aaa723edef50246e9b924fdee2a297844fe95aa3899b170598aabb473,
  Odoo Server 18.0-20260908. Sources Odoo 6ba80ed1 (07/09/2026).
- Les 119 modules hors proposition ont les mêmes sources ; pour neuf modules
  Odoo, les empreintes diffèrent uniquement par les PNG recompressés et les
  polices absentes déjà documentés dans docs/phase4/parity. Le nouvel inventaire
  et les empreintes locales sont identiques aux paires de cette preuve historique,
  pour la même image. Aucun autre écart de source admis.
- Dépendances OCA exactes par empreinte, notamment contract **18.0.2.5.3** à
  3c849d83fa5516e8a7306102dc7ca77ef06fbe6f, account_financial_report 95c63a6,
  account_reconcile_oca **et account_reconcile_model_oca** 8a24fc4,
  bi_sql_editor 89f82caa et sql_request_abstract 45619a77.
- Les trois modules modifiés correspondent aux sources serveur de `f0de375`
  avant la proposition : maintenance_shareholder_equipment, lartdubati_investor_home
  et lartdubati_manual. Le dernier change par ses documents et exports, sans
  changement de schéma. Les 122 empreintes et les trois AFTER sont enregistrés
  dans platform_expected.txt. `python docs/one_off_rental/check_parity.py` réussit.
- Limite conservée du protocole : les bibliothèques Python locales ne sont pas
  celles de l'image Docker. La vérification serveur avant/après exige son image
  exacte et ses 122 empreintes ; elle ne doit pas être remplacée par ce test local.
- Installation neuve : charger account/l10n_fr_account, puis le plan comptable
  français de la société, AVANT les 122 modules. lartdubati_facturation attend ce
  prérequis déjà présent sur le serveur ; aucune modification de ce module.

## Correction trouvée et tests

Sur contract serveur, `_insert_markers` formatait les dates récurrentes absentes
et empêchait la création du forfait. La surcharge garde la description du forfait,
uniquement pour `one_off` ; les préparateurs OCA et les autres contrats restent
inchangés. Les tests utilisent un contexte anglais explicite pour les assertions
anglaises. Le test historique de migration vérifie maintenant le stock incomplet
attendu indépendamment de la langue, après préparation des autres candidats.

**Résultat final : 0 failed, 0 error(s) of 301 tests** (212,86 s de post-tests).
Voir test-results.txt. Le compte Odoo inclut des tests/sous-tests ignorés : les
tours historiques et Hoot ne s’exécutent pas faute de websocket-client, comme
sur l’image serveur documentée. La classe TestInvestorWebsocket est aussi ignorée
avant ses méthodes. Le test de performance 10 000 lignes n’est pas sélectionné.
Les vérifications ciblées antérieures (6 migration, 1 traduction) recoupent les
301 cas ; elles ne s’ajoutent pas à ce nombre.

Commande exécutée sur cette base et ces sources, après installation :

```text
-u maintenance_shareholder_equipment,lartdubati_investor_home
--test-enable --test-tags /maintenance_shareholder_equipment,/lartdubati_investor_home
--workers=0 --http-port=8079 --max-cron-threads=0 --stop-after-init --log-level=test
```

La sélection couvre catalogue ordinaire/autonome, mouvements et droits matériel,
locations récurrentes et forfaitaires, factures/avoirs/frais 295 HT, restitution,
moniteur, multi-société et isolation des comptes investisseurs avec les autres
modules installés. Les tests du forfait couvrent aussi fuseau/durée, changement
annulant l'approbation, duplicata, devise/service/quantité/montant, facture annulée
puis remplacée, remise totale refusée, droits du bouton et traductions EN/FR/FA.
Les tentatives antérieures ont révélé les défauts ci-dessus ; seules les sorties
finales sans échec sont retenues, sans additionner les tests qui se recoupent.

Deux connexions REPEATABLE READ réelles sur une ligne TEST commise dans cette
même base à 122 modules : les deux observent l’absence de facture ; la première
crée et commit. La seconde reçoit SerializationFailure sur la ligne de contrat
révisée, puis une nouvelle transaction réutilise l’unique facture brouillon.
Script reproductible : check_concurrency.py, limité aux deux noms de bases locales.
Pas de doublure ni d’écriture SQL métier pour ce contrôle.

Inventaire des routes avec docs/phase4/routes.py, sources serveur de f0de375 puis
proposition, sur les mêmes 122 modules installés : **319 routes identiques**.
La liste résultante est dans routes.txt. Aucun contrôleur ou droit de société ajouté
par le forfait ; le rôle catalogue reste une permission explicite distincte.

## Interface, traductions et manuel

Formulaire contrôlé à nouveau dans Chromium sur cette même base à 122 modules,
français et persan, bureau et mobile : libellés traduits, début 10:00 et fin 14:00
avec navigateur Europe/Paris, durée exactement 4, sélection Forfait unique,
récurrence et fin ouverte cachées. Captures locales vérifiées, dont le persan RTL.
Ce contrôle ciblé ne remplace pas les tours historiques/Hoot ignorés ci-dessus.

Les POT des DEUX modules viennent de l'export Odoo, avec leurs PO français/persan.
Les POT sont également mis à jour : l'import Odoo fusionne les PO avec le POT
voisin et ignore autrement les nouveaux termes. Le test EN/FR/FA lit les vraies
métadonnées chargées. Les heures prévues ne modifient jamais les heures réelles
des mouvements. CPT-25 fait aligner navigateur, préférences et fuseau du contrat.

Contrôle du manuel FR/EN/FA : mêmes codes, nombres, étapes et liens. Exports des
six PDF/Word déjà régénérés ; aperçus bureau/mobile dont persan RTL vérifiés.
Python compilé et `git diff --check` propre. La correction de compatibilité
n'introduit aucun champ, libellé ou changement de procédure utilisateur.

Revue : REVIEW.md. Déploiement et retour arrière : DEPLOYMENT.md. L'ancien
inventaire phase4 par défaut ne correspond pas à cette livraison ; utiliser
explicitement le fichier platform_expected.txt de ce dossier. Le chariot distant
reste en brouillon jusqu'à cette mise à jour, puis CPT-25 s'applique à l'opération
existante sans duplication ni changement forcé d'état.

Le test historique de traduction active explicitement en_US et fr_FR avant de
comparer les deux libellés. Lorsque l'anglais est désactivé, cette version Odoo
met volontairement à jour le texte source en_US lors d'une écriture française ;
le test supposait à tort que l'anglais était toujours actif. Il ne s'agit pas
d'une correction du moteur de traduction ou du moniteur.

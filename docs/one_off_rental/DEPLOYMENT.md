# Déploiement de la location ponctuelle (18.0.5.2.3 / 18.0.3.1.0)

## 0. Décision du propriétaire du 18/10/2026 : mise à jour habituelle de artdubati_test

`artdubati` ne contient aucune donnée, n'est pas utilisée, et sera **réinitialisée puis
réinstallée entièrement** au passage en production ; son état n'importe pas avant la fin
des tests sur artdubati_test. La mise à jour se fait donc comme les précédentes (phases
1 à 4, ROADMAP 0, menu des demandes) : service partagé `odoo_web`, `deploy_modules.sh`
sur **artdubati_test uniquement**, avec l'accord explicite
`ARTDUBATI_DISPOSABLE=reset-before-production` exigé par le script à chaque exécution.

Conséquences acceptées :
- le schéma d'`artdubati` reste en retard sur le code jusqu'à sa réinitialisation ;
  l'ouvrir peut produire des erreurs ; **aucune donnée ne doit y être saisie** ;
- l'isolation des environnements (sections 1 à 3 ci-dessous, et CLAUDE.md : prérequis
  obligatoire avant toute production) reste à faire **avant** la production, puis
  `artdubati` est recréée sur le code validé.

Procédure : docs/one_off_rental/README.md, section « Mise à jour sur artdubati_test ».
Le reste de ce document décrit la séparation à préparer pour la production.

## Avant la production : isolation (plan initial de la PR nº 1)

> **Plan initial remplacé par la décision du 18/10/2026 (§0) pour la recette
> transitoire sur artdubati_test.** Les interdictions ci-dessous (ne pas utiliser
> `deploy_modules.sh`, isoler avant cette livraison) ne s'appliquent plus à cette
> livraison : `artdubati` étant jetable, son schéma peut rester en retard jusqu'à sa
> réinitialisation. **L'isolation reste obligatoire avant l'ouverture de la
> production**, puis `artdubati` est recréée sur le code validé. Les sections 1 à 3
> sont conservées comme plan de cette isolation.

Texte initial (audit de `1aa5355`, 17/10/2026, remplacé pour la recette) : ne pas
utiliser `docs/deploy_modules.sh` pour cette livraison sur le service partagé
`odoo_web`, car changer son checkout, mettre à jour seulement artdubati_test, puis
redémarrer ce service qui ouvre aussi artdubati chargerait les nouveaux champs stockés
et le moniteur SQL sur un schéma d'artdubati non mis à jour. Ce défaut est accepté
tant qu'artdubati est jetable ; il redevient bloquant pour toute base à conserver.

Le choix retenu est d’isoler artdubati_test. Mettre à jour artdubati n’est pas
autorisé par cette demande. Aucun changement d’infrastructure distant, fusion,
mise à jour de base ou exécution de réception n’a été effectué par ces corrections.

## 1. Préparer la séparation sur le code actuel, avant cette livraison

Cette étape d’exploitation doit être préparée et auditée à partir de la configuration
réelle du serveur ; aucun nom de volume, réseau, port ou secret ne doit être deviné.
Conserver l’ancien checkout partagé à son commit actuel pendant toute la séparation.

1. Relever les deux configurations Odoo/PostgreSQL, les montages résolus, filestores,
   services, réseaux, chemins d’addons, versions et empreintes. Ne pas publier les secrets.
2. Créer un checkout indépendant pour le service test, initialement **au même code
   ancien que le serveur**, avec ses dépendances OCA figées. Un git worktree distinct
   convient si aucun de ses chemins d’addons mutables n’est partagé avec le service restant.
   Un lien symbolique vers l’ancien checkout ne constitue pas une séparation.
3. Préparer un service dédié, par exemple odoo_test_web, sa configuration et son
   volume de données. Limiter db_name à artdubati_test, dbfilter à
   `^artdubati_test$`, list_db à False et les connexions PostgreSQL à cette seule
   base avec un rôle dédié. Désactiver les sorties de courrier et intégrations de test.
4. Conserver artdubati sur l’ancien service/checkout, restreint à `^artdubati$`.
   Le nouveau service test ne doit pouvoir ni sélectionner ni ouvrir artdubati,
   y compris via RPC et sessions antérieures. Les cron suivent les mêmes limites.
5. Après sauvegardes **base + filestore** des deux environnements et essais de
   restauration, arrêter les accès et cron qui peuvent modifier artdubati_test.
   Transférer son filestore au volume dédié sous le nom exact de sa base. Si la base
   est transférée vers un autre PostgreSQL, restaurer le dump cohérent correspondant.
   Ne jamais laisser deux services modifier la même base pendant cette bascule.
6. Démarrer les services séparés **sur l’ancien code**, puis vérifier routage, sessions,
   pièces jointes, droits, cron et absence d’accès croisé. Vérifier les montages réels
   avec Docker inspect : configuration, code et filestore du test sont indépendants.
   Consigner l’image, les empreintes des deux checkouts et les bases effectivement
   ouvertes par chaque service. En cas d’échec, revenir à l’ancienne configuration
   avec la sauvegarde cohérente ; ne pas charger le nouveau code pour dépanner.

L’isolation doit être constatée, pas déclarée par une variable d’environnement.
Le rôle PostgreSQL dédié et les restrictions d’accès apportent une limite réelle
en plus de dbfilter. La procédure détaillée de bascule reste à faire auditer avec
l’inventaire réel. Ces instructions sont un plan de séparation, pas sa preuve
d’exécution ni un script de déploiement prêt à lancer.

## 2. Adapter puis auditer les outils pour le service isolé

Les scripts historiques backup_db.sh, restore_db.sh, deploy_modules.sh et
phase4/check_modules.sh ciblent `odoo_web`, ses montages et l’ancien checkout.
**Ils ne sont pas réutilisables tels quels en remplaçant seulement ADDONS ou DB.**
Les outils adaptés devront désigner explicitement le service test, son image,
sa configuration, son rôle PostgreSQL, sa base, son checkout et son filestore.
Leur garde préalable doit prouver les limites de la section 1 et refuser l’ancien
service/checkout partagé, avant tout changement. Aucun redémarrage du service
artdubati ne doit faire partie de la mise à jour test.

Consigner une sauvegarde avec restauration d’essai, les sommes de contrôle et le
commit de retour arrière **du test isolé**. Un ancien manifeste du service partagé
n’est pas une sauvegarde de l’environnement isolé.

## 3. Mettre à jour uniquement le test isolé, après nouvel audit favorable

1. Vérifier la plateforme de test contre platform_expected.txt (122 modules avant,
   puis les trois empreintes AFTER). Les bibliothèques Python locales restent une
   limite du test de développement. Ne pas modifier l’inventaire pour masquer un écart.
2. Après revue et fusion du commit exact, vérifier que l’arbre à déployer est celui
   audité ; sauvegarder et tester la restauration du test isolé.
3. Arrêter **le service test uniquement**, changer **son checkout uniquement**, puis
   exécuter avec sa configuration la mise à jour conjointe de
   maintenance_shareholder_equipment **18.0.5.2.3** et lartdubati_investor_home
   **18.0.3.1.0** sur **artdubati_test uniquement**.
4. Avant démarrage, exécuter les tests de VALIDATION.md sur ce schéma mis à jour,
   puis les contrôles de plateforme. En cas d’échec, garder le test arrêté et
   restaurer ensemble sa base, son filestore et son ancien code.
5. Démarrer le test et vérifier le moniteur, les formulaires/traductions et les
   pièces jointes. Vérifier également que le service artdubati conserve son ancien
   code, son ancien schéma et ses montages, sans redémarrage lié à cette livraison.

Aucun nouveau code ne doit être chargé sur une base dont les modules n’ont pas été
mis à jour. Les anciennes approbations d’opérations peuvent nécessiter une nouvelle
approbation normale ; aucun changement forcé d’état n’est autorisé.

## 4. Tester le chariot dans l’environnement isolé

Reprendre EQOP/2026/1540 existante, sans duplication, selon CPT-25. Forfait 120 HT,
quatre heures Europe/Paris ; frais distincts 80 + 80 + 15 HT, soit 295 HT. Caution
1000 séparée ; remplacement 25000 HT sans dette automatique. Après exécution,
l’opération affiche dans Factures toutes les factures successives et leurs états.
Pour remplacer une facture, l’annuler puis utiliser le bouton de la ligne de
contrat ; ne retirer ni son lien ni sa ligne, et ne supprimer aucune pièce de
cet historique. Le profil catalogue autonome ne donne pas d’autoapprobation matériel.

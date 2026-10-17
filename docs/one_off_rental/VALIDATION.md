# Validation locale — 17/10/2026

Base isolée : `artdubati_test_oneoff_local`, Odoo 18.0 local, 86 modules installés,
dépendances OCA des branches 18.0. **Pas de parité établie avec le serveur à 122
modules** ; ces preuves ne remplacent pas les contrôles préalables au déploiement.
Aucune mise à jour, approbation ou exécution dans la base distante pendant ce travail.

## Tests métier

- Régression élargie : **206 tests, 0 échec, 0 erreur**. Ensemble du module
  maintenance_shareholder_equipment, sauf TestPhase2fTours, plus TestMonitorRent.
  Comprend les demandes catalogue ordinaires/autonomes et la vue des groupes.
- Après compléments de couverture : **18 tests ciblés, 0 échec, 0 erreur**.
  TestOneOffRental et TestMonitorRent : réception, facture, contrôle montant et
  service, frais distincts totalisant 295 HT, non-récurrence, avoir, annulation,
  facture créée par un vrai administrateur comptable, refus des autres profils,
  restitution, fuseau et durée, changement d'engagement, traduction en trois langues,
  remise totale refusée et moniteur excluant les frais du cumul des loyers.
  Ces 18 tests recoupent la régression précédente, ils ne s'ajoutent pas à son compte.
- Commandes de sélection :
  `--test-tags /maintenance_shareholder_equipment,-/maintenance_shareholder_equipment:TestPhase2fTours,/lartdubati_investor_home:TestMonitorRent`
  puis `--test-tags /maintenance_shareholder_equipment:TestOneOffRental,/lartdubati_investor_home:TestMonitorRent`.
  Lancer avec `-u maintenance_shareholder_equipment,lartdubati_investor_home`,
  `--test-enable --workers=0 --http-port=8079 --stop-after-init`, langues FR/FA
  chargées et sources correspondantes. Sur le serveur, suivre le protocole de
  plateforme/sauvegarde avant ces commandes.
- Vérification supplémentaire avec deux vraies connexions REPEATABLE READ sur une
  ligne TEST commise : les deux transactions observent l'absence de facture ; la
  première crée et valide sa transaction. La seconde reçoit SerializationFailure
  sur le parent révisé, puis une nouvelle transaction réutilise l'unique facture.
  Aucun doublon. Cette vérification utilise la méthode réelle et l'ORM, sans
  doublure ni écriture SQL métier. Une simple attente de verrou n'aurait pas rafraîchi
  l'instantané : le compteur technique ORM rend la nouvelle tentative obligatoire.

## Interface et traductions

Les fichiers POT des DEUX modules viennent de l'export de cette installation Odoo.
Les nouveaux termes PO français/persan utilisent ces références exactes. Les POT
sont également mis à jour : Odoo fusionne les PO avec le POT voisin à l'import et
ignore autrement les nouveaux termes absents de ce dernier. Le test des trois
langues vérifie réellement les métadonnées chargées, pas seulement les fichiers.

Écran d'opération vérifié dans Chromium, français et persan, bureau/mobile :
libellés traduits, heures 10:00–14:00 dans le navigateur Europe/Paris, sélection
Forfait unique, disparition de
la récurrence et de la fin ouverte, durée visible. Le fuseau explicite du contrat
sert aux dates civiles ; les widgets horaires suivent le fuseau du navigateur.
CPT-25 fait aligner les préférences, le navigateur et le fuseau sur Europe/Paris pour l'exercice.
Les heures prévues ne changent pas l'horodatage réel des mouvements.

Les tours historiques et la suite Hoot complète n'ont pas été exécutés. Les aperçus
du manuel et des exports ont été vérifiés en bureau et mobile, dont le persan RTL.

## Contrôles de livraison

- Python compilé ; XML de sécurité et des vues analysé ; `git diff --check` propre.
- Inventaire des routes par docs/phase4/routes.py, code de base 0bdd7f5 puis
  proposition sur les mêmes modules installés : **302 routes identiques**.
  Aucune nouvelle route ni modification de contrôleur, ACL ou règle de société.
- Manuel : refresh.py/check.py, mêmes codes/nombres/étapes/liens FR/EN/FA.
  CPT-25 réécrite, ADM-05 exige les deux mises à jour ensemble ; exports PDF/Word
  et archive des six manuels régénérés à partir des HTML.
- Le serveur courant reste sur l'ancien schéma. Le chariot TEST y reste en
  brouillon jusqu'au déploiement relu, puis doit être préparé/soumis normalement
  selon CPT-25, sans changement forcé de statut ni création d'un second exemplaire.

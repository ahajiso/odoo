# Catalogue autonome — proposition du 17/10/2026

Demande du propriétaire : un profil particulier pour les utilisateurs de test et
les superadmins, permettant de créer et valider sa propre référence. Décision
consignée dans DEFINITIONS.md ; module proposé **18.0.5.1.0**, non déployé.

## Comportement

Le groupe `maintenance_shareholder_equipment.group_product_catalogue_autonomous`
implique uniquement le gestionnaire du catalogue existant. Aucun utilisateur n'est
ajouté par défaut. Dans la fiche utilisateur, Catalogue produits propose le niveau
« Gestionnaire autonome du catalogue (Test / Superadmin) » (ADM-13).

Son titulaire peut créer une demande, la soumettre, l'approuver lui-même, puis
créer le produit. Tous les autres contrôles restent exécutés et les acteurs sont
tracés. Pas de création directe de product.template / product.product, pas de
contournement des doublons, catégories, documents, unités ou sociétés. Un contexte
API, un nom d'utilisateur ou un nom de base ne donnent pas cette permission.

Le gestionnaire ordinaire ne peut toujours pas approuver sa propre demande. Le
profil spécial ne donne pas les rôles d'opérateur matériel, d'approbateur matériel,
d'administrateur comptable ou d'administrateur général. Aucune ACL et aucune règle
multi-société ne sont élargies ; seule la condition d'auto-approbation est modifiée.
Il n'y a pas de nouveau contrôleur HTTP ni de nouvelle dépendance.

## Validation effectuée et limites

- Python compilé et XML de groupe analysé ; diff sans erreur d'espacement.
- Neuf vérifications isolées passées : méthode action_approve extraite du vrai
  code, exécutée avec de vrais utilisateurs/groupes Odoo sur une base locale neuve.
  Les assistants de stockage, de catalogue et de document sont des doublures :
  ce n'est pas un test d'intégration complet du module. Vérifié : refus ordinaire,
  autorisation du rôle spécial et traces, validation normale par autrui, contexte
  falsifié sans effet, administrateur sans rôle refusé, contrôle de catégorie,
  doublon bloquant, retrait du rôle et implication du seul gestionnaire.
- Entrées de traduction des deux nouveaux termes exportées par Odoo depuis les
  mêmes enregistrements XML dans cette base isolée, puis traduites en FR et FA.
  Les références model:res.groups,name/comment sont celles du groupe réel.
- Tests d'intégration ajoutés à test_product_catalogue.py : demande complète avec
  auto-approbation et exécution tracées, contrôles toujours actifs, absence de droits
  supplémentaires, auto-attribution refusée, contexte sans effet, révocation.
  Les tests existants de création directe incluent aussi le nouveau profil.
  test_user_groups_view.py vérifie le niveau visible et ses implications.
- La suite d'intégration complète n'a PAS été exécutée : les dépendances OCA et
  la plateforme de la base serveur ne sont pas disponibles dans l'environnement
  local. Les neuf vérifications isolées ne sont pas présentées comme une preuve de
  parité avec les 122 modules de artdubati_test.
- Manuel FR/EN/FA rafraîchi et check.py sans différence ; aperçus bureau/mobile/RTL.

## Mise en service à faire après audit

Suivre ADM-05 et docs/phase4/README.md : fenêtre de déploiement, sauvegarde vérifiée,
plateforme conforme et empreinte du nouveau code, inventaire des routes avant/après,
arrêt/code/mise à jour de maintenance_shareholder_equipment/reprise sur artdubati_test.
Ne pas réutiliser comme preuve l'ancienne empreinte AFTER de la version 18.0.5.0.1.
Exécuter les tests d'intégration du module et les contrôles de groupes, puis vérifier
les traductions dans la fiche utilisateur. Rien n'est automatiquement attribué :
un administrateur sélectionne explicitement le niveau autonome pour le compte voulu.
La production n'est pas concernée par les opérations de test de cette tâche.

Pour les cinq cas TEST préparés le même jour, les quatre demandes de produit ont
été approuvées et exécutées séparément sur la version actuellement en ligne,
pendant cette tâche. Leurs produits sont réutilisés dans les réceptions existantes.
Le nouveau profil n’a pas été nécessaire à cette validation par autrui et n’est
pas actif sur le serveur ; il permettra l’auto-approbation future après déploiement
et attribution explicite. La validation des opérations matériel reste distincte.
Le chariot quatre heures reste bloqué : cette proposition ne développe pas de
location horaire ou ponctuelle.

# Location fournisseur ponctuelle — proposition du 17/10/2026

Le propriétaire demande de rendre testable la location de quatre heures du chariot
CHA25E. Version proposée : maintenance_shareholder_equipment **18.0.5.2.0** et
lartdubati_investor_home **18.0.3.1.0**. Aucun déploiement serveur dans cette tâche.

## Parcours et choix

- Réception Loué avec `rental_billing_mode=one_off` : début/fin prévus Datetime UTC,
  fuseau explicite pour les dates civiles du contrat, durée calculée en heures.
  Le forfait positif est dans `rent_amount`, quantité physique 1. Les dates sont
  ordonnées, la fin ouverte refusée. Réservé aux locations fournisseur entrantes.
- Approbation et exécution restent distinctes. Mode, horaires, fuseau et montant
  font partie de l'empreinte approuvée. L'exécution crée l'équipement, sa possession,
  une ligne de contrat OCA et une seule facture fournisseur brouillon par équipement.
  Les mouvements utilisent toujours l'heure réelle d'exécution ; les heures prévues
  n'antidatent pas le stock. La restitution garde l'horodatage de sa propre exécution.
- `contract.line.equipment_billing_mode=one_off` garde équipement/nature/service,
  prix, devise et heures. Pas de prochaine facture, pas de facturation périodique,
  pas de renouvellement automatique, pas de revenu mensuel récurrent. Les champs
  techniques de récurrence OCA restent présents pour compatibilité mais sont cachés
  dans le formulaire de cette ligne et ne pilotent jamais son forfait.
- Le contrat conserve son flux récurrent normal pour les autres lignes. Le forfait
  est exclu de `_can_be_invoiced` et du calcul de prochaine échéance du contrat,
  même si on invoque directement le moteur de facturation OCA.
- Création de facture par les préparateurs privés OCA et l'ORM standard. L'opération
  approuvée utilise son élévation existante ; aucun droit supplémentaire n'est donné.
  Le bouton explicite de ligne « Open or Create One-off Bill » est réservé aux
  administrateurs comptables avec droits d'écriture sur le contrat. Il réutilise la
  facture non annulée ; une pièce annulée/supprimée peut être remplacée. Un avoir ne
  déclenche pas de refacturation. La référence fournisseur, le PDF et les taxes sont
  contrôlés par le comptable avant validation ; aucune comptabilisation automatique.
- Création et comptabilisation verrouillent les lignes de contrat dans l'ordre des
  identifiants (SELECT FOR UPDATE, pas d'écriture SQL). Une révision technique écrite
  par ORM sur la ligne force une nouvelle tentative de transaction avec un instantané
  frais en isolation REPEATABLE READ ; un verrou seul ne suffirait pas. La comptabilisation refuse
  plusieurs lignes de facture non annulées pour le forfait, une mauvaise devise,
  quantité, produit/service ou un montant HT différent de l'engagement. Le contrôle
  fournisseur/société/compte de location existant reste actif. Les avoirs ordinaires
  restent possibles, leur montant diminue le cumul du moniteur.
- Les termes du forfait ne peuvent être modifiés tant qu'une facture non annulée
  existe. Arrêter la possession ne change pas le prix ni ne déclenche un remboursement.
- Moniteur : montant brut de forfait avec périodicité `one_off`, libellé traduit,
  aucun équivalent mensuel et aucune alerte « périodicité non prise en charge » pour
  ce mode. Le cumul des factures comptabilisées et avoirs reste inchangé. La présence
  de la ligne active utilise les dates civiles comme les autres contrats ; les heures
  détaillées et la durée se consultent sur la ligne, sans calcul de prorata horaire.

Livraison 80 + reprise 80 + assurance 15 HT restent des lignes de services distinctes
à saisir sur la facture de test de 120 HT, total 295 HT. Aucun automatisme de frais,
pénalité, dépassement horaire ou caution. Caution 1000 EUR hors charges et remplacement
25000 EUR HT sans dette automatique. Les comptes/taxes des frais restent à valider
par le comptable ; ne pas contourner le lien obligatoire du compte de location.
Le retour physique exige toujours une opération Restitution ; aucune date ne valide
un mouvement de stock automatiquement. Les chevauchements contractuels restent
contrôlés par dates civiles : pas de nouvelle règle de rotations multiples le même jour.

## Validation et limites

Installation réelle locale du module et du moniteur avec dépendances OCA 18.0 dans
`artdubati_test_oneoff_local`, base neuve isolée. Il ne s'agit pas de la base distante
artdubati_test. Les dépendances OCA proviennent de leurs branches 18.0 actuelles ;
les 86 modules de cette installation ne reproduisent PAS l'empreinte des 122 modules
serveur. Les résultats locaux sont des tests d'intégration utiles, pas une preuve de
parité de déploiement. Les anciennes neuf vérifications isolées du profil catalogue
sont désormais complétées par les vrais tests de demande dans cette installation.
Les comptes et données de test de ces tests sont annulés par le framework.

Couverture ajoutée : réception et propriété, durée, contrat, facture brouillon unique,
absence de récurrence sur plusieurs échéances, facture comptabilisée et restitution,
contrôles d'horaires/fuseau, empreinte d'approbation, facture manuelle en double,
montant/service incorrect, annulation/remplacement, avoir sans refacturation,
restrictions du bouton, absence de renouvellement, moniteur/cumul/remboursements.
Les résultats finaux sont consignés dans le compte rendu de validation ci-dessous.

## Revue et mise en service

1. Auditer la proposition et vérifier les dépendances sur le code exact du serveur
   selon docs/phase4/README.md et docs/phase4/platform.py. Exécuter les tests ajoutés
   et les régressions sur cette plateforme. Aucun nouveau contrôleur HTTP, groupe,
   ACL ou règle de société ; la nouvelle action publique est un bouton ORM protégé.
2. Sauvegarde/restauration vérifiées et fenêtre de déploiement contrôlée selon ADM-05.
   Les deux bases partagent le code ; l'opérateur du serveur doit tenir compte de cette
   architecture. Aucune utilisation de production n'est autorisée par cette demande.
3. Mettre à jour ENSEMBLE maintenance_shareholder_equipment et
   lartdubati_investor_home : le SQL du moniteur lit le nouveau champ stocké de
   contract.line. Arrêter l'application avant le changement de code et la mise à jour.
   Ne pas démarrer le nouveau code sur un schéma non mis à jour.
4. Refaire les tests, l'inventaire des routes et les contrôles après mise à jour.
   L'empreinte des approbations inclut maintenant de nouveaux champs : les opérations
   approuvées auparavant peuvent repasser en brouillon et doivent être réapprouvées,
   jamais forcées à l'exécution. Les locations existantes deviennent `recurring` par
   défaut ; les brouillons restent inchangés tant qu'on ne choisit pas explicitement
   le forfait unique.
5. Dans artdubati_test uniquement, ouvrir la réception TEST existante du CHA25E,
   sélectionner Forfait unique, entrer les heures, le fuseau et le loyer 120 HT,
   puis suivre CPT-25. Ne pas recréer le produit ni dupliquer l'opération existante.
   Soumettre, faire approuver, exécuter à réception physique, contrôler la facture
   brouillon, saisir les frais séparés, comptabiliser/payer puis restituer normalement.
   Aucune demande ni réception distante n'a été exécutée par ce développement.

## Résultats consignés

Voir [VALIDATION.md](VALIDATION.md) : régression locale de 206 tests et dernier lot
ciblé de 18 tests sans échec ni erreur, vérification avec deux connexions réelles,
302 routes inchangées, traductions et manuel contrôlés. La parité avec le serveur
reste une condition distincte de mise en service.

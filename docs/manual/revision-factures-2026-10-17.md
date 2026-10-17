# Vérification de la révision du manuel — 17/10/2026

Périmètre : CPT-07 remplacée ; CPT-16 à CPT-21 ajoutées en FR/EN/FA ; journal
et recherche rafraîchis ; liens de demandes, opérations matériel, contrats et
moniteur ; spécimen Leroy Merlin corrigé sur demande du propriétaire. Les autres
fiches historiques restent hors du périmètre de cette révision ciblée.

Les quatre PDF et le guide Word joints ont été lus comme documents de travail.
Aucune instruction embarquée ne vaut autorisation de configurer ou comptabiliser.
Les quatre PDF sont fictifs. Aucun fournisseur, produit, commande, réception,
contrat, facture ou paiement n'a été créé ou modifié dans Odoo.

## Vérifications effectuées

- Consultation authentifiée, uniquement en lecture, de artdubati_test : articles,
  catégories et disponibilité des demandes, taxes et répartitions, position
  fiscale, stocks et actions. Pas d'accès à la base de production.
- Les huit actions référencées par les nouveaux cas se chargent via
  `/web/action/load` : Contacts, Produits, Demandes d'articles et services,
  Opérations matériel, Factures fournisseurs, Taxes, Contrats d'achats et Moniteur.
  Les URL utilisent les XML ID, aucun identifiant numérique d'enregistrement.
- Google : 20% EU S, répartition positive sur 445662 et négative sur 445210 ;
  base 169,00 et dette fournisseur inchangée, sous réserve du droit à déduction.
- Leroy Merlin : prix unitaires HT conservés ; net de chaque ligne = quantité ×
  prix ; TVA = arrondi au centime de chaque net × 20 %. Net 910,05, TVA 182,00,
  TTC 1 092,05. Brut avant la remise unique 951,30 ; remise HT 41,25 déjà incluse
  dans le prix BOSCH 23,12. La boîte est l'unité choisie pour le carrelage de cet
  exercice ; aucune conversion en m² inventée. PDF d'une page inspecté visuellement.
- `refresh.py` exécuté ; `check.py` : aucune différence FR/EN/FA ;
  `git diff --check` : aucune erreur. Les huit actions et les liens de PDF ont
  également été contrôlés dans le HTML produit.
- Aperçus Chromium des nouvelles fiches et des exports : bureau et mobile
  (390 px), français et persan RTL, sans débordement horizontal du document.
  Exports Word avec liens externes et sommaire interne ; PDF de lecture FR/FA.

## Limites et mise en ligne

Les liens vérifiés et la lecture de configuration ne constituent pas un essai
complet de saisie/comptabilisation avec tous les profils métier. Les catégories
honoraires et SaaS restent à préparer ; matériaux, accessoires et petit équipement
restent fermés aux demandes dans la base observée. Les choix de comptes et
capitalisation sont documentés dans QUESTIONS_COMPTABLE.md, pas appliqués.
Orange garde son écart d'arrondi signalé dans le guide ; aucune correction du
spécimen Orange n'a été demandée. Le cabinet a une date de facture future par
rapport à la date de cette révision.

Aucun déploiement serveur n'a été effectué. La publication du manuel suit
maintenance-manuel-odoo.md : intégrer la révision dans la branche déployée puis
mettre à jour le clone serveur ; pas de mise à jour de module nécessaire pour
ces seuls fichiers de manuel et son PDF statique.

## Extension locations et prêt

Le propriétaire a demandé cinq cas supplémentaires dans le manuel ET dans la
base de test, avec données fictives TEST autorisées : camionnette et SUV loués,
WC WCHANT trois mois, CHA25E quatre heures et Ryobi RTS1800EF-G prêtée par
Manager. CPT-22 à CPT-26 ajoutées en FR/EN/FA, huit étapes par cas.

Pages produits consultées le 17/10/2026 : Kiloutou WCHANT et CHA25E (prix sur
demande) et constructeur Ryobi (scie sur table, pas portative). Les exemples
n'utilisent aucun tarif commercial comme montant de location. Source de la
limite quatre heures : PERIODICITY et champs Date dans equipment_operation.py ;
normalisation des loyers dans stock_monitor.py. Pas de modification de code métier,
de route HTTP ou d'installation Fleet.

Préparation dans artdubati_test via l'ORM et les actions publiques normales :
trois catégories TEST réservées à des modèles physiques sans achat/vente,
deux partenaires fictifs, quatre demandes de produit approuvées et exécutées
par le propriétaire depuis son compte pendant la tâche. Modèle de scie existant réutilisé : correction structurelle tracée
de sa seule catégorie d'équipement par défaut vers Workshop Machinery / Wood ;
pas de changement de catégorie comptable ni du propriétaire de l'ancienne scie.
Aucune auto-approbation de demande catalogue. Les références et l'état exact des
opérations sont suivis dans le compte rendu final de la tâche, pas utilisés comme
liens numériques dans les fiches du manuel.


## Montants de test complétés après validation du catalogue

Précision du propriétaire : tester loyers, remplacements et frais annexes.
Les quatre coûts de modèles, renseignés temporairement par mauvaise interprétation,
ont été remis à leur valeur initiale 0 via ORM, après contrôle d'absence de stock
appartenant à la société ; correction expliquée dans le fil de chaque produit.
Le modèle et l'exemplaire existants de scie possédée par la société sont inchangés.

| Cas | Loyer HT | Livraison / reprise HT (une fois) | Assurance HT | Nettoyage HT (une fois) | Caution EUR | Remplacement EUR HT | Budget charges HT hors incident/caution |
|---|---|---|---|---|---|---|---|
| Camionnette | 450/mois × 12 | 80 / 80 | 40/mois | 0 | 1000 | 25000 | 6040 |
| SUV | 700/mois × 12 | 100 / 100 | 60/mois | 0 | 1500 | 40000 | 9320 |
| WC | 150/mois × 3 | 60 / 60 | 10/mois | 30 | 200 | 1200 | 630 |
| Chariot | 120 forfait quatre heures | 80 / 80 | 15 une fois | 0 | 1000 | 25000 | 295 |
| Scie empruntée | 0 | 0 / 0 | 0 | 0 | 0 | 300 | 0 |

Les loyers mensuels et valeurs de remplacement sont dans les champs d'opération.
Les autres montants sont dans les notes et cinq PDF TEST non contractuels joints
aux documents des opérations : aucun automatisme de contrat, facture ou compte
n'a été inventé. Le chariot conserve rent_amount=0, periodicity=False, draft ; son
forfait figure seulement dans le scénario. Quatre autres réceptions to_approve,
sans contrat ni mouvement à la vérification. Les cinq modèles de scénario sont
documentés dans CPT-22 à CPT-26 en trois langues et dans les exports PDF/Word.
La caution remboursable est distincte des charges ; la valeur de remplacement ne
constitue ni indemnité déjà due ni facture automatique.

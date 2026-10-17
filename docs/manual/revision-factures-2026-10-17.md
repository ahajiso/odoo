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

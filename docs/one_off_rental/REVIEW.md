# Réponse à l’audit de 62ef439 — gel de l’engagement

**Constat accepté ; nouveau candidat proposé, fusion non autorisée.** Les corrections
de 62ef439 ont été validées par l’audit, mais celui-ci a révélé que l’annulation
rouvrait les termes approuvés. Cette possibilité est supprimée dans la proposition
**18.0.5.2.2**, sans nouveau champ ni circuit de modification après exécution.

`contract.line.write` conserve le verrou de concurrence et consulte maintenant
`_equipment_one_off_history`, qui inclut les factures annulées. Dès la première
facture, produit, unité, quantité, prix calculé et source manuelle du prix, remise,
mode de tarification et horaires prévus restent gelés. L’identité technique reste
protégée par la garde précédente. Aucun contexte RPC ni sudo ne dispense de ce gel.
`_equipment_one_off_bills` continue à exclure les pièces annulées pour permettre
leur remplacement : recherche d’une facture réutilisable et gel de l’engagement
utilisent volontairement deux recherches distinctes.

Le nouveau test reproduit l’approbation de 120 EUR HT pour le 17/10/2026 de
10 h à 14 h Europe/Paris, l’exécution, la création puis l’annulation de la facture.
Il tente ensuite de passer à 1 200 EUR HT et à 8 h–18 h, séparément et ensemble,
avec un administrateur comptable et avec sudo. Produit, unité, quantité, remise
et source du prix sont aussi couverts. Chaque tentative est refusée. La facture
de remplacement reprend le produit, l’unité, la quantité, la remise et les
120 EUR HT d’origine ; les quatre heures restent inchangées sur le contrat.
Le même test corrige la référence fournisseur, applique une taxe de 20 % et ajoute
une pièce jointe au brouillon, puis comptabilise 120 EUR HT + 24 EUR de taxe.
Toutes les pièces restent rattachées à l’opération exécutée.

L’ancien test de remise totale modifiait aussi le contrat après annulation ; il
attend désormais le refus de cette modification. La remise à 100 % sur une copie
de facture reste refusée à la comptabilisation par le contrôle de montant existant.

`docs/DEFINITIONS.md` dit désormais « cancelled draft ». CPT-25 FR/EN/FA,
le journal et les six exports PDF/Word sont corrigés : annuler ne donne jamais
l’autorisation de modifier l’engagement. Le message de refus est exporté depuis
Odoo et traduit en français et persan.

Résultats finaux et exclusions : VALIDATION.md et test-results.txt. Les contrôles
Chromium de l’interface métier et de concurrence de 62ef439 restent des preuves
historiques ; la régression ORM complète est relancée pour ce candidat. Aucun
contrôleur, vue métier, champ stocké ou droit d’accès n’est ajouté par ce correctif.

**Fusion et déploiement restent deux décisions distinctes.** La PR reste en
brouillon. Aucune opération distante n’est effectuée ; isolation réelle de la base
de test et audit des outils adaptés restent obligatoires avant déploiement.

---

# Réponse à l’audit de 1aa5355 — 17/10/2026

**Décision reçue : fusion refusée.** L’audit transmis par le propriétaire identifie
deux blocages métier/déploiement et un défaut de traçabilité. La première revue
avait manqué ces points. La PR reste en brouillon et doit être réauditée sur le
nouveau commit ; aucune fusion ou opération serveur n’a été effectuée.

## 1. Détachement de la facture : constat accepté, corrigé

Le contrôle de comptabilisation seul ne suffisait pas : retirer contract_line_id
et quitter le compte 613500 faisait disparaître la preuve de facturation.

- account.move.line.write refuse de changer le lien de contrat, le mouvement ou
  le type d’affichage d’une ligne de facture fournisseur au forfait. Les écritures
  identiques restent possibles pour les mécanismes Odoo. Le lien est aussi en
  lecture seule dans le formulaire ; la protection réelle est côté serveur.
- unlink refuse sa suppression, y compris via les commandes relationnelles du
  parent. account.move.unlink refuse la suppression de la pièce entière et write
  interdit sa conversion en autre type de mouvement.
- Les protections restent actives après annulation. contract.line protège son
  identité et sa suppression tant qu’une facture fournisseur historique, même
  annulée, la référence. On ne peut pas retirer le mode one_off pour désactiver les
  gardes. La suppression du contrat parent est aussi refusée pour empêcher la
  cascade SQL de contourner unlink de sa ligne, y compris pour une ligne archivée.
  Aucune exception par contexte RPC ou sudo n’est ajoutée à ces gardes.
- Les données comptables du brouillon restent contrôlées à la comptabilisation
  (montant HT, devise, quantité, service, fournisseur et société). Le remplacement
  utilise l’annulation Odoo puis la création/réutilisation normale du forfait.

Le test reproduit exactement le détachement + changement vers un autre compte avec
un utilisateur administrateur comptable réel, puis vérifie le lien, le compte et
l’unicité avant comptabilisation. Un second test couvre suppression de ligne et
facture, effacement via le parent, déplacement de ligne, changement de type de
ligne/pièce et retrait du mode/de la ligne de contrat, avant/après annulation.

## 2. Déploiement partagé : constat accepté, procédure retirée

Mettre à jour seulement artdubati_test puis redémarrer le code partagé aurait
chargé de nouveaux champs sur l’ancien schéma d’artdubati. « Production non
utilisée » ne résout pas ce défaut. Aucune mise à jour de production n’est autorisée.

DEPLOYMENT.md exige désormais la séparation préalable, **sur l’ancien code**, du
service test, de son checkout, de sa configuration, de ses accès PostgreSQL et de
son filestore. Les services doivent être limités à leur base respective. Les
sauvegardes et outils de mise à jour/retour arrière doivent cibler explicitement
cet environnement isolé ; les anciens scripts ne sont pas réutilisables tels quels.

Le script historique deploy_modules.sh refuse les livraisons contenant le forfait
avant tout arrêt/changement de code, même en appel direct. La séparation distante
n’a pas été réalisée ni simulée comme acquise. L’adaptation opérationnelle des
outils et l’audit de l’inventaire réel restent des préalables au déploiement.
Les fiches ADM-05/CPT-25 FR/EN/FA reflètent cette interdiction.

## 3. Historique des remplacements : constat accepté, corrigé

La ligne de contrat conserve equipment_origin_operation_id, renseigné par le
workflow et non modifiable par le comptable. La création ou réutilisation d’une
facture ajoute son lien à cette seule opération via une élévation privée limitée.
Le comptable ne reçoit aucun droit général d’écriture sur les opérations.
Le lien inverse equipment_operation_ids de la facture ne peut pas non plus être
retiré par write. Les créations et écritures ordinaires de factures/lignes rattachent
aussi les forfaits à leur origine, y compris les brouillons saisis manuellement et
les copies. Le fournisseur et la société sont contrôlés avant ce rattachement ;
les montants restent vérifiés à la comptabilisation. Un lien déjà présent n’est
pas réécrit.
La liste est réservée aux droits de consultation existants. L’ancien champ de
factures du groupe Achat est également limité aux profils lecteurs : il était
chargé même invisible et empêchait un opérateur sans droits comptables d’ouvrir
une réception comportant une facture. Aucune ACL n’est élargie.

L’opération garde les factures annulées et toutes leurs remplaçantes. Son onglet
Factures les affiche en lecture seule avec référence, état et montant HT. Le test
qui attendait l’absence du remplacement est corrigé. Un test couvre deux
remplacements successifs et la consultation des états annulé/brouillon/comptabilisé.

## 4. Espaces du diff : constat accepté, preuve rectifiée

Le contrôle annoncé concernait le diff de travail ; il ne prouvait pas la propreté
de la comparaison complète avec main. Les espaces terminaux du résumé de tests
sont retirés ; les PDF sont déclarés binaires dans .gitattributes. Les prochaines
preuves indiquent la commande sur la comparaison complète f0de375..HEAD et son
code de retour, pas seulement git diff --check sans référence.

## Résultats et statut

Voir VALIDATION.md et test-results.txt pour les résultats finaux et leurs limites.
Le rôle catalogue autonome, la non-récurrence et la reprise de sérialisation ne sont
pas élargis. Aucun nouvel accès investisseur, aucune route HTTP ni droit de société.
Le nouveau candidat est **18.0.5.2.1** pour maintenance_shareholder_equipment ;
lartdubati_investor_home reste **18.0.3.1.0**. Les anciens résultats de 1aa5355
restent historiques ; ils ne valent pas validation des corrections ultérieures.

# Recette fonctionnelle sur artdubati_test — 18 octobre 2026

**Parcours ciblés validés sur le serveur déployé**, avec scénarios et montants fictifs TEST :
réceptions louées/empruntée, facturation, engagement gelé après annulation et
restitutions physiques. La lecture du cumul comptable du moniteur reste à vérifier
avec un profil habilité : le compte Test ne possède pas le groupe requis.
Ce résultat ne vaut ni ouverture de production ni validation fiscale réelle.

## Environnement et autorisations

- Session explicitement authentifiée sur **artdubati_test**, jamais sur artdubati.
- Versions constatées par ORM : maintenance_shareholder_equipment **18.0.5.2.3**,
  lartdubati_investor_home **18.0.3.1.0**, Odoo **18.0-20260908**.
- Le propriétaire confirme la mise à jour de la seule base test. La décision de
  main 9c432c5 du 18/10 autorise cette recette transitoire sur service partagé avec
  artdubati vide, inutilisée et à réinitialiser avant production. Aucun accès ou
  changement à cette dernière base pendant la recette. Isolation et réinstallation
  restent exigées avant production ; les montages/empreintes hôte ne sont pas
  vérifiables par cet accès applicatif.
- Compte Test (8) : opérateur matériel et administrateur comptable, sans rôle
  d’approbateur matériel. Son essai d’approbation du chariot a été refusé.
  Les cinq réceptions ont ensuite été approuvées par un compte distinct,
  désigné dans la preuve publique par « Approbateur TEST »
  avant leur exécution par Test. Aucun groupe ni droit ajouté.
- Recette par méthodes publiques Odoo et lectures ORM ; aucun SQL, changement forcé
  d’état, sudo distant, paiement ou envoi de facture au fournisseur.

## Résultats et dossiers conservés

Les liens de navigation sont dans les fiches du manuel. Cette copie publique
du compte rendu conserve les références TEST sans lien direct vers l’ERP.

| Cas | Réception | Équipement | Contrat / ligne | Résultat de facturation |
|---|---|---|---|---|
| Camionnette | 1537 | 1828, loué, actif | 682 / 719 | BILL/2026/10/0008, 450 EUR HT comptabilisés ; prochaine échéance mensuelle |
| SUV | 1538 | 1829, loué, actif | 683 / 720 | BILL/2026/10/0009, 700 EUR HT comptabilisés ; prochaine échéance mensuelle |
| WC trois mois | 1539 | 1830, loué, actif | 684 / 721 | BILL/2026/10/0010, 150 EUR HT comptabilisés, et deux brouillons prévisionnels de 150 EUR HT (799, 800) |
| Chariot quatre heures | 1540 | 1831, restitué et archivé | 685 / 722 | BILL/2026/10/0011, forfait 120 + frais 175 = 295 EUR HT comptabilisés |
| Scie prêtée par Manager | 1541 | 1832, restitué et archivé | 686 / 723 | Prêt gratuit, aucune facture |

Les cinq réceptions sont exécutées et ont chacune un transfert terminé. Chaque
exemplaire a un lot distinct, un propriétaire tiers conservé et une quantité physique
1. Aucun actif ni couche de valorisation en propriété n’est créé pour ces biens.
Les quatre modèles de location ont un coût d’achat observé de 0 ; leurs valeurs de
remplacement 25000 / 40000 / 1200 / 25000 EUR HT sont enregistrées séparément sur les
exemplaires. La scie empruntée a une valeur de remplacement de 300 EUR HT ; le modèle
physique existant n’a pas été reconfiguré.

### Chariot : forfait, remplacement et frais

L’opération existante a été passée explicitement en Forfait unique avant soumission :
17/10/2026 10:00–14:00 Europe/Paris (08:00–12:00 UTC), durée 4, prix 120 EUR HT.
La réception réelle du 18/10 conserve son horodatage propre. La facture initiale 793
était un brouillon de 120 EUR HT, sans échéance périodique ni équivalent mensuel.
Le bouton de facturation récurrente sur ce contrat n’a créé aucune pièce supplémentaire.

Contrôles exécutés et refusés côté serveur :

- détacher contract_line_id et changer le compte, supprimer la ligne de forfait ;
- après annulation de 793 : changer prix ou source manuelle, remise, quantité,
  produit, unité, mode de tarification, dates civiles et horaires UTC de la ligne ;
- changer fournisseur, contact facturé, devise directe/manuelle, journal et dates
  du contrat parent après annulation ;
- comptabiliser un doublon du forfait (798, ensuite annulé) ;
- comptabiliser le brouillon de remplacement avec un forfait porté à 1200 EUR HT.

Le bouton de la ligne réutilise le remplacement 797. Celui-ci conserve fournisseur,
société, devise, journal, période et forfait approuvés. Référence et pièce jointe TEST
ont été renseignées ; les lignes de frais distinctes ne portent aucun lien au forfait :

| Ligne | HT | Compte | Taxe de test |
|---|---:|---|---|
| Loyer lié à 722 | 120 EUR | 613500 | Achat existante 20% G |
| Livraison | 80 EUR | 624100 | 20% G |
| Reprise | 80 EUR | 624100 | 20% G |
| Assurance ponctuelle | 15 EUR | 616100 | Sans TVA, hypothèse TEST |
| Total | **295 EUR** | | **56 EUR de TVA, 351 EUR TTC** |

Aucun compte, taxe ou produit service créé pour ce test : les frais sont des lignes
libellées de charges. C32 dans QUESTIONS_COMPTABLE.md explicite les hypothèses,
modifiables sur chaque ligne avant comptabilisation et à valider sur la pièce réelle.
La caution 1000 EUR et le remplacement 25000 EUR HT ne sont ni des charges automatiques
ni des montants payés. La facture de service n’a créé aucun second équipement.
L’opération conserve les trois pièces : 793 et 798 annulées, 797 comptabilisée.

### WC : trois échéances, aucune quatrième

Le contrat va du 17/10/2026 au 16/01/2027. Le bouton standard a produit trois loyers
mensuels de 150 EUR HT : première facture comptabilisée, puis brouillons datés
17/11/2026 et 17/12/2026, explicitement prévisionnels. Total 450 EUR HT ; dernière
date couverte 16/01/2027 et recurring_next_date=False. Après l’appel de contrôle,
les lectures finales confirment exactement trois pièces, aucune quatrième.

Une assertion intermédiaire comparait aussi les noms affichés, modifiés par les
références des brouillons ; elle a signalé à tort un écart. La répétition du bouton
a été refusée par le contrôle automatique, par crainte de créer une pièce de plus.
Le diagnostic a été terminé **en lecture seule**, par identifiants et montants :
trois pièces, sans mutation corrective ou nouvelle répétition. La première échéance
seule est comptabilisée, les deux autres restent en brouillon ; aucun paiement.

### Prêt et retours physiques

Le contrat gratuit de la scie ne génère pas de facture, y compris via le bouton
standard de facturation. La restitution EQOP/2026/1726
a arrêté la ligne de prêt au 18/10 et sorti/archivé l’exemplaire 1832.
La restitution EQOP/2026/1727
a sorti/archivé le chariot 1831 sans changer ses quatre heures ni ses dates et prix
approuvés. Sa période de contrat était déjà échue, donc aucune ligne financière
active à arrêter. Le workflow n’exigeait pas de nouvelle approbation dans ces deux
retours ; aucune approbation contournée.

Les sept transferts (cinq entrées, deux sorties) sont terminés. Après retour, aucun
quant interne non nul ne subsiste pour les deux lots. Camionnette, SUV et WC restent
en stock, quantité 1 chacun, avec leurs propriétaires tiers.

## Moniteur et interface

Avant restitution, cinq lignes visibles : loyers mensuels 450 / 700 / 150 EUR HT,
prêt gratuit à 0, et chariot sans loyer mensuel. Le créneau prévu du chariot étant
passé, alerte de fin prévue et absence de forfait actif, sans sortie automatique.
Après restitution, seules les trois locations encore en stock restent au moniteur.
Aucune alerte de périodicité non prise en charge.

Chromium sur les pages réellement servies, FR/EN/FA, bureau et mobile : libellé de
forfait traduit, durée 4 et historique de trois factures. Captures versionnées dans
lartdubati_manual/static/screenshots/{fr,en,fa}/rental-one-off-history-20261018.png.
La préférence de langue de Test, changée pour ces contrôles, est restaurée à en_US.
Le manuel et les exports expliquent les résultats et permettent d’ouvrir les dossiers.

## Limites de validation

- Le champ rent_paid du moniteur exige account.group_account_readonly, absent du
  compte Test bien qu’il puisse comptabiliser les factures. Refus d’accès constaté ;
  aucun droit ajouté. Cumul affiché non validé avec ce profil ; factures et liens
  comptables vérifiés directement. Le profil doit être traité séparément si cette
  colonne est nécessaire à Test.
- Aucun paiement, rapprochement bancaire, dépôt/restitution de caution, sinistre ou
  indemnité de remplacement exécuté. Les frais annexes des autres locations restent
  des budgets ; seules leurs premières échéances de loyer ont été comptabilisées.
- Fiscalité réelle du SUV, déductibilité et traitement des assurances restent à
  confirmer par le comptable. Les justificatifs utilisés sont fictifs TEST.
- Version installée et comportement observés ; aucun accès à Docker/SSH pour une
  nouvelle preuve des empreintes hôte. Les suites unitaires historiques ne sont
  pas réexécutées sur le serveur : ceci est une recette fonctionnelle ciblée.

Preuves structurées : live-acceptance-20261018.json. Aucun code métier, version de
module, contrôleur ou droit modifié par la mise à jour documentaire. Les nouveaux
manuels sont proposés dans Git ; leur publication dans Odoo exige de récupérer ces
fichiers sur le serveur. Pas de mise à jour de schéma pour les seuls fichiers du manuel.

Contrôles documentaires : check.py FR/EN/FA sans différence ; pages du dépôt
(comptable et administration) et exports contrôlés dans Chromium, bureau/mobile
sans débordement, dont RTL persan. PDF : 23 pages FR, 20 EN et 20 FA ; une capture
de l’historique embarquée dans chaque PDF et Word. ZIP des six exports régénéré.

## Copie publique expurgée

Les scénarios, matériels et montants sont fictifs ; la recette a utilisé de vrais
comptes sur une base de test. Le nom et l’identifiant personnel de l’approbateur
sont retirés de la preuve JSON publique, remplacés par « Approbateur TEST ».
Ses trois URL de dossiers ERP sont supprimées ; ce compte rendu ne comporte plus
de lien direct vers les enregistrements ERP. Les liens fonctionnels du manuel,
nécessaires à la navigation et soumis à authentification, restent dans les fiches.

Les captures ont été reprises depuis les formulaires servis, avec remplacement
dans le rendu du navigateur de l’approbateur par « Approbateur TEST » et de la
société par « Entreprise TEST ». États, dates, montants et historique sont conservés.
Aucun nom d’utilisateur ou de société ni aucune approbation n’est modifié en base.
Les originaux de travail non expurgés ne sont pas ajoutés à l’arbre corrigé.
La réécriture du commit de PR ne garantit pas la purge des anciennes versions
déjà publiées, références ou caches GitHub. Les six exports
PDF/Word sont régénérés à partir des captures anonymisées.

Statut du lot : recette locations/prêts validée ; réserve de lecture comptable
ouverte avec account.group_account_readonly ; manuels prêts, publication après
revue/fusion de la PR nº 2. Production toujours bloquée par l’isolation et la
recréation d’artdubati. La correction de confidentialité ne change pas ces états.

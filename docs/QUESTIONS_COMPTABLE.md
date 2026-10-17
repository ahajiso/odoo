# Questions pour l'expert-comptable

Liste des choix comptables arrêtés sans avis du comptable. Règle du projet
(`CLAUDE.md`) : pour chaque besoin d'avis comptable, on arrête un choix, on le rend
paramétrable dès que possible, et on ajoute la question ici. Le comptable peut changer
chaque choix ; la colonne « Où le changer » indique comment.

État au 09/10/2026. Base concernée : `artdubati_test` (aucun de ces choix n'est en
production).

## Immobilisations et stock

| # | Question | Choix arrêté pour le test | Où le changer | Paramétrable |
|---|---|---|---|---|
| C1 | Compte d'immobilisation du matériel et de l'outillage suivis en stock ? | 215400 Matériels industriels | Catégorie d'immobilisation (**Facturation → Configuration → Immobilisations → Catégories d'immobilisation**), compte du plan comptable, catégorie de produit Fixed Assets ; ou constantes de `docs/phase0/setup_phase0.py` | Oui |
| C2 | Comptes d'amortissement et de dotation ? | 281500 et 681120 | Même catégorie d'immobilisation : **Compte de dépréciation**, **Compte de dépréciation (charge)** | Oui |
| C3 | Méthode et durée d'amortissement ? Une durée par famille de matériel ? | Linéaire, 5 ans, une ligne par an, prorata temporis ; une seule catégorie | Même catégorie : **Méthode de calcul**, **Nombre d'années**, **Prorata temporis** ; une autre durée = une autre catégorie sur un autre compte de classe 21 (ex. 215500) | Oui |
| C4 | Les immobilisations créées depuis une facture doivent-elles être validées à la main ? | Oui, elles restent en brouillon | Même catégorie : **Sauter l'état brouillon** | Oui |
| C5 | Une immobilisation par unité (une par numéro de série) vous convient-elle ? | Oui (nécessaire au suivi par équipement) | Même catégorie : **Créer une immobilisation par article** ; le désactiver casse le lien équipement → immobilisation | Oui, mais structurant |
| C6 | Valorisation du stock des biens immobilisés suivis en stock ? | Catégorie de produit « All / Fixed Assets » : valorisation manuelle (pas d'écriture de stock), coût moyen, compte de charges 215400 ; la valeur comptable vient de l'immobilisation | **Inventaire → Configuration → Catégories de produits** → Fixed Assets | Oui |
| C7 | Méthode de coût des consommables ? | Coût moyen (catégories 11 à 17) | Catégories de produits, **Méthode de coût** | Oui |
| C8 | Avoir fournisseur (saisi à la main ou par « Extourner ») sur une facture d'immobilisation : quel traitement ? Réduction de la valeur d'origine, annulation de l'immobilisation, sortie, autre ? Et si l'immobilisation est déjà validée ou amortie ? (D'après la lecture du code, l'avoir crée une immobilisation négative et laisse l'immobilisation d'origine ; à confirmer par un test.) | Interdit par défaut : un avoir fournisseur portant sur un compte d'immobilisation est refusé à la comptabilisation | Réglage société prévu en phase 1 (« Autoriser les avoirs fournisseurs sur comptes d'immobilisation », désactivé par défaut) | Prévu (phase 1) |
| C9 | Valeur de remise d'un actionnaire (`handover_value`) : transfert de propriété, apport en nature ou simple mise à disposition ? Date du transfert, compte de contrepartie (capital, 455, autre), TVA, justificatif ? | Conservée comme information, jamais utilisée en comptabilité | À définir selon la réponse | Non (en attente) |
| C19 | Équipement suivi en stock sans immobilisation (catégorie non immobilisée) : valeur d'inventaire et valeur comptable ? | Valeur d'inventaire = coût d'achat de l'équipement ; valeur comptable = ce que portent les comptes : valorisation de stock si la catégorie est en valorisation automatique, 0 si elle est passée en charge (cas de la scie, catégorie « All », compte 607000, alerte « Sans immobilisation »). Appliqué dans le moniteur (phase 3) | Catégorie de produit (valorisation, compte), ou passer la catégorie en immobilisations | Oui |
| C20 | Immobilisation en brouillon (créée à la comptabilisation de la facture, pas encore validée) : comment présenter sa valeur ? | Valeur nette affichée comme « provisoire » (valeur d'origine moins amortissements comptabilisés), comptée à part (« dont X provisoire ») ; valeur nette = valeur d'origine moins amortissements, valeur résiduelle incluse. Appliqué dans le moniteur (phase 3) | Validation des immobilisations (Facturation → Immobilisations), ou réglage « Sauter l'état brouillon » de la catégorie (C4) | Oui |
| C22 | Consommable d'une catégorie en valorisation manuelle (périodique) : quelle valeur comptable ? | Valeur d'inventaire = quantité × coût moyen ; valeur de stock et valeur comptable = 0 (les comptes ne portent rien), comme C19. En valorisation automatique : valeur de stock = valeur comptable = quantité × coût moyen. Appliqué dans le moniteur (phase 3) | **Inventaire → Configuration → Catégories de produits** : valorisation de l'inventaire (manuelle / automatique) | Oui |
| C23 | Consommables d'un tiers en dépôt chez nous (consignation) qui deviennent la propriété de la société, ou qui sont sortis du stock : quelle pièce et quelle contrepartie ? | Aucun choix tant que la caractérisation sur Odoo 18 (phase 4, P4-1) n'est pas faite. Hypothèse à confirmer : un passage à la société est un achat au déposant (commande et facture fournisseur, entrée valorisée au coût d'achat), une sortie est une restitution au déposant sans écriture (biens non valorisés) | À définir selon la réponse (action de régularisation de la phase 4) | Non (en attente) |
| C24 | Petit équipement durable non immobilisé (outil, appareil conservé et suivi physiquement, sous le seuil d'immobilisation) : charge immédiate avec suivi physique et valeur comptable nulle, ou stock valorisé ? Quel seuil ? | Aucun choix arrêté (ROADMAP section 0, audit du 11/10/2026) ; hypothèse de travail : charge immédiate (606300 Fournitures d'entretien et de petit équipement), équipement suivi avec une valeur comptable nulle, comme C19 | Catégorie de produit du petit équipement (compte, valorisation) | Oui (par catégorie) |
| C25 | Comptes des futures catégories de produits (services achetés : maintenance, assurance, télécom, logiciels et SaaS, locations, crédit-bail, honoraires, sous-traitance, transport, énergie, frais bancaires ; matériaux, consommables, marchandises ; immobilisations par nature : informatique, véhicules, mobilier, installations, logiciels acquis) | Hypothèses de test seulement (docs/roadmap0/NOMENCLATURE.md), aucune appliquée. Valorisation de test : consommables, matériaux et marchandises de la société au coût moyen en valorisation automatique, comme le prévoit DEFINITIONS.md ; la base l'écarte aujourd'hui (catégories 11 à 17 en valorisation manuelle, inventaire du 11/10/2026). Choix de test appliqués par la migration du point 3 (docs/roadmap0/MIGRATION.md) : Immobilisations / Informatique sur 218300 avec le profil « Matériel informatique (test) » (281800 / 681120, linéaire, **3 ans**, une immobilisation par article) ; Immobilisations / Matériel et outillage sur 215400 (profil « Matériel et outillage (test) », 5 ans) ; services achetés sur 613500, 626000, 627800, 606400 et ventes sur 706000, 704000, 708300 (les comptes déjà portés par les articles) | Catégories de produits : comptes, **Méthode de coût**, **Valorisation de l'inventaire** ; **Comptabilité → Configuration → Profils d'immobilisation** (durée, comptes) | Oui |

## Location et prêt

| # | Question | Choix arrêté pour le test | Où le changer | Paramétrable |
|---|---|---|---|---|
| C10 | Compte des loyers de matériel ? | 613500 Locations mobilières ; une facture sur ce compte doit être liée à une ligne de contrat | Réglage société prévu en phase 1 (`equipment_rent_account_id`) | Prévu (phase 1) |
| C11 | Valeur d'inventaire d'un bien emprunté ou loué : valeur de remplacement ? | Valeur de remplacement datée, saisie sur l'équipement | Saisie par équipement | Oui (par équipement) |
| C16 | Compte des loyers de matériel facturés aux clients (matériel prêté contre loyer) ? | 708300 Locations diverses, porté par le produit « Location de matériel (facturée) » | Compte de revenus du produit, ou autre produit dans le réglage **Paramètres → Facturation → Equipment → Rent Product (Received)** | Oui |
| C21 | Loyers payés : hors taxes ? TVA non récupérable à inclure ? | Hors taxes : lignes de produit des factures et avoirs fournisseurs comptabilisés liés au contrat de location, montant signé en devise société, avoirs déduits ; les lignes de taxe sont exclues. Proposé en phase 3 | Définition de la vue du moniteur (code) ; à rendre paramétrable si le comptable demande la TVA non récupérable | Prévu si demandé |
| C17 | Acquisition sans achat (don, apport en compte courant d'associé, régularisation) : base de valorisation et comptes de contrepartie ; immobilisation ? | Valeur unitaire saisie sur la ligne (obligatoire, par défaut le coût du produit), utilisée comme coût d'entrée (coût moyen mis à jour). Écriture pour les catégories valorisées automatiquement : débit du compte de valorisation du stock de la catégorie, crédit du compte de l'emplacement d'acquisition : don 778000, apport en compte courant d'associé 455100 (avance en compte courant, pas un apport au capital ; les autres formes d'apport attendent C9 ; valeur et date reportées dans `handover_value` / `handover_value_date` de l'équipement), régularisation 603200. Catégories d'immobilisation (valorisation manuelle) : aucune écriture ni immobilisation automatique, le comptable crée l'immobilisation et la lie à l'équipement | Comptes des trois emplacements « Acquisitions - … » (créés par docs/phase2/setup_phase2.py) ou autres emplacements dans **Paramètres → Facturation → Equipment → Acquisitions without purchase** | Oui |
| C18 | Vente, mise au rebut ou perte d'un équipement immobilisé : sortie de l'immobilisation (assistant de cession OCA), comptes de plus ou moins-value ? | Sortie de la société bloquée pour tous, sans exception de groupe, jusqu'à l'opération de cession (phase ultérieure) | À définir selon la réponse | Non (en attente) |

## Devises

| # | Question | Choix arrêté pour le test | Où le changer | Paramétrable |
|---|---|---|---|---|
| C12 | Conversion des valeurs vers la devise de chaque stock : quel taux et quelle date ? | Mode « historique » : chaque montant à sa date (immobilisation : date de début ; coût d'achat : date d'entrée ; coût moyen : date du moniteur ; valeur de remplacement : sa date ; loyer : début de la ligne ; factures : date comptable de chacune). Taux manquant : montant non converti, exclu des totaux, signalé. Le mode « sans conversion » est supprimé (phase 3 ; une société restée en « sans conversion » passe au dernier taux) | **Paramètres → Inventaire → Moniteur de stock → Conversion des devises** (historique / dernier taux) | Oui |

## Facturation BTP (questions déjà ouvertes, reprises ici)

| # | Question | Choix arrêté pour le test | Où le changer | Paramétrable |
|---|---|---|---|---|
| C13 | Comptes comptables utilisés dans les fiches CPT-02 à CPT-08 du manuel | Plan comptable général, présentés « à valider » | Fiches du manuel et plan comptable | Oui |
| C14 | Cases de la CA3 pour l'autoliquidation nationale de sous-traitance | Aucune case sur les 4 taxes (avertissement dans CPT-10, CPT-11) | Lignes de répartition des taxes d'autoliquidation | Oui |
| C15 | Régime de TVA : débits ou encaissements ? | Les deux régimes restent disponibles : le régime appliqué est celui de la taxe choisie sur chaque ligne (taxes « S » encaissement, « G » débits) | Taxes sur les lignes ; désactiver les taxes du régime non retenu, positions fiscales | Oui |

## Complément documentaire du 17/10/2026 — quatre factures spécimens

Ces propositions complètent C24/C25 ; aucune configuration n'a été appliquée.

| # | Question | Choix proposé pour l'exercice | Où le changer | Paramétrable |
|---|---|---|---|---|
| C26 | Catégories honoraires comptables et SaaS encore absentes : comptes à retenir ? | Honoraires sur 622600 ; SaaS sur une subdivision dédiée de 628000. Propositions de test à valider, sans utiliser 606400 ni capitaliser un abonnement. | Catégories de produits sous Services Purchased, compte de charge et disponibilité des demandes, par administrateur comptable | Oui |
| C27 | Achat Google en Irlande : taxe, déduction et déclaration ? | Réutiliser la taxe existante 20% EU S : 33,80 de TVA due (445210) et 33,80 déductible (445662) sur 169,00 HT si déduction intégrale. Contrôler le régime B2B, les numéros TVA et les droits réels ; aucune déclaration générée. | Taxe d'achat, répartitions, position fiscale et facture | Oui |
| C28 | Scie à 519,97 HT, vêtements/EPI et unité commerciale du carrelage ? | Ne pas appliquer de seuil automatique. Classer chaque scie selon C24 et la politique d'immobilisation ; suivre deux équipements physiques. Vêtements et coffret suivis en quantité. Confirmer boîte/m² et configuration de valorisation avant ouverture des catégories. | Catégories produit et équipement, unités et profils d'immobilisation | Oui |

Contrôles préalables des pièces : Orange présente un écart d'arrondi de TVA
(13,01 annoncé contre 13,00 par ligne ou 12,99 globalement) : pièce corrigée
ou justification nécessaire, sans ligne d'équilibrage arbitraire.
À la demande du propriétaire, le spécimen pédagogique Leroy Merlin a été corrigé
avant intégration au manuel : prix et quantités conservés, unité carrelage fixée
pour l'exercice à la boîte, brut 951,30 HT, remise unique 41,25 HT, net 910,05 HT,
TVA arrondie par ligne 182,00, TTC 1 092,05. Le PDF fictif est livré dans
lartdubati_manual/static/templates/facture-specimen-leroy-merlin-corrigee.pdf.

## Complément locations et prêt — exercice du 17/10/2026

Le propriétaire a demandé les cinq cas dans le manuel et artdubati_test, puis
explicitement autorisé des données fictives TEST. Aucun engagement réel auprès
d'un loueur n'est demandé. Prix de démonstration HT : camionnette 450 par mois,
SUV 700 par mois, WC 150 par mois sur trois mois ; chariot 120 pour un forfait
unique de quatre heures ; prêt Ryobi gratuit. Les valeurs de remplacement sont
respectivement 25 000, 40 000, 1 200, 25 000 et 300 EUR HT. Ces valeurs ne sont
pas des devis fournisseurs ni des valeurs comptables d'actifs de la société.

| # | Question | Choix de test / limite | Où le changer | Paramétrable |
|---|---|---|---|---|
| C29 | Catégories des nouveaux modèles physiques utilisés uniquement pour suivre des biens de tiers ? | Trois catégories neuves préfixées TEST sous Small Durable Equipment : Modèles véhicules, Installations temporaires, Manutention ; compte 606300, coût moyen, valorisation manuelle, sans profil d'actif. Les demandes désactivent achat et vente du modèle physique. Ce choix n'autorise aucun achat de véhicule en charge ni aucune politique de capitalisation ; le loyer porte sur le service configuré 613500. Aucun compte ni catégorie existante n'est changé. | Nouvelles catégories TEST et demandes, par administrateur comptable ; traitement d'un futur achat réel à décider séparément | Oui |
| C30 | Location de quatre heures : comment éviter une fausse récurrence mensuelle et un loyer mensuel erroné ? | Le cas est préparé mais reste en brouillon : réception actuelle uniquement Mois/Trimestre/Année et champs Date. Un parcours d'engagement ponctuel, heures prouvées, facture unique et exclusion de la récurrence est nécessaire avant exécution. Aucune conversion arbitraire du forfait de 120 HT en loyer mensuel. | Futur parcours de location ponctuelle et présentation dans le moniteur ; pas implémenté ici | Non, développement à définir |
| C31 | Fiscalité et usage personnel du SUV de fonction loué ? | Faire valider les taxes, déductibilité, charges et éventuel avantage en nature sur le cas réel ; ne pas recopier automatiquement la fiscalité de l'utilitaire. Aucun calcul fiscal, de paie ou de TVA réel n'est appliqué par les exemples. | Paramètres fiscaux du fournisseur, taxe et compte de la facture ; futur lien Fleet / paie | À définir selon le traitement |

Le catalogue courant impose un produit durable stocké et suivi en série pour les
nouvelles demandes. Les véhicules hors stock sont décrits dans DEFINITIONS.md,
mais ce choix n'est pas offert par la demande ; Fleet est non installé. Les
exemples expliquent ce décalage sans contourner les champs protégés.


Frais annexes TEST détaillés dans CPT-22 à CPT-26 et leurs pièces d'exercice :
livraison, reprise, assurance et nettoyage sont des budgets distincts du loyer.
Cautions remboursables 1000/1500/200/1000/0 EUR (camionnette/SUV/WC/chariot/scie)
hors charges ; valeurs de remplacement sans incidence comptable automatique.
Le formulaire n'a pas de champs dédiés à ces frais/cautions : notes et PDF joints
seulement, aucune ligne de facture créée. Faire valider les comptes et taxes lors
de la saisie des pièces TEST, puis le rapprochement et la restitution des cautions.

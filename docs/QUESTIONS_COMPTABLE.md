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

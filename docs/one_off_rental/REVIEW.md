# Revue technique du 17/10/2026

Périmètre relu : différence entre le serveur actuel (`f0de375`, empreintes des
modules vérifiées contre l'inventaire reçu) et la proposition (code `aff72e6` puis correction OCA décrite ci-dessous), profil
catalogue compris. Revue effectuée dans ce chat ; aucun avis d'un autre réviseur
GitHub n'est enregistré. Les résultats d'exécution sont dans VALIDATION.md.

- Entrées RPC : l'action publique de création de facture exige administrateur
  comptable et écriture du contrat ; aucun sudo de création sur cette entrée.
  Le chemin d'exécution d'opération conserve ses contrôles opérateur/approbateur.
  Les méthodes privées ne constituent pas des entrées RPC publiques.
- Catalogue : l'exception d'autoapprobation exige un groupe explicite, qui implique
  seulement le gestionnaire du catalogue. Aucune attribution automatique, aucun
  droit supplémentaire d'approbation des mouvements physiques. Les contrôles de
  référence, famille, doublons et exécution de demande restent actifs.
- Montants : une unité physique, un service de location et une facture brouillon
  pour le forfait. La comptabilisation vérifie fournisseur/société, service, devise,
  quantité et montant HT. Frais, cautions et remplacement restent distincts.
- Concurrence : verrou stable des lignes de contrat et révision écrite par ORM
  forcent une reprise de transaction en REPEATABLE READ. Le simple verrou sans
  révision aurait laissé l'instantané obsolète ; la vérification à deux connexions
  couvre ce cas. Aucune écriture métier SQL directe.
- Cycle de vie : aucune échéance périodique, reconduction ou équivalence mensuelle
  pour un forfait. Les autres lignes récurrentes conservent le moteur OCA. Annuler
  la facture permet son remplacement ; un avoir ne relance pas la facturation.
  Les engagements facturés sont protégés contre leur modification.
- Dates : horodatages UTC et fuseau explicite pour les dates civiles du contrat.
  Les widgets suivent le navigateur. Pas de prorata horaire, de dépassement
  automatique, ni de rotations contractuelles multiples le même jour.
- Mise à jour : les champs stockés sont lus par le moniteur ; les DEUX modules
  doivent être mis à jour application arrêtée. Les valeurs existantes prennent
  `recurring`. L'empreinte d'approbation change : réapprobation normale si requise.

La vérification sur OCA contract 18.0.2.5.3 a trouvé un défaut bloquant :
`_insert_markers` appelait `strftime` sur les dates récurrentes absentes du forfait.
Corrigé dans notre surcharge, uniquement pour `one_off`, en gardant sa description ;
le préparateur OCA et les autres contrats restent inchangés. Le test du parcours
complet vérifie aussi le préparateur de ligne. Les tests communs fixent leur contexte
à en_US pour leurs assertions anglaises, indépendamment du français activé par le
plan comptable. Le test de migration prépare les autres stocks candidats avec une
adresse et vérifie que l’erreur cite le stock incomplet attendu, dans toute langue.

Aucun autre défaut bloquant identifié dans ce périmètre. Cela n'atteste pas d'un audit
indépendant, d'une exécution serveur ou d'une validation comptable des comptes et
taxes. La procédure contrôlée reste applicable avant toute utilisation distante.

Le test historique de traduction active explicitement en_US et fr_FR avant de
comparer les deux libellés. Lorsque l'anglais est désactivé, cette version Odoo
met volontairement à jour le texte source en_US lors d'une écriture française ;
le test supposait à tort que l'anglais était toujours actif. Il ne s'agit pas
d'une correction du moteur de traduction ou du moniteur.

# Déployer sur artdubati_test

Exécution par le propriétaire du serveur, après revue de la proposition GitHub #1.
Aucun déploiement distant n'a été effectué dans le chat. L'application et les
fichiers de code servent aussi artdubati : cette procédure ne met à jour que
artdubati_test et suppose toujours l'absence d'utilisation réelle en production.

## 1. Préparer sans changer le code chargé

Remplacer la valeur de REVIEWED_COMMIT par le SHA complet annoncé dans le chat
pour cette livraison relue. Les commandes suivantes récupèrent les scripts dans
un dossier temporaire ; elles ne font ni pull, ni checkout du code de l'application.

```bash
set -euo pipefail
cd /opt/odoo/addons/custom
REVIEWED_COMMIT=REMPLACER_PAR_LE_SHA_COMPLET_ANNONCE
git fetch origin
git cat-file -e "$REVIEWED_COMMIT^{commit}"
STAGE=$(mktemp -d /tmp/oneoff_deploy.XXXXXX)
git archive "$REVIEWED_COMMIT" docs | tar -x -C "$STAGE"
EXPECTED_FILE="$STAGE/docs/one_off_rental/platform_expected.txt" bash "$STAGE/docs/phase4/check_modules.sh" before
```

Exiger `PLATFORM OK (before)` : même image, même version Odoo et mêmes 122
modules, versions et empreintes incluses. En cas d'écart, arrêter et transmettre
la sortie. Ne pas adapter l'inventaire pour faire passer le contrôle.

## 2. Fusionner la proposition relue, puis vérifier le contenu

Fusionner la PR #1 sur GitHub après l'audit prévu par CLAUDE.md. Ensuite, dans la
même session SSH :

```bash
git fetch origin
TARGET=$(git rev-parse origin/main)
git diff --exit-code "$REVIEWED_COMMIT" "$TARGET" --
```

Exiger une sortie vide et un code de retour 0. Le commit de fusion peut avoir un
SHA différent ; son arbre de fichiers doit être identique à la livraison relue.
Si main contient d'autres changements, arrêter pour les faire revoir.

## 3. Sauvegarder, puis mettre à jour ensemble

La sauvegarde arrête brièvement odoo_web, capture base et filestore et teste une
restauration complète. Choisir une fenêtre permettant ensuite l'arrêt pendant la
mise à jour et les tests. Garder les utilisateurs hors de l'application entre la
sauvegarde et la fin du déploiement.

```bash
bash "$STAGE/docs/backup_db.sh" oneoff_20261017
```

Exiger `BACKUP OK`. Le chemin du dump est lu dans le manifeste validé, sans
exécuter son contenu. Le nombre de tests attendu est celui consigné dans
VALIDATION.md pour l’environnement serveur sans websocket-client.

```bash
BACKUP=$(sed -n 's/^DUMP=//p' "${LOGDIR:-/opt/odoo/logs}/oneoff_20261017_backup")
[ -n "$BACKUP" ] && [ -s "$BACKUP" ]
bash "$STAGE/docs/deploy_modules.sh" "$BACKUP" 301 oneoff_20261017 "$TARGET"
```

Le script arrête l'application AVANT le changement de code, vérifie le
fast-forward vers origin/main, met à jour maintenance_shareholder_equipment et
lartdubati_investor_home, exécute les tests puis redémarre seulement si tout passe.
Les HTML du manuel sont servis depuis les fichiers de cette même livraison ;
aucun nouveau schéma du module manuel n'est introduit.

En cas d'échec après l'arrêt, le service reste arrêté. Ne pas simplement le
redémarrer sur une base partiellement mise à jour. Restaurer base, filestore et
ancien code avec le script préparé :

```bash
bash "$STAGE/docs/restore_db.sh" oneoff_20261017
```

## 4. Contrôler puis tester le chariot existant

```bash
EXPECTED_FILE="$STAGE/docs/one_off_rental/platform_expected.txt" bash "$STAGE/docs/phase4/check_modules.sh" after
```

Exiger `PLATFORM OK (after)` ; le contrôle inclut les nouvelles empreintes des
deux modules métier et du manuel. Vérifier aussi l'ouverture du manuel et des
formulaires en français/persan avec les profils concernés.

Dans artdubati_test, reprendre la réception TEST du CHA25E déjà en brouillon
(EQOP/2026/1540), sans la dupliquer. Suivre CPT-25 : forfait unique, fuseau
Europe/Paris, horaires 10:00–14:00 d'un jour TEST choisi, loyer 120 HT. Soumettre,
faire approuver par l'approbateur du matériel, exécuter à la réception physique.
Contrôler la facture brouillon ; saisir livraison 80, reprise 80 et assurance 15
HT en lignes distinctes, soit 295 HT. La caution 1000 reste séparée et la valeur
de remplacement 25000 HT ne crée pas de dette. Comptabiliser après contrôle des
comptes/taxes, puis enregistrer la restitution normalement.

Une ancienne approbation d'opération peut nécessiter une nouvelle approbation
car son empreinte d'engagement a changé. Le profil catalogue autonome ne donne
aucun droit d'autoapprobation des opérations de matériel.

#!/usr/bin/env bash
# Installe les modules OCA de gestion des immobilisations sur artdubati.
#   account_asset_management 18.0.1.1.11  (OCA/account-financial-tools @ e809f87)
#   report_xlsx 18.0.1.1.3, report_xlsx_helper 18.0.1.0.0 (OCA/reporting-engine @ 7a156ca)
# Usage : bash installer_oca_immobilisations.sh oca_immobilisations.zip
set -euo pipefail

ZIP="${1:-oca_immobilisations.zip}"
CONTAINER="odoo_web"
DB="artdubati"
MODULES="report_xlsx report_xlsx_helper account_asset_management"

[ -f "$ZIP" ] || { echo "Archive introuvable : $ZIP"; exit 1; }

# 1. Trouver le dossier des modules personnalisés (celui qui contient déjà maintenance_shareholder_equipment)
ADDONS_DIR="${ADDONS_DIR:-}"
for src in $(docker inspect "$CONTAINER" --format '{{range .Mounts}}{{.Source}} {{end}}'); do
  if [ -d "$src/maintenance_shareholder_equipment" ]; then ADDONS_DIR="$src"; fi
done
[ -n "$ADDONS_DIR" ] || { echo "Dossier des modules non trouvé. Indiquer-le : ADDONS_DIR=/chemin bash $0 $ZIP"; exit 1; }
echo "Dossier des modules : $ADDONS_DIR"

# 2. Copier les modules
TMP=$(mktemp -d)
unzip -q "$ZIP" -d "$TMP"
for m in $MODULES; do
  if [ -d "$ADDONS_DIR/$m" ]; then echo "Remplacement de $m existant"; rm -rf "$ADDONS_DIR/$m"; fi
  cp -r "$TMP/oca_immobilisations/$m" "$ADDONS_DIR/"
done
rm -rf "$TMP"

# 3. Installer (le module principal entraîne ses dépendances)
LOG=/tmp/install_oca_immobilisations.log
docker exec -i "$CONTAINER" odoo -d "$DB" -i account_asset_management --stop-after-init 2>&1 | tee "$LOG" | tail -5
if grep -qE " (ERROR|CRITICAL) " "$LOG"; then
  echo "ERREUR pendant l'installation. Rien n'a été redémarré. Journal : $LOG"
  grep -E " (ERROR|CRITICAL) " "$LOG" | head -20
  exit 1
fi

# 4. Redémarrer
docker restart "$CONTAINER" >/dev/null
echo "OK : modules installés et Odoo redémarré. Menu : Facturation → Immobilisations."

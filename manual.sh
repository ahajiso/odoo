#!/usr/bin/env bash
# Installation unique du module lartdubati_manual (sert le manuel sur /manuel).
# Usage : bash installer_module_manuel.sh lartdubati_manual.zip
set -euo pipefail
ZIP="${1:-lartdubati_manual.zip}"; CONTAINER="odoo_web"; DB="artdubati"
[ -f "$ZIP" ] || { echo "Archive introuvable : $ZIP"; exit 1; }
ADDONS_DIR="${ADDONS_DIR:-}"
if [ -z "$ADDONS_DIR" ]; then
  for src in $(docker inspect "$CONTAINER" --format '{{range .Mounts}}{{.Source}} {{end}}'); do
    [ -d "$src/maintenance_shareholder_equipment" ] && ADDONS_DIR="$src"
  done
fi
[ -n "$ADDONS_DIR" ] || { echo "Dossier des modules non trouvé. Relancer avec ADDONS_DIR=/chemin"; exit 1; }
echo "Dossier des modules : $ADDONS_DIR"
rm -rf "$ADDONS_DIR/lartdubati_manual"
unzip -q "$ZIP" -d "$ADDONS_DIR"
LOG=/tmp/install_lartdubati_manual.log
docker exec -i "$CONTAINER" odoo -d "$DB" -i lartdubati_manual --stop-after-init 2>&1 | tee "$LOG" | tail -3
if grep -qE " (ERROR|CRITICAL) " "$LOG"; then echo "ERREUR, voir $LOG"; grep -E " (ERROR|CRITICAL) " "$LOG" | head; exit 1; fi
docker restart "$CONTAINER" >/dev/null
echo "OK : ouvrir https://erp.lartdubati.com/manuel (ou le menu Manuel dans Odoo)."

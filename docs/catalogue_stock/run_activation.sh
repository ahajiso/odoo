#!/usr/bin/env bash
# Open the six existing stock categories on artdubati_test. Dry run by default.
set -euo pipefail
DB=${DB:-artdubati_test}
LOGDIR=${LOGDIR:-/opt/odoo/logs}
HERE=$(cd "$(dirname "$0")" && pwd)
MODE=dryrun
APPLY=0
case "${1:-}" in
  "") ;;
  --apply) MODE=apply; APPLY=1 ;;
  *) echo "usage: bash $0 [--apply]"; exit 2 ;;
esac
[ "$DB" = artdubati_test ] || { echo "REFUSED: DB must be artdubati_test"; exit 1; }
mkdir -p "$LOGDIR"
STAMP=$(date +%F_%H%M%S)
OUT="$LOGDIR/catalogue_stock_${MODE}_$STAMP.txt"
ERR="$LOGDIR/catalogue_stock_${MODE}_stderr_$STAMP.txt"

if [ -n "${ODOO_SHELL:-}" ]; then
  RUN() { CATALOGUE_STOCK_APPLY=$APPLY $ODOO_SHELL; }
elif [ "$(docker inspect -f '{{.State.Running}}' odoo_web)" = true ]; then
  RUN() { docker exec -i -e CATALOGUE_STOCK_APPLY=$APPLY odoo_web \
    odoo shell -d "$DB" --no-http; }
else
  IMG=$(docker inspect -f '{{.Config.Image}}' odoo_web)
  NET=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' odoo_web)
  read -r -a NETWORKS <<< "$NET"
  [ "${#NETWORKS[@]}" -eq 1 ] || { echo "REFUSED: odoo_web must have one network"; exit 1; }
  ENVF=$(mktemp)
  trap 'rm -f "$ENVF"' EXIT
  chmod 600 "$ENVF"
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo_web > "$ENVF"
  RUN() { docker run --rm -i --network "${NETWORKS[0]}" --volumes-from odoo_web \
    --env-file "$ENVF" -e CATALOGUE_STOCK_APPLY=$APPLY "$IMG" \
    odoo shell -d "$DB" --no-http; }
fi

if ! RUN < "$HERE/activate_categories.py" > "$OUT" 2> "$ERR"; then
  tail -30 "$OUT" || true
  tail -30 "$ERR" || true
  echo "ACTIVATION FAILED: nothing committed"
  exit 1
fi
if grep -qE '^(ERROR|REFUSED)[: |]' "$OUT" "$ERR"; then
  grep -E '^(ERROR|REFUSED)[: |]' "$OUT" "$ERR" || true
  echo "ACTIVATION FAILED: nothing committed"
  exit 1
fi
LAST=$(tail -1 "$OUT")
if [ "$APPLY" = 1 ]; then
  [[ "$LAST" =~ ^END\ \|\ applied,\ [0-9]+\ record\(s\)\ changed$ ]]
else
  [[ "$LAST" =~ ^END\ \|\ dry\ run,\ [0-9]+\ record\(s\)\ rolled\ back$ ]]
fi
echo "CATALOGUE STOCK OK ($MODE): $OUT"
echo "$LAST"

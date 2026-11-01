#!/usr/bin/env bash
# Create or update the "Fabro ticket to PR" SuperPlane app from canvas.yaml and
# console.yaml, and the organization secret its HTTP nodes authenticate with.
#
#   SP_URL=https://superplane.home.lapiduz.com SP_TOKEN=<SuperPlane API token> \
#   FABRO_TOKEN=<Fabro dev token> factory/superplane/import.sh
#
# Idempotent: an existing secret is updated, an existing canvas (matched by
# name) gets a new version. Neither token is printed.
set -euo pipefail
: "${SP_URL:?}" "${SP_TOKEN:?}" "${FABRO_TOKEN:?}"
here="$(cd "$(dirname "$0")" && pwd)"
name="Fabro ticket to PR"

api() {  # api METHOD PATH [JSON]
  curl -fsS -X "$1" "$SP_URL/api/v1$2" -H "Authorization: Bearer $SP_TOKEN" \
    -H "Content-Type: application/json" ${3:+--data-binary "$3"}
}
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

org=$(api GET /me | json 'd["user"]["organizationId"] if "user" in d else d["organizationId"]')

# ── secret `fabro` (key `token`) ───────────────────────────────────────────
secret=$(FABRO_TOKEN="$FABRO_TOKEN" python3 -c '
import json, os, sys
print(json.dumps({"secret": {"metadata": {"name": "fabro"},
                             "spec": {"provider": "PROVIDER_LOCAL",
                                      "local": {"data": {"token": os.environ["FABRO_TOKEN"]}}}},
                  "domain_type": "DOMAIN_TYPE_ORGANIZATION", "domain_id": sys.argv[1]}))' "$org")
if api GET "/secrets/fabro?domain_type=DOMAIN_TYPE_ORGANIZATION&domain_id=$org" >/dev/null 2>&1; then
  api PATCH "/secrets/fabro" "$secret" >/dev/null && echo "secret fabro: updated"
else
  api POST /secrets "$secret" >/dev/null && echo "secret fabro: created"
fi

# ── canvas ─────────────────────────────────────────────────────────────────
id=$(api GET /canvases | NAME="$name" json '"".join(c["id"] for c in d.get("canvases", []) if c["name"] == __import__("os").environ["NAME"])')
if [ -z "$id" ]; then
  id=$(api POST /canvases "$(NAME="$name" python3 -c 'import json,os; print(json.dumps({"name": os.environ["NAME"], "description": "Label an issue fabro; Fabro opens a tested PR."}))')" \
       | json 'd["canvas"]["metadata"]["id"]')
  echo "canvas: created $id"
else
  echo "canvas: updating $id"
fi

staging=$(ID="$id" python3 - "$here" <<'PY'
import base64, json, os, sys
here = sys.argv[1]
ops = []
for f in ("canvas.yaml", "console.yaml"):
    body = open(os.path.join(here, f), encoding="utf-8").read().replace("__CANVAS_ID__", os.environ["ID"])
    ops.append({"path": f, "content": base64.b64encode(body.encode()).decode()})
print(json.dumps({"operations": ops}))
PY
)
api PUT "/canvases/$id/staging" "$staging" >/dev/null
api POST "/canvases/$id/staging/commit" '{"commit_message": "Import from factory/superplane"}' \
  | json '"committed version " + str(d.get("version", {}).get("metadata", {}).get("id", "?"))'
echo "$SP_URL/canvases/$id"

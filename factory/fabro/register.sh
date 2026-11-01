#!/usr/bin/env bash
# Register factory/fabro/ticket_to_pr as an immutable Fabro workflow version,
# print its id, and store it in the Fabro server variable TICKET_TO_PR_VERSION,
# which the SuperPlane app reads before every run. Content-addressed: re-running
# with unchanged files prints the same id. No SuperPlane change is needed.
#
#   FABRO_URL=http://10.0.5.29:32276 FABRO_TOKEN=... factory/fabro/register.sh
#
# The Fabro API only admits SuperPlane's host (and Caddy), so run this there or
# on the Fabro VM against http://127.0.0.1:32276.
set -euo pipefail
: "${FABRO_URL:?set FABRO_URL}" "${FABRO_TOKEN:?set FABRO_TOKEN}"
dir="$(cd "$(dirname "$0")/ticket_to_pr" && pwd)"

body=$(python3 - "$dir" <<'PY'
import json, os, sys
root = sys.argv[1]
files = {}
for base, _, names in os.walk(root):
    for n in sorted(names):
        p = os.path.join(base, n)
        files[os.path.relpath(p, root)] = open(p, encoding="utf-8").read()
print(json.dumps({"entrypoint": "workflow.fabro", "files": files, "workflow_dependencies": {}}))
PY
)

id=$(curl -fsS -X POST "$FABRO_URL/api/v1/workflow-versions" \
  -H "Authorization: Bearer $FABRO_TOKEN" -H "Content-Type: application/json" \
  --data-binary "$body" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["workflow_version_id"])')

curl -fsS -o /dev/null -X POST "$FABRO_URL/api/v1/variables" \
  -H "Authorization: Bearer $FABRO_TOKEN" -H "Content-Type: application/json" \
  --data-binary "{\"name\": \"TICKET_TO_PR_VERSION\", \"value\": \"$id\", \"description\": \"ticket_to_pr workflow version started by SuperPlane\"}"
echo "$id"

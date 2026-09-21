#!/usr/bin/env bash
#
# One-command deploy of the MDM control plane to any Databricks workspace.
#
#   ./deploy.sh --profile <profile> [--target dev|hackathon] [--project <id>]
#
# What it does (idempotent — safe to re-run):
#   1. Creates the Lakebase Autoscaling project if it doesn't exist. DABs cannot
#      create an Autoscaling Lakebase project declaratively, so this is the one
#      imperative step; everything else is the bundle.
#   2. Discovers the real database resource path in that project.
#   3. `databricks bundle deploy` — uploads the app + attaches Lakebase.
#   4. Starts the app and prints its URL.
#
# The app creates its schema and seeds the LFLR data on first open (owned by the
# app's service principal), so there is no separate data-upload step.
set -euo pipefail

PROFILE=""
TARGET="dev"
PROJECT="mdm-article-master"
BRANCH="production"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --target)  TARGET="$2";  shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$PROFILE" ]]; then
  echo "Usage: ./deploy.sh --profile <profile> [--target dev|hackathon] [--project <id>]" >&2
  exit 1
fi

cd "$(dirname "$0")"
PROJECT_PATH="projects/${PROJECT}"
BRANCH_PATH="${PROJECT_PATH}/branches/${BRANCH}"

echo "==> [1/4] Ensuring Lakebase project '${PROJECT}' exists"
# A soft-deleted project still answers get-project (with delete_time set) but
# cannot be used and blocks its own id until purge — detect that explicitly.
# `|| true` so an absent project (non-zero get-project) doesn't trip set -e/pipefail.
PROJ_JSON="$(databricks postgres get-project "${PROJECT_PATH}" --profile "${PROFILE}" -o json 2>/dev/null || true)"
STATE="$(printf '%s' "${PROJ_JSON}" | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin)
  print("deleting" if d.get("delete_time") else ("exists" if d.get("name") else "absent"))
except Exception:
  print("absent")')"
case "${STATE}" in
  exists)
    echo "    project already exists — reusing it." ;;
  deleting)
    echo "    project '${PROJECT}' is soft-deleted (pending purge) — its id is unusable." >&2
    echo "    Re-run with a different id, e.g.  --project ${PROJECT}-01" >&2
    exit 1 ;;
  *)
    echo "    creating project (this can take a couple of minutes)…"
    databricks postgres create-project "${PROJECT}" \
      --json '{"spec": {"display_name": "MDM Article Master"}}' \
      --profile "${PROFILE}" ;;
esac

echo "==> [2/4] Discovering the database resource path"
DB_PATH="$(databricks postgres list-databases "${BRANCH_PATH}" --profile "${PROFILE}" -o json \
  | python3 -c 'import json,sys; dbs=json.load(sys.stdin) or []; print((dbs[0] if isinstance(dbs,list) else dbs.get("databases",[{}])[0]).get("name",""))')"
if [[ -z "${DB_PATH}" ]]; then
  echo "    could not resolve a database in ${BRANCH_PATH}." >&2
  exit 1
fi
echo "    using ${DB_PATH}"

# app.yaml holds LAKEBASE_ENDPOINT/LAKEBASE_PROJECT for the DEFAULT project id.
# If a different --project was chosen, patch app.yaml just for this deploy and
# restore it afterwards (keeps the working tree clean).
if [[ "${PROJECT}" != "mdm-article-master" ]]; then
  cp app.yaml app.yaml.bak
  trap 'mv -f app.yaml.bak app.yaml 2>/dev/null || true' EXIT
  python3 - app.yaml "${PROJECT}" <<'PY'
import sys, re
path, proj = sys.argv[1], sys.argv[2]
s = open(path).read()
s = re.sub(r'projects/[^/\s]+/branches/production/endpoints/primary',
           f'projects/{proj}/branches/production/endpoints/primary', s)
s = re.sub(r'(name: LAKEBASE_PROJECT\n\s*value: )\S+', rf'\g<1>{proj}', s)
open(path, 'w').write(s)
PY
  echo "    (app.yaml patched to project '${PROJECT}' for this deploy)"
fi

echo "==> [3/4] Deploying the bundle (target: ${TARGET})"
databricks bundle deploy -t "${TARGET}" \
  --var="postgres_project=${PROJECT}" \
  --var="postgres_database=${DB_PATH}" \
  --profile "${PROFILE}"

echo "==> [4/4] Starting the app"
databricks bundle run mdm_control_plane -t "${TARGET}" --profile "${PROFILE}" || true
URL="$(databricks apps get mdm-control-plane --profile "${PROFILE}" -o json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("url",""))' 2>/dev/null || true)"
echo
echo "Done. Open the app${URL:+: $URL}"
echo "First open seeds the schema + LFLR data (may take a few seconds while Lakebase wakes)."

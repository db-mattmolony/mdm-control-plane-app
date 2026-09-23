#!/usr/bin/env bash
#
# One-command deploy of the MDM control plane to any Databricks workspace.
#
#   ./deploy.sh [--profile <profile>] [--target dev|hackathon] [--project <id>] [--catalog <name>]
#
# --profile is optional: omit it when running inside a Databricks workspace web
# terminal (the CLI uses that workspace's ambient auth). Pass it when running
# from a machine that authenticates via a named ~/.databrickscfg profile.
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
CATALOG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --target)  TARGET="$2";  shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    --catalog) CATALOG="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

# --profile is optional. When set, pass it to every CLI call; when empty (e.g.
# running inside a Databricks workspace terminal), fall back to ambient auth.
# ${AUTH[@]+"${AUTH[@]}"} expands to nothing when empty — safe under `set -u`.
AUTH=()
[[ -n "$PROFILE" ]] && AUTH=(--profile "$PROFILE")

cd "$(dirname "$0")"
PROJECT_PATH="projects/${PROJECT}"
BRANCH_PATH="${PROJECT_PATH}/branches/${BRANCH}"

# The Lakebase steps below need a CLI recent enough to have `databricks postgres`.
# In-workspace terminals can ship an older CLI, so fail fast with a clear message.
if ! databricks postgres --help >/dev/null 2>&1; then
  echo "This databricks CLI is too old for Lakebase (it lacks 'databricks postgres')." >&2
  echo "Upgrade the CLI in this terminal, then re-run." >&2
  exit 1
fi

echo "==> [1/4] Ensuring Lakebase project '${PROJECT}' exists"
# A soft-deleted project still answers get-project (with delete_time set) but
# cannot be used and blocks its own id until purge — detect that explicitly.
# `|| true` so an absent project (non-zero get-project) doesn't trip set -e/pipefail.
PROJ_JSON="$(databricks postgres get-project "${PROJECT_PATH}" ${AUTH[@]+"${AUTH[@]}"} -o json 2>/dev/null || true)"
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
    # Detection can miss (e.g. a different CLI version returns another JSON
    # shape), so create-project may run against a project that already exists.
    # Treat an "already exists" failure as success and slide — anything else is
    # a real error and aborts.
    echo "    creating project (this can take a couple of minutes)…"
    if ! CREATE_ERR="$(databricks postgres create-project "${PROJECT}" \
          --json '{"spec": {"display_name": "MDM Article Master"}}' \
          ${AUTH[@]+"${AUTH[@]}"} 2>&1)"; then
      if printf '%s' "${CREATE_ERR}" | grep -qiE 'already exist|AlreadyExists|RESOURCE_ALREADY_EXISTS|resource_conflict|conflict'; then
        echo "    project already exists — reusing it."
      else
        printf '%s\n' "${CREATE_ERR}" >&2
        exit 1
      fi
    fi ;;
esac

echo "==> [2/4] Discovering the database resource path"
DB_PATH="$(databricks postgres list-databases "${BRANCH_PATH}" ${AUTH[@]+"${AUTH[@]}"} -o json \
  | python3 -c 'import json,sys; dbs=json.load(sys.stdin) or []; print((dbs[0] if isinstance(dbs,list) else dbs.get("databases",[{}])[0]).get("name",""))')"
if [[ -z "${DB_PATH}" ]]; then
  echo "    could not resolve a database in ${BRANCH_PATH}." >&2
  exit 1
fi
echo "    using ${DB_PATH}"

# app.yaml holds LAKEBASE_ENDPOINT/LAKEBASE_PROJECT for the DEFAULT project id and
# a hardcoded UC_CATALOG. If a different --project and/or a --catalog was chosen,
# patch app.yaml just for this deploy and restore it afterwards (keeps the working
# tree clean). Empty args below mean "leave that value untouched".
PATCH_PROJECT=""
[[ "${PROJECT}" != "mdm-article-master" ]] && PATCH_PROJECT="${PROJECT}"
if [[ -n "${PATCH_PROJECT}" || -n "${CATALOG}" ]]; then
  cp app.yaml app.yaml.bak
  trap 'mv -f app.yaml.bak app.yaml 2>/dev/null || true' EXIT
  python3 - app.yaml "${PATCH_PROJECT}" "${CATALOG}" <<'PY'
import sys, re
path, proj, catalog = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(path).read()
if proj:
    s = re.sub(r'projects/[^/\s]+/branches/production/endpoints/primary',
               f'projects/{proj}/branches/production/endpoints/primary', s)
    s = re.sub(r'(name: LAKEBASE_PROJECT\n\s*value: )\S+', rf'\g<1>{proj}', s)
if catalog:
    s = re.sub(r'(name: UC_CATALOG\n\s*value: )\S+', rf'\g<1>"{catalog}"', s)
open(path, 'w').write(s)
PY
  echo "    (app.yaml patched for this deploy:${PATCH_PROJECT:+ project=${PATCH_PROJECT}}${CATALOG:+ catalog=${CATALOG}})"
fi

echo "==> [3/4] Deploying the bundle (target: ${TARGET})"
databricks bundle deploy -t "${TARGET}" \
  --var="postgres_project=${PROJECT}" \
  --var="postgres_database=${DB_PATH}" \
  ${AUTH[@]+"${AUTH[@]}"}

echo "==> [4/4] Starting the app"
databricks bundle run mdm_control_plane -t "${TARGET}" ${AUTH[@]+"${AUTH[@]}"} || true
URL="$(databricks apps get mdm-control-plane ${AUTH[@]+"${AUTH[@]}"} -o json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("url",""))' 2>/dev/null || true)"
echo
echo "Done. Open the app${URL:+: $URL}"
echo "First open seeds the schema + LFLR data (may take a few seconds while Lakebase wakes)."

#!/usr/bin/env bash
# Called from .github/workflows/nightly.yml when the nightly test
# suite (built against wirelog `main`) fails. Files a new
# `nightly-failure` issue on first occurrence; on subsequent failures
# the same day it appends a comment to the existing issue instead.
#
# Required env vars (provided by the workflow):
#   GH_TOKEN, GITHUB_SERVER_URL, GITHUB_REPOSITORY, GITHUB_RUN_ID
set -euo pipefail

LABEL="nightly-failure"
DATE_UTC="$(date -u +%Y-%m-%d)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
TITLE="Nightly: wirelog main breaks PyreWire (${DATE_UTC})"

# Ensure the label exists. `gh label create` errors when the label is
# already present; tolerate that path so the nightly job stays green.
gh label create "$LABEL" --color B60205 \
  --description "Nightly CI against wirelog main failed" \
  || true

# Look for an open issue with the same label. If found, just append.
existing=$(gh issue list --label "$LABEL" --state open --limit 1 \
                       --json number --jq '.[0].number // empty' \
                       || echo "")
if [ -n "$existing" ]; then
  gh issue comment "$existing" --body \
    "Nightly run failed again at ${TIMESTAMP}. Workflow run: ${RUN_URL}"
  echo "appended to existing issue #$existing"
  exit 0
fi

body="Nightly CI against wirelog \`main\` failed at ${TIMESTAMP}.

Workflow run: ${RUN_URL}

Likely causes:
- wirelog renamed or removed a public symbol — cross-check
  \`tests/data/wirelog_abi.txt\` against the latest \`wirelog/wirelog*.h\`
  headers (see PyreWire #40 / wirelog#841).
- wirelog changed a contract that PyreWire relied on (e.g. a return
  code, a struct layout, or an enum value).
- Transient infrastructure failure — re-run before triaging.

Triage steps:
1. Open the workflow log above and find the failing test names.
2. Diff \`wirelog/wirelog.h\` / \`wirelog/wirelog-*.h\` between the last
   tagged release and \`main\`.
3. Update PyreWire bindings or open an upstream issue accordingly.
4. Once fixed, close this issue (subsequent failures will refile)."

gh issue create --title "$TITLE" --label "$LABEL" --body "$body"
echo "created new $LABEL issue"

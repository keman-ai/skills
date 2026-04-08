#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_NAME="chatgpt-pro"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

info() {
  echo "INFO: $*"
}

require_bin() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

parse_workspace_dir() {
  local raw
  raw="$(openclaw skills list --json 2>&1)" || fail "unable to query OpenClaw skills list"
  python3 -c '
import json
import sys

raw = sys.stdin.read()
start = raw.find("{")
if start < 0:
    raise SystemExit("no JSON object found in openclaw output")
obj = json.loads(raw[start:])
workspace = obj.get("workspaceDir")
if not workspace:
    raise SystemExit("workspaceDir missing from openclaw output")
print(workspace)
' <<<"$raw"
}

copy_skill_tree() {
  local src="$1"
  local dst="$2"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '.DS_Store' \
      --exclude '.playwright-cli/' \
      --exclude 'output/' \
      --exclude 'node_modules/' \
      "$src/" "$dst/"
    return
  fi

  mkdir -p "$dst"
  tar \
    --exclude='.DS_Store' \
    --exclude='.playwright-cli' \
    --exclude='output' \
    --exclude='node_modules' \
    -cf - -C "$src" . | tar -xf - -C "$dst"
}

require_bin openclaw
require_bin python3

WORKSPACE_DIR="${OPENCLAW_WORKSPACE_DIR:-$(parse_workspace_dir)}"
[[ -n "$WORKSPACE_DIR" ]] || fail "resolved empty OpenClaw workspace directory"

TARGET_ROOT="$WORKSPACE_DIR/skills"
TARGET_DIR="$TARGET_ROOT/$SKILL_NAME"
BACKUP_ROOT="$WORKSPACE_DIR/.skill-backups/$SKILL_NAME"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/chatgpt-pro-install.XXXXXX")"
TMP_DIR="$TMP_ROOT/$SKILL_NAME"
BACKUP_DIR=""

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

mkdir -p "$TARGET_ROOT"
mkdir -p "$BACKUP_ROOT"
copy_skill_tree "$ROOT" "$TMP_DIR"

while IFS= read -r legacy_backup; do
  [[ -n "$legacy_backup" ]] || continue
  info "relocating legacy backup out of skills root: $legacy_backup"
  mv "$legacy_backup" "$BACKUP_ROOT/$(basename "$legacy_backup")"
done < <(find "$TARGET_ROOT" -maxdepth 1 -mindepth 1 -type d -name "${SKILL_NAME}.bak.*" -print)

if [[ -e "$TARGET_DIR" ]]; then
  BACKUP_DIR="$BACKUP_ROOT/${SKILL_NAME}.bak.$(date +%Y%m%d-%H%M%S)"
  info "existing install found; moving it to $BACKUP_DIR"
  mv "$TARGET_DIR" "$BACKUP_DIR"
fi

mv "$TMP_DIR" "$TARGET_DIR"
info "installed $SKILL_NAME to $TARGET_DIR"

openclaw skills info "$SKILL_NAME" >/dev/null 2>&1 || fail "OpenClaw does not recognize $SKILL_NAME after install"

python3 - <<'PY' "$WORKSPACE_DIR" "$TARGET_DIR"
from pathlib import Path
import sys

workspace = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
try:
    target.relative_to(workspace)
except ValueError as exc:
    raise SystemExit(f"installed target escaped workspace root: {target}") from exc
print(f"PASS: target is inside workspace root: {target}")
PY

if [[ -n "$BACKUP_DIR" ]]; then
  info "backup kept at $BACKUP_DIR"
fi

echo "PASS: OpenClaw recognizes $SKILL_NAME"

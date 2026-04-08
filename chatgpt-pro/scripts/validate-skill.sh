#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

require_file() {
  local rel="$1"
  [[ -f "$ROOT/$rel" ]] || fail "missing required file: $rel"
}

require_pattern() {
  local pattern="$1"
  local rel="$2"
  local message="$3"
  rg -q --multiline "$pattern" "$ROOT/$rel" || fail "$message ($rel)"
}

reject_pattern() {
  local pattern="$1"
  local rel="$2"
  local message="$3"
  if rg -q --multiline "$pattern" "$ROOT/$rel"; then
    fail "$message ($rel)"
  fi
}

require_file "SKILL.md"
require_file "INSTALL.md"
require_file "scripts/install-openclaw-skill.sh"
require_file "references/backend-mapping.md"
require_file "references/selectors.md"
require_file "references/troubleshooting.md"
require_file "references/consent-scripts.md"
require_file "evals/smoke.md"

require_pattern '^name: chatgpt-pro$' "SKILL.md" "missing skill name"
require_pattern '^description: .+$' "SKILL.md" "missing skill description"
require_pattern '^version: [0-9]+\.[0-9]+\.[0-9]+$' "SKILL.md" "missing top-level skill version"
require_pattern '^metadata:$' "SKILL.md" "missing metadata block"
require_pattern '^  openclaw:$' "SKILL.md" "missing openclaw metadata"
require_pattern '^  claude_code:$' "SKILL.md" "missing claude_code metadata"
require_pattern '^    allowed_tools:$' "SKILL.md" "missing claude_code allowed_tools"
require_pattern '^trigger_mode: manual_only$' "SKILL.md" "missing manual_only trigger mode"
reject_pattern '^allowed-tools:' "SKILL.md" "legacy top-level allowed-tools should not be present"

skill_version="$(sed -n 's/^version: \([0-9][0-9.]*\)$/\1/p' "$ROOT/SKILL.md" | head -n1)"
[[ -n "$skill_version" ]] || fail "unable to parse skill version from SKILL.md"

require_pattern "Version: $skill_version" "SKILL.md" "inline version comment should match top-level version"

for rel in \
  "references/backend-mapping.md" \
  "references/selectors.md" \
  "references/troubleshooting.md" \
  "references/consent-scripts.md" \
  "evals/smoke.md"
do
  require_pattern "$skill_version" "$rel" "version mismatch: expected $skill_version"
done

require_pattern 'shared_page_model_badge' "references/selectors.md" "missing shared page model badge selector"
require_pattern 'share_copy_link_button' "references/selectors.md" "missing copy-link share selector"
require_pattern '[Aa]nyone with the link can read the entire conversation' "references/consent-scripts.md" "missing public-share warning"
require_pattern './scripts/validate-skill.sh' "evals/smoke.md" "smoke tests must mention the local validation step"
require_pattern './scripts/install-openclaw-skill.sh' "INSTALL.md" "install guide must mention the OpenClaw installer script"
require_pattern 'Prompt Ref:  sha256=<first 8>, len=<N>' "SKILL.md" "phase F must output a prompt fingerprint instead of prompt contents"
require_pattern 'Prompt Ref: sha256=b9ab5b7f, len=5' "evals/smoke.md" "smoke expectation must match prompt fingerprint output"
require_pattern 'capture_response_body' "SKILL.md" "skill must document network-response share extraction"
require_pattern 'responsebody' "references/backend-mapping.md" "backend mapping must mention OpenClaw responsebody"
require_pattern 'Never print `https://chatgpt\.com/share/<conv_id>`' "SKILL.md" "skill must forbid conv_id being used as share_id"
require_pattern '`--resume <conv_id>` is a \*\*share-recovery\*\* flow' "SKILL.md" "skill must define resume mode as share-only"
require_pattern 'treat that command itself as explicit consent to recover the public share link' "SKILL.md" "resume mode must skip the second share consent gate"
require_pattern 'When there are no warnings, print `none`' "SKILL.md" "phase F warnings field must have an explicit none case"
require_pattern 'Resume mode must never print `https://chatgpt\.com/share/<conv_id>`' "evals/smoke.md" "smoke spec must cover the conv_id/share_id regression"

reject_pattern 'read_clipboard' "SKILL.md" "clipboard fallback must not exist in skill workflow"
reject_pattern 'read_clipboard' "references/backend-mapping.md" "clipboard fallback must not exist in backend mapping"

todo_hits="$(rg -n ':\s+__TODO_SPIKE__\b' "$ROOT" --glob '!**/references/selectors.md' --glob '!**/scripts/validate-skill.sh' || true)"
[[ -z "$todo_hits" ]] || fail "raw spike selector placeholders leaked outside references/selectors.md"$'\n'"$todo_hits"

pass "skill package structure looks consistent (version $skill_version)"

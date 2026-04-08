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
require_pattern '^user-invocable: true$' "SKILL.md" "skill should be explicitly user-invocable for OpenClaw slash commands"
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
require_pattern './scripts/validate-skill.sh' "evals/smoke.md" "smoke tests must mention the local validation step"
require_pattern './scripts/install-openclaw-skill.sh' "INSTALL.md" "install guide must mention the OpenClaw installer script"
require_pattern 'Prompt Ref:  sha256=<first 8>, len=<N>' "SKILL.md" "phase F must output a prompt fingerprint instead of prompt contents"
require_pattern 'Prompt Ref: sha256=b9ab5b7f, len=5' "evals/smoke.md" "smoke expectation must match prompt fingerprint output"
require_pattern 'capture_response_body' "SKILL.md" "skill must document network-response share extraction"
require_pattern 'responsebody' "references/backend-mapping.md" "backend mapping must mention OpenClaw responsebody"
require_pattern 'Never print `https://chatgpt\.com/share/<conv_id>`' "SKILL.md" "skill must forbid conv_id being used as share_id"
require_pattern '`--resume <conv_id>` is a \*\*share-recovery\*\* flow' "SKILL.md" "skill must define resume mode as share-only"
require_pattern 'When there are no warnings, print `none`' "SKILL.md" "phase F warnings field must have an explicit none case"
require_pattern 'dedicated new tab' "SKILL.md" "skill must describe fresh-run tab selection as a dedicated new tab"
require_pattern 'Fresh .*never ask the user which existing tab to use' "SKILL.md" "fresh runs must never ask the user to pick an old tab"
require_pattern 'Use the "chatgpt-pro" skill for this request' "SKILL.md" "skill must recognize the OpenClaw slash-wrapper form"
require_pattern 'User input:' "SKILL.md" "skill must recognize the OpenClaw wrapped user input form"
require_pattern 'Do \*\*not\*\* answer the raw `User input:` locally' "SKILL.md" "skill must forbid answering the wrapped raw prompt locally"
require_pattern 'Within the next few tool calls, do these setup actions in order:' "SKILL.md" "skill must define the OpenClaw fast-path setup order"
require_pattern '`browser open https://chatgpt\.com/`' "SKILL.md" "skill must require dedicated ChatGPT tab creation on OpenClaw fresh runs"
require_pattern 'the \*\*only\*\* valid composer target is a node whose role is `textbox`' "SKILL.md" "skill must require textbox-only composer targeting on OpenClaw"
require_pattern 'Element "<ref>" not found or not visible' "SKILL.md" "skill must recover from wrong-target OpenClaw composer refs"
require_pattern 'Fresh-run reset failed; refusing to reuse an existing conversation\.' "SKILL.md" "skill must refuse stale conversation reuse on fresh runs"
require_pattern 'PROMPT-MISMATCH' "SKILL.md" "skill must abort public share generation when the visible prompt summary mismatches the requested prompt"
require_pattern 'Treat an explicit `/chatgpt-pro <prompt>` invocation, the OpenClaw wrapper form `Use the "chatgpt-pro" skill for this request \.\.\. User input: <prompt>`, or an explicit user instruction to use ChatGPT Pro for a specific prompt and return a shareable result, as sufficient consent' "SKILL.md" "skill must treat explicit invocation and the OpenClaw wrapper as quota/account/share consent"
require_pattern 'The only normal runtime consent gates are A2 / D2' "SKILL.md" "skill must limit normal runtime consent gates to A2/D2"
require_pattern 'On a manually logged-in browser profile, an explicit fresh run must \*\*never\*\* emit legacy account/send prompts such as `即将使用此浏览器 Profile 当前登录的 ChatGPT 账号。继续？`' "SKILL.md" "skill must explicitly forbid the legacy browser-profile gate on logged-in fresh runs"
require_pattern 'If the fresh thread tab disappears before any submit evidence exists' "SKILL.md" "skill must define the narrow pre-submit tab-loss recovery window"
require_pattern 'Do not emit an A5 confirmation gate' "SKILL.md" "skill must make A5 silent"
require_pattern 'do \*\*not\*\* ask `即将使用此浏览器 Profile 当前登录的 ChatGPT 账号。继续？`' "SKILL.md" "skill must retire the legacy browser-profile prompt in A5"
require_pattern 'emit a second submit confirmation gate' "SKILL.md" "skill must make C4 silent"
require_pattern 'do \*\*not\*\* ask `即将用 ChatGPT Pro 5\.4（进阶思考）提交。消耗 1 次 Pro 配额。继续？`' "SKILL.md" "skill must retire the legacy submit prompt in C4"
require_pattern 'guest/auth CTAs such as `登录`, `免费注册`, `Log in`, or `Sign up`' "SKILL.md" "skill must hard-stop on guest/login CTA pages"
require_pattern 'Never click login/signup/auth buttons' "SKILL.md" "skill must forbid auth-surface automation"
require_pattern 'Public-share work is illegal until a real `/c/<conv_id>` exists' "SKILL.md" "skill must forbid premature share work"
require_pattern 'Enter Phase E only when `share_ready=true`' "SKILL.md" "skill must hard-gate share flow on completion state"
require_pattern 'Fresh default runs that need a public share link must never submit from .*temporary-chat=true' "SKILL.md" "skill must forbid spending quota inside unexpected temporary chat"
require_pattern '\*\*A4c\. Unexpected temporary-chat escape' "SKILL.md" "skill must define pre-submit temporary-chat escape behavior"
require_pattern 'never type or submit while the URL still contains `temporary-chat=true`' "SKILL.md" "skill must hard-stop prompt entry on unexpected temporary chat"
require_pattern 'a direct local answer such as `ZENAS-\.\.\.`' "SKILL.md" "skill must forbid local completion of wrapped slash-wrapper input"
require_pattern 'the next substantive action must be a browser step from the OpenClaw fast path' "SKILL.md" "skill must force wrapped invocations into browser workflow"
require_pattern 'On a fresh-home page \(`/` or `/\?\.\.\.`\), only `composer` and `model_selector_button` are required for B-1' "SKILL.md" "skill must skip share-button drift checks on empty fresh-home pages"
require_pattern 'If the cached OpenClaw composer ref times out, becomes stale, or returns an `aria-ref=\.\.\.` lookup failure' "SKILL.md" "skill must recover from stale OpenClaw composer refs"
require_pattern 'prefer the composer ref from the freshest role snapshot' "SKILL.md" "skill must prefer refreshed role refs on recovered fresh-home pages"
require_pattern 'prefer the \*\*header-level share button\*\*' "SKILL.md" "skill must prefer the conversation-header share control when duplicate share buttons exist"
require_pattern 'Never use a share button inside the assistant reply action row' "SKILL.md" "skill must forbid using the reply-action-row share control"
require_pattern 'matched 2 elements' "SKILL.md" "skill must document the duplicate-share recovery path"
require_pattern 'shell controls such as `跳至内容` / `Skip to content`' "SKILL.md" "skill must define the OpenClaw degenerate-snapshot guard"
require_pattern 'Never click arbitrary tiny refs like `e1`, `e2`, or `e3`' "SKILL.md" "skill must forbid using tiny refs from degenerate share snapshots"
require_pattern 'waiting for locator\('\''aria-ref=\.\.\.'\''\)' "SKILL.md" "skill must mention aria-ref timeout failures in degenerate share snapshots"
require_pattern 'times out on a tiny ref' "SKILL.md" "skill must recover from degenerate share-snapshot click timeouts"
require_pattern '`snapshot --format aria` refs such as `ax137` are read-only diagnostic refs' "SKILL.md" "skill must forbid using OpenClaw aria refs for write actions"
require_pattern 'If an OpenClaw click fails with `waiting for locator\('\''aria-ref=\.\.\.'\''\)`' "SKILL.md" "skill must recover from aria-ref write failures"
require_pattern 'No leading prose, no trailing prose, no paraphrase' "references/consent-scripts.md" "consent scripts must forbid freeform wrappers"
require_pattern 'Reply with exactly one option label\.' "references/consent-scripts.md" "consent scripts must define the plain-text fallback reply contract"
require_pattern 'the skill no longer emits per-run A5, C4, E2, or E8 confirmation dialogs' "references/consent-scripts.md" "consent scripts must retire A5/C4/E2/E8"
require_pattern 'A2 and D2 remain the only normal interactive gates' "references/consent-scripts.md" "consent scripts must document the remaining interactive gates"
require_pattern 'The following legacy prompts are forbidden on explicit fresh runs' "references/consent-scripts.md" "consent scripts must explicitly forbid the legacy logged-in account/send prompts"
require_pattern '/skill chatgpt-pro <prompt>' "evals/smoke.md" "smoke spec must document the OpenClaw generic skill entrypoint"
require_pattern 'Resume mode must never print `https://chatgpt\.com/share/<conv_id>`' "evals/smoke.md" "smoke spec must cover the conv_id/share_id regression"
require_pattern 'must \*\*not\*\* ask which existing `chatgpt\.com` tab to use' "evals/smoke.md" "smoke spec must forbid fresh-run tab-choice prompts"
require_pattern 'No A5/C4/E2/E8 prompt appears at all during the run' "evals/smoke.md" "smoke spec must cover removal of the old A5/C4/E2/E8 prompts"
require_pattern 'The exact legacy account/send prompts do not appear at any point in the run' "evals/smoke.md" "smoke spec must require that the legacy account/send prompts never appear"
require_pattern 'Fresh OpenClaw run must not stall after status/tabs' "evals/smoke.md" "smoke spec must cover the status-tabs stall regression"
require_pattern 'A transcript that stops at `browser status` / `browser tabs` with no `chatgpt\.com` tab is a FAIL' "evals/smoke.md" "smoke spec must fail setup-only stalls before tab creation"
require_pattern 'missing `share_button` there must not be treated as DOM drift' "evals/smoke.md" "smoke spec must cover empty-thread share-button false positives"
require_pattern 'Recovery lands on guest/login surface' "evals/smoke.md" "smoke spec must cover guest/login recovery failures"
require_pattern 'No browser action targets a login/signup/auth CTA' "evals/smoke.md" "smoke spec must forbid auth-surface clicks"
require_pattern 'Composer stale aria-ref after recovery' "evals/smoke.md" "smoke spec must cover stale composer-ref recovery"
require_pattern 'A role snapshot is taken after the stale aria-ref timeout' "evals/smoke.md" "smoke spec must require the role-snapshot composer retry"
require_pattern 'only a `textbox` composer ref may be clicked or typed into' "evals/smoke.md" "smoke spec must require textbox-only composer targeting"
require_pattern 'No A5 account-confirmation gate, no C4 submit-confirmation gate, no E2 share-confirmation gate, and no E8 keep/revoke gate should appear' "evals/smoke.md" "smoke spec must explicitly forbid old confirmation prompts"
require_pattern 'Premature share step on fresh-home page' "evals/smoke.md" "smoke spec must cover premature share-step regression"
require_pattern 'Any share-related prompt or prose shown before a `/c/<conv_id>` exists is a FAIL' "evals/smoke.md" "smoke spec must forbid share work before conv creation"
require_pattern 'Fresh default run lands on temporary chat' "evals/smoke.md" "smoke spec must cover unexpected temporary-chat recovery"
require_pattern 'No Enter press happens while the page is still in temporary chat' "evals/smoke.md" "smoke spec must forbid temporary-chat submission on public-share runs"
require_pattern 'Slash-wrapper must not answer locally' "evals/smoke.md" "smoke spec must cover wrapped-invocation local-answer regression"
require_pattern 'The first substantive post-read action must be a browser step' "evals/smoke.md" "smoke spec must forbid local completion after wrapped SKILL read"
require_pattern 'Completed page has duplicate share buttons' "evals/smoke.md" "smoke spec must cover the duplicate-share-button regression"
require_pattern 'must click the header-level conversation share' "evals/smoke.md" "smoke spec must require the header share control on duplicate-share pages"
require_pattern 'The retried click/type uses a writable interactive ref namespace' "evals/smoke.md" "smoke spec must require writable refs after aria-ref failures"
require_pattern 'Share dialog snapshot degrades to `跳至内容`' "evals/smoke.md" "smoke spec must cover degenerate share-dialog snapshots"
require_pattern 'does not click arbitrary tiny refs like `e1`, `e2`, or `e3`' "evals/smoke.md" "smoke spec must forbid tiny-ref clicks from degenerate share snapshots"
require_pattern 'Prefer the header-level share button' "references/selectors.md" "selectors must document the header-level share preference"
require_pattern '回复操作' "references/selectors.md" "selectors must document the reply-action-row share exclusion"
require_pattern 'temporary_chat_exit_button' "references/selectors.md" "selectors must document the temporary-chat escape button"
require_pattern '关闭临时聊天' "references/selectors.md" "selectors must pin the observed temporary-chat exit button"
require_pattern 'shell-only content such as `跳至内容` / `Skip to content`' "references/selectors.md" "selectors must document degenerate OpenClaw snapshots"
require_pattern 'matched 2 elements' "references/troubleshooting.md" "troubleshooting must cover duplicate-share ambiguity"
require_pattern '`ax\.\.\.` refs as read-only' "references/troubleshooting.md" "troubleshooting must cover aria-ref write failures"
require_pattern 'stopped after `browser status` / `browser tabs` and never opened ChatGPT' "references/troubleshooting.md" "troubleshooting must cover the status-tabs stall regression"
require_pattern 'Element \\"e18\\" not found or not visible' "references/troubleshooting.md" "troubleshooting must cover wrong-target composer refs"
require_pattern 'the exact legacy prompts `即将使用此浏览器 Profile 当前登录的 ChatGPT 账号。继续？` and `即将用 ChatGPT Pro 5\.4（进阶思考）提交。消耗 1 次 Pro 配额。继续？` are both regressions' "references/troubleshooting.md" "troubleshooting must call the legacy account/send prompts regressions"
require_pattern 'landed on .*temporary-chat=true.*临时聊天' "references/troubleshooting.md" "troubleshooting must cover unexpected temporary-chat landing"
require_pattern 'answered the prompt locally' "references/troubleshooting.md" "troubleshooting must cover wrapped local-answer regression"
require_pattern 'snapshot collapsed to `跳至内容` / `Skip to content`' "references/troubleshooting.md" "troubleshooting must cover degenerate share-dialog snapshots"

reject_pattern 'read_clipboard' "SKILL.md" "clipboard fallback must not exist in skill workflow"
reject_pattern 'read_clipboard' "references/backend-mapping.md" "clipboard fallback must not exist in backend mapping"
reject_pattern 'Generate share link' "references/consent-scripts.md" "share confirmation gate must not remain active"
reject_pattern 'Keep public' "references/consent-scripts.md" "post-share keep/revoke gate must not remain active"

todo_hits="$(rg -n ':\s+__TODO_SPIKE__\b' "$ROOT" --glob '!**/references/selectors.md' --glob '!**/scripts/validate-skill.sh' || true)"
[[ -z "$todo_hits" ]] || fail "raw spike selector placeholders leaked outside references/selectors.md"$'\n'"$todo_hits"

pass "skill package structure looks consistent (version $skill_version)"

# Troubleshooting

> Common failures, symptoms, and fixes.
> **Skill version:** 0.3.7

---

## "Selectors not yet captured — skill will refuse to run"

**Cause:** First use. `references/selectors.md` contains `__TODO_SPIKE__` placeholders.

**Fix:** Run `/chatgpt-pro --spike` with a logged-in chatgpt.com tab open in Chrome.

---

## "The agent keeps talking about `__TODO_SPIKE__` instead of running"

**Cause:** An older build treated every current-backend placeholder as fatal, including modal-only selectors that are optional on the verified OpenClaw happy path.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.1 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. On OpenClaw, if `advanced_thinking_active_indicator` is already visible after `new_thread()`, the skill should skip the modal-only selectors and continue to submit/share normally.
4. If `advanced_thinking_active_indicator` is **not** visible, that is a real blocker — run `/chatgpt-pro --respike`.

---

## "`browser failed: tab not found` after I picked a tab or after submit"

**Cause:** OpenClaw kept a stale browser handle after a user-confirmation boundary or after a tab was replaced. The underlying `chatgpt.com` page was still recoverable, but the old `tabId` was not.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.2 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. For minimal OpenClaw smoke, keep exactly one logged-in `chatgpt.com` tab open before you invoke `/chatgpt-pro`.
4. If multiple tabs are open, the skill should now rebind by the user-chosen URL path instead of continuing with a stale tab handle.
5. If a conversation already exists, reopening `https://chatgpt.com/c/<conv_id>` is sufficient; the next run can recover from that page.

---

## "Share step said copied / 已复制链接, but the final report showed no public URL"

**Cause:** The browser action succeeded, but an older build treated the copy-link toast as good enough and never promoted the actual `https://chatgpt.com/share/<uuid>` into Phase F output.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.4 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Re-run from a fresh OpenClaw WebUI session if possible.
4. The fixed build treats clipboard-only evidence as insufficient. It must print the concrete share URL, usually from `responsebody("https://chatgpt.com/backend-api/share/create")` or, on current ChatGPT, from the observed `PATCH /backend-api/share/<uuid>` request URL.
5. On some OpenClaw WebUI runs, the request log can still be empty even though the copy succeeded. If eval is available, immediately try `navigator.clipboard.readText()` on the ChatGPT page and accept it only when it returns the full `https://chatgpt.com/share/<uuid>` string. This matched a live zenas-host run on 2026-04-08.
6. If the run still ends without a printed URL, treat it as a share-extraction failure and fall back to the private `chatgpt.com/c/<conv_id>` link instead of claiming public-share success.

---

## "`https://chatgpt.com/share/<conv_id>` returned 404"

**Cause:** The run confused the conversation id with the public share id. These are different identifiers.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.4 or later.

## "`--resume` ended with `share/<conv_id>` or with 'you can continue chatting'"

**Cause:** The model completed the browser steps but drifted out of the Phase E/F contract. This showed up in a live OpenClaw WebUI run on 2026-04-07: the browser really opened the share dialog, but the final report still printed `https://chatgpt.com/share/<conv_id>` or generic helper prose instead of a validated public URL.

**Fix:**
1. Treat `--resume` as a share-recovery state machine, not as a normal assistant reply.
2. Require a concrete `https://chatgpt.com/share/<uuid>` string before claiming public-share success.
3. If that string is unavailable, emit `PRIVATE-ONLY` and the private `chatgpt.com/c/<conv_id>` note.
4. Never append follow-up guidance like "继续提问" after Phase F.

## "`--resume` asked for another share confirmation and the reply stayed queued"

**Cause:** The skill asked a second conversational confirmation even though the user had already typed the exact slash command `/chatgpt-pro --resume <conv_id>`. In OpenClaw WebUI, that follow-up reply can remain queued instead of being consumed by the active turn.

**Fix:**
1. Treat exact `--resume` invocations as already share-authorized.
2. Skip the E2 confirmation gate for that mode.
3. Proceed directly to Phase E share recovery and Phase F final report.

## "`--resume` recovered the right share URL but still printed extra prose / missing fields"

**Cause:** The browser recovery succeeded, but Phase F was not treated as a strict template. A live OpenClaw run on 2026-04-07 showed a correct share URL with missing `Duration`, `Prompt Ref`, and `Warnings`, plus extra prose around the field block.

**Fix:**
1. Treat the six Phase F fields as mandatory, even on `--resume`.
2. When no warnings exist, print `none`.
3. Do not prepend headings like `恢复结果`.
4. Do not append explanatory prose after the field block.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Recover the public URL only from one of these sources:
   - the exact `POST /backend-api/share/create` response body,
   - a share slug/id in that response body, or
   - the observed `PATCH /backend-api/share/<uuid>` request URL.
4. Do not probe `https://chatgpt.com/share/<conv_id>` as a fallback. If no real `share_id` is available, report `PRIVATE-ONLY` instead.

---

## "ChatGPT DOM has drifted. Please run /chatgpt-pro --respike"

**Cause:** The health check (Phase B-1) found one of the three anchor elements missing. ChatGPT likely shipped a frontend change.

**Fix:**
1. Manually open chatgpt.com in Chrome, confirm you can use it normally.
2. Run `/chatgpt-pro --respike`.
3. If the spike captures new selectors successfully → continue.
4. If the spike fails (elements not found) → ChatGPT's model selector flow has changed substantially. Open an issue with the diff from old vs new spike snapshots.

---

## "About to use ChatGPT Pro quota from account X@Y — Continue? / Switch account"

**Cause:** Phase A5. The skill detected a specific account and wants confirmation before burning quota.

**Not a bug** — this is the cross-account protection. If X@Y is not the account you want:
1. Choose "Switch account (stop)"
2. Manually switch your Chrome profile or log out / log in
3. Re-run `/chatgpt-pro`

---

## "Account cross-check mismatch — possible tampering"

**Cause:** The sidebar DOM and `/backend-api/me` returned different emails. This is rare and indicates either:
- A stale cached DOM after a logout/login
- A browser extension injecting content into chatgpt.com
- A genuine attack

**Fix:**
1. STOP. Do not use the skill.
2. Fully log out of chatgpt.com, close the tab, reopen, log back in.
3. Disable browser extensions one by one to find the culprit if the error persists.
4. If still failing after a clean profile → contact the skill maintainer with a redacted repro.

---

## "Composer not found" / "Cannot focus composer"

**Cause (Claude Code):** `find()` returned the outer form or a placeholder node instead of the contenteditable.

**Fix:**
1. Check `references/selectors.md` → `composer.claude_code.primary` — is it a pinned CSS?
2. If no pinned CSS, Phase C is using `find()` which is fragile. Run `--respike` to capture a pinned CSS selector.

**Cause (OpenClaw):** The composer's snapshot role is `generic` instead of `textbox`.

**Fix:** This is a known fragility. Check `selectors.md` → `composer_role_exposure.openclaw.snapshot_role`. If it says `generic`, the skill falls back to placeholder-text matching at ~80% success rate. Try once; if it fails, consider running with Claude Code backend instead.

---

## "Pro Advanced thinking toggle disappeared"

**Cause:** ChatGPT A/B-tested away the "思考时长" modal or renamed "进阶" to something else.

**Fix:**
1. Manually verify in your Chrome that you can still select Pro Advanced through the UI.
2. If yes → the UI moved. Run `--respike` to capture the new flow.
3. If no → ChatGPT removed the feature for your account. This skill cannot help — either the feature is gone globally or you're no longer in the test group.

---

## "Share link generation failed (network slow or disabled)"

**Cause:** Phase E used the current copy-link dialog or the legacy create-link flow, but neither surfaced a usable share URL within the timeout.

**Fix:**
1. Check your internet connection.
2. Manually try to share the same conversation through the UI.
3. If the dialog only shows `复制链接`, prefer the OpenClaw network path instead of waiting for an input that may never appear.
4. If `responsebody("**/backend-api/share/**")` returns only discoverability JSON and no URL, inspect `openclaw browser requests --filter share` and extract the UUID from the observed `PATCH /backend-api/share/<uuid>` request. This matched the live ChatGPT flow on 2026-04-07.
5. If the request log is empty but eval is available, immediately try `navigator.clipboard.readText()` on the ChatGPT page. On zenas-host (2026-04-08), that clipboard read returned the correct public share URL even though the agent-visible request log was empty.
6. If you can target the create request exactly, prefer `responsebody("https://chatgpt.com/backend-api/share/create")` over a broad glob.
7. If manual share works, re-run with a longer timeout (edit `SKILL.md` Phase E5/E6, default 15s → try 30s).
8. If manual share still fails → ChatGPT may have disabled sharing for your account / region / conversation type.
9. Fall back: use the private `chatgpt.com/c/<conv_id>` link shown in Phase F output.

---

## "[skills] Skipping skill path that resolves outside its configured root."

**Cause:** OpenClaw found a symlinked skill that points outside the active workspace root and intentionally refused to load it.

**Fix:**
1. Do **not** symlink `chatgpt-pro` from another repo into OpenClaw.
2. Install a real copy inside `~/.openclaw/workspace/skills/chatgpt-pro`.
3. Use `./scripts/install-openclaw-skill.sh` from this repo to perform the copy safely.
4. Re-run `openclaw skills info chatgpt-pro` to confirm the skill is recognized.

---

## "openclaw browser ... gateway closed (1006 abnormal closure)"

**Cause:** The OpenClaw gateway is not running, or the CLI cannot reach the configured local gateway port.

**Fix:**
1. Start or restart the gateway using your normal OpenClaw workflow.
2. If you manage it manually, `openclaw gateway --force` is the fastest recovery path.
3. Re-run `openclaw browser status` and only continue once it responds normally.
4. If `browser` still fails, run `openclaw doctor` before blaming the skill.

---

## "Top banner still says ChatGPT, not Pro"

**Cause:** This is normal on the 2026-04-07 zh-CN build. The real model state is exposed in the selector dropdown row, not necessarily in the top banner label.

**Fix:**
1. Open the model selector.
2. Confirm the `Pro 研究级智能模型` row shows selected.
3. Confirm `进阶专业` is visible if Advanced is required.
4. Treat `current_model_label` as optional on this UI instead of forcing a banner text match.

---

## "15-minute timeout — still thinking..."

**Cause:** Your Pro Advanced prompt is genuinely taking >15 minutes. Not a bug.

**Fix:**
- Choose "Wait 5 more" in the dialog up to the 30-minute dead-man ceiling.
- If you want the skill to give up cleanly without stopping the run on chatgpt.com → "Exit (leave run on chatgpt)". Then later use `/chatgpt-pro --resume <conv_id>` to pick up just the share-link step.

---

## "30-minute dead-man — auto-exit"

**Cause:** No user response to the 10-min or 15-min `AskUserQuestion` for 30 total minutes (e.g. you walked away from the computer).

**What happened:**
- The skill exited cleanly without touching the chatgpt.com tab.
- The run on chatgpt.com is STILL executing (not stopped).
- `.in-flight.json` was written with the conv_id so your next invocation can recover.

**Fix:** Run `/chatgpt-pro --resume <conv_id>` to skip Phase A–D and just do Phase E (share link extraction). If you don't know the conv_id, check `.in-flight.json` in the skill directory.

---

## "Cloudflare challenge / bot verification"

**Cause:** chatgpt.com's Cloudflare fingerprinted your session as automated.

**Fix:**
1. STOP the skill.
2. Manually solve the Cloudflare challenge in Chrome.
3. Verify you can load chatgpt.com manually.
4. Re-run `/chatgpt-pro`.

**Do NOT** try to have the skill solve the challenge — that's explicitly prohibited by Claude's policies and will just get you rate-limited further.

---

## "ToS popup appeared — STOP"

**Cause:** ChatGPT is showing a new Terms of Service / Privacy Policy agreement.

**Fix:**
1. Manually read and accept the ToS in your browser.
2. Re-run `/chatgpt-pro`.

The skill will NEVER auto-accept a ToS — that's a user decision.

---

## "Session expired — please re-login"

**Cause:** Mid-run, your chatgpt.com session cookie expired or was invalidated.

**Fix:** Log back in manually, then re-run.

---

## "No compatible browser backend found"

**Cause:** Neither `mcp__Claude_in_Chrome__*` nor `browser` tool is available.

**Fix:**
- **Claude Code:** Install the Claude in Chrome MCP extension. See https://claude.ai/code for setup.
- **OpenClaw:** The `browser` tool is built-in to OpenClaw. Verify your OpenClaw version is current and the tool is not disabled in config. Run `openclaw browser status`.

---

## "Both backends detected — ambiguous"

**Cause:** Both `mcp__Claude_in_Chrome__*` and `browser` tools are available in the same session. The skill refuses to silently pick one.

**Fix:** Choose one and disable the other for the session, or answer the `AskUserQuestion` the skill will show.

---

## "evaluate disabled" warning (OpenClaw)

**Cause:** OpenClaw config has `browser.evaluateEnabled=false`.

**Behavior:** The skill falls back to the evaluate-free path for Phase B–E. Phase D becomes slower (~3s polls instead of ~2s observer), and Phase C3 loses its last-resort `execCommand` fallback.

**Fix:** Either:
- Accept the slower path (it works, just less efficient).
- Enable `browser.evaluateEnabled=true` in OpenClaw config if you trust the sites you visit.

---

## "Quota exhausted"

**Cause:** ChatGPT returned a quota-exceeded toast after you submitted.

**Behavior:** The skill detects the toast in Phase C/D and stops without attempting a share link.

**Fix:** Wait for your quota to reset (usually weekly for Pro Advanced). The skill cannot work around this.

---

## Extensions or dev tools interfering

If things feel weirdly broken, try:
1. Open chatgpt.com in a fresh Chrome profile with no extensions.
2. Close DevTools (it changes some iframe behavior).
3. Disable any userscripts targeting chatgpt.com.

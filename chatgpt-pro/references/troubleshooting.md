# Troubleshooting

> Common failures, symptoms, and fixes.
> **Skill version:** 0.3.32

---

## "Selectors not yet captured — skill will refuse to run"

**Cause:** First use. `references/selectors.md` contains `__TODO_SPIKE__` placeholders.

**Fix:** Run `/chatgpt-pro --spike` with a logged-in chatgpt.com tab open in Chrome.

---

## "The agent said "I'll start now" / "准备好了吗？我将开始执行" instead of showing a real confirmation gate"

**Cause:** The run drifted out of the `AskUserQuestion` contract and paraphrased a consent gate as ordinary assistant prose. On OpenClaw WebUI this can snowball into duplicate warnings, missing pauses, or a fake self-acknowledgement such as `✅ 确认继续` before the user ever answers.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.9 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start from a fresh OpenClaw WebUI session.
4. Treat A2 / D2 as valid only when they appear exactly as the scripts in `references/consent-scripts.md`, with no leading or trailing assistant prose.
5. If a run emits a free-text acknowledgement before the user answers, stop that run and start a fresh one; do not trust it as quota-safe.

## "The skill says `AskUserQuestion` is unavailable in OpenClaw WebUI"

**Cause:** A stricter build required the `AskUserQuestion` tool for consent gates, but the current OpenClaw WebUI environment exposes browser tools without that UI helper. The result is a safe stop before quota usage, not a browser failure.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.9 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start from a fresh OpenClaw WebUI session.
4. The fixed build detects this environment and falls back to the exact plain-text consent scripts from `references/consent-scripts.md`.
5. Reply with exactly one option label when the gate appears.

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

## "The fresh ChatGPT tab disappeared before submit and the run aborted"

**Cause:** The brand-new writable `https://chatgpt.com/` tab vanished before there was any proof that the prompt had actually been submitted. On zenas-host OpenClaw WebUI this reproduced multiple times on 2026-04-08 during the pre-submit window.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.13 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. In the fixed build, if no submit evidence exists yet, the run may recover exactly once by reopening a fresh `/` tab, restoring Pro Advanced if needed, and continuing from the silent pre-submit checkpoint for that same run.
4. The recovery must not emit any new A5 or C4 confirmation gate, because those gates are retired in `v0.3.17+`.
5. If the tab disappears again, or if the URL had already become `/c/<conv_id>` / streaming had already started, stop and use `--resume <conv_id>` only when a real `conv_id` is known.

---

## "The fresh run landed on `?temporary-chat=true` / `临时聊天` and then kept going"

**Cause:** ChatGPT opened the dedicated fresh tab in temporary-chat mode instead of a normal shareable fresh chat. An older build could then continue into Phase C, type the prompt, and risk spending quota inside an unshareable thread.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.27 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session.
4. In the fixed build, a fresh default run that needs a public share link must never submit from `temporary-chat=true` or from a page headed `临时聊天` / `Temporary chat`.
5. The run should first escape temporary mode exactly once by using `关闭临时聊天`, `新聊天`, or a one-shot navigate-to-`https://chatgpt.com/` recovery, then verify that the URL no longer contains `temporary-chat=true` before typing.
6. If temporary mode persists after that single recovery, stop before quota burn instead of improvising or falling through into Phase C.

---

## "The slash-wrapper read `SKILL.md` and then answered the prompt locally"

**Cause:** OpenClaw did rewrite the message into `Use the "chatgpt-pro" skill for this request ... User input:`, but the model still treated the wrapped prompt as something to answer directly instead of as browser-execution input. In a live zenas-host run on 2026-04-08, the session read `SKILL.md` and then replied only `ZENAS-RELIABILITY-AD-N`, with no browser tool calls at all.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.28 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session so the new wrapper guard is loaded.
4. In the fixed build, a wrapped invocation must never answer `User input:` locally; after reading `SKILL.md`, it must proceed into the browser workflow or a valid A2/D2 gate.
5. Treat any transcript that returns only the raw wrapped answer with no browser steps and no Phase F fields as an invalid run.

---

## "A fresh run opened the share dialog for an older conversation / the share warning showed the wrong prompt summary"

**Cause:** The run treated a pre-existing `/c/<old_id>` tab as the actual target conversation instead of as a session anchor, so Phase E prepared to share the wrong thread. A live zenas-host OpenClaw run on 2026-04-08 reproduced this exactly: the requested prompt ended with `-G`, but the share warning showed `tail="-E"` and opened the share dialog for `ZENAS-RELIABILITY-E`.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.11 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Fresh `/chatgpt-pro <prompt>` runs must not ask the user which existing `chatgpt.com` tab to use. They should open a dedicated new `https://chatgpt.com/` tab for the run and treat already-open `/c/<id>` pages as read-only evidence.
4. If the final `conv_id` matches an already-open conversation id, stop the run and do not generate a public share link.
5. Treat any fresh-run prompt that offers `/share/<uuid>` as a selectable tab as a regression.

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

## "The run navigated to `https://chatgpt.com/?prompt=...` and then stopped or treated it as success"

**Cause:** The model took a shortcut by encoding the prompt into the ChatGPT URL instead of completing Phase C normally. On huanghaibin-host OpenClaw WebUI this reproduced on 2026-04-08: the page landed on `https://chatgpt.com/?prompt=1%2B1%3D%3F`, the composer was prefilled, but no submit had happened yet.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.31 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Treat any `?prompt=` or `?model=...&prompt=...` ChatGPT URL as pre-submit composer state only.
4. The run must still verify the composer text, press Enter or click the enabled send button, and wait for a real `/c/<conv_id>` before Phase D/E.
5. A transcript that stops on a prefilled `?prompt=` page, with no `/c/<conv_id>` and no Phase F block, is an invalid run.

---

## "The transcript showed the answer, but there was no share URL and no strict Phase F block"

**Cause:** The browser actually reached an answer, but the model drifted into ordinary assistant prose and stopped before the share/public-output contract was satisfied. On huanghaibin-host OpenClaw WebUI this reproduced on 2026-04-08 when the model answered `1+1 = 2` in prose after reading the skill, instead of continuing through share extraction.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.31 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Treat exact `/chatgpt-pro <prompt>` runs the same as wrapped OpenClaw invocations for completion discipline: the run is not done until Phase F prints the six required fields with either a validated `https://chatgpt.com/share/<uuid>` or explicit `PRIVATE-ONLY`.
4. A screenshot-visible answer alone is not success.
5. If the browser answer exists but public-share extraction still fails, fall back to `PRIVATE-ONLY` plus the private `chatgpt.com/c/<conv_id>` note instead of freeform prose.

---

## "The share dialog opened, but the first snapshot still showed `复制链接` disabled"

**Cause:** On the current ChatGPT share dialog, `POST /backend-api/share/create` may already have fired while the first dialog snapshot still renders `复制链接` as disabled. On huanghaibin-host OpenClaw this reproduced on 2026-04-08: the button first appeared disabled, then became actionable, and the decisive evidence was the later `PATCH /backend-api/share/<uuid>` request.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.31 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. After opening the share dialog, if `复制链接` is disabled in the first snapshot, wait briefly and re-snapshot instead of aborting.
4. If the click later succeeds and the request log shows `PATCH /backend-api/share/<uuid>`, trust that `<uuid>` as the share id even if a stale snapshot still renders the button as disabled.
5. Validate the final public URL as `https://chatgpt.com/share/<uuid>` and confirm it loads before declaring success.

---

## "The run kept taking screenshots / clicking `进阶专业` on an old conversation and never created a new `/c/<conv_id>`"

**Cause:** The fresh run lost its dedicated run-tab affinity and drifted back onto a pre-existing `/c/<old_id>` page. On huanghaibin-host OpenClaw WebUI this reproduced on 2026-04-08: the browser stayed on the old `Mathematical Question` conversation, the tool log showed repeated `openclaw browser screenshot` calls plus a completed click on `进阶专业`, and no new conversation or share requests were created.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.32 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. On fresh OpenClaw runs, record `preexisting_tab_ids` before `browser open https://chatgpt.com/`, then bind and preserve a dedicated `run_tab_id` immediately after that open.
4. Every pre-submit Phase B/C write must stay on `run_tab_id`; a pre-existing `/c/<id>` page is never a valid write target, even if it exposes a better snapshot.
5. If the run is still on any `preexisting_conv_ids` page while taking repeated screenshots, reopening the model menu, or clicking `进阶专业` / `Advanced`, treat that as a stale-tab loop and repair back to fresh-home `/` before continuing.

---

## "`locator.click` timed out waiting for `aria-ref=...` on the composer"

**Cause:** On OpenClaw WebUI, a fresh-home recovery can leave the previously captured aria snapshot ref stale even though the current `chatgpt.com/` page is healthy. A live zenas-host run on 2026-04-08 reproduced this exactly: the first composer click timed out on `aria-ref=ax136`, but a fresh compact role snapshot immediately exposed the valid textbox ref and the run completed normally.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.16 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. On OpenClaw, if the first composer click times out on a cached aria ref, take a fresh compact role snapshot of the same `chatgpt.com` tab and retry once with the refreshed composer textbox ref.
4. Do not restart the run or emit any extra account/submission confirmation solely because the composer ref was stale.
5. If the refreshed role-ref retry still cannot focus/type, stop before quota burn instead of improvising.

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
2. Skip the old E2 confirmation gate for that mode.
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

## "`分享` matched 2 elements" / "it clicked the wrong share button"

**Cause:** The current zh-CN ChatGPT conversation page can expose two visible `分享` buttons at once: the valid conversation-header share near `模型选择器` / `打开对话选项`, and an invalid assistant reply-action-row share inside `回复操作`. A generic `button "分享"` click can therefore hit `matched 2 elements` or pick the wrong control.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.22 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session so the old in-memory skill copy is not reused.
4. In the fixed build, prefer the header-level share button and never use a share button inside the assistant reply action row.
5. If the first share click attempt still returns `matched 2 elements`, re-snapshot the completed `/c/<conv_id>` page with enough depth to distinguish the header controls from `回复操作`, then retry; do not fall back to a shallow aria snapshot.

---

## "`waiting for locator('aria-ref=...')`" / "`ax...` ref click timed out"

**Cause:** The run captured an OpenClaw `snapshot --format aria` tree, then tried to reuse an `ax...` aria ref for a write action such as clicking the composer. Those refs are diagnostic only and are not reliable write targets.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.23 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session.
4. In the fixed build, treat `ax...` refs as read-only and re-snapshot in a writable format (`snapshot --format ai --labels` or equivalent role snapshot) before any click or typing retry.
5. If the run keeps retrying the same `ax...` ref, treat that run as invalid; it is a ref-format bug, not ChatGPT DOM drift.

---

## "`Element \"e18\" not found or not visible`" during composer focus/typing

**Cause:** The run picked the wrong OpenClaw ref from a full-page snapshot. On fresh-home ChatGPT pages, sidebar headings, project rows, and history links can appear before the real main composer in the ref list. A live zenas-host run on 2026-04-08 reproduced this exactly: the agent clicked `e18` from the sidebar snapshot, then tried to type into that non-textbox ref instead of the main `textbox "与 ChatGPT 聊天"` composer.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.25 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session.
4. In the fixed build, the only valid OpenClaw composer target is a `textbox` whose accessible name matches the pinned composer label (`与 ChatGPT 聊天`, `Message ChatGPT`, or equivalent).
5. If a focus/type step returns `Element "<ref>" not found or not visible`, discard that ref, re-snapshot, and resolve the main-pane composer again; never keep typing into sidebar or banner refs.

---

## "The run stopped after `browser status` / `browser tabs` and never opened ChatGPT"

**Cause:** The model entered the skill, read `SKILL.md`, ran the initial OpenClaw setup probes, but stalled before creating the dedicated writable `https://chatgpt.com/` tab for the fresh run. A live zenas-host run on 2026-04-08 reproduced this exactly: the transcript showed `read`, then `browser status`, then `browser tabs`, with no subsequent ChatGPT tab creation.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.24 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session so the new fast-path instructions are loaded.
4. In the fixed build, `browser status` and `browser tabs` are setup-only probes. A fresh default run must immediately continue to `browser open https://chatgpt.com/`.
5. If a run ends or stalls with no dedicated ChatGPT tab ever created, treat that run as invalid orchestration, not as a DOM or account-state failure.

---

## "ChatGPT DOM has drifted. Please run /chatgpt-pro --respike"

**Cause:** The health check (Phase B-1) found one of the three anchor elements missing. ChatGPT likely shipped a frontend change.

**Fix:**
1. Manually open chatgpt.com in Chrome, confirm you can use it normally.
2. Run `/chatgpt-pro --respike`.
3. If the spike captures new selectors successfully → continue.
4. If the spike fails (elements not found) → ChatGPT's model selector flow has changed substantially. Open an issue with the diff from old vs new spike snapshots.

**Special case (not real drift):**
1. On zenas-host OpenClaw WebUI, a pre-submit recovery may reopen a fresh empty `/` page that legitimately has no `share_button` yet.
2. `chatgpt-pro` v0.3.15 or later must skip that anchor on fresh-home pages and continue.
3. If the run still stops on that exact condition, treat it as a skill bug in the recovery path rather than a selector-expiry event.

---

## "The run still asked 'About to use this browser profile's ChatGPT account. Continue?' or 'Send / Cancel'"

**Cause:** An older build is still installed, or the session loaded a stale copy of the skill from disk. Starting in `v0.3.19`, A5, C4, E2, and E8 are retired for explicit default `/chatgpt-pro` runs. On a manually logged-in browser profile, the run must not stop to ask whether it may use that already-signed-in account or whether it may press Send for the exact prompt the user explicitly invoked.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.19 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session so the new skill text is reloaded.
4. Re-run the skill. The only remaining normal interactive gates should be A2 or D2.
5. On a browser profile that is already manually logged into ChatGPT, the exact legacy prompts `即将使用此浏览器 Profile 当前登录的 ChatGPT 账号。继续？` and `即将用 ChatGPT Pro 5.4（进阶思考）提交。消耗 1 次 Pro 配额。继续？` are both regressions. Treat that run as invalid instead of answering them.

---

## "It asked to generate a public share link before ChatGPT had even submitted the prompt"

**Cause:** The run entered Phase E too early. A live zenas-host OpenClaw WebUI regression on 2026-04-08 showed E2 appearing while the browser was still on fresh-home `https://chatgpt.com/`, before any `/c/<conv_id>` existed and before the prompt had actually been submitted.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.18 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session.
4. In the fixed build, public-share work is forbidden until both are true:
   - a real `/c/<conv_id>` has been reached
   - Phase D completion has already been observed for the requested run
5. If a run ever talks about sharing while still on fresh-home `/`, treat it as a failed run. Do not trust any later share URL from that run.

---

## "The run still asked 'Generate share link' / 'Keep public' on a normal `/chatgpt-pro <prompt>` call"

**Cause:** An older build is still installed. Starting in `v0.3.19`, explicit default runs and exact `--resume` runs are already share-authorized, so they must go straight from completion into Phase E share extraction without E2/E8 dialogs.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.19 or later.
2. Reinstall it with `./scripts/install-openclaw-skill.sh`.
3. Start a fresh OpenClaw WebUI session so the old in-memory skill copy is not reused.
4. Re-run the skill. If `Generate share link`, `Keep public`, or similar still appears, treat that run as invalid and stop it.

---

## "OpenClaw WebUI `/chatgpt-pro ...` just echoed the answer instead of running the browser skill"

**Cause:** OpenClaw slash-command routing sanitizes direct skill command names, and the most reliable generic entrypoint is `/skill chatgpt-pro <prompt>`. On 2026-04-08, a live zenas-host WebUI test showed `/chatgpt-pro Reply exactly ...` and a naive skill-wrapper turn both reading the skill file but then answering locally instead of spending Pro quota. The runtime wrapper form is `Use the "chatgpt-pro" skill for this request ... User input: <prompt>`.

**Fix:**
1. Upgrade to `chatgpt-pro` v0.3.20 or later.
2. Invoke it from OpenClaw WebUI as `/skill chatgpt-pro <prompt>`.
3. In the fixed build, treat the OpenClaw wrapper text as fully equivalent to a literal `/chatgpt-pro <prompt>` invocation.
4. If the run still replies with the bare prompt output instead of opening ChatGPT browser tabs, treat that turn as a trigger-path failure rather than a ChatGPT/browser failure.

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

**Cause (OpenClaw WebUI exec-only host):** The run truncated the raw snapshot too early or tried to drive the composer with a nonexistent CLI path such as `openclaw browser act 'type ...'`.

**Fix:**
1. Do not inspect only the first ~80 lines of a fresh-home snapshot; that usually captures only the sidebar and hides the main-pane textbox.
2. Resolve the real composer from the full snapshot: `textbox "与 ChatGPT 聊天"` / `textbox "Message ChatGPT"`.
3. On OpenClaw `2026.3.24`, click the composer with `openclaw browser click <ref>`.
4. Then type via `openclaw browser fill --fields '[{"ref":"<composer_ref>","value":"<prompt>"}]'`.
5. Re-snapshot and confirm the textbox paragraph now contains the prompt text and that the send button changed to `发送提示` / `Send prompt`.

---

## "`openclaw browser act ...` / `openclaw browser type ...` exited with code 1"

**Cause:** The host is running an exec-only OpenClaw CLI build such as `2026.3.24`, whose `browser` command does not expose a generic `act` subcommand. The valid concrete write commands are `click`, `fill`, and `press`.

**Fix:**
1. Replace `openclaw browser act 'click <ref>'` with `openclaw browser click <ref> [--target-id <tabId>]`.
2. Replace `openclaw browser act 'type <ref> \"...\"'` with `openclaw browser fill --fields '[{"ref":"<ref>","value":"..."}]' [--target-id <tabId>]`.
3. Replace `openclaw browser act 'press Enter'` with `openclaw browser press Enter [--target-id <tabId>]`.
4. If the run also keeps retrying `--browser-profile user`, stop doing that once it is clear the host has no attached user profile and a logged-in ChatGPT session is already present in the default OpenClaw browser profile.

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

## "Share dialog snapshot collapsed to `跳至内容` / `Skip to content` and then the copy-link click timed out"

**Cause:** OpenClaw can occasionally return a degenerate writable snapshot right after the share dialog opens. Instead of the real dialog tree, the snapshot may only expose shell controls such as `跳至内容`, with a tiny writable ref set. If the run then clicks one of those tiny refs, it typically fails with a timeout like `waiting for locator('aria-ref=e2')`.

**Fix:**
1. Treat that shell-only snapshot as invalid evidence, not as DOM drift.
2. Re-snapshot the same ChatGPT tab in a writable format after a short delay.
3. If the dialog is already known open and the retry is still degenerate, click the pinned `share_copy_link_button` by role/name (`button "复制链接"` / `button "Copy link"`) instead of using tiny refs like `e1`, `e2`, or `e3`.
4. If a click fails with `waiting for locator('aria-ref=...')`, discard that ref, re-snapshot, and retry from the fresh snapshot.
5. Only after a real copy-link click should Phase E continue into `responsebody`, `requests --filter share`, or clipboard recovery.

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

## "Guest/login CTA page appeared after recovery — STOP"

**Cause:** A fresh-home recovery landed on a non-writable ChatGPT surface. On the 2026-04-08 `zenas-host` live run this showed up as a `https://chatgpt.com/` page that still exposed `登录` / `免费注册`, and the next mistaken click tried to navigate to `auth.openai.com`.

**Fix:**
1. Treat any visible `登录`, `免费注册`, `Log in`, or `Sign up` CTA as "not safely logged in" for this skill, even if parts of the sidebar or profile chrome still render.
2. Manually restore a clean logged-in ChatGPT home in the same browser profile.
3. Re-run `/chatgpt-pro`.

**Rules:**
- Do not let the skill click login/signup/auth buttons.
- Do not classify this as DOM drift.
- Do not infer a valid session from partial sidebar/history rendering when guest CTAs are present.

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

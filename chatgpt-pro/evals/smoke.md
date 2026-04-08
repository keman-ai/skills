# Smoke Test Cases

> Minimal regression tests for `chatgpt-pro` v0.3.32
> Per skill-creator guidance: small set, manual run, no benchmark harness.
> **Each test consumes real Pro quota unless marked `--temporary`.**

---

## How to run

1. Open chatgpt.com in Chrome, log in with the account you want to use
2. Run `./scripts/validate-skill.sh` and make sure it passes before any live-browser smoke
3. For OpenClaw runs, install the skill with `./scripts/install-openclaw-skill.sh`
4. For the cleanest OpenClaw smoke, keep the browser logged in. In `v0.3.19+`, fresh runs should open their own dedicated `chatgpt.com/` tab instead of reusing older conversation tabs.
5. On OpenClaw WebUI, invoke the skill as `/skill chatgpt-pro <prompt>`. The platform may wrap that into `Use the "chatgpt-pro" skill for this request ... User input: <prompt>` before the model sees it; `v0.3.20+` must treat that wrapper as a true explicit invocation.
6. When testing old-tab reuse regressions, keep note of the pre-run `chatgpt.com` tab ids or URLs so you can confirm the run stays on its dedicated `run_tab_id`
7. Ensure `references/selectors.md` is freshly spiked (`Last verified` within 7 days), or that the OpenClaw seed selectors still match the live UI you're testing
8. Run each test from the test description below
9. Record `PASS / FAIL / SKIP` in the table at the bottom

---

## Test 1 — Minimal happy path (Claude Code backend)

**Preconditions:**
- Exactly one chatgpt.com tab, logged in, on `/` (new conversation)
- Backend: Claude Code
- EVAL_DISABLED: false

**Invocation:**
```
/chatgpt-pro 1+1=?
```

**Expected behavior:**
1. A2 → skip (single tab)
2. A5 → silent account audit only; **no** runtime question is shown
3. B-1 → all 3 anchor probes pass
4. B → click model selector → 配置 → Pro → close modal
5. C → click composer → type "1+1=?" → verify → silent C4 pre-submit checks → press Enter directly
6. D → detect completion in <60s (simple prompt, even Pro Advanced is fast)
7. E1 → not temporary chat
8. E2 → no runtime share-confirmation gate should appear for an explicit default `/chatgpt-pro <prompt>` run
9. E3-E6 → click share, then either:
   - current UI: click `复制链接` and recover the share URL from the create response or, if needed, from the observed `PATCH /backend-api/share/<uuid>` request URL, or
   - legacy UI: click create link and poll the readonly URL input
10. E8 → no runtime keep/revoke gate should appear; keep the public link by default
11. F → output:
    ```
    ✅ Model: ChatGPT Pro 5.4 (Advanced thinking)
    ✅ Account: <real email>
    ✅ Conv ID: <conv_id>
    ✅ Duration: ~45s
    ✅ Prompt Ref: sha256=b9ab5b7f, len=5
    🔗 Share: https://chatgpt.com/share/<uuid>
    ```

**Assertions:**
- Share URL matches `/^https:\/\/chatgpt\.com\/share\/[a-f0-9-]+$/`
- A page at `https://chatgpt.com/?prompt=...` or `...?model=...&prompt=...` is pre-submit only; the run must still submit and reach `/c/<conv_id>`
- A transcript that stops after showing only the answer text, with no strict Phase F block and no validated share URL or `PRIVATE-ONLY`, is a FAIL
- On the current share dialog, `复制链接` may appear disabled in the first snapshot; the run should wait/re-snapshot and continue until it recovers a concrete `share/<uuid>` or an explicit `PRIVATE-ONLY` fallback
- The OpenClaw or Claude transcript must print the concrete `https://chatgpt.com/share/<uuid>` URL in the final report; a status like "已复制链接" or "Copied to clipboard" is a FAIL
- Resume mode must never print `https://chatgpt.com/share/<conv_id>` and must never end with helper prose like "你可以继续提问"; if public-share extraction fails, the correct fallback is `PRIVATE-ONLY`
- Exact `/chatgpt-pro --resume <conv_id>` invocations must not stop for a second conversational share-consent prompt in OpenClaw WebUI; they should proceed straight to share recovery
- Final Phase F output must contain all six fields with no heading and no trailing prose; `Warnings` should be `none` when empty
- Total elapsed < 90s
- No A5 account-confirmation gate, no C4 submit-confirmation gate, no E2 share-confirmation gate, and no E8 keep/revoke gate should appear in `v0.3.19+`
- On a manually logged-in browser profile, the exact legacy prompts `即将使用此浏览器 Profile 当前登录的 ChatGPT 账号。继续？` and `即将用 ChatGPT Pro 5.4（进阶思考）提交。消耗 1 次 Pro 配额。继续？` must not appear
- The option labels `继续`, `切换账号（停止）`, `发送`, and `取消` must not appear as standalone runtime consent choices on a default fresh run
- Any consent gate that does appear (normally only A2 / D2) must match the exact wording/options from `references/consent-scripts.md` and must appear without leading or trailing assistant prose
- If `AskUserQuestion` is unavailable on the backend, the same gate must fall back to exact plain text and end with `Reply with exactly one option label.`
- The run must not type or submit from a URL containing `temporary-chat=true`; if ChatGPT opens a fresh run into temporary chat, the skill must escape that mode before typing
- Account email echoed in output
- Conv ID echoed in output
- Follow the share URL manually and confirm it loads the same answer
- If the completed conversation view exposes two visible `分享` buttons, the run must click the header-level conversation share near `模型选择器` / `打开对话选项`, not the one inside `回复操作`
- If you intentionally open multiple `chatgpt.com` tabs, a fresh default run must still open a dedicated new writable tab instead of asking which old tab to use; a stale `tab not found` handle after that is still a regression

**On failure:** check which phase, check selectors.md freshness, check if ChatGPT UI changed.

---

## Test 2 — Poetry prompt (verify model is actually Pro, not Thinking)

**Preconditions:** same as Test 1

**Invocation:**
```
/chatgpt-pro 用七言律诗写一首春天的诗，100字以内
```

**Expected:**
- Same flow as Test 1, but duration likely 2-5 minutes
- Share link returns a page where:
  - The answer is a real 七言律诗 with 8 lines
  - The "Model" indicator on the shared page shows "Pro" (not "Thinking" or "Instant")

**Assertions:**
- Share URL loads
- Shared page has a model badge matching "Pro" (pinned via `selectors.md.shared_page_model_badge` if needed)
- Quota was actually consumed (manually check account quota usage in ChatGPT settings)

---

## Test 3 — Cold start (no chatgpt tab)

**Preconditions:**
- Close all chatgpt.com tabs in Chrome
- Skill detects zero tabs in A2

**Invocation:**
```
/chatgpt-pro 你好
```

**Expected:**
1. A2 → zero tabs → a dedicated new tab opens to https://chatgpt.com/
2. Wait for composer to appear (wait_until 10s)
3. Rest of flow proceeds normally
4. F → output includes the new tab id in Conv ID

**Assertions:**
- New tab was created (observe in Chrome)
- Skill completed without error
- User was NOT prompted "Which tab?" (there was only one after create)

---

## Test 3b — Fresh OpenClaw run must not stall after status/tabs

**Preconditions:**
- Backend: OpenClaw WebUI
- Close all `chatgpt.com` tabs first
- Start a fresh WebUI session so no old in-memory skill copy is reused

**Invocation:**
```
/skill chatgpt-pro Reply exactly ZENAS-RELIABILITY-STATUS-TABS
```

**Expected:**
1. The run may call `browser status`
2. The run may call `browser tabs`
3. It must then immediately create a dedicated writable `https://chatgpt.com/` tab for this run
4. It must not end, stall indefinitely, or claim completion before that dedicated ChatGPT tab exists

**Assertions:**
- After the initial OpenClaw setup probes, a real `chatgpt.com` tab appears in the browser
- A transcript that stops at `browser status` / `browser tabs` with no `chatgpt.com` tab is a FAIL
- The run continues into Phase A/B instead of waiting on the control page forever

## Test 3c — Slash-wrapper must not answer locally

**Preconditions:**
- Backend: OpenClaw WebUI
- Start a fresh WebUI session

**Invocation:**
```
/skill chatgpt-pro Reply exactly ZENAS-RELIABILITY-WRAPPER
```

**Expected:**
1. OpenClaw may rewrite the request into `Use the "chatgpt-pro" skill for this request ... User input:`
2. The run reads the installed `SKILL.md`
3. After that, it must enter the browser workflow; it must not directly answer `ZENAS-RELIABILITY-WRAPPER`

**Assertions:**
- A plain-text assistant answer equal to the wrapped prompt result, with no browser tool calls and no Phase F fields, is a FAIL
- The first substantive post-read action must be a browser step or a valid A2/D2 gate, not a local completion of `User input:`

---

## Test 4 — Existing old conversation / multi-tab regression (must open new thread)

**Preconditions:**
- Keep at least 2 `chatgpt.com` tabs open
- One tab is an old conversation at `/c/<old_id>` whose prompt has an easily recognized suffix such as `...-E`
- Optionally keep an unrelated `/share/<uuid>` page open too, to confirm it is not reused as a writable target

**Invocation:**
```
/chatgpt-pro Reply exactly ZENAS-RELIABILITY-G
```

**Expected:**
1. Fresh runs must **not** ask which existing `chatgpt.com` tab to use; `/share/<uuid>` pages must be ignored as writable targets
2. A2/A4 must use a dedicated fresh tab and open a fresh conversation (`/`), not stay on `/c/<old_id>`
3. After submit, the final `conv_id` must differ from `<old_id>`
4. The run must not pause for `Generate share link` / `Keep public` style questions
5. If the page remains on `<old_id>` or the final conversation id matches the old one, the run must stop before public share generation
6. The old conversation remains unchanged throughout the test

**Assertions:**
- The run never prompts the user to choose between `/c/<old_id>` and `/share/<uuid>` on a fresh invocation
- New conversation has a different id than the old one
- Any runtime `Generate share link` / `Keep public` prompt is a FAIL in `v0.3.19+`
- Any public share link emitted by the skill loads the requested `ZENAS-RELIABILITY-G` conversation, not the old `...-E` thread
- The old conversation is unchanged (check by manually clicking back to it — last message should still be the old last message)
- During pre-submit Phase B/C, the run must stay on its dedicated fresh `run_tab_id`; repeated screenshots or repeated `进阶专业` / `Advanced` clicks while the browser still sits on `<old_id>` are a FAIL

---

## Test 4b — Fresh tab disappears before submit (must recover before charging twice)

**Preconditions:**
- Backend: OpenClaw WebUI
- A logged-in `chatgpt.com/share/<uuid>` page may remain open
- No existing writable `chatgpt.com/c/<id>` tab is required

**Invocation:**
```
/chatgpt-pro Reply exactly ZENAS-RELIABILITY-I
```

**Manual perturbation:**
1. Let the run open the fresh writable `https://chatgpt.com/` tab and reach the pre-submit window
2. Before the browser presses Enter, force that just-opened fresh tab to disappear (for example by manually closing it, or by reproducing the remote tab-loss condition)

**Expected:**
1. The run must not abort immediately just because the fresh tab vanished before submission
2. If no submit evidence exists yet, the skill may recover exactly once by reopening a fresh `/` tab, restoring Pro Advanced if needed, retyping the same prompt, and pressing Enter once
3. The run must not emit any extra A5, C4, E2, or E8 confirmation gate during recovery
4. If a second tab-loss happens, or if any submit evidence already existed, the run must stop rather than risk a duplicate Pro charge
5. If recovery lands on a fresh `/` page, the missing `share_button` there must not be treated as DOM drift

**Assertions:**
- The recovered run reaches a brand-new `/c/<conv_id>` thread and completes normally
- The final conversation contains the requested `ZENAS-RELIABILITY-I` prompt, not stale content from an older thread
- No A5/C4/E2/E8 prompt appears at all during the run
- The exact legacy account/send prompts do not appear at any point in the run
- No duplicate submission is observed
- The run does not stop with `ChatGPT DOM has drifted` merely because the recovered page is a fresh empty thread without a share button

## Test 4c — Recovery lands on guest/login surface (must stop, not improvise)

**Preconditions:**
- Backend: OpenClaw WebUI
- A fresh-home recovery may reopen `https://chatgpt.com/`
- The recovered page exposes guest/auth CTAs such as `登录`, `免费注册`, `Log in`, or `Sign up`, or the next navigation jumps to `auth.openai.com`

**Invocation:**
```
/chatgpt-pro Reply exactly ZENAS-RELIABILITY-L
```

## Test 4d — Fresh default run lands on temporary chat (must escape before submit)

**Preconditions:**
- Backend: OpenClaw WebUI
- The browser is logged in
- Fresh default runs may intermittently open `https://chatgpt.com/?temporary-chat=true`
- User did **not** request `--temporary`

**Invocation:**
```
/skill chatgpt-pro Reply exactly ZENAS-RELIABILITY-TEMP
```

**Expected:**
1. The run opens its dedicated fresh `chatgpt.com` tab
2. If that tab lands on `?temporary-chat=true` or visibly shows `临时聊天` / `Temporary chat`, the run does **not** type yet
3. The run escapes temporary mode exactly once by using `关闭临时聊天`, `新聊天`, or a one-shot navigate-to-`https://chatgpt.com/` recovery
4. Only after the URL no longer contains `temporary-chat=true` may it continue into model configuration, typing, submit, completion, and share
5. If temporary mode persists after that one recovery, the run stops before quota burn instead of submitting inside an unshareable thread

**Assertions:**
- No prompt text is typed into the temporary-chat composer before the escape attempt
- No Enter press happens while the page is still in temporary chat
- Any public-share run that stays on `temporary-chat=true` and keeps going is a FAIL
- `--temporary` remains the only mode where temporary chat is allowed on purpose

**Expected:**
1. After recovery, the skill checks whether the fresh-home page is actually writable
2. If any guest/auth CTA is visible, or if the browser lands on `auth.openai.com`, the run must STOP with a manual re-login instruction
3. The skill must not keep inferring "logged in" from sidebar/history chrome
4. The skill must not click login/signup/auth buttons
5. The run must not misclassify this as DOM drift

**Assertions:**
- No browser action targets a login/signup/auth CTA
- No model-selector click is attempted on the guest/auth page
- The stop reason is a login/session-state problem, not selector drift
- No Pro submission occurs

## Test 4d — Composer stale aria-ref after recovery (must re-snapshot and continue)

**Preconditions:**
- Backend: OpenClaw WebUI
- The recovered page is a valid writable fresh-home page (`/` or `/?...`)
- The first composer click uses a stale aria ref and fails with a timeout such as `waiting for locator('aria-ref=...')`

**Invocation:**
```
/chatgpt-pro Reply exactly ZENAS-RELIABILITY-M
```

**Expected:**
1. The run does not stop on the first stale composer click
2. It immediately takes a fresh compact role snapshot of the same `chatgpt.com` tab
3. If the failing ref is an OpenClaw `ax...` aria ref, the run must treat that ref as read-only and switch to a writable `e...` ref from `snapshot --format ai --labels` (or equivalent writable role snapshot) before retrying
4. The retried composer target must be a real `textbox`, not a sidebar heading/link/history row ref

## Test 4e — Completed page has duplicate share buttons (must choose header share only)

**Preconditions:**
- Backend: OpenClaw WebUI
- The completed `/c/<conv_id>` page visibly exposes two `分享` buttons:
  - one in the conversation header near `模型选择器` / `打开对话选项`
  - one inside the assistant `回复操作` row near `复制回复` / `喜欢` / `不喜欢`

**Invocation:**
```
/skill chatgpt-pro Reply exactly ZENAS-RELIABILITY-V
```

**Expected:**
1. The run reaches a completed `/c/<conv_id>` conversation page
2. Before Phase E click, the run takes a fresh rich enough snapshot of that exact page
3. If the first generic `分享` locator is ambiguous or returns `matched 2 elements`, the run re-snapshots and disambiguates instead of falling back to a shallow aria snapshot
4. The header-level share button is used to open the share dialog
5. The reply-action-row `分享` control is never used as the Phase E entrypoint

**Assertions:**
- The retried write action does not reuse the stale `ax...` ref
- The retried click/type uses a writable interactive ref namespace (`e...`)
- A visible `复制链接` / `Copy link` affordance appears after the click
- The run does not stop on `matched 2 elements`
- The run does not click the `分享` button inside `回复操作`
- The final public URL still resolves to the requested `ZENAS-RELIABILITY-V` conversation

## Test 4f — Share dialog snapshot degrades to `跳至内容` (must re-snapshot before copy click)

**Preconditions:**
- Backend: OpenClaw WebUI
- The completed `/c/<conv_id>` page has already opened the share dialog
- The next writable snapshot transiently collapses to shell-only content such as `跳至内容` / `Skip to content`, or only a tiny ref set

**Invocation:**
```
/skill chatgpt-pro Reply exactly ZENAS-RELIABILITY-W
```

**Expected:**
1. The run reaches the share dialog on the correct completed conversation
2. If the next writable snapshot is degenerate, the run treats it as invalid and re-snapshots the same tab
3. If the retry is still degenerate but the dialog is already visibly open, the run clicks the pinned `share_copy_link_button` by role/name (`button "复制链接"` / `button "Copy link"`) instead of using tiny refs from the shell snapshot
4. The run continues into share URL recovery only after a real copy-link click

**Assertions:**
- A degenerate shell snapshot is not treated as DOM drift
- The run does not click arbitrary tiny refs like `e1`, `e2`, or `e3` from the shell snapshot
- If a click fails with `waiting for locator('aria-ref=...')`, the run discards that ref and re-snapshots before retrying
- The final public URL still resolves to the requested `ZENAS-RELIABILITY-W` conversation
3. It retries composer focus with the refreshed textbox ref and continues into typing/C4
4. It does not restart the whole run, emit A5/C4/E2/E8 prompts, or misclassify the page as DOM drift

**Assertions:**
- A role snapshot is taken after the stale aria-ref timeout
- After recovery, only a `textbox` composer ref may be clicked or typed into
- Sidebar/project/history refs must never be reused as the composer target
- The retry targets the refreshed composer textbox ref, not an unrelated control
- The run reaches C4 or later in the same session
- No A5/C4/E2/E8 prompt appears
- No extra fresh-home recovery loop is started solely because the first composer ref was stale

## Test 4e — Premature share step on fresh-home page (must never happen)

**Preconditions:**
- Backend: OpenClaw WebUI
- Fresh run from `/chatgpt-pro <prompt>`
- Browser starts on fresh-home `https://chatgpt.com/`

**Invocation:**
```
/chatgpt-pro Reply exactly ZENAS-RELIABILITY-O
```

**Expected:**
1. The run stays in Phases C/D until the prompt has actually been submitted and completed
2. No share-related question or prose appears while the current URL is `/` or `/?...`
3. No share-related question or prose appears before a real `/c/<conv_id>` exists for the requested prompt
4. If the run ever talks about generating/keeping a public link on fresh-home `/`, treat the run as failed rather than answering anything

**Assertions:**
- Any share-related prompt or prose shown before a `/c/<conv_id>` exists is a FAIL
- Any share-related prompt or prose shown before completion is a FAIL
- The correct sequence is: type -> submit -> completion -> share extraction -> Phase F

---

## Test 5 — Evaluate-free mode (OpenClaw with browser.evaluateEnabled=false)

**Preconditions:**
- Backend: OpenClaw
- Config: `browser.evaluateEnabled=false`
- Logged into chatgpt.com in the `user` profile

**Invocation:**
```
/chatgpt-pro 1+1=?
```

**Expected:**
1. Backend detection → `openclaw`
2. Eval probe → `EVAL_DISABLED=true`, cached
3. If `AskUserQuestion` is unavailable, `CONSENT_MODE=text_gate` and every remaining consent gate (`A2 / D2`) is emitted as exact plain text ending with `Reply with exactly one option label.`
3. A6 observer cleanup → skipped (no eval)
4. B-1 health check runs via `exists` (snapshot-based, slower)
5. If `advanced_thinking_active_indicator` is already visible after `new_thread()`, OpenClaw seed-mode may skip the modal/config branch and continue directly to Phase C
6. Otherwise B runs via snapshot + click actions. On OpenClaw WebUI exec-only hosts, this means literal CLI `click <ref>` commands, not `act`.
7. C1 focus via `click <composer_ref>`
8. C2 type via `fill --fields '[{"ref":"<composer_ref>","value":"<prompt>"}]'` on exec-only OpenClaw, or the native browser-tool type primitive when that backend actually exposes it
9. C3 verify via snapshot — if `send_button_enabled` is not pinned, composer text verification alone is sufficient; if that fails, STOP (no execCommand fallback)
10. D1 polling uses `exists(stop_button)` every 3s
11. E5 share link read prefers OpenClaw `responsebody("**/backend-api/share/**")`, then `requests --filter share`, and if eval is available but the request log is empty, `navigator.clipboard.readText()` immediately after the copy click; if the dialog falls back to a readonly input, read that instead
12. F → same output format as Test 1

**Assertions:**
- Skill completed despite eval being disabled
- On exec-only OpenClaw hosts, no step attempts nonexistent `openclaw browser act ...` or `openclaw browser type ...` subcommands
- Total elapsed longer than Test 1 by ~15-30s (snapshot overhead)
- Share URL valid
- Final report includes the concrete public share URL, not just a clipboard/copy confirmation

---

## Test 6 — Temporary chat mode

**Preconditions:**
- Open chatgpt.com in a new temporary chat (if UI supports) OR use `--temporary` flag

**Invocation:**
```
/chatgpt-pro --temporary 1+1=?
```

**Expected:**
1. A-C-D run normally
2. E1 → detects `--temporary` flag OR URL prefix → skips Phase E entirely
3. F → output:
   ```
   🔒 Share: TEMPORARY-NO-LINK — read the answer in the tab now, it disappears on close
   ```

**Assertions:**
- No share link in output
- No AskUserQuestion about share confirmation
- The tab's conversation still exists and can be read manually

---

## Test 7 — Unshare flow

**Preconditions:**
- Run Test 1 first; capture the `<conv_id>` from the output

**Invocation:**
```
/chatgpt-pro --unshare <conv_id>
```

**Expected:**
1. Fresh invocation, new consent gate
2. Locate the conversation by navigating to `/c/<conv_id>`
3. Open share dialog
4. Click "Delete link" / "删除链接"
5. Wait for confirmation
6. F → output: `🔗 Share: REVOKED`

**Assertions:**
- After the flow, the previously-shared URL returns 404 or "link has been removed"
- The conversation itself still exists in your account

---

## Results Table

| Test | Date | Backend | Eval | Result | Duration | Notes |
|---|---|---|---|---|---|---|
| 1 | `____` | claude_code | on | | | |
| 2 | `____` | claude_code | on | | | |
| 3 | `____` | claude_code | on | | | |
| 4 | `____` | claude_code | on | | | |
| 5 | `____` | openclaw    | off | | | |
| 6 | `____` | claude_code | on | | | |
| 7 | `____` | claude_code | on | | | |

---

## Smoke test acceptance criteria

- `./scripts/validate-skill.sh` must PASS before any live-browser smoke is considered valid
- Tests 1, 3, 4 must PASS for a release
- Tests 2, 5, 6, 7 are "nice to pass" — if any fails, open an issue and decide whether to ship
- Any `SKIP` must have a reason

---

## What smoke tests do NOT cover

- ChatGPT DOM drift between runs (use `--respike` when B-1 fails)
- Cloudflare challenges (manual intervention required)
- Quota-exhausted error path (need to drain quota to test)
- Cross-account tampering detection (need to forge a DOM mismatch to test)
- 30-minute dead-man timer (need to let it elapse — impractical for smoke)

These are "eyes-on" tests run as incidents surface.

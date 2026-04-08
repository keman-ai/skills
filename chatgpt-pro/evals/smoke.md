# Smoke Test Cases

> Minimal regression tests for `chatgpt-pro` v0.3.7
> Per skill-creator guidance: small set, manual run, no benchmark harness.
> **Each test consumes real Pro quota unless marked `--temporary`.**

---

## How to run

1. Open chatgpt.com in Chrome, log in with the account you want to use
2. Run `./scripts/validate-skill.sh` and make sure it passes before any live-browser smoke
3. For OpenClaw runs, install the skill with `./scripts/install-openclaw-skill.sh`
4. For the cleanest OpenClaw smoke, keep exactly one logged-in `chatgpt.com` tab open before invocation
5. Ensure `references/selectors.md` is freshly spiked (`Last verified` within 7 days), or that the OpenClaw seed selectors still match the live UI you're testing
6. Run each test from the test description below
7. Record `PASS / FAIL / SKIP` in the table at the bottom

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
2. A5 → AskUserQuestion account confirmation → user says "Continue"
3. B-1 → all 3 anchor probes pass
4. B → click model selector → 配置 → Pro → close modal
5. C → click composer → type "1+1=?" → verify → AskUserQuestion submit → press Enter
6. D → detect completion in <60s (simple prompt, even Pro Advanced is fast)
7. E1 → not temporary chat
8. E2 → AskUserQuestion share confirmation → user says "Generate share link"
9. E3-E6 → click share, then either:
   - current UI: click `复制链接` and recover the share URL from the create response or, if needed, from the observed `PATCH /backend-api/share/<uuid>` request URL, or
   - legacy UI: click create link and poll the readonly URL input
10. E8 → AskUserQuestion post-share → user says "Keep public"
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
- The OpenClaw or Claude transcript must print the concrete `https://chatgpt.com/share/<uuid>` URL in the final report; a status like "已复制链接" or "Copied to clipboard" is a FAIL
- Resume mode must never print `https://chatgpt.com/share/<conv_id>` and must never end with helper prose like "你可以继续提问"; if public-share extraction fails, the correct fallback is `PRIVATE-ONLY`
- Exact `/chatgpt-pro --resume <conv_id>` invocations must not stop for a second conversational share-consent prompt in OpenClaw WebUI; they should proceed straight to share recovery
- Final Phase F output must contain all six fields with no heading and no trailing prose; `Warnings` should be `none` when empty
- Total elapsed < 90s
- Account email echoed in output
- Conv ID echoed in output
- Follow the share URL manually and confirm it loads the same answer
- If you intentionally open multiple `chatgpt.com` tabs, the chosen URL path must be rebound to a fresh tab id before the next write action; a stale `tab not found` handle is a regression in versions earlier than v0.3.2

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
1. A2 → zero tabs → `tabs_create_mcp` + `navigate` → new tab opens to https://chatgpt.com/
2. Wait for composer to appear (wait_until 10s)
3. Rest of flow proceeds normally
4. F → output includes the new tab id in Conv ID

**Assertions:**
- New tab was created (observe in Chrome)
- Skill completed without error
- User was NOT prompted "Which tab?" (there was only one after create)

---

## Test 4 — Existing old conversation (must open new thread)

**Preconditions:**
- Open chatgpt.com, click an old conversation from the sidebar (URL = `/c/<old_id>`)
- Old conversation's last message should NOT be the target answer

**Invocation:**
```
/chatgpt-pro 当前时间戳
```

**Expected:**
1. A4 "open new thread" triggers → click "New chat" button OR navigate to `/`
2. Assert URL changed from `/c/<old_id>` to `/` → pass
3. Rest of flow proceeds normally
4. F → Conv ID is a NEW id, not `<old_id>`

**Assertions:**
- New conversation has a different id than the old one
- The old conversation is unchanged (check by manually clicking back to it — last message should still be the old last message)

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
3. A6 observer cleanup → skipped (no eval)
4. B-1 health check runs via `exists` (snapshot-based, slower)
5. If `advanced_thinking_active_indicator` is already visible after `new_thread()`, OpenClaw seed-mode may skip the modal/config branch and continue directly to Phase C
6. Otherwise B runs via snapshot + act clicks
7. C1 focus via `act click <composer_ref>`
8. C2 type via `act type`
9. C3 verify via snapshot — if `send_button_enabled` is not pinned, composer text verification alone is sufficient; if that fails, STOP (no execCommand fallback)
10. D1 polling uses `exists(stop_button)` every 3s
11. E5 share link read prefers OpenClaw `responsebody("**/backend-api/share/**")`, then `requests --filter share`, and if eval is available but the request log is empty, `navigator.clipboard.readText()` immediately after the copy click; if the dialog falls back to a readonly input, read that instead
12. F → same output format as Test 1

**Assertions:**
- Skill completed despite eval being disabled
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

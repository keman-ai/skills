# chatgpt-pro Selectors

> **Last verified:** `2026-04-07` (OpenClaw zh-CN live smoke subset; full dual-backend spike still recommended)
> **Skill version:** 0.3.6
> **Expiry:** 7 days from `Last verified`
> **Signed by:** `codex-live-smoke`

---

## Status

🟡 **PARTIALLY CAPTURED**

This file still contains `__TODO_SPIKE__` placeholders, but it now also contains a live-tested OpenClaw seed set captured on 2026-04-07 from a real logged-in zh-CN chatgpt.com session. The skill's B0 gate should check placeholders for the **current backend only**.

To fully finish the selector set:
```
/chatgpt-pro --spike
```

### Live-tested OpenClaw anchors (2026-04-07)

These were observed in a real browser run and are safe to use as seed locators for OpenClaw:

| Selector | Observed a11y shape | Notes |
|---|---|---|
| `new_chat_button` | `link "新聊天"` | Sidebar new-thread action |
| `model_selector_button` | `button "模型选择器"` | Top banner model switcher |
| `composer` | `textbox "与 ChatGPT 聊天"` | Main prompt box |
| `share_button` | `button "分享"` | Present after the conversation has content |
| `stop_button` | `button "停止流式传输"` | Reliable streaming-state marker |
| `pro_option_row` | `menuitem "Pro 研究级智能模型"` | Dropdown row showed selected state |
| `model_config_menuitem` | `menuitem "配置…"` | Still present in current menu |
| `advanced_thinking_active_indicator` | `button "进阶专业"` | Observed in the composer toolbar after Pro selection |
| `share_copy_link_button` | `button "复制链接"` | Current share dialog path; no URL input was visible |

### OpenClaw minimal smoke set (authoritative for v0.3.6)

If all selectors in this set are pinned and probes pass, the OpenClaw backend may run the full happy path without a fresh modal spike. In this mode, it is allowed to skip the modal/config branch when `advanced_thinking_active_indicator` is already visible after `new_thread()`.

- `new_chat_button`
- `composer`
- `model_selector_button`
- `advanced_thinking_active_indicator`
- `share_button`
- `share_copy_link_button`
- `stop_button`

These are **optional** for OpenClaw seed-mode and must not block the happy path when they are still `__TODO_SPIKE__`:

- `current_model_label`
- `model_menu_popover`
- `pro_option_selected_indicator`
- `thinking_modal_title`
- `thinking_level_current_value`
- `thinking_level_dropdown`
- `thinking_level_advanced_option`
- `thinking_modal_close_button`
- `composer_focused_state`
- `send_button_enabled`
- `share_dialog`
- `create_link_button`
- `share_url_input`
- `delete_link_button`
- `shared_page_model_badge`
- `temporary_chat_indicator`

---

## DOM Spike Procedure

A DOM Spike is a one-time, human-in-the-loop capture of DOM selectors from the user's real logged-in chatgpt.com UI, so the skill's automated clicks land on the right elements.

**Why required:**
- ChatGPT ships DOM-affecting frontend changes roughly weekly
- The Chinese-variant UI labels ("思考时长 / Pro 5.4 / 进阶") are not guaranteed to match the English public build
- Every user's account may see a different A/B experiment
- Writing selectors from guessed strings wastes Pro quota on doomed runs

**Procedure (executed by the LLM, with the user observing):**

### Step 0 — Precheck
- Confirm `BACKEND` (claude_code or openclaw)
- Confirm `EVAL_DISABLED` (false/true)
- Confirm `chatgpt.com` is open and logged in
- Confirm user is NOT in the middle of an important conversation (spike takes ~3 min)

### Step 1 — Landing page snapshot
- User opens https://chatgpt.com/ (empty new conversation)
- Run `snap()` → save RAW snapshot to `spike-01-landing.json`
- Apply **REDACTION FILTER** (below) → save sanitized to `spike-01-landing.redacted.json`
- Pin from sanitized:
  - `composer` — the bottom prompt input
  - `send_button_enabled` — the send button in its enabled state (may not exist before typing)
  - `model_selector_button` — the top-left "ChatGPT ▼" button
  - `account_email_display` — the element showing user's email/identifier
  - `new_chat_button` — the sidebar "New chat" button

### Step 2 — Model selector menu open
- Click `model_selector_button`
- Run `snap()` → `spike-02-model-menu.json` + `.redacted.json`
- Pin:
  - `model_menu_popover` — the popover container
  - `pro_option_row` — the visible `Pro 研究级智能模型` row
  - `model_config_menuitem` — the "配置... / Configure" item

### Step 3 — "Thinking duration" modal open
- First confirm whether the current UI even needs the modal.
- If `advanced_thinking_active_indicator` is already visible after selecting Pro, the modal may be a fallback path only.
- Otherwise click `model_config_menuitem`
- Wait 500ms for animation
- Run `snap()` → `spike-03-thinking-modal.json` + `.redacted.json`
- Pin:
  - `thinking_modal_title` — modal title "思考时长 / Thinking duration"
  - `instant_option_row`
  - `thinking_option_row`
  - `pro_option_row` — the "Pro 5.4 / 研究级智能模型" row
  - `thinking_level_section` — the "Pro 思考程度" subsection
  - `thinking_level_current_value` — current value label (e.g. "进阶 / Advanced")
  - `thinking_level_dropdown` — the dropdown trigger (if it's a dropdown)
  - `thinking_modal_close_button` — the × button

### Step 4 — Pro selected + Advanced chosen
- Click `pro_option_row`
- Verify selection indicator appears
- Run `snap()` → `spike-04-pro-selected.json` + `.redacted.json`
- Pin:
  - `pro_option_selected_indicator` — the checkmark element
  - `thinking_level_advanced_option` — the "进阶 / Advanced" option (if needed)
  - `advanced_thinking_active_indicator` — anything that tells us advanced is the active mode after closing the modal

### Step 5 — Modal closed, verify top button
- `press(Escape)` or click `thinking_modal_close_button`
- Run `snap()` → `spike-05-configured.json` + `.redacted.json`
- Pin:
  - `current_model_label` — the updated top button text **if and only if the current UI exposes it**
  - If the banner still only reads `ChatGPT`, note that explicitly and rely on `pro_option_selected_indicator` instead of forcing a fake label selector

### Step 6 — After-send state (OPTIONAL, costs 1 Pro quota)
- Type a minimal prompt ("ok") into composer
- Submit
- Wait ~5 seconds into streaming
- Run `snap()` → `spike-06-streaming.json` + `.redacted.json`
- Pin:
  - `stop_button` — the send-button's stop state (during streaming)
  - `last_assistant_message` — the streaming assistant message container
- Wait for completion
- Run `snap()` → `spike-07-answered.json` + `.redacted.json`
- Pin:
  - `share_button` — the share icon in the conversation header

### Step 7 — Share dialog
- Click `share_button`
- Run `snap()` → `spike-08-share-dialog.json` + `.redacted.json`
- Pin:
  - `share_dialog` — the modal container
  - `share_copy_link_button` — "复制链接 / Copy link" (current UI path, verified live on 2026-04-07)
  - `create_link_button` — "创建链接 / Create link" (legacy / fallback only)
  - `share_url_input` — the readonly input that will hold the URL (legacy / fallback only)
  - `delete_link_button` — "删除链接 / Delete link" (only if already shared)

### Step 8 — Shared page verification (OPTIONAL, no extra quota)
- Open the generated `https://chatgpt.com/share/<uuid>` in a disposable tab
- Run `snap()` → `spike-09-shared-page.json` + `.redacted.json`
- Pin:
  - `shared_page_model_badge` — the model badge or equivalent indicator on the public share page

### Step 9 — Sign and write
- LLM proposes selectors with justification
- User reviews the proposal
- If any value contains PII or a secret → abort and re-redact
- On approval → write this file, set `Last verified: <today>`, sign
- Delete the raw (unredacted) snapshot files from disk

---

## REDACTION FILTER (MANDATORY before anything is written to this file)

This filter runs on every snapshot before it touches disk. Any selector or example pulled from the snapshot must go through the same filter.

### Allow-list (these keys may be kept)
- `tag` / `tagName` / `nodeType`
- `role` / `aria-role`
- `aria-label` (max 80 chars, truncate with `…`)
- `aria-labelledby` (reference only, not text)
- `data-testid`
- `data-state`
- `data-*` attributes NOT matching the block-list regex below
- `class` (max 60 chars, truncate)
- Structural position (nth-child, parent role chain)

### Block-list (these must be stripped or replaced with `<TEXT len=N>`)
- All `textContent` / `innerText` / `innerHTML`
- All `value`, `placeholder`, `title`, `alt`
- All `id` attributes longer than 12 characters
- Any string matching `/[A-Za-z0-9_\-]{24,}/` (likely token)
- Any string matching `/\b(sk-|Bearer |eyJ[A-Za-z0-9_-]{10,})/` (auth tokens)
- Any string matching email regex `/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/`
- Any `<script>`, `<style>`, `<meta>` contents
- `__NEXT_DATA__` and similar JSON blobs
- `document.title` (may contain past conversation titles)

### Post-write assertion (MUST run after writing the redacted file)
```bash
grep -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' selectors.md && echo "LEAK: email" && exit 1
grep -E '[A-Za-z0-9_\-]{24,}' selectors.md && echo "LEAK: possible token" && exit 1
# If <conv_id> is known from the current tab, check it's not in the file either
```
If any grep matches → abort, restore backup, investigate.

---

## Selector Format (after spike)

Each selector has **both** locators — one per backend — plus a fallback chain and notes.

Example (template — empty values until spike):

```yaml
composer:
  claude_code:
    primary: 'div[contenteditable="true"][data-testid="__TODO_SPIKE__"]'
    fallback: 'role=textbox[aria-label=__TODO_SPIKE__]'
  openclaw:
    primary: 'textbox'            # snapshot role
    snapshot_name_contains: '__TODO_SPIKE__'
    fallback: 'by_placeholder_text'  # WILL BREAK on locale change — flag at runtime
  notes: |
    ChatGPT composer is ProseMirror-based. If the snapshot exposes it as
    generic instead of textbox, warn user: "80% success rate expected."

model_selector_button:
  claude_code:
    primary: '__TODO_SPIKE__'
    fallback: '__TODO_SPIKE__'
  openclaw:
    primary: '__TODO_SPIKE__'
    fallback: '__TODO_SPIKE__'
  notes: '__TODO_SPIKE__'

# ... repeat for every selector in the pinned list above
```

---

## Pinned Selectors

The entries below mix two states:
- **OpenClaw seed locators** captured from the 2026-04-07 live run
- Remaining `__TODO_SPIKE__` placeholders that still need a full spike, mostly on Claude Code or modal-only fallback paths

```yaml
# === Phase A — Session ===
account_email_display: __TODO_SPIKE__
new_chat_button:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: link
      name: 新聊天
    fallback:
      role: link
      name: New chat

# === Phase B-1 — Health check anchors (MUST all exist on every run) ===
composer:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: textbox
      name: 与 ChatGPT 聊天
    fallback:
      role: textbox
      name: Chat with ChatGPT
model_selector_button:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: button
      name: 模型选择器
share_button:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: button
      name: 分享

# === Phase B — Model config ===
current_model_label:
  claude_code: __TODO_SPIKE__
  openclaw:
    note: Banner text stayed "ChatGPT" in the 2026-04-07 UI; do not require this selector if the menu row is authoritative.
advanced_thinking_active_indicator:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: button
      name: 进阶专业
model_menu_popover:               __TODO_SPIKE__  # optional for OpenClaw seed-mode
model_config_menuitem:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: menuitem
      name: 配置…
thinking_modal_title:             __TODO_SPIKE__
pro_option_row:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: menuitem
      name: Pro 研究级智能模型
pro_option_selected_indicator:    __TODO_SPIKE__  # optional for OpenClaw seed-mode
thinking_level_current_value:     __TODO_SPIKE__  # optional for OpenClaw seed-mode
thinking_level_dropdown:          __TODO_SPIKE__  # optional for OpenClaw seed-mode
thinking_level_advanced_option:   __TODO_SPIKE__  # optional for OpenClaw seed-mode
thinking_modal_close_button:      __TODO_SPIKE__  # optional for OpenClaw seed-mode

# === Phase C — Input ===
composer_focused_state: __TODO_SPIKE__  # optional when typing proof succeeds
send_button_enabled:    __TODO_SPIKE__  # optional when composer text verification succeeds

# === Phase D — Wait ===
stop_button:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: button
      name: 停止流式传输
last_assistant_message:   __TODO_SPIKE__
streaming_class_selector: '.result-streaming, [data-is-streaming="true"]'  # historical default, verify

# === Phase E — Share ===
share_dialog:       __TODO_SPIKE__  # optional if copy-link or create-link action appears
share_copy_link_button:
  claude_code: __TODO_SPIKE__
  openclaw:
    primary:
      role: button
      name: 复制链接
create_link_button: __TODO_SPIKE__  # optional for current copy-link UI
share_url_input:    __TODO_SPIKE__  # optional for current copy-link UI
delete_link_button: __TODO_SPIKE__  # optional until unshare flow is exercised
shared_page_model_badge: __TODO_SPIKE__  # optional until share-page verification is exercised

# === Temporary chat detection ===
temporary_chat_indicator: __TODO_SPIKE__  # optional until temporary mode is exercised
```

---

## Composer Locator Strategy Note (captured during spike)

The spike MUST record, for each backend, whether the composer exposes a proper `textbox` role.

```yaml
composer_role_exposure:
  claude_code:
    finds_via: __TODO_SPIKE__  # e.g. "find('bottom prompt input')" → returns correct/incorrect
    use_strategy: __TODO_SPIKE__  # "pinned_css" recommended
  openclaw:
    snapshot_role: textbox
    use_strategy: by_role_name
```

If either backend reports FRAGILE, the skill must print a warning at runtime: "Composer located via placeholder text fallback; expect ~80% success rate."

---

## Change Log

| Date | Change | Signed by |
|---|---|---|
| 2026-04-07 | Added OpenClaw live-tested seed selectors and current copy-link share-dialog notes | codex-live-smoke |
| 2026-04-07 | Declared the OpenClaw minimal smoke set and marked modal-only selectors as optional for seed-mode happy path | codex-openclaw-webui |
| 2026-04-07 | Initial placeholder, awaiting first full spike | team-lead |

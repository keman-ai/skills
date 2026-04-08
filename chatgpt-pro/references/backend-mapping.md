# Backend Mapping — Primitives → Tool Calls

> How each primitive in `SKILL.md` is implemented on each backend.
> **Skill version:** 0.3.6

---

## Backend detection (runtime)

```
if tool "mcp__Claude_in_Chrome__tabs_context_mcp" in tools:
    BACKEND = "claude_code"
    EVAL_DISABLED = False   # Claude-in-Chrome always supports javascript_tool
elif tool "browser" in tools:
    BACKEND = "openclaw"
    # one-shot evaluate probe (cache the result for the rest of the run)
    result = browser(kind="evaluate", fn="1+1")
    EVAL_DISABLED = (result is error or contains "disabled")
else:
    raise "No compatible browser backend"

if both available:
    raise "Ambiguous: both backends present, ask user"
```

---

## Primitive → Tool Mapping

### `ensure_session()` → `{tabId, backend, eval_disabled}`

| Backend | Tool sequence |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__tabs_context_mcp({createIfEmpty: true})` → enumerate result → filter by URL contains `chatgpt.com` → if empty: `mcp__Claude_in_Chrome__tabs_create_mcp()` then `mcp__Claude_in_Chrome__navigate({tabId, url: "https://chatgpt.com/"})` |
| `openclaw` | `browser kind=tabs` → filter → if empty: `browser kind=open url=https://chatgpt.com/` |

### `rebind_tab(chosen_path?, conv_id?)` → `tabId`

| Backend | Tool sequence |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__tabs_context_mcp()` → filter `chatgpt.com` tabs → prefer exact URL path match on `chosen_path`, else exact `/c/<conv_id>` match, else sole remaining tab, else ask user again |
| `openclaw` | `browser kind=tabs` → filter `chatgpt.com` tabs → prefer exact URL path match on `chosen_path`, else exact `/c/<conv_id>` match, else sole remaining tab, else ask user again |

**Use this whenever a prior browser action returns `tab not found`, or immediately after an A2 user selection on OpenClaw.**

### `new_thread(tabId)`

| Backend | Tool sequence |
|---|---|
| `claude_code` | **Preferred:** `mcp__Claude_in_Chrome__find({tabId, query: "New chat sidebar button"})` → `mcp__Claude_in_Chrome__computer({tabId, action: "left_click", coordinate: [ref.x, ref.y]})`. **Fallback:** `mcp__Claude_in_Chrome__navigate({tabId, url: "https://chatgpt.com/"})` |
| `openclaw` | **Preferred:** `browser kind=snapshot --format ai` → find new-chat ref → `browser kind=act "click <ref>"`. **Fallback:** `browser kind=navigate url=https://chatgpt.com/` |

**Assertion (both):** wait for URL to match `/^https:\/\/chatgpt\.com\/?(\?.*)?$/` within 5s.

### `assert_host(tabId, expected_host)`

| Backend | Tool sequence |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__tabs_context_mcp` → find tab by id → check `url` starts with `https://<expected_host>` — if not, RAISE |
| `openclaw` | `browser kind=tabs` → find by id → check hostname — if not, RAISE |

**This primitive MUST be called internally by every `click` / `type` / `press` before the write action.**

### `snap(tabId)`

| Backend | Tool sequence | Output form |
|---|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__read_page({tabId, filter: "interactive"})` | interactive tree with refs |
| `openclaw` | `browser kind=snapshot --format ai` | a11y tree with numeric refs |

### `click(tabId, locator)`

Locator format:
```json
{"kind": "ref", "value": "12"}
{"kind": "text", "value": "配置", "role": "menuitem"}
{"kind": "role_name", "value": {"role": "button", "name": "ChatGPT"}}
{"kind": "css", "value": "button[data-testid=\"model-switcher\"]"}
```

| Backend | Strategy per locator kind |
|---|---|
| `claude_code` | `ref`: use read_page's coordinate then `computer left_click`. `text`: `find({query: "<role> with text <value>"})` → click. `role_name`: `find({query: "<role> <name>"})` → click. `css`: `javascript_tool({text: "document.querySelector('<css>').click()"})` — also verify via snap afterward. |
| `openclaw` | `ref`: `browser kind=act "click <ref>"`. `text`: `browser kind=snapshot` → find matching node → `act click <ref>`. `role_name`: same as text. `css`: `browser kind=evaluate fn="document.querySelector('<css>').click()"` (fails if eval disabled — fall back to snapshot+text search). |

**Always `assert_host` first. Always verify the click landed via a follow-up `snap` or `exists` probe.**

### `type(tabId, locator, text)`

**Critical:** the target is contenteditable. Use REAL keyboard events, not `form_input` / value setter.

| Backend | Tool sequence |
|---|---|
| `claude_code` | First `click(tabId, locator)` to focus, then `mcp__Claude_in_Chrome__computer({tabId, action: "type", text: "<text>"})` |
| `openclaw` | First ensure focused via `act click <ref>`, then `browser kind=act "type <ref> \"<escaped text>\""` |

**Verify:** after type, `read_attr(locator, "text")` contains first 40 chars of input.

### `press(tabId, key, modifiers?)`

| Backend | Tool sequence |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__computer({tabId, action: "key", text: "<chord>"})`. Chord format: `"Return"`, `"Escape"`, `"cmd+shift+o"` |
| `openclaw` | `browser kind=act "press <key>"` or `browser kind=act "press <modifiers>+<key>"` |

### `exists(tabId, locator) → bool`

**Critical for evaluate-free Phase D.** Must be cheap (no full snapshot).

| Backend | Strategy |
|---|---|
| `claude_code` | If `EVAL_DISABLED=false`: `javascript_tool({text: "!!document.querySelector('<css>')"})` → read bool. Else: `find({query: "<locator description>"})` → check returns non-empty. |
| `openclaw` | If `EVAL_DISABLED=false`: `browser kind=evaluate fn="!!document.querySelector('<css>')"`. Else: `browser kind=snapshot` + scan for matching ref (expensive — use sparingly). |

### `read_attr(tabId, locator, attr)`

| Backend | Strategy |
|---|---|
| `claude_code` | If eval: `javascript_tool({text: "document.querySelector('<css>')?.<attr>"})`. Else: `read_page({filter: "interactive"})` + extract from matching node. |
| `openclaw` | If eval: `browser kind=evaluate fn="document.querySelector('<css>')?.<attr>"`. Else: `snapshot` + extract. |

### `capture_response_body(tabId, url_pattern, timeout_ms)`

Use this only when the share dialog exposes a direct "复制链接 / Copy link" action and no stable readonly URL input.

| Backend | Strategy |
|---|---|
| `claude_code` | Not natively available. Prefer `share_url_input` polling if the UI exposes it; otherwise fall back to returning the private `chatgpt.com/c/<id>` URL instead of guessing. |
| `openclaw` | Prefer the most specific matcher you can, ideally `browser responsebody "https://chatgpt.com/backend-api/share/create" --target-id <tabId> --timeout-ms <timeout_ms>`. If you must use a broad glob like `"**/backend-api/share/**"`, be aware that current ChatGPT may first `POST /share/create` when the dialog opens and only later `PATCH /share/<uuid>` when "复制链接 / Copy link" is pressed. In the 2026-04-07 live run, the `PATCH` body only returned discoverability JSON, so the robust fallback was `browser requests --target-id <tabId> --filter share` and extracting `<uuid>` from the `PATCH /backend-api/share/<uuid>` request URL. This primitive only succeeds once it can emit a concrete `https://chatgpt.com/share/<uuid>` string; a copy-link toast or clipboard side effect does not count. Never substitute `conv_id` for `share_id`; `share/<conv_id>` is the wrong URL shape. If no concrete public URL can be recovered, Phase F must return `PRIVATE-ONLY` rather than prose like "copied successfully". |

### `wait_until(tabId, primitive_call, expected, timeout_ms, heartbeat_ms?)`

Loop the given primitive (usually `exists` or `read_attr`), compare to `expected`, every `poll_interval_ms` (default 2000ms for eval, 3000ms for evaluate-free). Emit heartbeat every `heartbeat_ms` if set. Raise on timeout.

| Backend | Note |
|---|---|
| both | Same loop structure. Pure LLM control — no tool-level wait primitive needed. |

### `wait_for_navigation(tabId, url_pred, timeout_ms)`

| Backend | Strategy |
|---|---|
| `claude_code` | Poll `tabs_context_mcp` every 300ms, extract matching tab's URL, check predicate. |
| `openclaw` | Poll `browser kind=tabs` every 300ms, same logic. |

### `screenshot(tabId, ref?)` (debug only)

| Backend | Tool |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__computer({tabId, action: "screenshot"})` |
| `openclaw` | `browser kind=screenshot [--ref <ref>]` |

---

## Evaluate-Free Fallback Notes (OpenClaw only)

When `EVAL_DISABLED=true`, the following degradations apply:

| Feature | Normal path | Degraded path |
|---|---|---|
| Phase A6 observer cleanup | skip (observer never installed) | skip |
| Phase C3 `execCommand` fallback | available | **unavailable** — if C3 verify fails, STOP with no retry |
| Phase D1 completion detection | MutationObserver polling `window.__cgptDone` | `exists(stop_button_selector)` every 3s |
| Phase D speed | ~2s poll on a cached flag | ~3s + full snapshot each time (slower, more context) |
| Phase E5 share link read | `evaluate: document.querySelector('input[readonly]').value` or visible copy-link UI fallback | Prefer exact `responsebody("https://chatgpt.com/backend-api/share/create")`; if only a broad share matcher is available and it returns discoverability JSON, inspect `requests --filter share` and extract the UUID from `PATCH /backend-api/share/<uuid>`; if unavailable, `snap` the dialog and look for a visible readonly value. If you still cannot print the concrete URL, treat the step as failed/private-only rather than "copied successfully". |

If a public share tab is already open, verify its visible content matches the target conversation before reusing that URL in Phase F.
| Share link poll cost | cheap | expensive — may need to relax 250ms → 500ms interval |

---

## Known asymmetries (neither backend hides these)

1. **`find()` natural-language query** only exists on Claude Code. OpenClaw equivalent is "snap + LLM filters results". Keep this in mind when the locator is `text` or `role_name`.

2. **Cmd+Shift+O hotkey** for new chat is backend-independent (Chrome itself handles it) but may need different `press` chord serialization.

3. **Tab management in OpenClaw** distinguishes `openclaw` profile from `user` profile. This skill must use the `user` profile (the one attached to the user's real logged-in Chrome). Set `--browser-profile user` on every `browser` call in OpenClaw mode.

4. **OpenClaw has a useful edge on share extraction.** The CLI/tool exposes both `responsebody` and `requests`. In the current copy-link dialog, `responsebody` is best when you can target `/backend-api/share/create` exactly; otherwise combine it with `requests --filter share` and extract the UUID from the observed `PATCH /backend-api/share/<uuid>` URL.

5. **Cloudflare challenge** appears the same on both. Neither should attempt to solve — STOP and tell the user.

# Backend Mapping — Primitives → Tool Calls

> How each primitive in `SKILL.md` is implemented on each backend.
> **Skill version:** 0.3.43

---

## Backend detection (runtime)

```
if tool "mcp__Claude_in_Chrome__tabs_context_mcp" in tools:
    BACKEND = "claude_code"
    EVAL_DISABLED = False   # Claude-in-Chrome always supports javascript_tool
elif tool "browser" in tools:
    BACKEND = "openclaw"
    # one-shot evaluate probe (cache the result for the rest of the run)
    result = browser(kind="evaluate", fn='() => "__CHATGPT_PRO_EVAL_OK__"')
    EVAL_DISABLED = (result is error or contains "disabled" or result != "__CHATGPT_PRO_EVAL_OK__")
elif tool "exec" in tools or tool "process" in tools:
    # mandatory concrete probe; do not conclude "no backend" from tool names alone
    status = exec('openclaw browser status 2>/dev/null')
    if status succeeded:
        BACKEND = "openclaw_cli_exec"
        # one-shot evaluate probe through the installed CLI
        result = exec('openclaw browser evaluate --fn '\''() => "__CHATGPT_PRO_EVAL_OK__"'\'' 2>/dev/null')
        EVAL_DISABLED = (result is error or exitCode != 0 or stdout does not contain "__CHATGPT_PRO_EVAL_OK__")
    else:
        raise "No compatible browser backend"
else:
    raise "No compatible browser backend"

if both available:
    raise "Ambiguous: both backends present, ask user"
```

### OpenClaw WebUI exec-only compatibility

Some OpenClaw WebUI sessions expose `exec` / `process` instead of the raw `browser` tool, while still having the OpenClaw CLI installed locally. In that case:

- Treat `openclaw browser ...` CLI calls as the concrete OpenClaw backend.
- Follow the concrete subcommand grammar from OpenClaw `2026.3.24`: `openclaw browser open <url>` takes no timeout flag, while `responsebody` uses `--timeout-ms <n>`. Do not append `--timeout <n>` after a subcommand.
- If the wrapped invocation reads `SKILL.md` and the next substantive action is still a plain-text answer instead of an `openclaw browser ...` CLI step, that run is invalid even when the raw `browser` tool is absent.
- If `exec` / `process` exists, first probe `openclaw browser status`. An exec-only host must not be classified as "Neither is available" without that concrete probe.
- Use the subcommands that actually exist on OpenClaw `2026.3.24`: `status`, `tabs`, `open`, `navigate`, `snapshot`, `click`, `fill`, `press`, `requests`, `responsebody`, `screenshot`.
- Do **not** invent `openclaw browser act ...` or `openclaw browser type ...` in exec-only mode.
- Do **not** execute the user prompt through `openclaw browser evaluate`. `evaluate` is reserved for inert backend probes or DOM inspection only. The prompt itself may only flow into Phase C composer fill/type operations on `chatgpt.com`.
- The sequence `openclaw browser status` + inert `openclaw browser evaluate --fn '() => "__CHATGPT_PRO_EVAL_OK__"'` + `openclaw browser tabs` is still setup-only. It does **not** authorize final output, and it does **not** justify reusing a private `https://chatgpt.com/c/<conv_id>` URL from the tab inventory as the reported share link.
- Even after `openclaw browser open https://chatgpt.com/`, the run is still in setup until it re-enumerates tabs, binds the dedicated `run_tab_id`, and takes a writable snapshot from that bound tab. Reading `references/selectors.md` before that point is allowed only as setup help; it is not evidence of successful execution.
- Once a logged-in `chatgpt.com` state has been verified in the default OpenClaw profile, stop retrying `--browser-profile user` on hosts where the attached user profile is unavailable.

---

## Consent gates

- A2 / D2 must use `AskUserQuestion` when that tool exists, otherwise the exact text-gate fallback from `references/consent-scripts.md`.
- In text-gate mode, the assistant turn must contain only the scripted question/options plus `Reply with exactly one option label.`
- On OpenClaw WebUI, prose such as "I'll start now", "准备好了吗？我将开始执行", or "✅ 确认继续" is a regression, not a valid consent turn.
- On the OpenClaw slash-wrapper path (`Use the "chatgpt-pro" skill for this request ... User input:`), directly answering `User input:` in plain text is also a regression. After `SKILL.md` is read, the next substantive step must be the browser workflow or a valid A2/D2 gate.
- After emitting a consent gate, pause until the user answers with one of the listed options exactly.
- A5 account audit and C4 pre-submit checks are silent internal phases in `v0.3.17+`. In `v0.3.19+`, exact `/chatgpt-pro <prompt>` invocation also authorizes public-share creation/retention for that prompt, so default runs must not emit E2 / E8 gates.
- OpenClaw `/skill chatgpt-pro <prompt>` may arrive in the model as `Use the "chatgpt-pro" skill for this request ... User input: <prompt>`. Treat that wrapper as equivalent to a literal `/chatgpt-pro <prompt>` invocation.
- Public-share work must never begin until the run is on a populated `/c/<conv_id>` page and Phase D completion has already been observed. On fresh-home `/`, the next step is still C/D, not sharing.
- If the fresh ChatGPT tab disappears before any submit evidence exists, OpenClaw may safely reopen one fresh `/` tab, restore Pro Advanced, rerun the silent A5/C4 checks, and continue. Once any submit evidence exists, never resubmit.
- If a fresh default run lands on `https://chatgpt.com/?temporary-chat=true` or on a visible `临时聊天` / `Temporary chat` page and the user did not ask for `--temporary`, escape that mode before typing or submitting. Never spend quota inside an unshareable temporary chat on a public-share run.
- If recovery lands on `auth.openai.com` or a `chatgpt.com` page exposing `登录` / `免费注册` / `Log in` / `Sign up`, STOP for manual re-login. Never automate auth-surface clicks.
- On OpenClaw fresh default runs, `browser status` and `browser tabs` are setup probes only. The run must immediately continue to `browser open https://chatgpt.com/`; stopping after status/tabs with no dedicated ChatGPT run tab is a regression.

## Primitive → Tool Mapping

### `ensure_session()` → `{tabId, backend, eval_disabled}`

| Backend | Tool sequence |
|---|---|
| `claude_code` | Fresh default run: enumerate tabs only to record existing `/c/<id>` conversation ids, then `mcp__Claude_in_Chrome__tabs_create_mcp()` and `mcp__Claude_in_Chrome__navigate({tabId, url: "https://chatgpt.com/"})` for the dedicated run tab. Resume/unshare: enumerate and bind to the requested `/c/<id>` tab. |
| `openclaw` / `openclaw_cli_exec` | Fresh default run: `browser kind=status` or `exec("openclaw browser status")` → `browser kind=tabs` or `exec("openclaw browser tabs")` only to record existing `/c/<id>` conversation ids → immediately `browser kind=open url=https://chatgpt.com/` or `exec("openclaw browser open https://chatgpt.com/")` for the dedicated run tab. Resume/unshare: enumerate and bind to the requested `/c/<id>` tab. |

### `rebind_tab(chosen_path?, conv_id?)` → `tabId`

| Backend | Tool sequence |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__tabs_context_mcp()` → filter `chatgpt.com` tabs → prefer exact URL path match on `chosen_path`, else exact `/c/<conv_id>` match, else sole remaining tab, else ask user again |
| `openclaw` / `openclaw_cli_exec` | `browser kind=tabs` or `exec("openclaw browser tabs")` → filter `chatgpt.com` tabs → prefer exact URL path match on `chosen_path`, else exact `/c/<conv_id>` match, else sole remaining tab, else ask user again |

**Use this whenever a prior browser action returns `tab not found`, or immediately after an A2 user selection on OpenClaw. Fresh default runs should rebind only to the dedicated run tab they created, never to an unrelated old `/c/<id>` tab.**

### `new_thread(tabId)`

| Backend | Tool sequence |
|---|---|
| `claude_code` | **Preferred:** `mcp__Claude_in_Chrome__find({tabId, query: "New chat sidebar button"})` → `mcp__Claude_in_Chrome__computer({tabId, action: "left_click", coordinate: [ref.x, ref.y]})`. **Fallback:** `mcp__Claude_in_Chrome__navigate({tabId, url: "https://chatgpt.com/"})` |
| `openclaw` / `openclaw_cli_exec` | **Preferred:** `browser kind=snapshot --format ai` or `exec("openclaw browser snapshot")` → find new-chat ref → `browser kind=click <ref>` or `exec("openclaw browser click <ref> [--target-id <tabId>]")`. **Fallback:** `browser kind=navigate url=https://chatgpt.com/` or `exec("openclaw browser navigate https://chatgpt.com/")` |

**Assertion (both):** wait for URL to match `/^https:\/\/chatgpt\.com\/?(\?.*)?$/` within 5s.

### `assert_host(tabId, expected_host)`

| Backend | Tool sequence |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__tabs_context_mcp` → find tab by id → check `url` starts with `https://<expected_host>` — if not, RAISE |
| `openclaw` / `openclaw_cli_exec` | `browser kind=tabs` or `exec("openclaw browser tabs")` → find by id → check hostname — if not, RAISE |

**This primitive MUST be called internally by every `click` / `type` / `press` before the write action.**

### `snap(tabId)`

| Backend | Tool sequence | Output form |
|---|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__read_page({tabId, filter: "interactive"})` | interactive tree with refs |
| `openclaw` / `openclaw_cli_exec` | Prefer `browser snapshot --format ai --labels` or `exec("openclaw browser snapshot")` before any click/type. Reserve `--format aria` for read-only diagnosis only. If the snapshot only exposes shell controls such as `跳至内容` / `Skip to content`, or only a tiny ref set on a page that is already known to contain the composer or share dialog, treat it as degenerate and re-snapshot before using any ref. Do **not** truncate a fresh-home snapshot to the first ~80 lines when searching for the composer; that hides the main pane and leaves only sidebar refs. | writable `e...` refs for actions; `ax...` aria refs are read-only |

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
| `openclaw` / `openclaw_cli_exec` | `ref`: `browser kind=click <ref>` or `exec("openclaw browser click <ref> [--target-id <tabId>]")`. `text`: `browser kind=snapshot` or `exec("openclaw browser snapshot")` → find matching node → `click <ref>`. `role_name`: same as text. `css`: `browser kind=evaluate fn="document.querySelector('<css>').click()"` (fails if eval disabled — fall back to snapshot+text search). If the latest writable snapshot is degenerate (`跳至内容` / `Skip to content`, or only tiny shell refs), discard those refs, re-snapshot, and retry. On the share dialog, prefer the pinned role/name click for `button "复制链接"` over blindly clicking tiny refs from a degenerate snapshot. |

**Always `assert_host` first. Always verify the click landed via a follow-up `snap` or `exists` probe.**

### `type(tabId, locator, text)`

**Critical:** the target is contenteditable. Use REAL keyboard events, not `form_input` / value setter.

| Backend | Tool sequence |
|---|---|
| `claude_code` | First `click(tabId, locator)` to focus, then `mcp__Claude_in_Chrome__computer({tabId, action: "type", text: "<text>"})` |
| `openclaw` | First ensure focused via click, then `browser kind=act "type <ref> \"<escaped text>\""` if the native browser tool exposes that primitive. |
| `openclaw_cli_exec` | First ensure focused via `exec("openclaw browser click <ref> [--target-id <tabId>]")`, then `exec("openclaw browser fill --fields '[{\"ref\":\"<ref>\",\"value\":\"<escaped text>\"}]' [--target-id <tabId>]")`. On OpenClaw `2026.3.24`, `fill` with `ref` + `value` is the working contenteditable path for the ChatGPT composer. Do **not** call nonexistent `openclaw browser act 'type ...'` or `openclaw browser type ...`. |

**Verify:** after type, `read_attr(locator, "text")` contains first 40 chars of input.
**OpenClaw guard:** only use a `textbox` ref whose accessible name matches the pinned composer label. If the chosen ref is a sidebar heading/link or returns `Element "<ref>" not found or not visible`, discard it, re-snapshot, and resolve the main-pane composer again.

### `press(tabId, key, modifiers?)`

| Backend | Tool sequence |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__computer({tabId, action: "key", text: "<chord>"})`. Chord format: `"Return"`, `"Escape"`, `"cmd+shift+o"` |
| `openclaw` / `openclaw_cli_exec` | `browser kind=press <key>` or `exec("openclaw browser press <key> [--target-id <tabId>]")` |

### `exists(tabId, locator) → bool`

**Critical for evaluate-free Phase D.** Must be cheap (no full snapshot).

| Backend | Strategy |
|---|---|
| `claude_code` | If `EVAL_DISABLED=false`: `javascript_tool({text: "!!document.querySelector('<css>')"})` → read bool. Else: `find({query: "<locator description>"})` → check returns non-empty. |
| `openclaw` / `openclaw_cli_exec` | If `EVAL_DISABLED=false`: `browser kind=evaluate fn="!!document.querySelector('<css>')"` or `exec('openclaw browser evaluate "!!document.querySelector(\\\"<css>\\\")"')`. Else: `browser kind=snapshot` or `exec("openclaw browser snapshot")` + scan for matching ref (expensive — use sparingly). |

### `read_attr(tabId, locator, attr)`

| Backend | Strategy |
|---|---|
| `claude_code` | If eval: `javascript_tool({text: "document.querySelector('<css>')?.<attr>"})`. Else: `read_page({filter: "interactive"})` + extract from matching node. |
| `openclaw` / `openclaw_cli_exec` | If eval: `browser kind=evaluate fn="document.querySelector('<css>')?.<attr>"` or `exec('openclaw browser evaluate "document.querySelector(\\\"<css>\\\")?.<attr>"')`. Else: `snapshot` + extract. |

### `capture_response_body(tabId, url_pattern, timeout_ms)`

Use this only when the share dialog exposes a direct "复制链接 / Copy link" action and no stable readonly URL input.

| Backend | Strategy |
|---|---|
| `claude_code` | Not natively available. Prefer `share_url_input` polling if the UI exposes it; otherwise fall back to returning the private `chatgpt.com/c/<id>` URL instead of guessing. |
| `openclaw` / `openclaw_cli_exec` | Prefer the most specific matcher you can, ideally `browser responsebody "https://chatgpt.com/backend-api/share/create" --target-id <tabId> --timeout-ms <timeout_ms>` or `exec("openclaw browser responsebody https://chatgpt.com/backend-api/share/create --target-id <tabId> --timeout-ms <timeout_ms>")`. If you must use a broad glob like `"**/backend-api/share/**"`, be aware that current ChatGPT may first `POST /share/create` when the dialog opens and only later `PATCH /share/<uuid>` when "复制链接 / Copy link" is pressed. In the 2026-04-07 live run, the `PATCH` body only returned discoverability JSON, so the robust fallback was `browser requests --target-id <tabId> --filter share` or `exec("openclaw browser requests --target-id <tabId>")` and extracting `<uuid>` from the `PATCH /backend-api/share/<uuid>` request URL. If that request log is empty but the copy click definitely happened and eval is available, immediately try `browser kind=evaluate fn="async () => await navigator.clipboard.readText()"` and accept the result only when it is a concrete `https://chatgpt.com/share/<uuid>` string. This matched a zenas-host OpenClaw WebUI run on 2026-04-08. This primitive only succeeds once it can emit a concrete `https://chatgpt.com/share/<uuid>` string; a copy-link toast alone does not count. Never substitute `conv_id` for `share_id`; `share/<conv_id>` is the wrong URL shape. If no concrete public URL can be recovered, Phase F must return `PRIVATE-ONLY` rather than prose like "copied successfully". |

### `wait_until(tabId, primitive_call, expected, timeout_ms, heartbeat_ms?)`

Loop the given primitive (usually `exists` or `read_attr`), compare to `expected`, every `poll_interval_ms` (default 2000ms for eval, 3000ms for evaluate-free). Emit heartbeat every `heartbeat_ms` if set. Raise on timeout.

| Backend | Note |
|---|---|
| both | Same loop structure. Pure LLM control — no tool-level wait primitive needed. |

### `wait_for_navigation(tabId, url_pred, timeout_ms)`

| Backend | Strategy |
|---|---|
| `claude_code` | Poll `tabs_context_mcp` every 300ms, extract matching tab's URL, check predicate. |
| `openclaw` / `openclaw_cli_exec` | Poll `browser kind=tabs` or `exec("openclaw browser tabs")` every 300ms, same logic. |

### `screenshot(tabId, ref?)` (debug only)

| Backend | Tool |
|---|---|
| `claude_code` | `mcp__Claude_in_Chrome__computer({tabId, action: "screenshot"})` |
| `openclaw` / `openclaw_cli_exec` | `browser kind=screenshot [--ref <ref>]` or `exec("openclaw browser screenshot [--ref <ref>]")` |

---

## Evaluate-Free Fallback Notes (OpenClaw only)

When `EVAL_DISABLED=true`, the following degradations apply:

| Feature | Normal path | Degraded path |
|---|---|---|
| Phase A6 observer cleanup | skip (observer never installed) | skip |
| Phase C3 `execCommand` fallback | available | **unavailable** — if C3 verify fails, STOP with no retry |
| Phase D1 completion detection | MutationObserver polling `window.__cgptDone` | `exists(stop_button_selector)` every 3s |
| Phase D speed | ~2s poll on a cached flag | ~3s + full snapshot each time (slower, more context) |
| Phase E5 share link read | `evaluate: document.querySelector('input[readonly]').value`, `requests --filter share`, or `evaluate: navigator.clipboard.readText()` right after the copy click | Prefer exact `responsebody("https://chatgpt.com/backend-api/share/create")`; if only a broad share matcher is available and it returns discoverability JSON, inspect `requests --filter share` and extract the UUID from `PATCH /backend-api/share/<uuid>`; if the request log is empty but eval is available, immediately try `navigator.clipboard.readText()` and accept it only when it returns a full `https://chatgpt.com/share/<uuid>` string. If unavailable, `snap` the dialog and look for a visible readonly value. If you still cannot print the concrete URL, treat the step as failed/private-only rather than "copied successfully". |

If a public share tab is already open, verify its visible content matches the target conversation before reusing that URL in Phase F.
| Share link poll cost | cheap | expensive — may need to relax 250ms → 500ms interval |

---

## Known asymmetries (neither backend hides these)

1. **`find()` natural-language query** only exists on Claude Code. OpenClaw equivalent is "snap + LLM filters results". Keep this in mind when the locator is `text` or `role_name`.

2. **Cmd+Shift+O hotkey** for new chat is backend-independent (Chrome itself handles it) but may need different `press` chord serialization.

3. **Tab management in OpenClaw** can distinguish `openclaw` profile from `user` profile, but some hosts do not have an attached `user` profile even when the operator is logged into a separate real Chrome. Prefer the attached user profile when it exists; if it fails repeatedly and a manually verified logged-in ChatGPT session is already present in the default OpenClaw profile, continue on that default profile instead of looping on `--browser-profile user`.

4. **OpenClaw has a useful edge on share extraction.** The CLI/tool exposes both `responsebody` and `requests`, and when eval is available the page context can sometimes read `navigator.clipboard.readText()` immediately after the copy click. In the current copy-link dialog, `responsebody` is best when you can target `/backend-api/share/create` exactly; otherwise combine it with `requests --filter share` and extract the UUID from the observed `PATCH /backend-api/share/<uuid>` URL. If the request log is empty, the clipboard API can still recover the concrete share URL.
5. **OpenClaw writable snapshots can transiently degrade after the share dialog opens.** A snapshot that only shows shell controls such as `跳至内容` / `Skip to content`, or only a tiny ref set, is not safe to drive. Re-snapshot first; if the dialog is already visibly open, prefer the pinned role/name click for `share_copy_link_button` instead of tiny refs like `e1/e2/e3`.

5. **Cloudflare challenge** appears the same on both. Neither should attempt to solve — STOP and tell the user.

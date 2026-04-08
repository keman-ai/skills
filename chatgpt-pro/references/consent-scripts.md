# Consent Scripts

> Exact wording of every `AskUserQuestion` the skill emits. Bilingual (EN + 中文).
> **Skill version:** 0.3.32
> **Rule:** These scripts MUST be used verbatim — do not rephrase at runtime.
> **Runtime rule:** When any script below is emitted, it must be the entire assistant turn. No leading prose, no trailing prose, no paraphrase, and no fake acknowledgement such as "✅ confirmed" before the user answers.
> **Consent mode rule:** If `AskUserQuestion` is available, emit the script through `AskUserQuestion`. Otherwise emit the same question and option labels as plain text, append `Reply with exactly one option label.`, then wait for the next user message.

---

## A2 — Multiple chatgpt.com tabs

### EN
**Question:** "Multiple chatgpt.com tabs are open. Which one should I use?"
**Header:** "Select tab"
**Options:**
- `<URL path 1>` — Description: `Tab 1`
- `<URL path 2>` — Description: `Tab 2`
- ... (max 4)

### 中文
**Question:** "检测到多个 chatgpt.com 标签页，使用哪一个？"
**Header:** "选择标签页"
**Options:**
- `<URL path 1>` — Description: `标签页 1`

**Rules:**
- Show URL path only (e.g. `/c/abc123...`), NEVER `document.title`
- Never auto-pick the "frontmost" — user must choose
- Max 4 tabs shown; if more, group overflow into "Other" (user types in)

---

## Retired gates (do not emit)

Starting in `v0.3.19`, the skill no longer emits per-run A5, C4, E2, or E8 confirmation dialogs for explicit default `/chatgpt-pro` runs.

- Exact `/chatgpt-pro <prompt>` invocation, or an explicit instruction to use ChatGPT Pro for a specific prompt and return the shareable result, already counts as authorization to use the currently logged-in ChatGPT account in that browser profile, spend one Pro invocation, and generate/keep the public share link.
- The skill still performs the A5 **account audit** and C4 **pre-submit checks**, but both are silent internal phases now.
- Default fresh runs and exact `--resume` runs must not pause for any extra share-confirmation or keep/revoke choice.
- If the wrong account is signed in, or the browser is on a guest/auth surface, the skill must STOP with an error instead of asking the user to answer an extra A5/C4 gate inside the run.
- A2 and D2 remain the only normal interactive gates.
- The following legacy prompts are forbidden on explicit fresh runs and wrapped OpenClaw `/skill chatgpt-pro <prompt>` runs:
  - `即将使用此浏览器 Profile 当前登录的 ChatGPT 账号。继续？`
  - `继续`
  - `切换账号（停止）`
  - `即将用 ChatGPT Pro 5.4（进阶思考）提交。消耗 1 次 Pro 配额。继续？`
  - `发送`
  - `取消`

---

## D2 — 10-min heartbeat

### EN
**Question:** "10 minutes elapsed. Still thinking. Continue waiting?"
**Header:** "Wait?"
**Options:**
- `Wait 5 more` — Description: `Keep polling until 15 min`
- `Give up (leave run)` — Description: `Exit skill cleanly. The run continues on chatgpt.com. Use /chatgpt-pro --resume <conv_id> to reconnect.`

### 中文
**Question:** "已等待 10 分钟，仍在思考。继续等吗？"
**Header:** "继续等待？"
**Options:**
- `再等 5 分钟` — Description: `继续轮询到 15 分钟`
- `放弃（保留 chatgpt 页面的运行）` — Description: `干净退出 skill，chatgpt 继续跑。下次用 /chatgpt-pro --resume <conv_id> 接回来`

---

## D2 — 15-min ceiling

### EN
Same structure, different preamble:
**Question:** "15-minute ceiling reached. What now?"
**Options:**
- `Wait 5 more (up to 20 min)`
- `Exit (leave run on chatgpt)`

### 中文
**Question:** "已到达 15 分钟上限。下一步？"
**Options:**
- `再等 5 分钟`
- `退出（保留 chatgpt 的运行）`

---

## Top-level slash routing

The skill accepts these subcommands via the invocation string. If the user types bare `/chatgpt-pro <prompt>` the default flow runs. Otherwise:

| User input | Skill flow |
|---|---|
| `/chatgpt-pro <prompt>` | Default (A→F) |
| `/chatgpt-pro --temporary <prompt>` | Skip Phase E |
| `/chatgpt-pro --unshare <conv_id>` | Fresh flow: locate conversation, open share dialog, click delete, confirm. New consent gate. |
| `/chatgpt-pro --spike` | DOM Spike flow (see references/selectors.md) |
| `/chatgpt-pro --respike` | Force re-spike |
| `/chatgpt-pro --resume <conv_id>` | Check `.in-flight.json`, run Phase E only |

For ambiguous inputs ("ask chatgpt about X"), DO NOT trigger the skill — instead AskUserQuestion: "Did you mean ChatGPT Pro 5.4 specifically? This burns your weekly Pro quota. [Yes / No]".

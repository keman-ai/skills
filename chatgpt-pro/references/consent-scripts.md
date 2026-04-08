# Consent Scripts

> Exact wording of every `AskUserQuestion` the skill emits. Bilingual (EN + 中文).
> **Skill version:** 0.3.7
> **Rule:** These scripts MUST be used verbatim — do not rephrase at runtime.

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

## A5 — Account confirmation

### EN
**Question:** "About to use ChatGPT Pro 5.4 quota from account `<email>`. Continue?"
**Header:** "Confirm account"
**Options:**
- `Continue` — Description: `Use this account's Pro quota for one invocation`
- `Switch account (stop)` — Description: `Exit the skill so you can switch Chrome profile manually`

### 中文
**Question:** "即将使用账号 `<email>` 的 ChatGPT Pro 5.4 配额。继续？"
**Header:** "确认账号"
**Options:**
- `继续` — Description: `使用此账号消耗一次 Pro 配额`
- `切换账号（停止）` — Description: `退出 skill，手动切换 Chrome Profile 后再调用`

### Variants
- If cross-check (NEXT_DATA + backend-api/me) mismatched:
  **EN:** "Account cross-check mismatch (sidebar says `<A>`, backend says `<B>`). This may indicate tampering. Continue anyway?"
  **Options:** `Abort (recommended)` / `Continue anyway (not recommended)`
  **中文:** "账号交叉校验不一致（侧边栏：`<A>`，后端：`<B>`）。可能存在篡改。是否继续？"
- If no safe email is available (common on OpenClaw evaluate-free runs):
  **EN:** "About to use the currently signed-in ChatGPT account in this browser profile. Continue?"
  **Options:** `Continue` / `Switch account (stop)`
  **中文:** "即将使用此浏览器 Profile 当前登录的 ChatGPT 账号。继续？"
  **Options:** `继续` / `切换账号（停止）`

---

## C4 — Pre-submit final confirmation

### EN
**Question:** "Ready to submit to ChatGPT Pro 5.4 (Advanced thinking). This burns 1 Pro invocation from your weekly quota. Prompt: `len=<N>, head=\"<first 3>\", tail=\"<last 3>\"`. Continue?"
**Header:** "Submit"
**Options:**
- `Send` — Description: `Press Enter now`
- `Cancel` — Description: `Exit without submitting (no quota used)`

### 中文
**Question:** "即将用 ChatGPT Pro 5.4（进阶思考）提交。消耗 1 次 Pro 配额。Prompt: `长度=<N>, 开头=\"<前3字>\", 结尾=\"<后3字>\"`。继续？"
**Header:** "发送"
**Options:**
- `发送` — Description: `按回车提交`
- `取消` — Description: `不提交，不消耗配额`

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

## E2 — Per-call share confirmation (CRITICAL)

### EN
**Question:** "About to generate a PUBLIC share link for this conversation. Anyone with the link can read the entire conversation (both your prompt and the answer). Prompt summary: `len=<N>, head=\"<first 3>\", tail=\"<last 3>\"`. Choose:"
**Header:** "Share?"
**Options:**
- `Generate share link` — Description: `Public — anyone with the URL can read it`
- `Return private link only` — Description: `chatgpt.com/c/<id>, only your account can read it`
- `Cancel` — Description: `Skill finishes, nothing returned. The conversation remains in your account history.`

### 中文
**Question:** "即将为此对话生成 **公开** 分享链接。任何持有链接的人都能看到完整对话（你的提示词 + AI 的答复）。Prompt 摘要：`长度=<N>, 开头=\"<前3字>\", 结尾=\"<后3字>\"`。"
**Header:** "分享？"
**Options:**
- `生成分享链接` — Description: `公开 — 任何拿到链接的人都能读`
- `仅返回私有链接` — Description: `chatgpt.com/c/<id>，仅你的账号可见`
- `取消` — Description: `什么也不返回。对话仍保留在你的账号历史中`

**Rules:**
- Show this EVERY call — never cache consent across calls
- The prompt summary uses `len + head + tail`, NOT a hash
- Never omit the "anyone with the link" warning

---

## E7 — Post-share decision

### EN
**Question:** "Share link generated: `<url>`. Keep it public, or revoke immediately?"
**Header:** "Keep or revoke?"
**Options:**
- `Keep public` — Description: `Return the URL and exit. You can revoke later with /chatgpt-pro --unshare <conv_id>.`
- `Revoke now (synchronous)` — Description: `Click the delete-link button now. May take up to 60s.`

### 中文
**Question:** "分享链接已生成：`<url>`。保持公开，还是立刻撤销？"
**Header:** "保持/撤销"
**Options:**
- `保持公开` — Description: `返回链接并退出。之后可用 /chatgpt-pro --unshare <conv_id> 撤销。`
- `立即撤销（同步，最多 60s）` — Description: `现在就点击删除链接按钮`

**Rules:**
- NO "revoke after 30 minutes" option — that was越权 (see security review)
- NO deferred scheduling — revocation happens in this turn or via a separate call

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

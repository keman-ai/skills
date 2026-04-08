# chatgpt-pro — Installation Guide

Dual-platform skill for **Claude Code** and **OpenClaw**. Single source, two install paths.

---

## Prerequisites (both platforms)

1. **Chrome (or Chromium) with a logged-in `chatgpt.com` session**
   - Pro 5.4 subscription active on the logged-in account
   - "思考时长 / Thinking duration" modal and "Pro 进阶思考 / Advanced" option visible in the UI
2. **A compatible browser automation backend** — see below per platform
3. **Willingness to run a one-time DOM Spike** (~3 min) before first use

---

## Install on Claude Code

**1. Drop the skill into `~/.claude/skills/chatgpt-pro/`:**

```bash
# If installing from this repo
cp -r chatgpt-pro ~/.claude/skills/

# Or clone directly
git clone https://github.com/<your-org>/chatgpt-pro ~/.claude/skills/chatgpt-pro
```

**2. Verify Claude Code picks it up:**

Start a new Claude Code session. The skill should appear in the available-skills list as `chatgpt-pro`. If not:
- Check `~/.claude/skills/chatgpt-pro/SKILL.md` exists and has valid frontmatter
- Check file permissions (`chmod -R u+rX ~/.claude/skills/chatgpt-pro`)

**3. Install the Claude in Chrome MCP extension** (for browser control):

Follow the setup at https://claude.ai/code under "Browser automation". The extension provides `mcp__Claude_in_Chrome__*` tools.

**4. Log in to chatgpt.com** in your normal Chrome profile, confirm you can use Pro 5.4 manually.

**5. Run the DOM Spike:**

```
/chatgpt-pro --spike
```

Follow the on-screen steps (~3 minutes). At the end, `references/selectors.md` will be populated and signed.

**6. Smoke test:**

```bash
./scripts/validate-skill.sh
/chatgpt-pro 1+1=?
```

Expected: validation passes first, then the live run returns a `https://chatgpt.com/share/<uuid>` link in Phase F output.

---

## Install on OpenClaw

**1. Install a real copy into the OpenClaw workspace skill root:**

OpenClaw loads workspace skills from the active workspace, typically `~/.openclaw/workspace/skills/`. It will **skip** symlinked skill folders that resolve outside the configured workspace root.

```bash
./scripts/validate-skill.sh
./scripts/install-openclaw-skill.sh
```

The installer script:
- discovers the active OpenClaw `workspaceDir`
- copies this skill into `<workspaceDir>/skills/chatgpt-pro`
- excludes local debug artifacts such as `.playwright-cli/` and `output/`
- verifies `openclaw skills info chatgpt-pro` succeeds afterward

**Do not use a symlink from outside the workspace**, for example:
```bash
ln -s /some/other/repo/chatgpt-pro ~/.openclaw/workspace/skills/chatgpt-pro
```
OpenClaw will print `[skills] Skipping skill path that resolves outside its configured root.` and ignore it.

**2. Verify the skill is recognized:**

```bash
openclaw skills info chatgpt-pro
```

**3. Verify the `browser` tool is available:**

```bash
openclaw browser status
```

If the browser CLI says the gateway is closed, start or restart OpenClaw's gateway first. The skill expects the `user` profile (attached to your real Chrome), not the managed `openclaw` profile.

**4. Configure `browser.profiles.user`** in your OpenClaw config to point at your real Chrome's user-data directory, so the skill can attach to your logged-in chatgpt.com session. Consult OpenClaw docs for exact syntax.

**5. (Optional) Verify `browser.evaluateEnabled`:**

```bash
openclaw browser --browser-profile user evaluate --fn "1+1"
```

- Returns `2` → evaluate enabled, skill uses the fast path
- Returns error "disabled" → skill uses the evaluate-free fallback (slower but still works)

Either is fine. The skill auto-detects at runtime.

**6. Load the skill:**

Restart OpenClaw or use its skill reload command. The skill should appear with the 🧠 emoji.

**7. Run the DOM Spike:**

From an OpenClaw session, invoke the skill with `--spike` (exact syntax depends on your OpenClaw CLI/UI).

**8. Smoke test:**

Run `./scripts/validate-skill.sh`, then send `1+1=?` through the skill and verify a share link is returned.

---

## Uninstall

### Claude Code
```bash
rm -rf ~/.claude/skills/chatgpt-pro
```

### OpenClaw
```bash
rm -rf ~/.openclaw/workspace/skills/chatgpt-pro
```

**Also clean up local state:**
```bash
rm -f ~/.claude/skills/chatgpt-pro/.in-flight.json
rm -f ~/.claude/skills/chatgpt-pro/history.jsonl
```

---

## Updates

When you pull a new version:
1. `cd ~/.claude/skills/chatgpt-pro && git pull` (or re-copy)
2. Check `references/selectors.md` → `Last verified` date
3. If `Last verified` is >7 days old OR the B-1 health check fails on next invocation → run `/chatgpt-pro --respike`
4. Re-run smoke tests (`evals/smoke.md`)
5. Re-run `./scripts/validate-skill.sh`

---

## Troubleshooting install

- **"Skill not recognized"** on Claude Code → Check SKILL.md frontmatter is valid YAML with `name:` and `description:` fields. Restart Claude Code.
- **"[skills] Skipping skill path that resolves outside its configured root."** on OpenClaw → remove the symlink and run `./scripts/install-openclaw-skill.sh`.
- **"No browser tool available"** on OpenClaw → `openclaw browser status` to verify; check OpenClaw config; ensure you're not running with `--no-tools=browser` or similar.
- **"Cloudflare challenge blocks login"** on either platform → log in manually in a non-headless Chrome first, solve the challenge, then let the skill attach.
- **"evaluate disabled"** on OpenClaw → Either enable it in config, or accept the slower fallback path (it works).

See `references/troubleshooting.md` for runtime issues (after install works).

---

## Security note before your first `--spike`

The DOM Spike captures a filtered snapshot of chatgpt.com's structure. The filter scrubs emails, tokens, and text content before writing to disk — but you should still **eyeball** the proposed `selectors.md` before you sign off on it. If you see any real email address, conversation title, or long token-looking string, ABORT and report a bug.

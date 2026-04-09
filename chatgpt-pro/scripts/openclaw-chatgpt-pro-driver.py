#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import site
import socket
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_WARNING_RE = re.compile(r"^Config warnings:\\n", re.MULTILINE)
PLUGIN_WARNING_RE = re.compile(r"^- plugins\.entries\.a2hmarket: .*$", re.MULTILINE)
BOX_LINE_RE = re.compile(r"^[│├┤╭╮╯╰◇].*$", re.MULTILINE)
OPENED_ID_RE = re.compile(r"^id:\s*([A-F0-9]+)\s*$", re.MULTILINE)
TAB_ENTRY_RE = re.compile(
    r"^\d+\.\s+(?P<title>.+?)\n\s+(?P<url>\S+)\n\s+id:\s*(?P<id>[A-F0-9]+)\s*$",
    re.MULTILINE,
)
CONV_URL_RE = re.compile(r"https://chatgpt\.com/c/([a-zA-Z0-9-]+)")
CONV_REQ_RE = re.compile(r"/conversation/([a-zA-Z0-9-]+)")
SHARE_URL_RE = re.compile(r"https://chatgpt\.com/share/([a-zA-Z0-9-]+)")
SHARE_REQ_RE = re.compile(r"https://chatgpt\.com/backend-api/share/([a-zA-Z0-9-]+)")
SNAPSHOT_LINE_RE = re.compile(
    r'^\s*-\s+(?P<role>[A-Za-z]+)\s+"(?P<label>[^"]+)"(?P<meta>[^\n]*?\[ref=(?P<ref>e\d+)\][^\n]*)$',
    re.MULTILINE,
)
DEBUG = os.environ.get("CHATGPT_PRO_DEBUG") == "1"
CDP_PROBE_SCRIPT = Path(__file__).with_name("cdp_browser_probe.py")


def debug(message: str) -> None:
    if DEBUG:
        print(f"[chatgpt-pro] {message}", file=sys.stderr, flush=True)


def now_ms() -> int:
    return int(time.time() * 1000)


def sha256_prefix(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def fmt_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60}m {total % 60}s"


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def should_use_cdp_probe() -> bool:
    override = os.environ.get("CHATGPT_PRO_USE_CDP_PROBE", "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    if not CDP_PROBE_SCRIPT.exists():
        return False
    host = socket.gethostname().lower()
    if "huanghaibin" in host:
        return True
    clone_dir = Path.home() / ".openclaw/browser/chatgpt-pro-gui-clone"
    return sys.platform == "darwin" and clone_dir.exists()


@dataclass
class BrowserResult:
    code: int
    stdout: str
    stderr: str


class DriverError(RuntimeError):
    pass


def is_tab_not_found(error: Exception) -> bool:
    return "tab not found" in str(error).lower()


class OpenClawBrowser:
    def __init__(self, browser_profile: str | None = None) -> None:
        normalized = (browser_profile or "").strip()
        if normalized.lower() in {"", "default", "openclaw"}:
            normalized = ""
        self.browser_profile = normalized or None
        self.base = ["openclaw", "browser"]
        if self.browser_profile:
            self.base.extend(["--browser-profile", self.browser_profile])

    def _strip_output(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text.replace("\r\n", "\n")
        cleaned = CONFIG_WARNING_RE.sub("", cleaned)
        cleaned = PLUGIN_WARNING_RE.sub("", cleaned)
        cleaned = BOX_LINE_RE.sub("", cleaned)
        cleaned = re.sub(r"^\s*\n", "", cleaned, flags=re.MULTILINE)
        return cleaned.strip()

    def run(self, *args: str, check: bool = True, timeout: int = 60) -> BrowserResult:
        proc = subprocess.run(
            [*self.base, *args],
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        stdout = self._strip_output(proc.stdout)
        stderr = self._strip_output(proc.stderr)
        if check and proc.returncode != 0:
            raise DriverError(f"openclaw browser {' '.join(args)} failed: {stderr or stdout or proc.returncode}")
        return BrowserResult(proc.returncode, stdout, stderr)

    def status(self) -> dict[str, str]:
        result = self.run("status")
        status: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            status[key.strip()] = value.strip()
        return status

    def tabs(self) -> list[dict[str, str]]:
        result = self.run("tabs")
        tabs = []
        for match in TAB_ENTRY_RE.finditer(result.stdout):
            tabs.append(
                {
                    "title": match.group("title").strip(),
                    "url": match.group("url").strip(),
                    "id": match.group("id").strip(),
                }
            )
        return tabs

    def open(self, url: str) -> str:
        result = self.run("open", url)
        match = OPENED_ID_RE.search(result.stdout)
        if not match:
            raise DriverError(f"unable to parse opened tab id from: {result.stdout}")
        return match.group(1)

    def navigate(self, target_id: str, url: str) -> None:
        self.run("navigate", url, "--target-id", target_id, timeout=30)

    def requests(self, target_id: str, filter_text: str | None = None, clear: bool = False) -> str:
        args = ["requests", "--target-id", target_id]
        if filter_text:
            args.extend(["--filter", filter_text])
        if clear:
            args.append("--clear")
        return self.run(*args, timeout=30).stdout

    def snapshot(self, target_id: str, fmt: str = "ai") -> str:
        return self.run("snapshot", "--target-id", target_id, "--format", fmt, timeout=60).stdout

    def fill(self, target_id: str, fields: list[dict[str, str]]) -> None:
        self.run("fill", "--target-id", target_id, "--fields", json.dumps(fields, ensure_ascii=False), timeout=30)

    def click(self, target_id: str, ref: str) -> None:
        self.run("click", ref, "--target-id", target_id, timeout=30)

    def press(self, target_id: str, key: str) -> None:
        self.run("press", key, "--target-id", target_id, timeout=20)

    def eval_json(self, target_id: str, fn: str, timeout: int = 60) -> Any:
        result = self.run("evaluate", "--target-id", target_id, "--fn", fn, timeout=timeout)
        text = result.stdout.strip()
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch not in "[{":
                continue
            try:
                payload, _ = decoder.raw_decode(text[idx:])
                return payload
            except json.JSONDecodeError:
                continue
        raise DriverError(f"unable to parse JSON from evaluate output: {text[:400]}")


def page_state_fn() -> str:
    return r"""() => {
  const text = (el) => ((el?.innerText || el?.textContent || '').replace(/\s+/g, ' ').trim());
  const buttons = [...document.querySelectorAll('button,a,[role="button"],[role="menuitem"]')].map((el) => ({
    tag: el.tagName,
    role: el.getAttribute('role') || '',
    aria: el.getAttribute('aria-label') || '',
    text: text(el).slice(0, 120),
    disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true'
  }));
  const mainText = (document.querySelector('main')?.innerText || '').slice(0, 1200);
  const bodyText = (document.body?.innerText || '').slice(0, 1200);
  const has = (matcher) => buttons.some((entry) => matcher.test(`${entry.aria} ${entry.text}`.trim()));
  return {
    href: location.href,
    title: document.title,
    mainText,
    bodyText,
    guest: /登录|免费注册|Log in|Sign up/.test(bodyText) || /auth\.openai\.com/.test(location.href),
    temporary: /temporary-chat=true/.test(location.href) || /临时聊天|Temporary chat/.test(bodyText),
    composer: !!document.querySelector('textarea,[role="textbox"],[contenteditable="true"]'),
    advanced: has(/进阶专业|Advanced thinking/),
    share: has(/分享|复制链接|Copy link|Share/),
    copyLink: has(/复制链接|Copy link/),
    stop: has(/停止流式传输|Stop streaming/),
    buttons: buttons.filter((entry) => /模型选择器|进阶专业|分享|复制链接|与 ChatGPT 聊天|新聊天|Pro|临时聊天|Temporary/.test(JSON.stringify(entry))).slice(0, 80)
  };
}"""


def click_text_fn(pattern: str, prefer_header_share: bool = False) -> str:
    pattern_json = js_string(pattern)
    return f"""() => {{
  const regex = new RegExp({pattern_json}, 'i');
  const text = (el) => ((el?.innerText || el?.textContent || '').replace(/\\s+/g, ' ').trim());
  const visible = (el) => {{
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  }};
  const score = (el) => {{
    let value = 0;
    if (visible(el)) value += 100;
    if ({'true' if prefer_header_share else 'false'}) {{
      if (el.closest('header')) value += 50;
      if (el.closest('main > div')) value += 10;
      if (el.closest('article,[data-message-author-role],li')) value -= 40;
    }}
    return value;
  }};
  const nodes = [...document.querySelectorAll('button,a,[role="button"],[role="menuitem"]')];
  const matches = nodes.filter((el) => regex.test((el.getAttribute('aria-label') || '') + ' ' + text(el)));
  matches.sort((a, b) => score(b) - score(a));
  const chosen = matches[0];
  if (!chosen) return {{ok:false, count:0}};
  chosen.click();
  return {{
    ok:true,
    count: matches.length,
    chosenAria: chosen.getAttribute('aria-label') || '',
    chosenText: text(chosen).slice(0, 120)
  }};
}}"""


def set_prompt_fn(prompt: str) -> str:
    prompt_json = js_string(prompt)
    return f"""() => {{
  const prompt = {prompt_json};
  const textarea = document.querySelector('textarea[aria-label="与 ChatGPT 聊天"], textarea');
  const editable = document.querySelector('[role="textbox"][contenteditable="true"], [contenteditable="true"][aria-label="与 ChatGPT 聊天"]');
  const target = textarea || editable;
  if (!target) return {{ok:false, reason:'composer-missing'}};
  const fireInput = (el) => {{
    el.dispatchEvent(new InputEvent('input', {{bubbles:true, inputType:'insertText', data: prompt}}));
    el.dispatchEvent(new Event('change', {{bubbles:true}}));
  }};
  target.focus();
  if (target.tagName === 'TEXTAREA') {{
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
    if (setter) {{
      setter.call(target, prompt);
    }} else {{
      target.value = prompt;
    }}
    fireInput(target);
    return {{ok:true, kind:'textarea', valueLen: target.value.length}};
  }}
  target.innerHTML = '';
  target.textContent = prompt;
  fireInput(target);
  const selection = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(target);
  range.collapse(false);
  selection.removeAllRanges();
  selection.addRange(range);
  return {{ok:true, kind:'contenteditable', valueLen: (target.innerText || target.textContent || '').length}};
}}"""


def clipboard_fn() -> str:
    return """async () => {
  try {
    return {ok:true, text: await navigator.clipboard.readText()};
  } catch (error) {
    return {ok:false, error: String(error)};
  }
}"""


def submit_prompt_fn() -> str:
    return """() => {
  const text = (el) => ((el?.innerText || el?.textContent || '').replace(/\\s+/g, ' ').trim());
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const ta = document.querySelector('textarea');
  const form = ta?.closest('form') || ta?.parentElement?.closest('form') || ta?.parentElement;
  if (!form) return {ok:false, reason:'composer-form-missing'};
  const buttons = [...form.querySelectorAll('button')];
  const score = (el) => {
    const label = `${el.getAttribute('aria-label') || ''} ${text(el)}`;
    let value = 0;
    if (visible(el)) value += 100;
    if (/发送|send|submit/i.test(label)) value += 100;
    if ((el.className || '').includes('composer-submit-button-color')) value += 40;
    if ((el.type || '').toLowerCase() === 'submit') value += 20;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') value -= 1000;
    return value;
  };
  buttons.sort((a, b) => score(b) - score(a));
  const chosen = buttons[0];
  if (!chosen) return {ok:false, reason:'composer-submit-missing'};
  chosen.click();
  return {
    ok:true,
    aria: chosen.getAttribute('aria-label') || '',
    text: text(chosen).slice(0, 80),
    className: (chosen.className || '').slice(0, 160)
  };
}"""


def verify_share_fn(expected_url: str) -> str:
    expected_json = js_string(expected_url)
    return f"""() => {{
  const expected = {expected_json};
  return {{
    href: location.href,
    title: document.title,
    ok: location.href === expected && !/404|Not Found|无法访问/.test(document.body?.innerText || '')
  }};
}}"""


def probe_tab_fn() -> str:
    return """() => ({href: location.href, title: document.title})"""


def wait_for(predicate, timeout_s: float, interval_s: float = 0.5):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval_s)
    return last


def resolve_browser(requested_profile: str | None) -> tuple[OpenClawBrowser, dict[str, str], list[str]]:
    requested = (requested_profile or os.environ.get("CHATGPT_PRO_BROWSER_PROFILE") or "auto").strip()
    requested = requested or "auto"
    warnings: list[str] = []

    def probe(profile_name: str | None) -> tuple[OpenClawBrowser, dict[str, str]]:
        browser = OpenClawBrowser(profile_name)
        status = browser.status()
        label = browser.browser_profile or "openclaw"
        if status.get("running") != "true":
            raise DriverError(f"OpenClaw browser profile {label} is not running.")
        debug(f"resolved browser profile={label}")
        return browser, status

    normalized = requested.lower()
    if normalized == "auto":
        failures: list[str] = []
        for candidate in ("user", None):
            label = candidate or "openclaw"
            try:
                browser, status = probe(candidate)
                if candidate is None and failures:
                    warnings.append("browser-profile auto-fallback -> openclaw")
                return browser, status, warnings
            except DriverError as exc:
                failures.append(f"{label}: {exc}")
                debug(f"browser profile probe failed profile={label} error={exc}")
        raise DriverError("unable to resolve a working OpenClaw browser profile: " + "; ".join(failures))

    profile_name = None if normalized in {"default", "openclaw"} else requested
    browser, status = probe(profile_name)
    return browser, status, warnings


def parse_share_url_from_requests(text: str) -> str | None:
    matches = [m.group(1) for m in SHARE_REQ_RE.finditer(text) if m.group(1) != "create"]
    if not matches:
        return None
    return f"https://chatgpt.com/share/{matches[-1]}"


def parse_conv_id(url: str) -> str | None:
    match = CONV_URL_RE.search(url)
    return match.group(1) if match else None


def parse_conv_id_from_requests(text: str) -> str | None:
    matches = [m.group(1) for m in CONV_REQ_RE.finditer(text) if m.group(1) != "prepare"]
    if not matches:
        return None
    return matches[-1]


def parse_share_url_from_tabs(tabs: list[dict[str, str]]) -> str | None:
    for tab in reversed(tabs):
        match = SHARE_URL_RE.search(tab["url"])
        if match:
            return f"https://chatgpt.com/share/{match.group(1)}"
    return None


def is_root_chatgpt_url(url: str) -> bool:
    return bool(re.fullmatch(r"https://chatgpt\.com/(?:\?.*)?", url))


def is_browser_error_state(state: dict[str, Any]) -> bool:
    href = str(state.get("href", ""))
    haystack = " ".join(
        [
            href,
            str(state.get("title", "")),
            str(state.get("mainText", "")),
            str(state.get("bodyText", "")),
        ]
    )
    return bool(
        href.startswith("chrome-error://")
        or re.search(
            r"ERR_CONNECTION_CLOSED|无法访问此网站|This site can.?t be reached|This page isn.?t working",
            haystack,
            re.IGNORECASE,
        )
    )


def snapshot_ref_candidates(snapshot: str, *, role: str, label_pattern: str) -> list[dict[str, str | int | bool]]:
    label_re = re.compile(label_pattern, re.IGNORECASE)
    candidates: list[dict[str, str | int | bool]] = []
    for index, match in enumerate(SNAPSHOT_LINE_RE.finditer(snapshot)):
        if match.group("role").lower() != role.lower():
            continue
        label = match.group("label")
        if not label_re.search(label):
            continue
        meta = match.group("meta") or ""
        score = 0
        if "[active]" in meta:
            score += 50
        if "[cursor=pointer]" in meta:
            score += 10
        if "[disabled]" in meta:
            score -= 1000
        candidates.append(
            {
                "ref": match.group("ref"),
                "label": label,
                "meta": meta,
                "score": score,
                "index": index,
                "disabled": "[disabled]" in meta,
            }
        )
    candidates.sort(key=lambda item: (int(item["score"]), -int(item["index"])), reverse=True)
    return candidates


def require_snapshot_ref(
    snapshot: str,
    *,
    role: str,
    label_pattern: str,
    require_enabled: bool = False,
) -> dict[str, str | int | bool]:
    candidates = snapshot_ref_candidates(snapshot, role=role, label_pattern=label_pattern)
    if require_enabled:
        candidates = [item for item in candidates if not item["disabled"]]
    if not candidates:
        raise DriverError(f"unable to find snapshot ref for {role} /{label_pattern}/")
    return candidates[0]


def rebind_chatgpt_tab(
    *,
    pre_tabs: list[dict[str, str]],
    post_tabs: list[dict[str, str]],
    opened_id: str | None = None,
    conv_id: str | None = None,
    prefer_root: bool = False,
) -> str:
    pre_ids = {tab["id"] for tab in pre_tabs}
    candidates = [tab for tab in post_tabs if "chatgpt.com" in tab["url"]]
    if opened_id:
        for tab in candidates:
            if tab["id"] == opened_id:
                return tab["id"]
    if conv_id:
        for tab in candidates:
            if f"/c/{conv_id}" in tab["url"]:
                return tab["id"]
    new_tabs = [tab for tab in candidates if tab["id"] not in pre_ids]
    if prefer_root:
        for tab in new_tabs:
            if re.fullmatch(r"https://chatgpt\.com/(?:\?.*)?", tab["url"]):
                return tab["id"]
    if new_tabs:
        return new_tabs[0]["id"]
    if prefer_root:
        for tab in candidates:
            if re.fullmatch(r"https://chatgpt\.com/(?:\?.*)?", tab["url"]):
                return tab["id"]
    if len(candidates) == 1:
        return candidates[0]["id"]
    raise DriverError("unable to rebind a live chatgpt.com tab id")


def prompt_block(prompt_text: str) -> tuple[str, int]:
    prompt_text = prompt_text.rstrip("\n")
    return sha256_prefix(prompt_text), len(prompt_text)


def bind_live_chatgpt_tab(
    browser: OpenClawBrowser,
    *,
    pre_tabs: list[dict[str, str]],
    opened_id: str | None = None,
    conv_id: str | None = None,
    prefer_root: bool = False,
    timeout_s: float = 20.0,
) -> str:
    deadline = time.time() + timeout_s
    last_error = "no candidate tab probed"
    while time.time() < deadline:
        post_tabs = browser.tabs()
        try:
            candidate = rebind_chatgpt_tab(
                pre_tabs=pre_tabs,
                post_tabs=post_tabs,
                opened_id=opened_id,
                conv_id=conv_id,
                prefer_root=prefer_root,
            )
        except DriverError as exc:
            last_error = str(exc)
            time.sleep(1.0)
            continue
        try:
            browser.eval_json(candidate, probe_tab_fn(), timeout=20)
            return candidate
        except DriverError as exc:
            last_error = str(exc)
            time.sleep(1.0)
    raise DriverError(f"unable to bind a live chatgpt.com tab id: {last_error}")


def snapshot_with_rebind(
    browser: OpenClawBrowser,
    *,
    tab_id: str,
    pre_tabs: list[dict[str, str]],
    warnings: list[str],
    conv_id: str | None = None,
    prefer_root: bool = False,
    timeout_s: float = 20.0,
) -> tuple[str, str]:
    try:
        return browser.snapshot(tab_id), tab_id
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        rebound = bind_live_chatgpt_tab(
            browser,
            pre_tabs=pre_tabs,
            conv_id=conv_id,
            prefer_root=prefer_root,
            timeout_s=timeout_s,
        )
        warnings.append("snapshot rebound after tab-not-found")
        return browser.snapshot(rebound), rebound


def eval_json_with_rebind(
    browser: OpenClawBrowser,
    *,
    tab_id: str,
    fn: str,
    pre_tabs: list[dict[str, str]],
    warnings: list[str],
    conv_id: str | None = None,
    prefer_root: bool = False,
    timeout: int = 60,
) -> tuple[Any, str]:
    try:
        return browser.eval_json(tab_id, fn, timeout=timeout), tab_id
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        rebound = bind_live_chatgpt_tab(
            browser,
            pre_tabs=pre_tabs,
            conv_id=conv_id,
            prefer_root=prefer_root,
            timeout_s=20.0,
        )
        warnings.append("run-tab rebound after tab-not-found")
        return browser.eval_json(rebound, fn, timeout=timeout), rebound


def press_with_rebind(
    browser: OpenClawBrowser,
    *,
    tab_id: str,
    key: str,
    pre_tabs: list[dict[str, str]],
    warnings: list[str],
    conv_id: str | None = None,
    prefer_root: bool = False,
) -> str:
    try:
        browser.press(tab_id, key)
        return tab_id
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        rebound = bind_live_chatgpt_tab(
            browser,
            pre_tabs=pre_tabs,
            conv_id=conv_id,
            prefer_root=prefer_root,
            timeout_s=20.0,
        )
        warnings.append("press rebound after tab-not-found")
        browser.press(rebound, key)
        return rebound


def navigate_with_rebind(
    browser: OpenClawBrowser,
    *,
    tab_id: str,
    url: str,
    pre_tabs: list[dict[str, str]],
    warnings: list[str],
    conv_id: str | None = None,
    prefer_root: bool = False,
) -> str:
    try:
        browser.navigate(tab_id, url)
        return tab_id
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        rebound = bind_live_chatgpt_tab(
            browser,
            pre_tabs=pre_tabs,
            conv_id=conv_id,
            prefer_root=prefer_root,
            timeout_s=20.0,
        )
        warnings.append("navigate rebound after tab-not-found")
        browser.navigate(rebound, url)
        return rebound


def print_phase_f(
    *,
    account: str,
    conv_id: str,
    duration_s: float,
    prompt_hash: str,
    prompt_len: int,
    share: str,
    warnings: list[str],
) -> None:
    warning_text = "; ".join(warnings) if warnings else "none"
    print("✅ Model:       ChatGPT Pro 5.4 (Advanced thinking)")
    print(f"✅ Account:     {account}")
    print(f"✅ Conv ID:     {conv_id}")
    print(f"✅ Duration:    {fmt_duration(duration_s)}")
    print(f"✅ Prompt Ref:  sha256={prompt_hash}, len={prompt_len}")
    print(f"🔗 Share:       {share}")
    print(f"⚠️  Warnings:   {warning_text}")


def run_cdp_probe_fresh(prompt: str) -> dict[str, str]:
    if not CDP_PROBE_SCRIPT.exists():
        raise DriverError(f"cdp probe script missing: {CDP_PROBE_SCRIPT}")
    env = dict(os.environ)
    env.pop("PYTHONNOUSERSITE", None)
    env.pop("PYTHONHOME", None)
    candidates = [
        os.environ.get("CHATGPT_PRO_PYTHON_BIN") or "",
        "/Library/Developer/CommandLineTools/usr/bin/python3",
        "/usr/bin/python3",
        sys.executable,
        shutil.which("python3") or "",
        "/opt/homebrew/bin/python3",
    ]
    probe_python = ""
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if not Path(candidate).exists():
            continue
        check = subprocess.run(
            [candidate, "-c", "import requests, websocket"],
            text=True,
            capture_output=True,
            timeout=20,
            env=env,
        )
        if check.returncode == 0:
            probe_python = candidate
            break
    if not probe_python:
        raise DriverError("no usable python interpreter with requests+websocket available for cdp probe")

    proc = subprocess.run(
        [probe_python, str(CDP_PROBE_SCRIPT), "fresh", "--prompt", prompt],
        text=True,
        capture_output=True,
        timeout=360,
        env=env,
    )
    if proc.returncode != 0:
        tail = "\n".join(line for line in proc.stderr.splitlines()[-10:] if line.strip())
        if not tail:
            tail = "\n".join(line for line in proc.stdout.splitlines()[-10:] if line.strip())
        raise DriverError(f"cdp probe fresh failed: {tail or proc.returncode}")
    for line in reversed(proc.stdout.splitlines()):
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("conv_id") and payload.get("share_url"):
            return {
                "conv_id": str(payload["conv_id"]),
                "share_url": str(payload["share_url"]),
            }
    raise DriverError("cdp probe fresh did not emit conv_id/share_url")


def ensure_logged_in_state(state: dict[str, Any]) -> None:
    if state.get("guest"):
        raise DriverError("Session expired or browser is not in a writable ChatGPT login state.")


def recover_public_share(
    browser: OpenClawBrowser,
    *,
    conv_id: str,
    warnings: list[str],
) -> str | None:
    debug(f"resume-share recovery start conv_id={conv_id}")
    resume_pre_tabs = browser.tabs()
    resume_tab_id = browser.open(f"https://chatgpt.com/c/{conv_id}")
    resume_tab_id = bind_live_chatgpt_tab(
        browser,
        pre_tabs=resume_pre_tabs,
        opened_id=resume_tab_id,
        conv_id=conv_id,
        prefer_root=False,
    )

    final_state = None
    deadline = time.time() + 120
    while time.time() < deadline:
        state, resume_tab_id = eval_json_with_rebind(
            browser,
            tab_id=resume_tab_id,
            fn=page_state_fn(),
            pre_tabs=resume_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        ensure_logged_in_state(state)
        if not state.get("stop") and state.get("share"):
            final_state = state
            break
        time.sleep(2.0)
    if not final_state:
        debug("resume-share recovery could not reach a shareable state")
        return None

    browser.requests(resume_tab_id, filter_text="share", clear=True)

    share_snapshot, resume_tab_id = snapshot_with_rebind(
        browser,
        tab_id=resume_tab_id,
        pre_tabs=resume_pre_tabs,
        warnings=warnings,
        conv_id=conv_id,
        prefer_root=False,
    )
    share_ref = str(
        require_snapshot_ref(
            share_snapshot,
            role="button",
            label_pattern=r"^分享$|^Share$",
            require_enabled=True,
        )["ref"]
    )
    browser.click(resume_tab_id, share_ref)
    debug(f"resume-share clicked share ref={share_ref}")

    copy_ref = None
    deadline = time.time() + 45
    while time.time() < deadline:
        share_snapshot, resume_tab_id = snapshot_with_rebind(
            browser,
            tab_id=resume_tab_id,
            pre_tabs=resume_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        copy_candidates = snapshot_ref_candidates(
            share_snapshot,
            role="button",
            label_pattern=r"^(复制链接|Copy link)$",
        )
        copy_candidates = [item for item in copy_candidates if not item["disabled"]]
        if copy_candidates:
            copy_ref = str(copy_candidates[0]["ref"])
            break
        time.sleep(1.0)
    if not copy_ref:
        debug("resume-share never exposed copy link")
        return None

    browser.click(resume_tab_id, copy_ref)
    debug(f"resume-share clicked copy ref={copy_ref}")
    time.sleep(1.0)

    share_url = None
    try:
        clipboard, resume_tab_id = eval_json_with_rebind(
            browser,
            tab_id=resume_tab_id,
            fn=clipboard_fn(),
            pre_tabs=resume_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        if clipboard.get("ok") and isinstance(clipboard.get("text"), str):
            clip_text = clipboard["text"].strip()
            if SHARE_URL_RE.search(clip_text):
                share_url = clip_text
                debug("resume-share url recovered from clipboard")
    except DriverError as exc:
        warnings.append("resume clipboard read failed")
        debug(f"resume clipboard read failed: {exc}")

    if not share_url:
        req_text = browser.requests(resume_tab_id, filter_text="share")
        share_url = parse_share_url_from_requests(req_text)
        if share_url:
            debug("resume-share url recovered from requests")

    if not share_url:
        share_url = parse_share_url_from_tabs(browser.tabs())
        if share_url:
            debug("resume-share url recovered from tabs")

    if not share_url:
        debug("resume-share recovery failed to find a public url")
        return None

    verify_pre_tabs = browser.tabs()
    verify_tab_id = browser.open(share_url)
    verify_tab_id = bind_live_chatgpt_tab(
        browser,
        pre_tabs=verify_pre_tabs,
        opened_id=verify_tab_id,
        prefer_root=False,
    )
    verify = wait_for(
        lambda: browser.eval_json(verify_tab_id, verify_share_fn(share_url)),
        timeout_s=15,
        interval_s=1.0,
    )
    if not verify or not verify.get("ok"):
        warnings.append("resume share verification fallback failed")
        debug("resume-share verification reported failure")
    else:
        debug(f"resume-share verified url={share_url}")
    return share_url


def fresh_run(prompt: str, requested_profile: str | None = None) -> int:
    started = time.time()
    prompt_hash, prompt_len = prompt_block(prompt)
    if should_use_cdp_probe():
        debug("fresh_run using cdp probe backend")
        result = run_cdp_probe_fresh(prompt)
        print_phase_f(
            account="USER-CONFIRMED",
            conv_id=result["conv_id"],
            duration_s=time.time() - started,
            prompt_hash=prompt_hash,
            prompt_len=prompt_len,
            share=result["share_url"],
            warnings=["backend=cdp-probe"],
        )
        return 0

    browser, status, profile_warnings = resolve_browser(requested_profile)
    warnings: list[str] = list(profile_warnings)
    debug(f"fresh_run start prompt_len={prompt_len} prompt_hash={prompt_hash}")
    debug("browser status ok")

    initial_tabs = browser.tabs()
    initial_ids = {tab["id"] for tab in initial_tabs if "chatgpt.com" in tab["url"]}
    run_pre_tabs = initial_tabs
    run_tab_id = ""
    state = None
    for attempt in range(1, 6):
        debug(f"fresh-home attempt {attempt}: opening new root tab")
        attempt_pre_tabs = browser.tabs()
        opened_id = browser.open("https://chatgpt.com/")
        candidate_tab_id = bind_live_chatgpt_tab(
            browser,
            pre_tabs=attempt_pre_tabs,
            opened_id=opened_id,
            prefer_root=True,
        )
        if candidate_tab_id in initial_ids:
            warnings.append("new-open returned a preexisting tab id")

        state = None
        deadline = time.time() + 15
        while time.time() < deadline:
            state, candidate_tab_id = eval_json_with_rebind(
                browser,
                tab_id=candidate_tab_id,
                fn=page_state_fn(),
                pre_tabs=attempt_pre_tabs,
                warnings=warnings,
                prefer_root=True,
            )
            if state:
                ensure_logged_in_state(state)
                debug(
                    "fresh-home probe "
                    f"attempt={attempt} tab={candidate_tab_id} "
                    f"href={state.get('href')} composer={state.get('composer')} "
                    f"advanced={state.get('advanced')} share={state.get('share')}"
                )
            if state and is_browser_error_state(state):
                warnings.append(f"fresh-home browser error on open attempt {attempt}")
                debug(f"fresh-home attempt {attempt}: browser error page")
                break
            if state and state.get("composer"):
                run_pre_tabs = attempt_pre_tabs
                run_tab_id = candidate_tab_id
                debug(f"fresh-home attempt {attempt}: acquired writable tab {run_tab_id}")
                break
            time.sleep(1.0)
        if run_tab_id:
            break
    if not run_tab_id:
        debug("fresh-home: trying existing writable root tab fallback")
        fallback_tabs = browser.tabs()
        for tab in reversed(fallback_tabs):
            if not is_root_chatgpt_url(tab["url"]):
                continue
            try:
                fallback_state = browser.eval_json(tab["id"], page_state_fn(), timeout=20)
            except DriverError:
                continue
            ensure_logged_in_state(fallback_state)
            if is_browser_error_state(fallback_state):
                continue
            if not fallback_state.get("composer"):
                continue
            run_pre_tabs = fallback_tabs
            run_tab_id = tab["id"]
            state = fallback_state
            warnings.append("reused existing writable root tab after fresh-open failures")
            debug(f"fresh-home fallback: using existing root tab {run_tab_id}")
            break
    if not run_tab_id:
        raise DriverError("unable to acquire a writable fresh ChatGPT home tab")
    if not state:
        raise DriverError("timed out waiting for fresh ChatGPT home")
    if is_browser_error_state(state):
        raise DriverError("fresh ChatGPT home stayed on a browser error page")
    if not state.get("composer"):
        raise DriverError("composer not visible on fresh ChatGPT home")
    if not state.get("advanced"):
        warnings.append("advanced-thinking indicator missing on fresh home")
    debug(f"pre-submit tab ready tab={run_tab_id}")

    writer_snapshot, run_tab_id = snapshot_with_rebind(
        browser,
        tab_id=run_tab_id,
        pre_tabs=run_pre_tabs,
        warnings=warnings,
        prefer_root=True,
    )
    composer_ref = require_snapshot_ref(
        writer_snapshot,
        role="textbox",
        label_pattern=r"^(与 ChatGPT 聊天|Chat with ChatGPT)$",
    )["ref"]
    try:
        browser.fill(run_tab_id, [{"ref": str(composer_ref), "value": prompt}])
        debug(f"filled composer ref={composer_ref} tab={run_tab_id}")
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        writer_snapshot, run_tab_id = snapshot_with_rebind(
            browser,
            tab_id=run_tab_id,
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            prefer_root=True,
        )
        composer_ref = require_snapshot_ref(
            writer_snapshot,
            role="textbox",
            label_pattern=r"^(与 ChatGPT 聊天|Chat with ChatGPT)$",
        )["ref"]
        warnings.append("fill rebound after tab-not-found")
        browser.fill(run_tab_id, [{"ref": str(composer_ref), "value": prompt}])
        debug(f"filled composer after rebound ref={composer_ref} tab={run_tab_id}")

    send_ref = None
    deadline = time.time() + 20
    while time.time() < deadline:
        writer_snapshot, run_tab_id = snapshot_with_rebind(
            browser,
            tab_id=run_tab_id,
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            prefer_root=True,
        )
        send_candidates = snapshot_ref_candidates(
            writer_snapshot,
            role="button",
            label_pattern=r"^(发送提示|Send prompt|Send message|发送)$",
        )
        send_candidates = [item for item in send_candidates if not item["disabled"]]
        if send_candidates:
            send_ref = str(send_candidates[0]["ref"])
            break
        time.sleep(0.5)
    if not send_ref:
        debug("primary tab never exposed enabled send button; trying alternate root tabs")
        alternate_tabs = browser.tabs()
        for tab in reversed(alternate_tabs):
            if tab["id"] == run_tab_id or not is_root_chatgpt_url(tab["url"]):
                continue
            try:
                alt_snapshot = browser.snapshot(tab["id"])
                alt_composer_ref = str(
                    require_snapshot_ref(
                        alt_snapshot,
                        role="textbox",
                        label_pattern=r"^(与 ChatGPT 聊天|Chat with ChatGPT)$",
                    )["ref"]
                )
                browser.fill(tab["id"], [{"ref": alt_composer_ref, "value": prompt}])
                debug(f"alternate root tab fill attempted tab={tab['id']} ref={alt_composer_ref}")
            except DriverError:
                continue

            alt_send_ref = None
            alt_deadline = time.time() + 10
            current_tab_id = tab["id"]
            while time.time() < alt_deadline:
                try:
                    alt_snapshot, current_tab_id = snapshot_with_rebind(
                        browser,
                        tab_id=current_tab_id,
                        pre_tabs=alternate_tabs,
                        warnings=warnings,
                        prefer_root=True,
                    )
                except DriverError:
                    break
                alt_candidates = snapshot_ref_candidates(
                    alt_snapshot,
                    role="button",
                    label_pattern=r"^(发送提示|Send prompt|Send message|发送)$",
                )
                alt_candidates = [item for item in alt_candidates if not item["disabled"]]
                if alt_candidates:
                    alt_send_ref = str(alt_candidates[0]["ref"])
                    break
                time.sleep(0.5)
            if alt_send_ref:
                run_pre_tabs = alternate_tabs
                run_tab_id = current_tab_id
                send_ref = alt_send_ref
                warnings.append("reused alternate writable root tab after disabled send on primary tab")
                debug(f"alternate root tab acquired tab={run_tab_id} send_ref={send_ref}")
                break

    if not send_ref:
        raise DriverError("composer did not expose an enabled send button after fill")
    debug(f"submit button ready ref={send_ref} tab={run_tab_id}")

    try:
        browser.click(run_tab_id, send_ref)
        debug("clicked submit")
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        writer_snapshot, run_tab_id = snapshot_with_rebind(
            browser,
            tab_id=run_tab_id,
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            prefer_root=True,
        )
        send_ref = str(
            require_snapshot_ref(
                writer_snapshot,
                role="button",
                label_pattern=r"^(发送提示|Send prompt|Send message|发送)$",
                require_enabled=True,
            )["ref"]
        )
        warnings.append("submit rebound after tab-not-found")
        browser.click(run_tab_id, send_ref)
        debug("clicked submit after rebound")

    conv_state = None
    conv_id = None
    deadline = time.time() + 180
    submit_activity_logged = False
    while time.time() < deadline:
        state, run_tab_id = eval_json_with_rebind(
            browser,
            tab_id=run_tab_id,
            fn=page_state_fn(),
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            prefer_root=True,
        )
        conv_id = conv_id or parse_conv_id(str(state.get("href", "")))
        if not conv_id:
            conv_id = parse_conv_id_from_requests(browser.requests(run_tab_id, filter_text="conversation"))
            if conv_id:
                debug(f"conversation id recovered from requests conv_id={conv_id}")
        if conv_id:
            conv_state = state
            break
        if state.get("stop") and not submit_activity_logged:
            debug("submit accepted; waiting for conversation id")
            submit_activity_logged = True
        time.sleep(2.0 if state.get("stop") else 1.0)
    if not conv_state or not conv_id:
        raise DriverError("submit did not create a conversation URL")
    debug(f"conversation created conv_id={conv_id} tab={run_tab_id}")

    browser.requests(run_tab_id, filter_text="share", clear=True)

    final_state = None
    deadline = time.time() + 180
    while time.time() < deadline:
        state, run_tab_id = eval_json_with_rebind(
            browser,
            tab_id=run_tab_id,
            fn=page_state_fn(),
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        if not state.get("stop") and state.get("share"):
            final_state = state
            break
        time.sleep(2.0)
    if not final_state:
        raise DriverError("conversation did not reach a shareable completed state")
    debug("conversation reached shareable completed state")

    share_snapshot, run_tab_id = snapshot_with_rebind(
        browser,
        tab_id=run_tab_id,
        pre_tabs=run_pre_tabs,
        warnings=warnings,
        conv_id=conv_id,
        prefer_root=False,
    )
    share_ref = str(
        require_snapshot_ref(
            share_snapshot,
            role="button",
            label_pattern=r"^分享$|^Share$",
            require_enabled=True,
        )["ref"]
    )
    try:
        browser.click(run_tab_id, share_ref)
        debug(f"clicked share ref={share_ref}")
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        share_snapshot, run_tab_id = snapshot_with_rebind(
            browser,
            tab_id=run_tab_id,
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        share_ref = str(
            require_snapshot_ref(
                share_snapshot,
                role="button",
                label_pattern=r"^分享$|^Share$",
                require_enabled=True,
            )["ref"]
        )
        warnings.append("share-click rebound after tab-not-found")
        browser.click(run_tab_id, share_ref)
        debug(f"clicked share after rebound ref={share_ref}")

    copy_ref = None
    deadline = time.time() + 45
    while time.time() < deadline:
        share_snapshot, run_tab_id = snapshot_with_rebind(
            browser,
            tab_id=run_tab_id,
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        copy_candidates = snapshot_ref_candidates(
            share_snapshot,
            role="button",
            label_pattern=r"^(复制链接|Copy link)$",
        )
        copy_candidates = [item for item in copy_candidates if not item["disabled"]]
        if copy_candidates:
            copy_ref = str(copy_candidates[0]["ref"])
            break
        time.sleep(1.0)
    if not copy_ref:
        raise DriverError("share dialog never exposed an enabled copy-link button")
    debug(f"copy link ready ref={copy_ref}")

    try:
        browser.click(run_tab_id, copy_ref)
        debug("clicked copy link")
    except DriverError as exc:
        if not is_tab_not_found(exc):
            raise
        share_snapshot, run_tab_id = snapshot_with_rebind(
            browser,
            tab_id=run_tab_id,
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        copy_ref = str(
            require_snapshot_ref(
                share_snapshot,
                role="button",
                label_pattern=r"^(复制链接|Copy link)$",
                require_enabled=True,
            )["ref"]
        )
        warnings.append("copy-link rebound after tab-not-found")
        browser.click(run_tab_id, copy_ref)
        debug("clicked copy link after rebound")
    time.sleep(1.0)

    share_url = None
    try:
        clipboard, run_tab_id = eval_json_with_rebind(
            browser,
            tab_id=run_tab_id,
            fn=clipboard_fn(),
            pre_tabs=run_pre_tabs,
            warnings=warnings,
            conv_id=conv_id,
            prefer_root=False,
        )
        if clipboard.get("ok") and isinstance(clipboard.get("text"), str):
            clip_text = clipboard["text"].strip()
            if SHARE_URL_RE.search(clip_text):
                share_url = clip_text
                debug("share url recovered from clipboard")
    except DriverError as exc:
        warnings.append("clipboard read failed")
        debug(f"clipboard read failed: {exc}")

    if not share_url:
        req_text = browser.requests(run_tab_id, filter_text="share")
        share_url = parse_share_url_from_requests(req_text)
        if share_url:
            debug("share url recovered from requests")

    if not share_url:
        share_url = parse_share_url_from_tabs(browser.tabs())
        if share_url:
            debug("share url recovered from tabs")

    if not share_url:
        debug("primary share extraction failed; retrying via resume-share recovery")
        share_url = recover_public_share(browser, conv_id=conv_id, warnings=warnings)

    if not share_url:
        warnings.append("public-share extraction failed")
        share_value = "PRIVATE-ONLY"
        debug("share extraction failed; falling back to PRIVATE-ONLY")
    else:
        verify_pre_tabs = browser.tabs()
        verify_tab_id = browser.open(share_url)
        verify_tab_id = bind_live_chatgpt_tab(
            browser,
            pre_tabs=verify_pre_tabs,
            opened_id=verify_tab_id,
            prefer_root=False,
        )
        verify = wait_for(
            lambda: browser.eval_json(verify_tab_id, verify_share_fn(share_url)),
            timeout_s=15,
            interval_s=1.0,
        )
        if not verify or not verify.get("ok"):
            warnings.append("share-url verification fallback failed")
            debug("share verification reported fallback failure")
        share_value = share_url
        debug(f"share verified url={share_url}")

    print_phase_f(
        account="USER-CONFIRMED",
        conv_id=conv_id,
        duration_s=time.time() - started,
        prompt_hash=prompt_hash,
        prompt_len=prompt_len,
        share=share_value,
        warnings=warnings,
    )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exec-only OpenClaw driver for the chatgpt-pro skill.")
    parser.add_argument("mode", choices=["fresh", "resume"])
    parser.add_argument("--conv-id")
    parser.add_argument("--browser-profile")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.mode == "fresh":
        prompt = sys.stdin.read()
        if not prompt.strip():
            raise DriverError("fresh mode requires a prompt on stdin")
        return fresh_run(prompt, requested_profile=args.browser_profile)
    if args.mode == "resume":
        if not args.conv_id:
            raise DriverError("resume mode requires --conv-id")
        browser, status, warnings = resolve_browser(args.browser_profile)
        share_url = recover_public_share(browser, conv_id=args.conv_id, warnings=warnings)
        if not share_url:
            raise DriverError(f"resume mode could not recover a public share for {args.conv_id}")
        print(share_url)
        return 0
    raise DriverError(f"unsupported mode: {args.mode}")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except DriverError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import os
import re
import subprocess
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import requests
    import websocket
except ImportError as exc:  # pragma: no cover - environment bootstrap
    print(f"missing dependency: {exc}", file=sys.stderr)
    raise SystemExit(2)

with contextlib.suppress(Exception):
    import urllib3

    warnings.filterwarnings("ignore", category=urllib3.exceptions.NotOpenSSLWarning)


CDP_PORT = 9223
CLONE_DIR = Path.home() / ".openclaw/browser/chatgpt-pro-gui-clone"
PROFILE_DIR = "Profile 2"
CONV_URL_RE = re.compile(r"https://chatgpt\.com/c/([A-Za-z0-9-]+)")
SHARE_URL_RE = re.compile(r"https://chatgpt\.com/share/[A-Za-z0-9-]+")
SHARE_API_RE = re.compile(r"https://chatgpt\.com/backend-api/share/([A-Za-z0-9-]+)")


def run(
    cmd: list[str],
    *,
    check: bool = True,
    timeout: int = 60,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, input=input_text, capture_output=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"command failed: {' '.join(cmd)}")
    return proc


def asuser_prefix() -> list[str]:
    password = os.environ.get("CHATGPT_PRO_SUDO_PASSWORD", "").strip()
    if not password:
        return []
    console_uid = run(["stat", "-f", "%u", "/dev/console"], timeout=10).stdout.strip()
    run(["sudo", "-S", "-v"], timeout=20, input_text=password + "\n")
    return ["sudo", "-n", "launchctl", "asuser", console_uid]


def ensure_clone_running() -> None:
    prefix = asuser_prefix()
    clone_marker = f"--user-data-dir={CLONE_DIR}"
    run(
        [*prefix, "pkill", "-f", clone_marker],
        check=False,
        timeout=20,
    )
    time.sleep(1)
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        path = CLONE_DIR / name
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except FileNotFoundError:
            pass
    cmd = [
        "open",
        "-na",
        "Google Chrome",
        "--args",
        f"--user-data-dir={CLONE_DIR}",
        f"--profile-directory={PROFILE_DIR}",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-debugging-address=127.0.0.1",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    run([*prefix, *cmd], check=False, timeout=20)
    for _ in range(30):
        time.sleep(1)
        probe = run(["curl", "-sS", f"http://127.0.0.1:{CDP_PORT}/json/version"], check=False, timeout=5)
        if probe.returncode == 0 and probe.stdout.strip().startswith("{"):
            return
    raise RuntimeError("cdp clone did not start listening on 9223")


@dataclass
class Session:
    browser: "CdpBrowser"
    target_id: str
    session_id: str


class CdpBrowser:
    def __init__(self) -> None:
        self.version = requests.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=5).json()
        self.ws = websocket.create_connection(self.version["webSocketDebuggerUrl"], timeout=60)
        self._seq = itertools.count(1)
        self._events: list[dict[str, Any]] = []

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def send(self, method: str, params: dict[str, Any] | None = None, *, session_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"id": next(self._seq), "method": method}
        if params:
            payload["params"] = params
        if session_id:
            payload["sessionId"] = session_id
        self.ws.send(json.dumps(payload))
        want = payload["id"]
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == want:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"]))
                return msg.get("result", {})
            self._events.append(msg)

    def recv_until(self, method: str, *, session_id: str | None = None, timeout: float = 20.0) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        for idx, msg in enumerate(list(self._events)):
            if msg.get("method") == method and (session_id is None or msg.get("sessionId") == session_id):
                return self._events.pop(idx)
        while time.time() < deadline:
            msg = json.loads(self.ws.recv())
            if msg.get("method") == method and (session_id is None or msg.get("sessionId") == session_id):
                return msg
            self._events.append(msg)
        return None

    def drain_events(
        self,
        *,
        session_id: str | None = None,
        timeout: float = 3.0,
        methods: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        wanted = methods or set()
        drained: list[dict[str, Any]] = []
        keep: list[dict[str, Any]] = []
        for msg in self._events:
            if session_id is not None and msg.get("sessionId") != session_id:
                keep.append(msg)
                continue
            if wanted and msg.get("method") not in wanted:
                keep.append(msg)
                continue
            drained.append(msg)
        self._events = keep
        original_timeout = self.ws.gettimeout()
        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                remaining = max(0.1, min(1.0, deadline - time.time()))
                self.ws.settimeout(remaining)
                try:
                    msg = json.loads(self.ws.recv())
                except websocket.WebSocketTimeoutException:
                    break
                if session_id is not None and msg.get("sessionId") != session_id:
                    self._events.append(msg)
                    continue
                if wanted and msg.get("method") not in wanted:
                    self._events.append(msg)
                    continue
                drained.append(msg)
        finally:
            self.ws.settimeout(original_timeout)
        return drained

    def new_page(self, url: str = "about:blank") -> Session:
        target = self.send("Target.createTarget", {"url": url})
        return self.attach_page(target["targetId"])

    def attach_page(self, target_id: str) -> Session:
        attached = self.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session = Session(self, target_id, attached["sessionId"])
        self.send("Page.enable", session_id=session.session_id)
        self.send("Runtime.enable", session_id=session.session_id)
        self.send("Network.enable", session_id=session.session_id)
        return session

    def list_pages(self) -> list[dict[str, Any]]:
        pages = requests.get(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=5).json()
        return [page for page in pages if page.get("type") == "page"]


def eval_json(session: Session, expr: str) -> Any:
    result = session.browser.send(
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True},
        session_id=session.session_id,
    )
    payload = result.get("result", {})
    if "value" in payload:
        value = payload["value"]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    return json.loads(value)
                except Exception:
                    pass
        return value
    if payload.get("description"):
        raise RuntimeError(payload["description"])
    raise RuntimeError(f"unexpected evaluate result: {result}")


def eval_json_await(session: Session, expr: str) -> Any:
    result = session.browser.send(
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True, "awaitPromise": True},
        session_id=session.session_id,
    )
    payload = result.get("result", {})
    if "value" in payload:
        value = payload["value"]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    return json.loads(value)
                except Exception:
                    pass
        return value
    if payload.get("description"):
        raise RuntimeError(payload["description"])
    raise RuntimeError(f"unexpected evaluate result: {result}")


def navigate(session: Session, url: str, *, wait_timeout: float = 30.0) -> None:
    session.browser.send("Page.navigate", {"url": url}, session_id=session.session_id)
    session.browser.recv_until("Page.loadEventFired", session_id=session.session_id, timeout=wait_timeout)


def wait_for_value(session: Session, expr: str, *, timeout: float = 30.0, interval: float = 0.5) -> Any:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = eval_json(session, expr)
        if last:
            return last
        time.sleep(interval)
    return last


def type_text_slowly(session: Session, selector_expr: str, value: str, *, delay: float = 0.06) -> dict[str, Any]:
    focus = eval_json(
        session,
        f"""(() => {{
  const input = {selector_expr};
  if (!input) return {{ok:false, reason:'input-missing'}};
  const setter =
    input.tagName === 'TEXTAREA'
      ? Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set
      : Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
  input.focus();
  if (setter) setter.call(input, '');
  else input.value = '';
  input.dispatchEvent(new Event('input', {{bubbles:true}}));
  return {{ok:true}};
}})()""",
    )
    if not focus or not focus.get("ok"):
        return focus or {"ok": False, "reason": "focus-failed"}
    typed = ""
    for ch in value:
        typed += ch
        eval_json(
            session,
            f"""(() => {{
  const input = {selector_expr};
  if (!input) return {{ok:false, reason:'input-missing'}};
  const setter =
    input.tagName === 'TEXTAREA'
      ? Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set
      : Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
  input.focus();
  if (setter) setter.call(input, {json.dumps(typed, ensure_ascii=False)});
  else input.value = {json.dumps(typed, ensure_ascii=False)};
  input.dispatchEvent(new InputEvent('input', {{bubbles:true, inputType:'insertText', data:{json.dumps(ch, ensure_ascii=False)}}}));
  input.dispatchEvent(new Event('change', {{bubbles:true}}));
  return {{ok:true, len: input.value.length}};
}})()""",
        )
        time.sleep(delay)
    return eval_json(
        session,
        f"""(() => {{
  const input = {selector_expr};
  if (!input) return {{ok:false, reason:'input-missing'}};
  input.dispatchEvent(new Event('blur', {{bubbles:true}}));
  return {{ok:true, value: input.value, len: input.value.length}};
}})()""",
    )


def parse_state_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"body": payload, "href": "", "title": ""}
    return payload if isinstance(payload, dict) else {}


def has_button(state: dict[str, Any], pattern: str) -> bool:
    regex = re.compile(pattern, re.I)
    for item in state.get("buttons", []):
        if not isinstance(item, dict):
            continue
        blob = f"{item.get('text', '')} {item.get('aria', '')}"
        if regex.search(blob):
            return True
    return False


def is_logged_in_chatgpt_state(state: dict[str, Any]) -> bool:
    inputs = state.get("inputs", [])
    has_composer = any(
        item.get("visible")
        and (
            (item.get("name") == "prompt-textarea")
            or ("与 ChatGPT 聊天" in (item.get("aria") or ""))
            or (
                item.get("role") == "textbox"
                and item.get("contenteditable") == "true"
            )
        )
        for item in inputs
        if isinstance(item, dict)
    )
    href = state.get("href", "")
    return "chatgpt.com/" in href and "auth/error" not in href and has_composer


def has_share_dialog(state: dict[str, Any]) -> bool:
    body = state.get("body", "")
    return bool(re.search(r"复制链接|Copy link|LinkedIn|Reddit", body, re.I))


def has_share_affordance(state: dict[str, Any]) -> bool:
    if has_button(state, r"分享|复制链接|Share|Copy link"):
        return True
    body = state.get("body", "")
    return bool(re.search(r"分享|复制链接|Share|Copy link", body, re.I))


def share_url_from_pages(browser: CdpBrowser) -> str:
    for page in reversed(browser.list_pages()):
        url = page.get("url", "")
        match = SHARE_URL_RE.search(url)
        if match:
            return match.group(0)
    return ""


def share_url_from_events(events: list[dict[str, Any]]) -> str:
    for msg in reversed(events):
        params = msg.get("params") or {}
        request = params.get("request") or {}
        response = params.get("response") or {}
        for url in (request.get("url"), response.get("url")):
            if not isinstance(url, str):
                continue
            direct = SHARE_URL_RE.search(url)
            if direct:
                return direct.group(0)
            api = SHARE_API_RE.search(url)
            if api and api.group(1).lower() != "create":
                return f"https://chatgpt.com/share/{api.group(1)}"
    return ""


def wait_for_visible_input(session: Session, selector_expr: str, *, timeout: float = 30.0) -> bool:
    return bool(
        wait_for_value(
            session,
            f"""(() => {{
  const nodes = [...document.querySelectorAll({json.dumps(selector_expr)})];
  return nodes.some((el) => {{
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }});
}})()""",
            timeout=timeout,
            interval=0.5,
        )
    )


def press_key(session: Session, key: str) -> None:
    params = {"key": key, "code": key}
    session.browser.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", **params}, session_id=session.session_id)
    session.browser.send("Input.dispatchKeyEvent", {"type": "keyUp", **params}, session_id=session.session_id)


def press_enter(session: Session) -> None:
    params = {
        "key": "Enter",
        "code": "Enter",
        "windowsVirtualKeyCode": 13,
        "nativeVirtualKeyCode": 13,
        "text": "\r",
        "unmodifiedText": "\r",
    }
    session.browser.send("Input.dispatchKeyEvent", {"type": "keyDown", **params}, session_id=session.session_id)
    session.browser.send("Input.dispatchKeyEvent", {"type": "char", **params}, session_id=session.session_id)
    session.browser.send("Input.dispatchKeyEvent", {"type": "keyUp", **params}, session_id=session.session_id)


def complete_google_login(session: Session, email: str, password: str) -> None:
    print({"flow": "google-sso"}, flush=True)
    if wait_for_visible_input(session, "input[type=email], input[name=identifier]", timeout=15):
        print(type_text_slowly(session, "document.querySelector('input[type=email], input[name=identifier]')", email), flush=True)
        print(eval_json(session, js_click_button(r"^(下一步|Next)$", exact=True)), flush=True)
    password_ready = False
    for _ in range(4):
        if wait_for_visible_input(session, "input[type=password], input[name=Passwd]", timeout=8):
            password_ready = True
            break
        state = parse_state_payload(eval_json(session, state_expr()))
        print(state, flush=True)
        body = state.get("body", "")
        if "试试其他方式" in body or "Try another way" in body or "通行密钥" in body or "passkey" in body.lower():
            print(eval_json(session, js_click_button(r"^(试试其他方式|Try another way)$", exact=True)), flush=True)
            time.sleep(3)
            print(
                eval_json(
                    session,
                    js_click_button(r"输入.*密码|使用.*密码|Password|password", exact=False),
                ),
                flush=True,
            )
            time.sleep(2)
            if not wait_for_visible_input(session, "input[type=password], input[name=Passwd]", timeout=3):
                for key in ["Tab", "Tab", "Enter"]:
                    press_key(session, key)
                    time.sleep(0.8)
            time.sleep(3)
            continue
    if not password_ready:
        raise RuntimeError("google password input did not appear")
    print(type_text_slowly(session, "document.querySelector('input[type=password], input[name=Passwd]')", password), flush=True)
    print(eval_json(session, js_click_button(r"^(下一步|Next)$", exact=True)), flush=True)
    left_google = wait_for_value(
        session,
        r"""(() => !/accounts\.google\.com/.test(location.href))()""",
        timeout=90,
        interval=1.0,
    )
    if not left_google:
        raise RuntimeError("google sign-in did not return to OpenAI/ChatGPT")


def state_expr() -> str:
    return r"""(() => JSON.stringify({
  ready: document.readyState,
  href: location.href,
  title: document.title,
  body: (document.body?.innerText || '').slice(0, 2500),
  inputs: [...document.querySelectorAll('input,textarea,[role=textbox],[contenteditable=true]')].map(el => ({
    type: el.type || '',
    name: el.name || '',
    placeholder: el.placeholder || '',
    aria: el.getAttribute('aria-label') || '',
    role: el.getAttribute('role') || '',
    contenteditable: el.getAttribute('contenteditable') || '',
    visible: (() => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
    })()
  })),
  buttons: [...document.querySelectorAll('button,a,[role=button]')].map(el => ({
    text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(),
    aria: el.getAttribute('aria-label') || ''
  })).filter(x => x.text || x.aria).slice(0, 60)
}))()"""


def visible_composer_expr() -> str:
    return r"""(() => {
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };
  const candidates = [
    ...document.querySelectorAll('[role="textbox"][contenteditable="true"], [contenteditable="true"][aria-label*="ChatGPT"], textarea[aria-label*="ChatGPT"], textarea[name="prompt-textarea"], textarea')
  ].filter(visible);
  const target = candidates.find((el) => el.getAttribute('contenteditable') === 'true')
    || candidates.find((el) => el.tagName === 'TEXTAREA')
    || null;
  if (!target) return null;
  return {
    tag: target.tagName,
    role: target.getAttribute('role') || '',
    aria: target.getAttribute('aria-label') || '',
    contenteditable: target.getAttribute('contenteditable') || '',
    value: ('value' in target ? target.value : (target.innerText || target.textContent || '')).slice(0, 200)
  };
})()"""


def js_set_input(selector_expr: str, value: str) -> str:
    return f"""(() => {{
  const value = {json.dumps(value, ensure_ascii=False)};
  const input = {selector_expr};
  if (!input) return JSON.stringify({{ok:false}});
  input.focus();
  if (input.getAttribute('contenteditable') === 'true') {{
    input.innerHTML = '';
    input.textContent = value;
    input.dispatchEvent(new InputEvent('beforeinput', {{bubbles:true, inputType:'insertText', data:value}}));
    input.dispatchEvent(new InputEvent('input', {{bubbles:true, inputType:'insertText', data:value}}));
    input.dispatchEvent(new Event('change', {{bubbles:true}}));
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(input);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
    return JSON.stringify({{ok:true, kind:'contenteditable', valueLen: (input.innerText || input.textContent || '').length}});
  }}
  const setter =
    input.tagName === 'TEXTAREA'
      ? Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set
      : Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
  if (setter) {{
    setter.call(input, value);
  }} else {{
    input.value = value;
  }}
  input.dispatchEvent(new InputEvent('beforeinput', {{bubbles:true, inputType:'insertText', data:value}}));
  input.dispatchEvent(new InputEvent('input', {{bubbles:true, inputType:'insertText', data:value}}));
  input.dispatchEvent(new Event('change', {{bubbles:true}}));
  return JSON.stringify({{ok:true, kind:'input', valueLen: (input.value || input.innerText || '').length}});
}})()"""


def js_click_button(pattern: str, *, exact: bool = False, selector_expr: str | None = None) -> str:
    selector_js = json.dumps(selector_expr) if selector_expr else "null"
    return f"""(() => {{
  const regex = new RegExp({json.dumps(pattern)}, 'i');
  const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const scopedNodes = {selector_js}
    ? [...document.querySelectorAll({selector_js})]
    : [];
  const allNodes = [...document.querySelectorAll('button,a,[role=button],input[type=submit]')];
  const nodes = scopedNodes.length ? scopedNodes : allNodes;
  const parts = (el) => {{
    const text = normalize(el.innerText || el.textContent || '');
    const aria = normalize(el.getAttribute('aria-label') || '');
    const value = normalize(el.value || '');
    const label = normalize([text, aria, value].filter(Boolean).join(' '));
    return {{text, aria, value, label}};
  }};
  let target = null;
  if ({str(exact).lower()}) {{
    target = nodes.find(el => {{
      const {{text, aria, value}} = parts(el);
      return [text, aria, value].some(part => part && regex.test(part) && !/继续使用|Continue with/i.test(part));
    }});
  }}
  if (!target) {{
    target = nodes.find(el => {{
      const {{label}} = parts(el);
      return label && regex.test(label);
    }});
  }}
  if (!target && nodes !== allNodes) {{
    target = allNodes.find(el => {{
      const {{text, aria, value, label}} = parts(el);
      if (!label || !regex.test(label)) return false;
      return !{str(exact).lower()} || [text, aria, value].some(part => part && regex.test(part) && !/继续使用|Continue with/i.test(part));
    }});
  }}
  if (!target) {{
    const genericVisible = [...document.querySelectorAll('*')].filter((el) => {{
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      if (rect.width <= 0 || rect.height <= 0) return false;
      if (style.display === 'none' || style.visibility === 'hidden') return false;
      const {{text}} = parts(el);
      return !!text && text.length <= 500;
    }});
    genericVisible.sort((a, b) => parts(a).text.length - parts(b).text.length);
    target = genericVisible.find((el) => {{
      const {{text}} = parts(el);
      return text && regex.test(text) && (!{str(exact).lower()} || !/继续使用|Continue with/i.test(text));
    }});
  }}
  if (!target) return JSON.stringify({{ok:false}});
  const clickable = [target, ...(() => {{
    const chain = [];
    let cur = target.parentElement;
    while (cur && chain.length < 5) {{
      chain.push(cur);
      cur = cur.parentElement;
    }}
    return chain;
  }})()].find((el) => {{
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    if (rect.width <= 0 || rect.height <= 0) return false;
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const role = el.getAttribute('role') || '';
    const tag = el.tagName;
    return ['BUTTON', 'A', 'DIV', 'LI', 'SPAN'].includes(tag) || role === 'button' || el.hasAttribute('tabindex');
  }}) || target;
  clickable.scrollIntoView({{block: 'center', inline: 'center'}});
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {{
    clickable.dispatchEvent(new MouseEvent(type, {{bubbles: true, cancelable: true, view: window}}));
  }}
  if (typeof clickable.click === 'function') clickable.click();
  return JSON.stringify({{ok:true, text: parts(clickable).label}});
}})()"""


def submit_prompt_fn() -> str:
    return """(() => {
  const text = (el) => ((el?.innerText || el?.textContent || '').replace(/\\s+/g, ' ').trim());
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const composer = [...document.querySelectorAll('[role="textbox"][contenteditable="true"], [contenteditable="true"][aria-label*="ChatGPT"], textarea[aria-label*="ChatGPT"], textarea[name="prompt-textarea"], textarea')].find(visible);
  if (!composer) return {ok:false, reason:'composer-missing'};
  composer.focus();
  const form = composer.closest('form') || composer.parentElement?.closest('form') || composer.parentElement;
  const buttons = [...form.querySelectorAll('button')];
  const score = (el) => {
    const label = `${el.getAttribute('aria-label') || ''} ${text(el)}`;
    let value = 0;
    if (visible(el)) value += 100;
    if (/发送|send|submit/i.test(label)) value += 100;
    if ((el.className || '').includes('composer-submit-button-color')) value += 40;
    if ((el.type || '').toLowerCase() === 'submit') value += 20;
    if (/启动语音功能|开始听写|voice|dictation/i.test(label)) value -= 500;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') value -= 1000;
    return value;
  };
  buttons.sort((a, b) => score(b) - score(a));
  const chosen = buttons[0];
  if (!chosen || score(chosen) < 100) return {ok:false, reason:'composer-submit-missing', composerTag: composer.tagName, composerRole: composer.getAttribute('role') || ''};
  chosen.click();
  return {
    ok:true,
    aria: chosen.getAttribute('aria-label') || '',
    text: text(chosen).slice(0, 80),
    className: (chosen.className || '').slice(0, 160)
  };
})()"""


def login(email: str, password: str) -> None:
    ensure_clone_running()
    browser = CdpBrowser()
    try:
        session = browser.new_page()
        navigate(session, "https://chatgpt.com/auth/login")
        time.sleep(2)
        initial_state = parse_state_payload(eval_json(session, state_expr()))
        initial_inputs = initial_state.get("inputs", [])
        if any(
            (item.get("name") == "prompt-textarea") or ("与 ChatGPT 聊天" in (item.get("aria") or ""))
            for item in initial_inputs
            if isinstance(item, dict)
        ):
            print(initial_state, flush=True)
            print(
                json.dumps(
                    {
                        "href": initial_state.get("href", ""),
                        "title": initial_state.get("title", ""),
                        "body": initial_state.get("body", ""),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return
        if not eval_json(session, r"""(() => !!document.querySelector('input[type=email], input[name=email]'))()"""):
            print(eval_json(session, js_click_button(r"^(登录|Log in)$", exact=True)), flush=True)
        ready = False
        login_entry_deadline = time.time() + 30
        while time.time() < login_entry_deadline:
            current_state = parse_state_payload(eval_json(session, state_expr()))
            current_inputs = current_state.get("inputs", [])
            if any(
                (item.get("name") == "prompt-textarea") or ("与 ChatGPT 聊天" in (item.get("aria") or ""))
                for item in current_inputs
                if isinstance(item, dict)
            ):
                print(current_state, flush=True)
                print(
                    json.dumps(
                        {
                            "href": current_state.get("href", ""),
                            "title": current_state.get("title", ""),
                            "body": current_state.get("body", ""),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                return
            if eval_json(session, r"""(() => !!document.querySelector('input[type=email], input[name=email]'))()"""):
                ready = True
                print(current_state, flush=True)
                break
            time.sleep(1)
        if not ready:
            print(parse_state_payload(eval_json(session, state_expr())), flush=True)
            raise RuntimeError("email input did not appear on login page")

        print(type_text_slowly(session, "document.querySelector('input[type=email], input[name=email]')", email), flush=True)
        print(
            eval_json(
                session,
                js_click_button(
                    r"^(继续|Continue)$",
                    exact=True,
                    selector_expr="form button, form [role=button], form input[type=submit], button[type=submit], input[type=submit]",
                ),
            ),
            flush=True,
        )

        ready = False
        logged_in_payload: str | None = None
        password_deadline = time.time() + 60
        retry_count = 0
        while time.time() < password_deadline:
            current_state = parse_state_payload(eval_json(session, state_expr()))
            inputs = current_state.get("inputs", [])
            has_chatgpt_composer = any(
                (item.get("name") == "prompt-textarea") or ("与 ChatGPT 聊天" in (item.get("aria") or ""))
                for item in inputs
                if isinstance(item, dict)
            )
            if (
                "chatgpt.com/" in current_state.get("href", "")
                and "auth/error" not in current_state.get("href", "")
                and has_chatgpt_composer
            ):
                logged_in_payload = json.dumps(
                    {
                        "href": current_state.get("href", ""),
                        "title": current_state.get("title", ""),
                        "body": current_state.get("body", ""),
                    },
                    ensure_ascii=False,
                )
                ready = True
                break
            if "accounts.google.com" in current_state.get("href", ""):
                complete_google_login(session, email, password)
                ready = True
                break
            ready = eval_json(session, r"""(() => !!document.querySelector('input[type=password], input[name=password]'))()""")
            if ready:
                break
            state = current_state
            body = state.get("body", "")
            href = state.get("href", "")
            if (
                ("Operation timed out" in body or "糟糕，出错了" in body or "Try again" in body or "重试" in body)
                and retry_count < 3
            ):
                retry_count += 1
                print({"retry": retry_count, "href": href, "reason": "error-page"}, flush=True)
                print(eval_json(session, js_click_button(r"^(重试|Try again|Retry)$", exact=True)), flush=True)
                time.sleep(4)
                if eval_json(session, r"""(() => !!document.querySelector('input[type=email], input[name=email]'))()"""):
                    print(type_text_slowly(session, "document.querySelector('input[type=email], input[name=email]')", email), flush=True)
                    print(
                        eval_json(
                            session,
                            js_click_button(
                                r"^(继续|Continue)$",
                                exact=True,
                                selector_expr="form button, form [role=button], form input[type=submit], button[type=submit], input[type=submit]",
                            ),
                        ),
                        flush=True,
                    )
                time.sleep(3)
                continue
            if "email-verification" in href or "email_otp" in href or "验证码" in body:
                print(eval_json(session, js_click_button(r"输入密码|Enter password|使用密码|password instead", exact=False)), flush=True)
                time.sleep(3)
                continue
            time.sleep(1.0)
        if not ready:
            print(parse_state_payload(eval_json(session, state_expr())), flush=True)
            raise RuntimeError("password input did not appear after email step")
        post_password_state = parse_state_payload(eval_json(session, state_expr()))
        print(post_password_state, flush=True)

        if "accounts.google.com" not in post_password_state.get("href", "") and "auth.openai.com" in post_password_state.get("href", ""):
            print(type_text_slowly(session, "document.querySelector('input[type=password], input[name=password]')", password), flush=True)
            print(
                eval_json(
                    session,
                    js_click_button(
                        r"^(继续|Continue|登录|Log in|Sign in)$",
                        exact=True,
                        selector_expr="form button, form [role=button], form input[type=submit], button[type=submit], input[type=submit]",
                    ),
                ),
                flush=True,
            )

        logged_in = logged_in_payload or wait_for_value(
            session,
            r"""(() => {
  const body = document.body?.innerText || '';
  if (/登录|免费注册|Log in|Sign up/.test(body)) return '';
  if (/auth\.openai\.com/.test(location.href)) return '';
  if (/auth\/error/.test(location.href)) return '';
  return JSON.stringify({href: location.href, title: document.title, body: body.slice(0, 1200)});
})()""",
            timeout=60,
            interval=1.0,
        )
        if not logged_in:
            print(parse_state_payload(eval_json(session, state_expr())), flush=True)
            raise RuntimeError("login did not reach an authenticated chatgpt.com page")
        print(logged_in, flush=True)
    finally:
        browser.close()


def dump(url: str) -> None:
    ensure_clone_running()
    browser = CdpBrowser()
    try:
        session = browser.new_page()
        navigate(session, url)
        time.sleep(2)
        print(eval_json(session, state_expr()))
    finally:
        browser.close()


def fresh(prompt: str) -> None:
    ensure_clone_running()
    browser = CdpBrowser()
    try:
        prompt = prompt.rstrip("\r\n")
        pre_pages = browser.list_pages()
        pre_ids = {page.get("id") for page in pre_pages}
        session = browser.new_page()
        navigate(session, "https://chatgpt.com/")
        deadline = time.time() + 45
        state: dict[str, Any] = {}
        while time.time() < deadline:
            state = parse_state_payload(eval_json(session, state_expr()))
            if is_logged_in_chatgpt_state(state):
                break
            time.sleep(1)
        if not is_logged_in_chatgpt_state(state):
            raise RuntimeError("chatgpt.com is not in a logged-in writable state")

        print(state, flush=True)
        composer = eval_json(session, visible_composer_expr())
        print({"composer": composer}, flush=True)
        if not composer:
            raise RuntimeError("visible composer did not appear on chatgpt.com root page")
        set_result = eval_json(
            session,
            js_set_input(
                """(() => [...document.querySelectorAll('[role="textbox"][contenteditable="true"], [contenteditable="true"][aria-label*="ChatGPT"], textarea[aria-label*="ChatGPT"], textarea[name="prompt-textarea"], textarea')].find((el) => {
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
}))()""",
                prompt,
            ),
        )
        print(set_result, flush=True)
        time.sleep(1)
        press_enter(session)
        time.sleep(1)
        send_result = eval_json(session, submit_prompt_fn())
        print(send_result, flush=True)
        if not isinstance(send_result, dict) or not send_result.get("ok"):
            state = parse_state_payload(eval_json(session, state_expr()))
            if is_root_chatgpt_url(state.get("href", "")):
                press_enter(session)
                time.sleep(2)
                followup_state = parse_state_payload(eval_json(session, state_expr()))
                print({"followup_state": followup_state}, flush=True)
            else:
                raise RuntimeError(f"submit control not ready: {send_result}")

        conv_id = ""
        rebound = False
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                state = parse_state_payload(eval_json(session, state_expr()))
                href = state.get("href", "")
                match = CONV_URL_RE.search(href)
                if match:
                    conv_id = match.group(1)
                    if has_button(state, r"停止流式传输|Stop streaming"):
                        pass
                    elif has_share_affordance(state):
                        break
            except Exception:
                state = {}
            if not conv_id or not rebound:
                post_pages = browser.list_pages()
                candidate = next(
                    (
                        page
                        for page in reversed(post_pages)
                        if page.get("id") not in pre_ids and CONV_URL_RE.search(page.get("url", ""))
                    ),
                    None,
                )
                if candidate:
                    conv_id = CONV_URL_RE.search(candidate["url"]).group(1)
                    session = browser.attach_page(candidate["id"])
                    rebound = True
            time.sleep(2)
        if not conv_id:
            raise RuntimeError("conversation url did not appear after submit")

        def attach_conv_session() -> Session:
            post_pages = browser.list_pages()
            candidate = next(
                (
                    page
                    for page in reversed(post_pages)
                    if conv_id in page.get("url", "")
                ),
                None,
            )
            if not candidate:
                raise RuntimeError(f"unable to find live conversation tab for {conv_id}")
            return browser.attach_page(candidate["id"])

        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                session = attach_conv_session()
                state = parse_state_payload(eval_json(session, state_expr()))
            except Exception:
                state = {}
            if has_share_affordance(state) and not has_button(state, r"停止流式传输|Stop streaming"):
                break
            time.sleep(2)
        print(state, flush=True)
        if not has_share_affordance(state):
            raise RuntimeError("share button did not appear after completion")

        dialog_state = state
        session = attach_conv_session()
        share_methods = {"Network.requestWillBeSent", "Network.responseReceived"}
        browser.drain_events(
            timeout=0.2,
            methods=share_methods,
        )
        share_events: list[dict[str, Any]] = []
        for _ in range(4):
            dialog_state = parse_state_payload(eval_json(session, state_expr()))
            if has_share_dialog(dialog_state):
                break
            print(eval_json(session, js_click_button(r"^(分享|Share)$", exact=True)), flush=True)
            time.sleep(1.5)
            share_events.extend(browser.drain_events(timeout=1.0, methods=share_methods))
            session = attach_conv_session()
        print(dialog_state, flush=True)
        if not has_share_dialog(dialog_state):
            raise RuntimeError("share dialog did not expose a copy-link action")

        share_url = ""
        clip: Any = {}
        for _ in range(3):
            session = attach_conv_session()
            browser.drain_events(timeout=0.2, methods=share_methods)
            copy_result = eval_json(session, js_click_button(r"复制链接|Copy link", exact=False))
            print(copy_result, flush=True)
            if not isinstance(copy_result, dict) or not copy_result.get("ok"):
                raise RuntimeError(f"copy-link control not ready: {copy_result}")
            time.sleep(2)
            share_events.extend(browser.drain_events(
                timeout=8.0,
                methods=share_methods,
            ))
            share_url = share_url_from_events(share_events) or share_url_from_pages(browser)
            if share_url:
                break
            session = attach_conv_session()
            dialog_state = parse_state_payload(eval_json(session, state_expr()))
            if not has_share_dialog(dialog_state):
                print(eval_json(session, js_click_button(r"^(分享|Share)$", exact=True)), flush=True)
                time.sleep(1.5)
        if not share_url:
            session = attach_conv_session()
            clip = eval_json_await(
                session,
                r"""navigator.clipboard.readText().then((text) => ({text}))""",
            )
        share_url = ""
        recovered = share_url_from_events(share_events) or share_url_from_pages(browser)
        if recovered:
            share_url = recovered
        elif isinstance(clip, dict):
            share_url = str(clip.get("text") or "")
        if not SHARE_URL_RE.search(share_url):
            raise RuntimeError(f"share flow did not produce a public share url: {share_url!r}")
        print(json.dumps({"conv_id": conv_id, "share_url": share_url}, ensure_ascii=False), flush=True)
    finally:
        browser.close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    dump_p = sub.add_parser("dump")
    dump_p.add_argument("url")

    login_p = sub.add_parser("login")
    login_p.add_argument("--email", default=os.environ.get("CHATGPT_PRO_LOGIN_EMAIL"))
    login_p.add_argument("--password", default=os.environ.get("CHATGPT_PRO_LOGIN_PASSWORD"))
    login_p.add_argument("--stdin-credentials", action="store_true")

    fresh_p = sub.add_parser("fresh")
    fresh_p.add_argument("--prompt", default=None)

    args = parser.parse_args(argv)
    if args.cmd == "dump":
        dump(args.url)
        return 0
    if args.cmd == "login":
        email = args.email
        password = args.password
        if args.stdin_credentials:
            lines: list[str] = []
            for _ in range(3):
                line = sys.stdin.readline()
                if not line:
                    break
                lines.append(line.rstrip("\n"))
            if not os.environ.get("CHATGPT_PRO_SUDO_PASSWORD") and lines:
                os.environ["CHATGPT_PRO_SUDO_PASSWORD"] = lines[0]
            if not email and len(lines) > 1:
                email = lines[1]
            if not password and len(lines) > 2:
                password = lines[2]
        if not email or not password:
            raise RuntimeError("login requires credentials via flags, env, or --stdin-credentials")
        login(email, password)
        return 0
    if args.cmd == "fresh":
        prompt = args.prompt or sys.stdin.read()
        if not prompt.strip():
            raise RuntimeError("fresh requires a prompt")
        fresh(prompt)
        return 0
    raise RuntimeError(f"unsupported command: {args.cmd}")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

from __future__ import annotations

import base64
import json
import random
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class WebBridgeError(RuntimeError):
    pass


def webbridge_binary_path() -> Path:
    binary = Path.home() / ".kimi-webbridge" / "bin" / "kimi-webbridge"
    if binary.exists():
        return binary
    windows_binary = binary.with_suffix(".exe")
    if windows_binary.exists():
        return windows_binary
    return windows_binary if Path.home().drive else binary


def webbridge_status() -> dict[str, Any]:
    binary = webbridge_binary_path()
    if not binary.exists():
        raise WebBridgeError(
            f"Kimi WebBridge is not installed at {binary}. "
            "Install it from https://www.kimi.com/features/webbridge and try again."
        )
    completed = subprocess.run(
        [str(binary), "status"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        raise WebBridgeError((completed.stderr or completed.stdout or "Kimi WebBridge status failed").strip())
    try:
        status = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise WebBridgeError(f"Kimi WebBridge returned invalid status: {completed.stdout!r}") from exc
    if not isinstance(status, dict):
        raise WebBridgeError(f"Kimi WebBridge returned invalid status: {status!r}")
    return status


def start_webbridge_daemon() -> None:
    binary = webbridge_binary_path()
    completed = subprocess.run(
        [str(binary), "start"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise WebBridgeError((completed.stderr or completed.stdout or "Kimi WebBridge start failed").strip())


def ensure_webbridge_ready(*, timeout_seconds: float = 20.0, start_daemon: bool = True) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    status = webbridge_status()
    if start_daemon and not status.get("running"):
        start_webbridge_daemon()

    while True:
        status = webbridge_status()
        if status.get("running") and status.get("extension_connected"):
            return status
        if time.monotonic() >= deadline:
            if not status.get("running"):
                raise WebBridgeError("Kimi WebBridge daemon is not running and could not be started.")
            raise WebBridgeError(
                "Kimi WebBridge daemon is running, but the browser extension is not connected. "
                "Open the browser with the Kimi WebBridge extension installed, then retry. "
                "Install/help: https://www.kimi.com/features/webbridge"
            )
        time.sleep(1)


@dataclass
class WebBridgeClient:
    base_url: str = "http://127.0.0.1:10086"
    session: str = "deal-webbridge"
    timeout: float = 30.0
    _has_open_tab: bool = field(default=False, init=False, repr=False)

    def command(self, action: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "action": action,
            "args": args or {},
            "session": self.session,
        }
        request = Request(
            f"{self.base_url.rstrip('/')}/command",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise WebBridgeError(f"WebBridge daemon is not reachable at {self.base_url}") from exc
        if not result.get("ok"):
            error = result.get("error") or {}
            message = error.get("message") or result
            raise WebBridgeError(f"{action} failed: {message}")
        return result.get("data") or {}

    def navigate(self, url: str, *, new_tab: bool = True, group_title: str | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"url": url, "newTab": new_tab}
        if group_title:
            args["group_title"] = group_title
        data = self.command("navigate", args)
        self._has_open_tab = True
        return data

    def navigate_reuse_tab(self, url: str, *, group_title: str | None = None) -> dict[str, Any]:
        return self.navigate(url, new_tab=not self._has_open_tab, group_title=group_title)

    def find_tab(self, url: str, *, active: bool = True) -> dict[str, Any]:
        return self.command("find_tab", {"url": url, "active": active})

    def snapshot(self) -> dict[str, Any]:
        return self.command("snapshot")

    def evaluate(self, code: str) -> Any:
        data = self.command("evaluate", {"code": code})
        return data.get("value")

    def evaluate_json(self, code: str) -> Any:
        value = self.evaluate(code)
        if value in (None, ""):
            return None
        if not isinstance(value, str):
            return value
        return json.loads(value)

    def click(self, selector: str) -> dict[str, Any]:
        return self.command("click", {"selector": selector})

    def mouse_click(self, selector: str) -> dict[str, Any]:
        return self.command("mouse_click", {"selector": selector})

    def fill(self, selector: str, value: str) -> dict[str, Any]:
        return self.command("fill", {"selector": selector, "value": value})

    def send_keys(self, keys: str, *, repeat: int = 1) -> dict[str, Any]:
        return self.command("send_keys", {"keys": keys, "repeat": repeat})

    def key_type(self, text: str) -> dict[str, Any]:
        return self.command("key_type", {"text": text})

    def scroll_by(self, pixels: int) -> None:
        self.evaluate(f"window.scrollBy({{ top: {int(pixels)}, left: 0, behavior: 'smooth' }}); true")

    def type_like_human(
        self,
        selector: str,
        text: str,
        *,
        char_delay_ms: tuple[int, int] = (120, 420),
        word_delay_ms: tuple[int, int] = (250, 900),
        clear_first: bool = True,
    ) -> None:
        if clear_first:
            self.fill(selector, "")
        self.click(selector)
        for char in text:
            self.key_type(char)
            delay = random.randint(*char_delay_ms)
            if char.isspace() or char.isdigit():
                delay += random.randint(*word_delay_ms)
            time.sleep(delay / 1000)

    def screenshot(self, path: Path, *, selector: str | None = None, image_format: str = "png") -> Path:
        args: dict[str, Any] = {"format": image_format}
        if selector:
            args["selector"] = selector
        data = self.command("screenshot", args)
        encoded = data.get("data")
        if not encoded:
            raise WebBridgeError("screenshot returned no image data")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(encoded))
        return path

    def close_session(self) -> dict[str, Any]:
        data = self.command("close_session")
        self._has_open_tab = False
        return data

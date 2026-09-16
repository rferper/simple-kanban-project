"""The stack these tests run against.

`docker-compose.yaml`, brought up under its own compose project so that a
development stack and a test run cannot be mistaken for one another. The
teardown deletes a volume, so the project name is checked here and again on the
line that does the deleting.

This is a near-twin of the helper in `backend/tests/test_compose.py`, and
deliberately not shared with it: the two live in different pytest roots, and a
cross-root import to save forty lines would cost more than it saved. What must
not be shared is the project name — see `PROJECT` there and here.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]

#: Never "nextlane" (the development stack) and never "nextlane-it" (the
#: integration suite's), so the three can run at once without meeting.
PROJECT = "nextlane-e2e"

APP_PORT = 18100
DB_PORT = 15532

FORBIDDEN = {"nextlane", "nextlane-it"}
assert PROJECT not in FORBIDDEN, "the e2e stack must be its own compose project"


class Stack:
    """`docker compose`, for one isolated project."""

    base_url = f"http://127.0.0.1:{APP_PORT}"

    def compose(self, *arguments: str, check: bool = True, timeout: int = 600):
        environment = {**os.environ, "APP_PORT": str(APP_PORT), "DB_PORT": str(DB_PORT)}
        return subprocess.run(
            ["docker", "compose", "-p", PROJECT, *arguments],
            cwd=REPO,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )

    def up(self, *, build: bool = False) -> None:
        self.compose("up", "-d", "--wait", *(["--build"] if build else []))
        self.wait_for_the_app()

    def down(self, *, volumes: bool = False) -> None:
        assert PROJECT not in FORBIDDEN, "refusing to remove a stack that is not this one"
        self.compose("down", *(["-v"] if volumes else []), check=False)

    def restart_the_app(self) -> None:
        """What a deploy looks like from the outside."""
        self.compose("restart", "app")
        self.wait_for_the_app()

    def wait_for_the_app(self, seconds: int = 60) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                with urlopen(self.base_url + "/", timeout=2) as response:
                    if response.status == 200:
                        return
            except (URLError, OSError):
                pass
            time.sleep(1)
        raise AssertionError(f"the app never answered on {self.base_url}\n{self.logs()}")

    def logs(self) -> str:
        return self.compose("logs", "--tail", "40", check=False).stdout

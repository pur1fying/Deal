from pathlib import Path

from core.autoamtion.platforms.jd.collector import JdAutomation
from deal.models import RunPaths


class ChromiumStub:
    def __init__(self):
        self.user_data_dir = None

    async def launch_persistent_context(self, user_data_dir, **kwargs):
        self.user_data_dir = user_data_dir
        return object()


class PlaywrightStub:
    def __init__(self):
        self.chromium = ChromiumStub()


def test_platform_profile_dir_is_config_profiles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    playwright = PlaywrightStub()
    paths = RunPaths.create(Path("output"), now=__import__("datetime").datetime(2026, 5, 15, 10, 0, 0))

    automation = JdAutomation(playwright, paths, max_items=1, wait_seconds=0)

    import asyncio

    asyncio.run(automation.launch_context())

    assert Path(playwright.chromium.user_data_dir) == Path("config") / "profiles" / "jd"

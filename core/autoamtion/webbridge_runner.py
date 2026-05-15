from __future__ import annotations

from typing import Any

from core.autoamtion.webbridge_common import InteractionConfig
from core.autoamtion.webbridge_platforms import WEBBRIDGE_AUTOMATIONS
from core.webbridge import WebBridgeClient, ensure_webbridge_ready
from deal.io import write_json
from deal.models import PLATFORMS, ProductConfig, RunPaths


def collect_all_with_webbridge(
    products: list[ProductConfig],
    paths: RunPaths,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    ensure_webbridge_ready()
    webbridge_config = config.get("webbridge_search", {})
    interaction = InteractionConfig.from_config(webbridge_config)
    session_name = str(webbridge_config.get("session_name", "deal-webbridge"))
    all_items: list[dict[str, Any]] = []
    for platform in config.get("output_layout", {}).get("platforms", PLATFORMS):
        automation_cls = WEBBRIDGE_AUTOMATIONS[str(platform)]
        client = WebBridgeClient(session=f"{session_name}-{platform}")
        automation = automation_cls(
            client=client,
            paths=paths,
            config=webbridge_config,
            interaction=interaction,
        )
        items = automation.collect(products)
        write_json(paths.platform_result_json(str(platform)), items)
        all_items.extend(items)
    return all_items

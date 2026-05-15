from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from core.autoamtion.official_specs.dedupe import dedupe_result_file, draw_deduped_table
from core.autoamtion.official_specs.runner import collect_official_specs, print_camera_specs_table
from core.autoamtion.webbridge_runner import collect_all_with_webbridge
from core.logger import logger
from core.webbridge import ensure_webbridge_ready
from deal.collector import collect_all
from deal.config import ConfigSet, check_config, load_products
from deal.io import write_json
from deal.models import RunPaths, next_incremental_run_id
from deal.plotting import plot_history
from deal.summary import build_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.json")
    args = parser.parse_args()
    config_path = Path(args.config)
    config = check_config(config_path.parent, config_path.name)
    run_configured_task(config)


def run_configured_task(config: ConfigSet) -> Path | None:
    task = config.get("task", "run")
    if task == "collect":
        return run_collect(config)
    if task == "webbridge_collect":
        return run_webbridge_collect(config)
    if task in {"cam_spec", "official_specs"}:
        return run_cam_spec(config)
    if task == "summary":
        run_dir = configured_or_latest_run(config, "summary.run_dir")
        build_summary(run_dir, Path(config.get("output_dir", "output")))
        print(run_dir / "summary")
        return run_dir
    if task == "plot":
        output_root = Path(config.get("output_dir", "output"))
        run_dir_value = config.get("plot.run_dir")
        charts_dir = Path(run_dir_value) / "charts" if run_dir_value else output_root / "charts"
        written = plot_history(output_root, charts_dir)
        print(f"wrote {len(written)} chart(s) to {charts_dir}")
        return charts_dir
    if task == "run":
        return run_all(config)
    raise ValueError(f"Unsupported config task: {task}")


def run_collect(config: ConfigSet) -> Path:
    paths = create_run_paths(config)
    logger.set_log_file(paths.logs / "run.log")
    logger.attr("collect task started")
    products = load_products(Path(config.get("products_file", "config/products.json")))
    normalized = asyncio.run(collect_all(
        products,
        paths,
        int(config.get("collector.max_items", 20)),
        int(config.get("collector.wait_seconds", 6)),
    ))
    write_json(paths.logs / "run.json", {"task": "collect", "run_dir": str(paths.root), "items": len(normalized)})
    print(paths.root)
    return paths.root


def run_webbridge_collect(config: ConfigSet) -> Path:
    paths = create_run_paths(config)
    logger.set_log_file(paths.logs / "run.log")
    logger.attr("webbridge collect task started")
    products = load_products(Path(config.get("products_file", "config/products.json")))
    items = collect_all_with_webbridge(products, paths, config.config)
    write_json(paths.logs / "run.json", {
        "task": "webbridge_collect",
        "run_dir": str(paths.root),
        "items": len(items),
    })
    print(paths.root)
    return paths.root


def run_cam_spec(config: ConfigSet) -> Path:
    run_dir = create_task_run_dir(config, str(config.get("cam_spec.task_name", "cam_spec")))
    logs_dir = run_dir / str(config.get("output_layout.log_dir", "log"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.set_log_file(logs_dir / "run.log")
    logger.attr("checking webbridge")
    status = ensure_webbridge_ready()
    logger.info(f"webbridge ready (daemon={status.get('version')}, extension={status.get('extension_version')})")
    merge = bool(config.get("cam_spec.merge", True))
    dedupe = bool(config.get("cam_spec.dedupe", True))
    draw_table = bool(config.get("cam_spec.draw_table", True))
    result_filename = str(config.get("cam_spec.result_file", "result.json"))
    result = collect_official_specs(
        run_dir,
        brands=list(config.get("cam_spec.brands", ["fujifilm", "canon", "sony", "hasselblad", "nikon"])),
        max_workers=int(config.get("cam_spec.max_workers", 5)),
        max_pages_per_brand=config.get("cam_spec.max_pages_per_brand"),
        merge=merge,
        result_filename=result_filename,
    )
    deduped_result = None
    deduped_path = None
    table_path = None
    table_items = result.get("items", [])
    if dedupe:
        if merge and result.get("result_path"):
            deduped_path = run_dir / str(config.get("cam_spec.dedupe_result_file", "result_deduped.json"))
            deduped_result = dedupe_result_file(Path(result["result_path"]), deduped_path)
            table_items = deduped_result.get("items", [])
            logger.info(f"cam spec deduped result written: {deduped_path}")
        else:
            logger.warning("cam spec dedupe skipped because merge is disabled")
    if draw_table:
        table_path = run_dir / str(config.get("cam_spec.table_image_file", "charts/cam_spec_full_table_deduped.png"))
        draw_deduped_table(
            table_items,
            table_path,
            source_label=f"Source: {deduped_path or result.get('result_path') or run_dir}",
            title="Camera Official Specs - Record Table",
        )
        logger.info(f"cam spec table image written: {table_path}")
    write_json(logs_dir / "cam_spec_run.json", {
        "task": "cam_spec",
        "task_name": str(config.get("cam_spec.task_name", "cam_spec")),
        "run_dir": str(run_dir),
        "output_dir": result["output_dir"],
        "result_path": result["result_path"],
        "merge": merge,
        "dedupe": dedupe,
        "draw_table": draw_table,
        "deduped_result_path": str(deduped_path) if deduped_path else None,
        "table_image_path": str(table_path) if table_path else None,
        "items": result["total"],
        "deduped_items": deduped_result.get("total") if deduped_result else None,
        "errors": result["errors"],
    })
    print_camera_specs_table(table_items)
    logger.info(f"cam spec output directory: {run_dir}")
    return run_dir


run_official_specs = run_cam_spec


def run_all(config: ConfigSet) -> Path:
    paths = create_run_paths(config)
    logger.set_log_file(paths.logs / "run.log")
    logger.attr("run task started")
    products = load_products(Path(config.get("products_file", "config/products.json")))
    normalized = asyncio.run(collect_all(
        products,
        paths,
        int(config.get("collector.max_items", 20)),
        int(config.get("collector.wait_seconds", 6)),
    ))
    build_summary(paths.root, Path(config.get("output_dir", "output")))
    charts = plot_history(Path(config.get("output_dir", "output")), paths.charts)
    write_json(paths.logs / "run.json", {
        "task": "run",
        "run_dir": str(paths.root),
        "items": len(normalized),
        "charts": [str(path) for path in charts],
    })
    print(paths.root)
    return paths.root


def create_run_paths(config: ConfigSet) -> RunPaths:
    platforms = tuple(str(item) for item in config.get("output_layout.platforms", ["tb", "jd", "pdd", "goofish"]))
    return RunPaths.create(
        Path(config.get("output_dir", "output")),
        datetime.now(),
        config.get("run_id"),
        platforms=platforms,
        date_format=str(config.get("output_layout.date_format", "%Y-%m-%d")),
        run_id_format=str(config.get("output_layout.run_id_format", "%H%M%S")),
    )


def create_task_run_dir(config: ConfigSet, task_name: str) -> Path:
    now = datetime.now()
    date_format = str(config.get("output_layout.date_format", "%Y-%m-%d"))
    parent = Path(config.get("output_dir", "output")) / now.strftime(date_format) / task_name
    run_id = str(config.get("run_id") or next_incremental_run_id(parent))
    run_dir = parent / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def configured_or_latest_run(config: ConfigSet, key: str) -> Path:
    run_dir = config.get(key)
    if run_dir:
        return Path(run_dir)
    latest = latest_run(Path(config.get("output_dir", "output")))
    if latest is None:
        raise FileNotFoundError(f"No run found under {config.get('output_dir', 'output')}")
    return latest


def latest_run(output_root: Path) -> Path | None:
    candidates = []
    for normalized in output_root.glob("*/*/normalized/products.json") if output_root.exists() else []:
        run_dir = normalized.parents[1]
        candidates.append(run_dir)
    return max(candidates, key=lambda path: (path.parent.name, path.name), default=None)


if __name__ == "__main__":
    main()

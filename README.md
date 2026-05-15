# Deal

Camera price monitor for Taobao, JD, Pinduoduo, and Xianyu.

The collector uses Playwright with visible Chrome windows. It does not bypass login,
captcha, region prompts, or platform risk controls. When a page needs manual action,
handle it in Chrome and press Enter in the terminal.

## Setup

```powershell
uv sync --extra test
uv run playwright install chrome
```

If Chrome is already installed locally, Playwright can usually use it through
`channel="chrome"` without downloading a bundled browser.

## Config

Runtime settings live in `config/config.json`:

```json
{
  "task": "run",
  "output_dir": "output",
  "products_file": "config/products.json",
  "run_id": null,
  "collector": {
    "max_items": 20,
    "wait_seconds": 6
  },
  "summary": {
    "run_dir": null
  },
  "plot": {
    "run_dir": null
  }
}
```

Supported `task` values are `collect`, `summary`, `plot`, and `run`.
When the app starts, missing config files are created and `config/config.json`
is recursively updated from defaults. Deprecated keys not present in the default
schema are removed during that update.

Edit `config/products.json`:

```json
{
  "products": [
    {
      "brand": "Sony",
      "model": "A7M4",
      "keywords": ["Sony A7M4", "索尼 A7M4"],
      "exclude_words": ["贴膜", "保护套"],
      "platform_keywords": {
        "jd": ["索尼 A7M4 相机"]
      }
    }
  ]
}
```

## Run

```powershell
python main.py
```

Each run writes files under `output/{YYYY-MM-DD}/{HHMMSS}/`:

```text
raw/{platform}.json
normalized/products.json
summary/platform_min_prices.json
summary/daily_changes.json
charts/*.png
logs/run.json
screenshots/
html/
```

Browser profiles are stored separately from run output so login state can be
reused:

```text
config/profiles/{platform}/
```

Platform-specific browser automation lives under:

```text
core/autoamtion/platforms/jd/
core/autoamtion/platforms/tb/
core/autoamtion/platforms/pdd/
core/autoamtion/platforms/goofish/
```

Price summaries prefer `effective_price` and fall back to `list_price`.
Daily changes compare the current run with the latest available run from an earlier date.

## Tests

```powershell
python -m pytest
```

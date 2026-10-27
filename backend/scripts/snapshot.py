"""Fetch the January-2026 decision window from Elexon and save it to DATA_DIR.

    python -m scripts.snapshot          (run from backend/)

Committing backend/data/*.json makes deployments start instantly and keeps the
demo working even if the Elexon API is slow or down.
"""
import logging

from app import store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    window = store.Window.from_settings()
    print(f"Delivery days {window.first_delivery_day} .. {window.last_delivery_day}; "
          f"WINDFOR published {window.publish_from} .. {window.publish_to}")
    actuals, forecasts = store.fetch_live(window)
    store.save_snapshot(actuals, forecasts)
    print(f"Saved {len(actuals)} actuals and {len(forecasts)} forecast points to {store.settings.data_dir}")

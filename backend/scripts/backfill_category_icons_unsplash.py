"""One-off backfill: set categories.icon_url to a matching Unsplash photo.

Searches Unsplash's /search/photos endpoint using each category's name as the
query and takes the top result. Requires UNSPLASH_ACCESS_KEY in backend/.env
(from unsplash.com/developers -> New Application -> Access Key).

Unsplash's API guidelines require pinging the photo's `download_location`
whenever it's put into real use, so this script does that for every photo it
picks.

Free-tier Unsplash apps are capped at 50 requests/hour; this uses 2 requests
per category (search + download ping), so ~50 categories fits in two
batches -- the script sleeps between batches automatically if needed.

Usage: python scripts/backfill_category_icons_unsplash.py [--dry-run]
"""
import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, ".")
from app.core.database import engine

load_dotenv()

API_BASE = "https://api.unsplash.com"

# A few category names in the seed data don't read as a useful photo search
# on their own; override with a better query term.
QUERY_OVERRIDES = {
    "Mare Mare": "mother and baby",
}


def search_photo(session: requests.Session, query: str) -> dict | None:
    resp = session.get(
        f"{API_BASE}/search/photos",
        params={"query": query, "per_page": 1, "orientation": "squarish"},
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    return results[0] if results else None


def ping_download(session: requests.Session, download_location: str) -> None:
    resp = session.get(download_location)
    resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not access_key:
        print("UNSPLASH_ACCESS_KEY not set in backend/.env, aborting.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"Authorization": f"Client-ID {access_key}"})

    with engine.connect() as conn:
        categories = conn.execute(text("SELECT id, name FROM categories ORDER BY name")).fetchall()

    results = []
    for i, (cat_id, name) in enumerate(categories, 1):
        query = QUERY_OVERRIDES.get(name, name)
        try:
            photo = search_photo(session, query)
        except requests.HTTPError as e:
            print(f"  FAILED search for {name!r}: {e}")
            photo = None

        if photo is None:
            print(f"  no result for {name!r}")
            results.append((cat_id, name, None, None))
        else:
            url = photo["urls"]["small"]
            download_location = photo["links"]["download_location"]
            results.append((cat_id, name, url, download_location))
            print(f"  {name}: {url}")

        # Free tier: 50 req/hour. One search request per category here;
        # download pings happen in a second pass below (real run only).
        if i % 50 == 0 and i < len(categories):
            print("  ...rate limit pause (50 req/hour), sleeping 60 min...")
            time.sleep(3600)

    if args.dry_run:
        missing = [name for _, name, url, _ in results if url is None]
        if missing:
            print(f"\nNo photo found for: {', '.join(missing)}")
        return

    with engine.begin() as conn:
        for cat_id, name, url, download_location in results:
            if url is None:
                continue
            conn.execute(
                text("UPDATE categories SET icon_url = :url WHERE id = :id"),
                {"url": url, "id": cat_id},
            )

    updated = sum(1 for _, _, url, _ in results if url is not None)
    print(f"updated {updated}/{len(results)} categories")

    # Attribution ping, required by Unsplash API guidelines when a photo is
    # actually put into use (best-effort, failures don't affect the DB write).
    for _, name, url, download_location in results:
        if download_location is None:
            continue
        try:
            ping_download(session, download_location)
        except requests.HTTPError as e:
            print(f"  download-ping failed for {name!r}: {e}")


if __name__ == "__main__":
    main()

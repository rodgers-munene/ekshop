"""One-off migration: copy product images from the legacy Namecheap host
(served publicly at LEGACY_BASE) into the AWS_S3_BUCKET configured in
app.core.config, then rewrite product_images.url/thumbnail_url to point at
S3 instead.

Safe to re-run: uploads are skipped if the S3 key already exists, and the
DB rewrite only touches rows that still start with "/" (already-migrated
rows are absolute S3 URLs and get skipped).

Usage: python scripts/migrate_images_to_s3.py [--dry-run]
"""
import argparse
import concurrent.futures
import sys

import boto3
import requests
from sqlalchemy import text

sys.path.insert(0, ".")
from app.core.config import settings
from app.core.database import engine

LEGACY_BASE = "https://ekshop.store"
WORKERS = 16


def fetch_relative_paths() -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT url, thumbnail_url FROM product_images")).fetchall()
    paths = set()
    for url, thumb in rows:
        for p in (url, thumb):
            if p and p.startswith("/"):
                paths.add(p)
    return paths


def guess_content_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def migrate_one(s3, bucket: str, path: str) -> tuple[str, str]:
    key = path.lstrip("/")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return path, "skipped (already exists)"
    except s3.exceptions.ClientError:
        pass

    resp = requests.get(f"{LEGACY_BASE}{path}", timeout=30)
    resp.raise_for_status()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=resp.content,
        ContentType=guess_content_type(path),
    )
    return path, "uploaded"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not (settings.AWS_S3_BUCKET and settings.AWS_S3_PUBLIC_URL):
        print("AWS_S3_BUCKET / AWS_S3_PUBLIC_URL not configured, aborting.")
        sys.exit(1)

    paths = fetch_relative_paths()
    print(f"{len(paths)} unique legacy image paths to migrate")

    if args.dry_run:
        for p in list(paths)[:10]:
            print("  would migrate:", p)
        return

    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    uploaded = skipped = failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(migrate_one, s3, settings.AWS_S3_BUCKET, p): p for p in paths}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            path = futures[fut]
            try:
                _, status = fut.result()
                if status.startswith("uploaded"):
                    uploaded += 1
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                print(f"  FAILED {path}: {e}")
            if i % 200 == 0:
                print(f"  ...{i}/{len(paths)}")

    print(f"uploaded={uploaded} skipped={skipped} failed={failed}")

    if failed:
        print("Some uploads failed -- not rewriting DB URLs. Re-run the script to retry.")
        sys.exit(1)

    base = settings.AWS_S3_PUBLIC_URL.rstrip("/")
    with engine.begin() as conn:
        r1 = conn.execute(
            text("UPDATE product_images SET url = :base || url WHERE url LIKE '/%'"),
            {"base": base},
        )
        r2 = conn.execute(
            text(
                "UPDATE product_images SET thumbnail_url = :base || thumbnail_url "
                "WHERE thumbnail_url LIKE '/%'"
            ),
            {"base": base},
        )
    print(f"rewrote {r1.rowcount} url rows, {r2.rowcount} thumbnail_url rows")


if __name__ == "__main__":
    main()

"""Debug helper: figure out what the NOTION_*_DB_ID values actually point to.

Prints the object type and title for each ID. If you see object='page'
instead of 'database', the ID is wrong — read the docstring at the bottom
for how to get the right one.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError


def main() -> int:
    load_dotenv(override=True)
    client = Client(auth=os.environ["NOTION_TOKEN"])

    for label, env_key in [("Articles", "NOTION_ARTICLES_DB_ID"), ("Issues", "NOTION_ISSUES_DB_ID")]:
        the_id = os.environ.get(env_key, "")
        print(f"\n=== {label} (env={env_key}={the_id!r}) ===")
        if not the_id:
            print("  (not set)")
            continue

        # Try as a database first.
        try:
            db = client.databases.retrieve(database_id=the_id)
            title_parts = db.get("title", [])
            title = "".join(p.get("plain_text", "") for p in title_parts) or "(untitled)"
            print(f"  object: database")
            print(f"  title:  {title}")
            print(f"  properties (direct): {sorted(db.get('properties', {}).keys())}")

            # Notion 2025 multi-data-source model: real fields live on the data source.
            data_sources = db.get("data_sources", [])
            print(f"  data_sources: {len(data_sources)}")
            for ds in data_sources:
                ds_id = ds.get("id")
                ds_name = ds.get("name") or "(unnamed)"
                print(f"    - {ds_name!r}  id={ds_id}")
                try:
                    ds_full = client.request(path=f"data_sources/{ds_id}", method="GET")
                    props = ds_full.get("properties", {})
                    print(f"      properties: {sorted(props.keys())}")
                except APIResponseError as e:
                    print(f"      data_sources.retrieve failed: {e.code} {e}")
            continue
        except APIResponseError as e:
            print(f"  databases.retrieve failed: {e.code}")

        # Then as a page.
        try:
            page = client.pages.retrieve(page_id=the_id)
            print(f"  object: page (NOT a database!)")
            # Best-effort: page title is in properties under whichever prop is type=title
            title = "(unknown)"
            for prop_name, prop in page.get("properties", {}).items():
                if prop.get("type") == "title":
                    title = "".join(t.get("plain_text", "") for t in prop["title"]) or "(empty)"
                    break
            print(f"  title:  {title}")
        except APIResponseError as e:
            print(f"  pages.retrieve also failed: {e.code} {e}")

    print("""
If you see object='page' above, the ID points to a wrapper page, not the
database itself. To get the real database ID:

1. In Notion, click the database title (or, if inline, hover the database
   and click the ⤢ "Open as page" icon in the top-right of the block).
2. In the opened full-page view, click ••• (top right) → "Copy link to view".
3. The URL looks like:
       https://www.notion.so/<workspace>/<32hex>?v=<32hex>&pvs=...
   The FIRST 32-hex string (before ?v=) is the database ID.

If the database is inline and you can't get the full-page view, click the
database title and hover the ••• menu next to it; "Open as page" is there too.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Validate that the Notion databases match what the code expects.

Run after Notion setup to catch typos in field names, wrong field types,
or missing select options before they cause cryptic API errors at write time.

Usage:
    python -m scripts.check_notion_schema
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from notion_client import Client
from notion_client.errors import APIResponseError

from src.notion_client import (
    CATEGORY_OPTIONS,
    SOURCE_OPTIONS,
    STATUS_OPTIONS,
    ArticleProp,
)


# (property name, expected Notion property type)
ARTICLES_EXPECTED: list[tuple[str, str]] = [
    (ArticleProp.TITLE, "title"),
    (ArticleProp.SOURCE, "select"),
    (ArticleProp.URL, "url"),
    (ArticleProp.PUBLISHED_DATE, "date"),
    (ArticleProp.COLLECTED_DATE, "date"),
    (ArticleProp.CATEGORY, "select"),
    (ArticleProp.RELEVANCE_SCORE, "number"),
    (ArticleProp.HU_SUMMARY, "rich_text"),
    (ArticleProp.RSS_SUMMARY, "rich_text"),
    (ArticleProp.STATUS, "select"),
    (ArticleProp.HIGHLIGHTED, "checkbox"),
    (ArticleProp.FULL_HU_TRANSLATION, "rich_text"),
    (ArticleProp.KIEMELT_INFO_HU, "rich_text"),
    (ArticleProp.FILTER_REASONING, "rich_text"),
    (ArticleProp.ISSUE, "relation"),
]

ISSUES_EXPECTED: list[tuple[str, str]] = [
    ("Issue name", "title"),
    ("Year", "number"),
    ("Week number", "number"),
    ("Publish date", "date"),
    ("Substack URL", "url"),
    ("Articles", "relation"),
    ("Releases this week", "rich_text"),
    ("Releases next week", "rich_text"),
    ("Status", "select"),
    ("Notes", "rich_text"),
]

ISSUES_STATUS_OPTIONS = frozenset({"Draft", "Published"})


def main() -> int:
    load_dotenv(override=True)

    token = os.environ.get("NOTION_TOKEN")
    articles_id = os.environ.get("NOTION_ARTICLES_DB_ID")
    issues_id = os.environ.get("NOTION_ISSUES_DB_ID")
    missing = [k for k, v in [
        ("NOTION_TOKEN", token),
        ("NOTION_ARTICLES_DB_ID", articles_id),
        ("NOTION_ISSUES_DB_ID", issues_id),
    ] if not v]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        print("Fill them in .env (see .env.example).")
        return 1

    client = Client(auth=token)
    problems: list[str] = []

    print("Checking Articles database...")
    problems += _check_db(
        client, articles_id, "Articles", ARTICLES_EXPECTED,
        select_options={
            ArticleProp.SOURCE: SOURCE_OPTIONS,
            ArticleProp.CATEGORY: CATEGORY_OPTIONS,
            ArticleProp.STATUS: STATUS_OPTIONS,
        },
    )

    print("Checking Issues database...")
    problems += _check_db(
        client, issues_id, "Issues", ISSUES_EXPECTED,
        select_options={"Status": ISSUES_STATUS_OPTIONS},
    )

    if problems:
        print("\nFound issues:")
        for p in problems:
            print(f"  - {p}")
        print(f"\n{len(problems)} problem(s). Fix in Notion and re-run.")
        return 1

    print("\nAll good. Schemas match.")
    return 0


def _check_db(
    client: Client,
    database_id: str,
    label: str,
    expected: list[tuple[str, str]],
    select_options: dict[str, frozenset[str]],
) -> list[str]:
    """Resolve the database's data source, then check its schema.

    The Notion 2025 API model places properties on data sources, not directly
    on databases. We expect exactly one data source per database.
    """
    problems: list[str] = []
    try:
        db = client.databases.retrieve(database_id=database_id)
    except APIResponseError as e:
        return [f"[{label}] cannot retrieve database (is integration shared with it?): {e}"]

    sources = db.get("data_sources", [])
    if not sources:
        return [f"[{label}] database has no data sources (unexpected for the 2025 API model)"]
    if len(sources) > 1:
        return [
            f"[{label}] database has {len(sources)} data sources; expected exactly one"
        ]

    try:
        ds = client.data_sources.retrieve(data_source_id=sources[0]["id"])
    except APIResponseError as e:
        return [f"[{label}] cannot retrieve data source: {e}"]

    actual = ds.get("properties", {})

    for name, expected_type in expected:
        prop = actual.get(name)
        if prop is None:
            problems.append(f"[{label}] missing property: {name!r} (expected type {expected_type})")
            continue
        actual_type = prop.get("type")
        if actual_type != expected_type:
            problems.append(
                f"[{label}] property {name!r} has type {actual_type!r}, expected {expected_type!r}"
            )
            continue
        # Select option coverage
        if expected_type == "select" and name in select_options:
            actual_opts = {o["name"] for o in prop["select"].get("options", [])}
            missing = select_options[name] - actual_opts
            if missing:
                problems.append(
                    f"[{label}] select {name!r} missing options: {sorted(missing)}"
                )

    return problems


if __name__ == "__main__":
    sys.exit(main())

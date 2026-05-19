#!/usr/bin/env python3
"""Fetch recent image-related papers from arXiv and merge them into papers.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPERS_JSON = ROOT / "papers.json"
ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# 你可以按自己的研究方向继续扩展关键词。
SEARCH_PROFILES = [
    {
        "category": "sr",
        "query": 'cat:cs.CV AND ("super resolution" OR "image super-resolution" OR "image restoration" OR "attention" OR "transformer")',
        "tags": ["Super-Resolution", "Auto-Fetched"],
    },
    {
        "category": "generation",
        "query": 'cat:cs.CV AND ("image generation" OR "image editing" OR "diffusion model" OR "text-to-image")',
        "tags": ["Generation", "Auto-Fetched"],
    },
    {
        "category": "restoration",
        "query": 'cat:cs.CV AND ("image restoration" OR "image enhancement" OR "denoising" OR "deblurring" OR "low-light")',
        "tags": ["Restoration", "Auto-Fetched"],
    },
    {
        "category": "recognition",
        "query": 'cat:cs.CV AND ("segmentation" OR "object detection" OR "image recognition" OR "open-vocabulary")',
        "tags": ["Recognition", "Auto-Fetched"],
    },
    {
        "category": "geometry",
        "query": 'cat:cs.CV AND ("3D reconstruction" OR "Gaussian Splatting" OR "NeRF" OR "depth estimation")',
        "tags": ["3D Vision", "Auto-Fetched"],
    },
]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or fallback


def arxiv_id_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def year_from_date(value: str) -> int:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).year
    except ValueError:
        return datetime.now(timezone.utc).year


def fetch_arxiv(query: str, max_results: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    url = f"{ARXIV_API}?{params}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ImagePaperHub/1.0 (daily paper updater)"},
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                xml_text = response.read()
            break
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"arXiv request failed after retries: {last_error}")

    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall("atom:entry", NS):
        title = normalize_text(entry.findtext("atom:title", default="", namespaces=NS))
        summary = normalize_text(entry.findtext("atom:summary", default="", namespaces=NS))
        published = entry.findtext("atom:published", default="", namespaces=NS)
        arxiv_url = entry.findtext("atom:id", default="", namespaces=NS)
        authors = [normalize_text(author.findtext("atom:name", default="", namespaces=NS)) for author in entry.findall("atom:author", NS)]
        primary_category = entry.find("arxiv:primary_category", NS)
        categories = [cat.attrib.get("term", "") for cat in entry.findall("atom:category", NS)]
        if primary_category is not None:
            categories.insert(0, primary_category.attrib.get("term", ""))

        arxiv_id = arxiv_id_from_url(arxiv_url)
        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": ", ".join(authors[:4]) + (" et al." if len(authors) > 4 else ""),
                "summary": summary[:260] + ("..." if len(summary) > 260 else ""),
                "year": year_from_date(published),
                "published": published,
                "arxiv": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
                "categories": [item for item in categories if item],
            }
        )
    return papers


def load_site_data() -> dict:
    return json.loads(PAPERS_JSON.read_text(encoding="utf-8"))


def existing_keys(data: dict) -> set[str]:
    keys = set()
    for paper in data.get("papers", []):
        keys.add(paper.get("id", ""))
        arxiv = paper.get("links", {}).get("arxiv", "")
        if arxiv:
            keys.add(arxiv_id_from_url(arxiv))
        keys.add(normalize_text(paper.get("title", "")).lower())
    return keys


def merge_papers(data: dict, max_results_per_profile: int, dry_run: bool) -> int:
    keys = existing_keys(data)
    added = 0

    for profile in SEARCH_PROFILES:
        try:
            fetched = fetch_arxiv(profile["query"], max_results_per_profile)
        except RuntimeError as exc:
            print(f"Warning: skip {profile['category']} because {exc}", file=sys.stderr)
            continue
        time.sleep(3)  # Respect arXiv API usage guidance.
        for item in fetched:
            title_key = item["title"].lower()
            if item["arxiv_id"] in keys or title_key in keys:
                continue

            paper_id = f"arxiv-{slugify(item['arxiv_id'], str(int(time.time())))}"
            paper = {
                "id": paper_id,
                "title": item["title"],
                "authors": item["authors"] or "Unknown authors",
                "venue": "arXiv",
                "year": item["year"],
                "category": profile["category"],
                "tags": profile["tags"],
                "summary": item["summary"] or "待补充摘要。",
                "links": {"paper": item["pdf"], "arxiv": item["arxiv"], "code": ""},
                "status": "自动收录，待人工复核",
            }
            data.setdefault("papers", []).append(paper)
            keys.update({paper_id, item["arxiv_id"], title_key})
            added += 1

    if added and not dry_run:
        data.setdefault("site", {})["updated"] = datetime.now(timezone.utc).date().isoformat()
        PAPERS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch recent arXiv image papers and update papers.json.")
    parser.add_argument("--max-results", type=int, default=5, help="每个方向最多检索多少篇最新论文。")
    parser.add_argument("--dry-run", action="store_true", help="只检查新增数量，不写入文件。")
    args = parser.parse_args()

    data = load_site_data()
    added = merge_papers(data, max(args.max_results, 1), args.dry_run)
    print(f"Added {added} new papers." + (" Dry run only." if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

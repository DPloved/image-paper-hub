#!/usr/bin/env python3
"""Fetch image-related papers from multiple scholarly search sources.

Default search window is 2025-2026. Sources:
- Semantic Scholar: broad scholarly web index with citations.
- OpenAlex: broad scholarly metadata index.
- arXiv: preprints, used as an additional source rather than the only source.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PAPERS_JSON = ROOT / "papers.json"
ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SEARCH_API = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_PAPER_API = "https://api.semanticscholar.org/graph/v1/paper/"
OPENALEX_API = "https://api.openalex.org/works"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
TODAY = datetime.now(timezone.utc).date().isoformat()

# Every website subcategory has a corresponding search profile.
SEARCH_PROFILES = [
    ("geometry", "geometry-3d-reconstruction", "3D reconstruction Gaussian Splatting NeRF dynamic scene computer vision", ["3D Vision", "Reconstruction"]),
    ("geometry", "geometry-depth", "depth estimation camera pose multi-view geometry computer vision", ["Depth", "Geometry"]),
    ("geometry", "geometry-registration", "point cloud registration multi-view registration spatial mapping", ["Registration", "3D Vision"]),
    ("generation", "generation-image", "image generation image editing diffusion text-to-image computer vision", ["Generation", "Image Editing"]),
    ("generation", "generation-video", "video generation video diffusion video editing computer vision", ["Video Generation", "Diffusion"]),
    ("generation", "generation-3d", "3D generation 3D editing diffusion gaussian generation", ["3D Generation", "Diffusion"]),
    ("generation", "generation-tokenizer", "multimodal generation visual tokenizer interleaved generation", ["Multimodal", "Tokenizer"]),
    ("medical", "medical-segmentation", "medical image segmentation foundation model", ["Medical Image", "Segmentation"]),
    ("medical", "medical-reconstruction", "medical image reconstruction inverse problem imaging", ["Medical Image", "Reconstruction"]),
    ("medical", "medical-vlm", "medical VLM medical vision language model uncertainty", ["Medical VLM", "Reliability"]),
    ("medical", "medical-registration", "medical image registration deformable registration", ["Medical Image", "Registration"]),
    ("recognition", "recognition-segmentation", "image segmentation video segmentation segment anything", ["Segmentation", "Recognition"]),
    ("recognition", "recognition-detection", "object detection open vocabulary detection long tail OOD", ["Detection", "Recognition"]),
    ("recognition", "recognition-correspondence", "semantic correspondence keypoint optical flow video tracking representation", ["Correspondence", "Tracking"]),
    ("recognition", "recognition-special", "human motion action recognition sign language visual recognition", ["Recognition", "Human"]),
    ("multimodal", "multimodal-reasoning", "vision language model multimodal reasoning high resolution image understanding", ["VLM", "Reasoning"]),
    ("multimodal", "multimodal-safety", "vision language model safety attack defense jailbreak", ["VLM", "Safety"]),
    ("multimodal", "multimodal-video", "video language model visual language video understanding", ["Video VLM", "Multimodal"]),
    ("robotics", "robotics-embodied", "embodied AI robot manipulation navigation vision language action", ["Robotics", "Embodied AI"]),
    ("robotics", "robotics-driving", "autonomous driving world model scene mining computer vision", ["Autonomous Driving", "World Model"]),
    ("robotics", "robotics-agent", "game agent visual agent embodied world model", ["Agent", "Embodied AI"]),
    ("efficiency", "efficiency-compression", "model compression acceleration edge vision model efficient", ["Efficiency", "Compression"]),
    ("efficiency", "efficiency-inference", "efficient inference vision transformer architecture pruning", ["Inference", "Efficiency"]),
    ("efficiency", "efficiency-optimization", "federated learning optimization clustering vision model", ["Optimization", "Federated"]),
    ("efficiency", "efficiency-distillation", "data distillation dataset quality vision model", ["Data Distillation", "Data Quality"]),
    ("security", "security-watermark", "image watermark copyright provenance generative model", ["Watermark", "Copyright"]),
    ("security", "security-privacy", "privacy membership inference data security vision model", ["Privacy", "Security"]),
    ("security", "security-robustness", "adversarial attack defense robustness vision model", ["Robustness", "Security"]),
    ("dataset", "dataset-benchmark", "computer vision benchmark evaluation dataset", ["Benchmark", "Dataset"]),
    ("dataset", "dataset-highres", "high resolution real world image benchmark dataset", ["High-Resolution", "Dataset"]),
    ("dataset", "dataset-task", "image dataset benchmark computer vision task", ["Dataset", "Benchmark"]),
    ("sr", "sr-super-resolution", "image super-resolution real-world super resolution lightweight SR", ["Super-Resolution", "Low-Level Vision"]),
    ("sr", "sr-attention", "image super-resolution attention transformer self-attention channel attention", ["Super-Resolution", "Attention"]),
    ("sr", "restoration-enhancement", "image restoration enhancement denoising deblurring low-light", ["Restoration", "Enhancement"]),
    ("sr", "restoration-generative", "diffusion prior blind image restoration generative prior", ["Restoration", "Diffusion Prior"]),
]


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or fallback


def arxiv_id_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def year_from_date(value: str) -> int:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).year
    except ValueError:
        try:
            return int(value[:4])
        except Exception:
            return datetime.now(timezone.utc).year


def date_only(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10] if value else ""


def request_json(url: str, timeout: int = 45) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": "ImagePaperHub/1.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    print(f"Warning: request failed: {url[:120]} ({last_error})", file=sys.stderr)
    return None


def semantic_by_arxiv(arxiv_id: str) -> dict:
    url = SEMANTIC_PAPER_API + urllib.parse.quote(f"ARXIV:{arxiv_id}") + "?fields=title,venue,publicationVenue,publicationDate,year,citationCount,url,externalIds,openAccessPdf,abstract,authors"
    payload = request_json(url, timeout=30)
    return semantic_payload_to_item(payload) if payload else {}


def semantic_payload_to_item(item: dict) -> dict:
    if not item or not item.get("title"):
        return {}
    external = item.get("externalIds") or {}
    pdf = item.get("openAccessPdf") or {}
    venue_obj = item.get("publicationVenue") or {}
    publication = venue_obj.get("name") or item.get("venue") or "Semantic Scholar"
    authors = ", ".join([a.get("name", "") for a in (item.get("authors") or [])[:4] if a.get("name")])
    if len(item.get("authors") or []) > 4:
        authors += " et al."
    arxiv_id = external.get("ArXiv") or ""
    doi = external.get("DOI") or ""
    paper_url = item.get("url") or (f"https://doi.org/{doi}" if doi else "")
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
    return {
        "source": "Semantic Scholar",
        "source_id": item.get("paperId") or doi or arxiv_id or normalize_title(item["title"]),
        "title": normalize_text(item.get("title")),
        "authors": authors or "Unknown authors",
        "summary": normalize_text(item.get("abstract"))[:260] or "??????",
        "year": item.get("year") or year_from_date(item.get("publicationDate") or ""),
        "published_date": item.get("publicationDate") or (f"{item.get('year')}-01-01" if item.get("year") else ""),
        "publication": publication,
        "citation_count": item.get("citationCount"),
        "citation_source": "Semantic Scholar",
        "citation_updated": TODAY if item.get("citationCount") is not None else "",
        "links": {"paper": paper_url or (pdf.get("url") or ""), "arxiv": arxiv_url, "code": ""},
    }


def fetch_semantic(query: str, year_from: int, year_to: int, limit: int) -> list[dict]:
    params = urllib.parse.urlencode({
        "query": query,
        "year": f"{year_from}-{year_to}",
        "limit": limit,
        "fields": "title,authors,abstract,year,venue,publicationVenue,publicationDate,citationCount,url,externalIds,openAccessPdf",
    })
    payload = request_json(f"{SEMANTIC_SEARCH_API}?{params}", timeout=45)
    if not payload:
        return []
    return [x for x in (semantic_payload_to_item(item) for item in payload.get("data", [])) if x]


def fetch_openalex(query: str, year_from: int, year_to: int, limit: int) -> list[dict]:
    filters = f"from_publication_date:{year_from}-01-01,to_publication_date:{year_to}-12-31"
    params = urllib.parse.urlencode({"search": query, "filter": filters, "per-page": limit, "sort": "publication_date:desc"})
    payload = request_json(f"{OPENALEX_API}?{params}", timeout=45)
    if not payload:
        return []
    papers = []
    for item in payload.get("results", []):
        title = normalize_text(item.get("title"))
        if not title:
            continue
        authorships = item.get("authorships") or []
        authors = ", ".join([a.get("author", {}).get("display_name", "") for a in authorships[:4] if a.get("author", {}).get("display_name")])
        if len(authorships) > 4:
            authors += " et al."
        primary = item.get("primary_location") or {}
        source = primary.get("source") or {}
        landing = primary.get("landing_page_url") or item.get("doi") or item.get("id") or ""
        pdf = primary.get("pdf_url") or ""
        papers.append({
            "source": "OpenAlex",
            "source_id": item.get("id") or item.get("doi") or normalize_title(title),
            "title": title,
            "authors": authors or "Unknown authors",
            "summary": normalize_text(item.get("abstract_inverted_index") and "" ) or "??????",
            "year": item.get("publication_year") or year_from_date(item.get("publication_date") or ""),
            "published_date": item.get("publication_date") or "",
            "publication": source.get("display_name") or "OpenAlex",
            "citation_count": item.get("cited_by_count"),
            "citation_source": "OpenAlex",
            "citation_updated": TODAY if item.get("cited_by_count") is not None else "",
            "links": {"paper": landing or pdf, "arxiv": "", "code": ""},
        })
    return papers


def fetch_arxiv(query: str, year_from: int, year_to: int, limit: int) -> list[dict]:
    arxiv_query = "cat:cs.CV AND (" + " OR ".join([f'"{part.strip()}"' for part in query.split()[:8]]) + ")"
    params = urllib.parse.urlencode({"search_query": arxiv_query, "start": 0, "max_results": limit, "sortBy": "submittedDate", "sortOrder": "descending"})
    request = urllib.request.Request(f"{ARXIV_API}?{params}", headers={"User-Agent": "ImagePaperHub/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            xml_text = response.read()
    except (TimeoutError, urllib.error.URLError) as exc:
        print(f"Warning: arXiv request failed: {exc}", file=sys.stderr)
        return []
    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall("atom:entry", NS):
        published = entry.findtext("atom:published", default="", namespaces=NS)
        year = year_from_date(published)
        if year < year_from or year > year_to:
            continue
        title = normalize_text(entry.findtext("atom:title", default="", namespaces=NS))
        arxiv_url = entry.findtext("atom:id", default="", namespaces=NS)
        arxiv_id = arxiv_id_from_url(arxiv_url)
        authors = [normalize_text(a.findtext("atom:name", default="", namespaces=NS)) for a in entry.findall("atom:author", NS)]
        semantic = semantic_by_arxiv(arxiv_id)
        papers.append({
            "source": "arXiv",
            "source_id": arxiv_id,
            "title": title,
            "authors": ", ".join(authors[:4]) + (" et al." if len(authors) > 4 else ""),
            "summary": normalize_text(entry.findtext("atom:summary", default="", namespaces=NS))[:260] or "??????",
            "year": year,
            "published_date": semantic.get("published_date") or date_only(published),
            "publication": semantic.get("publication") or "arXiv",
            "citation_count": semantic.get("citation_count"),
            "citation_source": semantic.get("citation_source", ""),
            "citation_updated": semantic.get("citation_updated", ""),
            "links": {"paper": f"https://arxiv.org/pdf/{arxiv_id}", "arxiv": f"https://arxiv.org/abs/{arxiv_id}", "code": ""},
        })
        time.sleep(1)
    return papers


def load_site_data() -> dict:
    return json.loads(PAPERS_JSON.read_text(encoding="utf-8"))


def existing_keys(data: dict) -> set[str]:
    keys = set()
    for paper in data.get("papers", []):
        keys.add(paper.get("id", ""))
        keys.add(normalize_title(paper.get("title", "")))
        for url in (paper.get("links") or {}).values():
            if url:
                keys.add(url.lower())
    return keys


def ensure_metadata_fields(data: dict) -> None:
    for paper in data.get("papers", []):
        paper.setdefault("published_date", f"{paper.get('year', '')}-01-01" if paper.get("year") else "")
        paper.setdefault("publication", paper.get("venue", ""))
        paper.setdefault("citation_count", None)
        paper.setdefault("citation_source", "")
        paper.setdefault("citation_updated", "")


def maybe_refresh_citation(paper: dict) -> bool:
    arxiv_url = (paper.get("links") or {}).get("arxiv", "")
    if not arxiv_url or paper.get("citation_updated") == TODAY:
        return False
    meta = semantic_by_arxiv(arxiv_id_from_url(arxiv_url))
    if not meta:
        return False
    changed = False
    for key in ["citation_count", "citation_source", "citation_updated", "publication", "published_date"]:
        if meta.get(key) not in (None, "") and paper.get(key) != meta.get(key):
            paper[key] = meta[key]
            changed = True
    return changed


def iter_sources(query: str, year_from: int, year_to: int, limit: int, sources: Iterable[str]) -> list[dict]:
    results = []
    if "semantic" in sources:
        results.extend(fetch_semantic(query, year_from, year_to, limit))
        time.sleep(1)
    if "openalex" in sources:
        results.extend(fetch_openalex(query, year_from, year_to, limit))
        time.sleep(1)
    if "arxiv" in sources:
        results.extend(fetch_arxiv(query, year_from, year_to, limit))
        time.sleep(3)
    return results


def merge_papers(data: dict, max_results_per_profile: int, dry_run: bool, year_from: int, year_to: int, sources: list[str]) -> int:
    ensure_metadata_fields(data)
    keys = existing_keys(data)
    added = 0

    for category, subcategory, query, tags in SEARCH_PROFILES:
        for item in iter_sources(query, year_from, year_to, max_results_per_profile, sources):
            title_key = normalize_title(item["title"])
            link_keys = {v.lower() for v in item.get("links", {}).values() if v}
            if title_key in keys or keys.intersection(link_keys):
                continue
            paper_id = f"{item['source'].lower().replace(' ', '-')}-{slugify(item['source_id'], title_key)}"
            paper = {
                "id": paper_id,
                "title": item["title"],
                "authors": item.get("authors") or "Unknown authors",
                "venue": item.get("publication") or item.get("source") or "Unknown",
                "publication": item.get("publication") or item.get("source") or "Unknown",
                "published_date": item.get("published_date") or f"{item.get('year', year_from)}-01-01",
                "citation_count": item.get("citation_count"),
                "citation_source": item.get("citation_source", ""),
                "citation_updated": item.get("citation_updated", ""),
                "year": item.get("year") or year_from,
                "category": category,
                "subcategory": subcategory,
                "tags": [*tags, "Auto-Fetched"],
                "summary": item.get("summary") or "??????",
                "links": item.get("links") or {"paper": "", "arxiv": "", "code": ""},
                "status": "??????????",
            }
            data.setdefault("papers", []).append(paper)
            keys.add(title_key)
            keys.update(link_keys)
            added += 1

    refreshed = 0
    if not dry_run:
        for paper in data.get("papers", [])[:40]:
            if maybe_refresh_citation(paper):
                refreshed += 1
                time.sleep(1)

    if (added or refreshed) and not dry_run:
        data.setdefault("site", {})["updated"] = TODAY
        PAPERS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Refreshed citations: {refreshed}")
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch recent image papers from Semantic Scholar, OpenAlex, and arXiv.")
    parser.add_argument("--max-results", type=int, default=2, help="???????????????????")
    parser.add_argument("--year-from", type=int, default=2025, help="????????? 2025?")
    parser.add_argument("--year-to", type=int, default=2026, help="????????? 2026?")
    parser.add_argument("--sources", default="semantic,openalex,arxiv", help="??????????semantic,openalex,arxiv?")
    parser.add_argument("--dry-run", action="store_true", help="??????????????")
    args = parser.parse_args()

    sources = [x.strip().lower() for x in args.sources.split(",") if x.strip()]
    data = load_site_data()
    added = merge_papers(data, max(args.max_results, 1), args.dry_run, args.year_from, args.year_to, sources)
    print(f"Added {added} new papers from {', '.join(sources)} for {args.year_from}-{args.year_to}." + (" Dry run only." if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

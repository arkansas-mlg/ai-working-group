#!/usr/bin/env python3
"""Build the AI Working Group site from editable YAML content."""

import argparse
from datetime import date, datetime
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parent.parent
COLLECTIONS = ("people", "events", "compute", "funding", "projects")
ROUTES = {
    "home": ("", "home.html", "Home"),
    "about": ("about", "about.html", "About & goals"),
    "people": ("people", "people.html", "People"),
    "events": ("schedule", "collection.html", "Schedule"),
    "compute": ("compute", "collection.html", "Compute & credits"),
    "funding": ("funding", "collection.html", "Funding opportunities"),
}


class ContentError(ValueError):
    """A content file cannot be rendered safely or consistently."""


def require_text(value, location):
    if not isinstance(value, str) or not value.strip():
        raise ContentError(f"{location}: expected nonempty text")


def validate_link(value, location):
    require_text(value, location)
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in {"https", "http", "mailto"}:
        raise ContentError(f"{location}: use an https, http, mailto, or local link")
    if value.startswith("//") or "\\" in value or any(ord(c) < 32 for c in value):
        raise ContentError(f"{location}: invalid link")
    if ".." in parsed.path.split("/"):
        raise ContentError(f"{location}: parent-directory links are not supported")


def validate_fields(value, location):
    """Catch common editing errors, including unsafe URLs, before publication."""
    if isinstance(value, dict):
        for key, item in value.items():
            field = f"{location}.{key}"
            if key in {"url", "path", "primary_path", "secondary_path"} and item:
                validate_link(item, field)
            if key in {"date", "deadline", "last_checked"} and item:
                if isinstance(item, date) and not isinstance(item, datetime):
                    value[key] = item.isoformat()
                else:
                    try:
                        date.fromisoformat(str(item))
                    except ValueError as exc:
                        raise ContentError(f"{field}: use YYYY-MM-DD or omit the field") from exc
            if key == "sample" and not isinstance(item, bool):
                raise ContentError(f"{field}: use true or false, without quotes")
            if key in {"tags", "interests", "topics", "details"}:
                if not isinstance(item, list) or any(not isinstance(x, str) for x in item):
                    raise ContentError(f"{field}: expected a list of text values")
            validate_fields(item, field)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_fields(item, f"{location}[{index + 1}]")


def read_content(content_dir):
    data = {}
    for name in ("site", "about", *COLLECTIONS):
        path = content_dir / f"{name}.yaml"
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ContentError(f"{path}: {exc}") from exc
        if name in COLLECTIONS:
            if value is None:
                value = []
            if not isinstance(value, list):
                raise ContentError(f"{path}: expected a YAML list (use [] for no entries)")
            ids = set()
            for index, item in enumerate(value):
                location = f"{path}, entry {index + 1}"
                if not isinstance(item, dict):
                    raise ContentError(f"{location}: expected a mapping")
                for key in ("id", "name" if name == "people" else "title"):
                    require_text(item.get(key), f"{location}.{key}")
                if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item["id"]):
                    raise ContentError(f"{location}.id: use lowercase words separated by hyphens")
                if item["id"] in ids:
                    raise ContentError(f"{location}: duplicate id {item['id']!r}")
                ids.add(item["id"])
        elif not isinstance(value, dict):
            raise ContentError(f"{path}: expected a YAML mapping")
        validate_fields(value, str(path))
        data[name] = value
    require_text(data["site"].get("name"), "site.yaml.name")
    nav = data["site"].get("nav", [])
    if not isinstance(nav, list):
        raise ContentError("site.yaml.nav: expected a list")
    for index, item in enumerate(nav):
        if not isinstance(item, dict):
            raise ContentError(f"site.yaml.nav[{index + 1}]: expected a mapping")
        require_text(item.get("label"), "site.yaml.nav.label")
        validate_link(item.get("path"), "site.yaml.nav.path")
    for key in ("hero", "join", "pages"):
        if key in data["site"] and not isinstance(data["site"][key], dict):
            raise ContentError(f"site.yaml.{key}: expected a mapping")
    for key, metadata in data["site"].get("pages", {}).items():
        if not isinstance(metadata, dict):
            raise ContentError(f"site.yaml.pages.{key}: expected a mapping")
    for key in ("themes", "goals", "milestones"):
        entries = data["about"].get(key, [])
        if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
            raise ContentError(f"about.yaml.{key}: expected a list of mappings")
    return data


def normalize_base_path(value):
    if not value or value == "/":
        return ""
    path = "/" + value.strip("/")
    if not re.fullmatch(r"(?:/[A-Za-z0-9._-]+)+", path) or ".." in path.split("/"):
        raise ContentError("base path must be a local URL path, such as /ai-working-group")
    return path


def format_date(value, style="full"):
    if not value:
        return "To be announced"
    parsed = date.fromisoformat(str(value))
    if style == "month":
        return parsed.strftime("%b")
    if style == "day":
        return str(parsed.day)
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def build_site(content_dir, output, base_path="", exclude_samples=False):
    content_dir, output = Path(content_dir).resolve(), Path(output).resolve()
    base_path = normalize_base_path(base_path)
    protected = (ROOT, content_dir, ROOT / "templates", ROOT / "assets", ROOT / "scripts")
    if any(output == path or output in path.parents for path in protected):
        raise ContentError("output directory must not replace source files")
    if any(path in output.parents for path in protected[1:]):
        raise ContentError("output directory must be outside content, templates, assets, and scripts")
    if output.exists() and (not output.is_dir() or (any(output.iterdir()) and not (output / ".aiwg-build").is_file())):
        raise ContentError(f"{output}: refusing to overwrite an unmarked nonempty directory")
    data = read_content(content_dir)
    if exclude_samples:
        for name in COLLECTIONS:
            data[name] = [item for item in data[name] if not item.get("sample", False)]
    today = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    for name in ("events", "compute", "funding"):
        for item in data[name]:
            boundary = item.get("date" if name == "events" else "deadline")
            if boundary and str(boundary) < today:
                item["status"] = "Past" if name == "events" else "Closed"
    data["events"].sort(key=lambda item: (item.get("status") == "Past", item.get("date") or "9999", item["title"]))
    for name in ("compute", "funding"):
        data[name].sort(key=lambda item: (item.get("status") == "Closed", item.get("deadline") or "9999", item["title"]))

    def url(path=""):
        path = str(path)
        if urlsplit(path).scheme or path.startswith("#"):
            return path
        return base_path + "/" + path.lstrip("/")

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date_label"] = format_date
    env.globals.update(url=url)
    context = {
        **data,
        "has_samples": any(item.get("sample") for name in COLLECTIONS for item in data[name]),
        "year": today[:4],
        "base_path": base_path,
        "today": today,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Render everything before replacing the previous successful build.
    with tempfile.TemporaryDirectory(prefix=".aiwg-", dir=output.parent) as temp:
        staging = Path(temp) / "site"
        staging.mkdir()
        shutil.copytree(ROOT / "assets", staging / "assets")
        for page, (route, template, title) in ROUTES.items():
            entries = data.get(page, []) if page in COLLECTIONS else []
            metadata = data["site"].get("pages", {}).get(page, {})
            page_context = {
                **context, "page": page, "route": route,
                "page_title": metadata.get("title", title), "page_meta": metadata,
                "entries": entries,
                "types": sorted({item["type"] for item in entries if item.get("type")}),
                "statuses": sorted({item["status"] for item in entries if item.get("status")}),
            }
            target = staging / route / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(env.get_template(template).render(**page_context), encoding="utf-8")
        (staging / "404.html").write_text(env.get_template("404.html").render(
            **context, page="404", route="404", page_title="Page not found"
        ), encoding="utf-8")
        (staging / ".nojekyll").touch()
        (staging / ".aiwg-build").write_text("Generated by scripts/build.py\n", encoding="utf-8")
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(staging, output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-dir", type=Path, default=ROOT / "content")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--base-path", default="", help="GitHub Pages project path, e.g. /ai-working-group")
    parser.add_argument("--exclude-samples", action="store_true", help="Omit records marked sample: true")
    args = parser.parse_args()
    try:
        result = build_site(args.content_dir, args.output, args.base_path, args.exclude_samples)
    except ContentError as exc:
        parser.exit(1, f"Content error: {exc}\n")
    print(f"Built {len(ROUTES)} pages + 404 in {result} (base path: {normalize_base_path(args.base_path) or '/'})")


if __name__ == "__main__":
    main()

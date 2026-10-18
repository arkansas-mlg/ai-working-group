"""Integration checks for content-driven builds and GitHub Pages paths."""

from html.parser import HTMLParser
from pathlib import Path
import shutil
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

import yaml

from scripts.build import build_site


ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = ("people", "events", "compute", "funding")
ROUTES = (
    "index.html",
    "about/index.html",
    "people/index.html",
    "schedule/index.html",
    "compute/index.html",
    "funding/index.html",
    "404.html",
)


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.references = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        for attribute in ("href", "src"):
            if attributes.get(attribute):
                self.references.append(attributes[attribute])


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.content = self.workspace / "content"
        shutil.copytree(ROOT / "content", self.content)
        self.output = self.workspace / "site"

    def write_content(self, name, data):
        (self.content / (name + ".yaml")).write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def read_content(self, name):
        return yaml.safe_load(
            (self.content / (name + ".yaml")).read_text(encoding="utf-8")
        )

    def assert_routes_exist(self):
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertTrue((self.output / route).is_file(), route)

    def assert_internal_links_resolve(self, base_path):
        pages = {}
        for path in self.output.rglob("*.html"):
            parser = PageLinks()
            parser.feed(path.read_text(encoding="utf-8"))
            pages[path.resolve()] = parser
        checked = 0
        for source, parser in pages.items():
            for reference in parser.references:
                link = urlsplit(reference)
                if link.scheme or link.netloc:
                    continue
                path = unquote(link.path)
                if path.startswith("/"):
                    self.assertTrue(
                        path == base_path or path.startswith(base_path + "/"),
                        "%s escapes the project path in %s" % (reference, source),
                    )
                    target = self.output / path[len(base_path):].lstrip("/")
                elif path:
                    target = source.parent / path
                else:
                    target = source
                if target.is_dir():
                    target = target / "index.html"
                target = target.resolve()
                self.assertTrue(
                    target.is_file(), "%s is broken in %s" % (reference, source)
                )
                if link.fragment and target.suffix == ".html":
                    self.assertIn(
                        unquote(link.fragment),
                        pages[target].ids,
                        "%s has no matching anchor in %s" % (reference, source),
                    )
                checked += 1
        self.assertGreater(checked, 20, "Expected a complete site with internal links")

    def test_project_path_build_has_valid_links_and_assets(self):
        build_site(self.content, self.output, base_path="/ai-working-group")
        self.assert_routes_exist()
        self.assertTrue((self.output / ".nojekyll").is_file())
        self.assert_internal_links_resolve("/ai-working-group")

    def test_empty_collections_keep_all_pages_usable(self):
        for index, name in enumerate(COLLECTIONS):
            # Both an explicit empty list and a blank YAML file are supported.
            (self.content / (name + ".yaml")).write_text(
                "[]\n" if index % 2 == 0 else "", encoding="utf-8"
            )
        build_site(self.content, self.output)
        self.assert_routes_exist()
        self.assert_internal_links_resolve("")

    def test_minimal_entries_render_without_optional_fields(self):
        labels = []
        for name in COLLECTIONS:
            label = "Minimal %s entry" % name
            labels.append(label)
            self.write_content(name, [{
                "id": "minimal-" + name,
                "name" if name == "people" else "title": label,
            }])
        build_site(self.content, self.output, base_path="/ai-working-group")
        self.assert_routes_exist()
        self.assert_internal_links_resolve("/ai-working-group")
        rendered = "\n".join(
            path.read_text(encoding="utf-8") for path in self.output.rglob("*.html")
        )
        for label in labels:
            self.assertIn(label, rendered)

    def test_excluding_samples_preserves_real_entries(self):
        people = self.read_content("people")
        self.assertTrue(people, "Initial content must include the founding PIs")
        people[0]["name"] = "Retained Researcher 9217"
        people[0]["sample"] = False
        people.append({"id": "sample-person", "name": "Sample Researcher 8462", "sample": True})
        self.write_content("people", people)
        build_site(self.content, self.output, exclude_samples=True)
        self.assert_routes_exist()
        rendered = "\n".join(
            path.read_text(encoding="utf-8") for path in self.output.rglob("*.html")
        )
        self.assertIn("Retained Researcher 9217", rendered)
        self.assertNotIn("Sample Researcher 8462", rendered)
        for name in COLLECTIONS:
            for item in self.read_content(name) or []:
                if item.get("sample"):
                    self.assertNotIn(item.get("title", item.get("name")), rendered)

    def test_content_is_html_escaped(self):
        people = self.read_content("people")
        people[0]["name"] = 'Test <script>alert("unsafe")</script> & Member'
        self.write_content("people", people)
        build_site(self.content, self.output)
        rendered = (self.output / "people/index.html").read_text(encoding="utf-8")
        self.assertNotIn('<script>alert("unsafe")</script>', rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&amp; Member", rendered)

    def test_invalid_collection_structure_is_rejected(self):
        self.write_content("people", {"name": "A mapping is not a collection"})
        with self.assertRaises(ValueError):
            build_site(self.content, self.output)

    def test_missing_required_entry_field_is_rejected(self):
        self.write_content("people", [{"id": "missing-name"}])
        with self.assertRaises(ValueError):
            build_site(self.content, self.output)

    def test_unsafe_links_are_rejected(self):
        for link in (
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "//untrusted.example/",
            "../outside-project/",
        ):
            with self.subTest(link=link):
                self.write_content("funding", [{
                    "id": "unsafe-link",
                    "title": "Unsafe example",
                    "url": link,
                }])
                with self.assertRaises(ValueError):
                    build_site(self.content, self.output)

    def test_invalid_page_metadata_is_rejected(self):
        site = self.read_content("site")
        for metadata in ([], None, "Not a mapping"):
            with self.subTest(metadata=metadata):
                site["pages"] = {"compute": metadata}
                self.write_content("site", site)
                with self.assertRaises(ValueError):
                    build_site(self.content, self.output)

    def test_duplicate_ids_are_rejected(self):
        self.write_content("events", [
            {"id": "same-event", "title": "First activity"},
            {"id": "same-event", "title": "Second activity"},
        ])
        with self.assertRaises(ValueError):
            build_site(self.content, self.output)

    def test_malformed_yaml_is_rejected(self):
        (self.content / "funding.yaml").write_text("items: [\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            build_site(self.content, self.output)

    def test_existing_unrelated_output_is_preserved(self):
        self.output.mkdir()
        original = self.output / "keep.txt"
        original.write_text("Existing user content", encoding="utf-8")
        with self.assertRaises(ValueError):
            build_site(self.content, self.output)
        self.assertEqual(original.read_text(encoding="utf-8"), "Existing user content")

    def test_rebuild_replaces_stale_generated_content(self):
        self.write_content("people", [{"id": "researcher", "name": "Previous Profile 2643"}])
        build_site(self.content, self.output)
        stale = self.output / "obsolete.html"
        stale.write_text("A page from an older build", encoding="utf-8")
        self.write_content("people", [{"id": "researcher", "name": "Updated Profile 8571"}])
        build_site(self.content, self.output)
        self.assertFalse(stale.exists())
        rendered = (self.output / "people/index.html").read_text(encoding="utf-8")
        self.assertIn("Updated Profile 8571", rendered)
        self.assertNotIn("Previous Profile 2643", rendered)
        self.assert_routes_exist()


if __name__ == "__main__":
    unittest.main()

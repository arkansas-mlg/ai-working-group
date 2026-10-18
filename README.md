# AI Working Group

A YAML-driven website for the University of Arkansas College of Engineering AI Working Group. It introduces the group and its three founding PIs, with room for a growing schedule, compute and credit opportunities, funding, and research concepts.

The site is generated with Python, Jinja2, and PyYAML. The output is ordinary HTML, CSS, and JavaScript suitable for GitHub Pages. There is no database or backend service.

## Local preview

Use Python 3.9 or later:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/build.py
python -m http.server 8000 --directory dist
```

Open <http://localhost:8000>. After editing content or templates, run the build again and refresh the browser.

To preview the repository path used by a GitHub Pages project site:

```sh
python scripts/build.py --base-path /ai-working-group --output .preview/ai-working-group
python -m http.server 8000 --directory .preview
```

Open <http://localhost:8000/ai-working-group/>. Replace `/ai-working-group` with the actual repository path when needed. A user, organization, or custom-domain site can use an empty base path.

## Edit content

Edit files in `content/`, then rebuild. Most content changes do not require editing templates.

| File | Contents |
| --- | --- |
| `site.yaml` | Group identity, navigation, homepage introduction, contact details, footer |
| `about.yaml` | Mission, research themes, goals, planned milestones |
| `people.yaml` | PI and participant profiles |
| `events.yaml` | Upcoming, planned, and past activities |
| `compute.yaml` | Computing access and credit opportunities |
| `funding.yaml` | Funding opportunities |
| `projects.yaml` | Research concepts and collaboration ideas |

`site.yaml` and `about.yaml` contain mappings. The remaining files contain lists. Each list entry needs a unique `id` and a `title`; people use `name` instead of `title`. Other information is optional. Keep IDs stable when editing an existing item.

Page headings are optional: omit `title` from `about.yaml` or a page under `site.yaml` → `pages` to hide its large heading. The browser tab still uses a default page name.

An opportunity can start with a small entry:

```yaml
- id: example-research-credits
  title: Example research credit opportunity
  summary: Replace this description with a verified opportunity.
  provider: Example provider
  type: Cloud credits
  status: Planned
  sample: true
  tags:
    - GPUs
```

Additional fields used by the initial content include:

- **People:** `role`, `department`, `email`, `bio`, `interests`, and `initials`.
- **Events:** `type`, `summary`, `date`, `time`, `location`, `status`, and `tags`.
- **Compute and funding:** `provider`, `type`, `summary`, `eligibility`, `deadline`, `status`, and `tags`. Compute can include `access` and `details`; funding can include `amount`.
- **Projects:** `summary`, `type`, `status`, and `tags`.

Add `url` for a profile, project, or opportunity link. Schedule, compute, and funding listings can use `link_label` for its display text and `last_checked` to show when the listing was verified. Supported links are HTTPS, HTTP, email, and local site paths.

Quote dates as `"YYYY-MM-DD"`. Omit a date or deadline when it is not confirmed. Events with past dates and opportunities with past deadlines are marked past or closed when the site is rebuilt. Collection pages also refresh these statuses in the browser between builds, using the group's America/Chicago time zone. Use `[]` or a blank file for an empty collection; its page remains available without entries. Text is rendered as plain content rather than raw HTML.

The initial activities, opportunities, and research concepts are illustrative and marked internally with `sample: true`, which produces no visible notices or labels. Replace or remove them as real content becomes available. To build a version that omits all samples:

```sh
python scripts/build.py --exclude-samples
```

Navigation labels and paths are in `site.yaml`. Use paths such as `people/` relative to the site root so the build can add the GitHub Pages base path. Changing navigation does not create a new page route; adding a new section requires a corresponding template and build route.

## Validate and publish

```sh
python -m unittest discover -s tests -v
```

Tests check generated routes, project-path links and assets, empty collections, minimal entries, sample removal, HTML escaping, unsafe links, invalid content, and safe rebuilds.

The GitHub Actions workflow builds and tests pull requests. Pushes to `main` and manual runs also publish to GitHub Pages after successful checks.

To enable the first publication:

1. Push this repository to GitHub.
2. Open **Settings → Pages → Build and deployment** and select **GitHub Actions** as the source.
3. Open **Actions → Build and deploy GitHub Pages → Run workflow**, or push a change to `main`.
4. Use the URL shown by the completed deployment or the repository's Pages settings.

The workflow obtains the hosting base path from GitHub Pages. Generated files are uploaded as a deployment artifact; do not commit `dist/` or `.preview/`. To publish without sample content, add `--exclude-samples` to the workflow's build command.

The generator creates a `.aiwg-build` marker in its output directory. Subsequent builds replace that generated directory; a nonempty directory without the marker is protected from replacement. Keep hand-maintained files outside build output directories.

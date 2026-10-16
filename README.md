# contextkit.outhad.com

The website and documentation for [ContextKit](https://contextkit.outhad.com), long-term memory for AI agents.

- **Library:** [`outhad-contextkitai`](https://pypi.org/project/outhad-contextkitai/) — `pip install outhad-contextkitai`
- **Cloud SDK:** [`outhad-contextkit-sdk`](https://pypi.org/project/outhad-contextkit-sdk/) — `pip install outhad-contextkit-sdk`
- **Docs:** <https://contextkit.outhad.com/docs/>
- **Changelog:** <https://contextkit.outhad.com/changelog/>

Found a mistake in the docs? Open an issue, or use the "Edit this page on GitHub" link at the bottom of any page.

## How the site stays current

Every build reads both packages from PyPI. Nothing version-specific is written by hand, so a release updates the site on its own:

| Generated from PyPI | Where |
|---|---|
| Latest versions, install commands, release dates | Landing page, docs, `/release.json` |
| Every release, with notes from `content/changelog/<package>/<version>.md` | `/changelog/` |
| Public classes, methods, signatures, and docstrings, parsed from the latest wheel with `ast` | `/docs/reference/library/`, `/docs/reference/sdk/` |
| Every config field and default, parsed from the latest wheel | `/docs/reference/config/` |
| "Coming in the next release" notices on guides whose `requires:` module is not in the latest wheel | Each guide |

A build is triggered by:

1. **A release from the library repository.** Its release workflow publishes to PyPI, waits until PyPI serves the new version, then commits the release notes to `content/changelog/`. That push rebuilds and deploys the site.
2. **A release published by hand** (`twine upload`). A scheduled run every six hours compares PyPI with the live `/release.json` and deploys when PyPI is ahead. Run the **Build and deploy** workflow from the Actions tab to update right away.
3. **Any push to `main`**, such as a docs edit.

Pull requests are built and link-checked but not deployed.

## Work on it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build.py --serve        # http://localhost:8000
.venv/bin/python build.py --offline      # rebuild from .cache/ without calling PyPI
```

The build fails on a broken internal link or anchor, or on a `python` code block that does not parse.

## Layout

```text
site.toml              site settings, packages, sidebar order
build.py               the generator
templates/             home.html (landing page), doc.html, changelog.html, base.html, 404.html
static/                site.css, site.js, favicon.svg
content/docs/          one Markdown file per guide
content/changelog/     release notes: library/<version>.md, sdk/<version>.md
content/snippets/      code shown on the landing page
.github/workflows/     deploy.yml
```

## Writing docs

Each guide is Markdown with a short header:

```markdown
---
title: Context graph
nav: Context graph                     # sidebar label (optional, defaults to title)
description: One sentence under the title, and the page's meta description.
requires: outhad_contextkit.memory.context_graph   # optional
---
```

- `requires:` names a module (`a.b.c`) or something in one (`a.b.c:Class.method`). While the latest release on PyPI does not contain it, the page carries a "coming in the next release" notice. Set `show_unreleased = false` in `site.toml` to leave such pages out instead.
- `{{ library.version }}`, `{{ library.install }}`, `{{ library.dist }}` and the same for `sdk` are replaced with values from PyPI.
- Use `!!! note "Title"` or `!!! warning "Title"` for callouts.
- Link between pages with absolute paths, such as `/docs/scoping/#filter-by-metadata`.

Add a page by creating `content/docs/<slug>.md` and listing `<slug>` in a `[[nav]]` section of `site.toml`.

## Settings in `site.toml`

| Setting | Meaning |
|---|---|
| `show_unreleased` | Build pages whose `requires:` is not released yet (with a notice). |
| `cloud_open` | Set to `true` when the hosted cloud opens for sign-ups; until then the cloud pages say it is not open. |
| `[packages.*.api]` | Modules and classes the API reference is generated from. |
| `[[packages.library.config]]` | Modules and config classes the configuration reference is generated from. |

## Hosting

GitHub Pages, deployed by `.github/workflows/deploy.yml`. One-time setup:

1. **Settings → Pages → Source:** GitHub Actions.
2. **Settings → Pages → Custom domain:** `contextkit.outhad.com`, then **Enforce HTTPS**.
3. **DNS:** a `CNAME` record for `contextkit` at `outhad.com` pointing to `tanzil7890.github.io`. The landing page is served at `/` and the docs at `/docs/`, and the hosted cloud lives on its own hosts: the API at `api.contextkit.outhad.com` (the SDK's `DEFAULT_HOST` from 1.10.0) and the dashboard at `app.contextkit.outhad.com`.

## License

Apache-2.0. See [LICENSE](LICENSE).

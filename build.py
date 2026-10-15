#!/usr/bin/env python3
"""Build https://contextkit.outhad.com into _site/.

The site has two kinds of content:

* Hand-written pages: templates/home.html and the Markdown guides in content/docs/.
* Release data read from PyPI on every build: each package's versions and release
  dates, and the public API and configuration defaults parsed out of its latest
  wheel with `ast`, so nothing is imported or installed.

Nothing version-specific is written by hand, so publishing a release to PyPI is
all it takes to update the site: the next build picks it up.

    python build.py               build into _site/
    python build.py --serve       build, then serve _site/ on http://localhost:8000
    python build.py --offline     use the copies in .cache/ instead of calling PyPI
    python build.py --check-live  print changed=true|false: is PyPI ahead of the live site?
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import functools
import hashlib
import html
import http.server
import json
import os
import re
import shutil
import sys
import textwrap
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from packaging.version import InvalidVersion, Version
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"
CACHE = ROOT / ".cache"
CONTENT = ROOT / "content"
USER_AGENT = "contextkit-site-build (+https://contextkit.outhad.com)"


# --------------------------------------------------------------------------- PyPI


@dataclass
class Release:
    version: str
    date: str
    notes: str = ""


@dataclass
class Package:
    key: str
    dist: str
    import_name: str
    label: str
    install: str
    reference: str
    cfg: dict
    version: str = ""
    released: str = ""
    requires_python: str = ""
    releases: list[Release] = field(default_factory=list)
    wheel: zipfile.ZipFile | None = None
    files: set[str] = field(default_factory=set)

    @property
    def pypi_url(self) -> str:
        return f"https://pypi.org/project/{self.dist}/"

    def source(self, path: str) -> str | None:
        if self.wheel is None or path not in self.files:
            return None
        return self.wheel.read(path).decode("utf-8")


def http_get(url: str, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as err:
            if err.code == 404 or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def sort_key(version: str) -> Version:
    try:
        return Version(version)
    except InvalidVersion:
        return Version("0")


def pypi_json(dist: str, offline: bool) -> dict:
    cached = CACHE / "pypi" / f"{dist}.json"
    if offline:
        if not cached.exists():
            sys.exit(f"{cached} is missing; run once without --offline")
        return json.loads(cached.read_text())
    raw = http_get(f"https://pypi.org/pypi/{dist}/json")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(raw)
    return json.loads(raw)


def load_package(key: str, cfg: dict, offline: bool) -> Package:
    pkg = Package(
        key=key,
        cfg=cfg,
        **{name: cfg[name] for name in ("dist", "import_name", "label", "install", "reference")},
    )
    data = pypi_json(pkg.dist, offline)
    pkg.version = data["info"]["version"]
    pkg.requires_python = data["info"].get("requires_python") or ""
    for version, files in data["releases"].items():
        files = [f for f in files if not f.get("yanked")]
        if files:
            date = min(f["upload_time_iso_8601"] for f in files)[:10]
            pkg.releases.append(Release(version, date, read_notes(key, version)))
    pkg.releases.sort(key=lambda r: sort_key(r.version), reverse=True)
    pkg.released = next((r.date for r in pkg.releases if r.version == pkg.version), "")

    wheel = next((f for f in data["urls"] if f["packagetype"] == "bdist_wheel"), None)
    if wheel:
        pkg.wheel = zipfile.ZipFile(fetch_wheel(wheel, offline))
        pkg.files = set(pkg.wheel.namelist())
    else:
        print(f"warning: {pkg.dist} {pkg.version} has no wheel; reference pages will be empty")
    return pkg


def fetch_wheel(entry: dict, offline: bool) -> Path:
    path = CACHE / "wheels" / entry["filename"]
    if path.exists():
        return path
    if offline:
        sys.exit(f"{path} is missing; run once without --offline")
    blob = http_get(entry["url"])
    if hashlib.sha256(blob).hexdigest() != entry["digests"]["sha256"]:
        sys.exit(f"checksum mismatch for {entry['filename']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return path


def read_notes(key: str, version: str) -> str:
    path = CONTENT / "changelog" / key / f"{version}.md"
    return path.read_text() if path.exists() else ""


# ------------------------------------------------------------ reading the wheels


def find_member(tree: ast.Module, dotted: list[str]) -> ast.AST | None:
    node: ast.AST = tree
    for name in dotted:
        match = None
        for child in getattr(node, "body", []):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
                match = child
            elif isinstance(child, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in child.targets
            ):
                match = child
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and child.target.id == name:
                match = child
        if match is None:
            return None
        node = match
    return node


def requirement_met(packages: dict[str, Package], spec: str) -> bool:
    """`spec` names a module (`a.b.c`) or something in one (`a.b.c:Class.method`)."""
    module, _, attr = spec.partition(":")
    pkg = next((p for p in packages.values() if module.split(".")[0] == p.import_name), None)
    if pkg is None:
        raise SystemExit(f"requires: {spec!r} is not in any package in site.toml")
    base = module.replace(".", "/")
    path = next((p for p in (f"{base}.py", f"{base}/__init__.py") if p in pkg.files), None)
    if path is None:
        return False
    if not attr:
        return True
    return find_member(ast.parse(pkg.source(path)), attr.split(".")) is not None


@dataclass
class Member:
    name: str
    kind: str
    signature: str
    doc: str


@dataclass
class ApiClass:
    name: str
    module: str
    doc: str
    members: list[Member]


def format_arg(arg: ast.arg, default: ast.expr | None) -> str:
    text = arg.arg
    if arg.annotation is not None:
        text += ": " + ast.unparse(arg.annotation)
    if default is not None:
        text += (" = " if arg.annotation is not None else "=") + ast.unparse(default)
    return text


def format_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef, drop_self: bool) -> str:
    args = fn.args
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    params = []
    for index, (arg, default) in enumerate(zip(positional, defaults)):
        if index == 0 and drop_self and arg.arg in ("self", "cls"):
            continue
        params.append(format_arg(arg, default))
        if args.posonlyargs and index == len(args.posonlyargs) - 1:
            params.append("/")
    if args.vararg:
        params.append("*" + format_arg(args.vararg, None))
    elif args.kwonlyargs:
        params.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append(format_arg(arg, default))
    if args.kwarg:
        params.append("**" + format_arg(args.kwarg, None))

    prefix = "async def " if isinstance(fn, ast.AsyncFunctionDef) else "def "
    returns = f" -> {ast.unparse(fn.returns)}" if fn.returns is not None else ""
    one_line = f"{prefix}{fn.name}({', '.join(params)}){returns}"
    if len(one_line) <= 88 or not params:
        return one_line
    inner = "".join(f"    {p},\n" for p in params)
    return f"{prefix}{fn.name}(\n{inner}){returns}"


def extract_api(pkg: Package, module_path: str, class_names: list[str]) -> list[ApiClass]:
    src = pkg.source(module_path)
    if src is None:
        return []
    tree = ast.parse(src)
    module = module_path.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
    found = []
    for name in class_names:
        node = find_member(tree, [name])
        if not isinstance(node, ast.ClassDef):
            continue
        members: dict[str, Member] = {}
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name.startswith("_") and item.name != "__init__":
                continue
            decorators = {ast.unparse(d) for d in item.decorator_list}
            if "overload" in decorators or "typing.overload" in decorators:
                continue
            if "property" in decorators:
                kind = "property"
            elif "classmethod" in decorators:
                kind = "classmethod"
            elif "staticmethod" in decorators:
                kind = "staticmethod"
            elif isinstance(item, ast.AsyncFunctionDef):
                kind = "async"
            else:
                kind = ""
            members.pop(item.name, None)  # a later definition wins, in its own place
            members[item.name] = Member(
                item.name,
                kind,
                format_signature(item, drop_self=kind != "staticmethod"),
                ast.get_docstring(item) or "",
            )
        found.append(ApiClass(name, module, ast.get_docstring(node) or "", list(members.values())))
    return found


def extract_constants(pkg: Package, module_path: str, names: list[str]) -> dict[str, str]:
    src = pkg.source(module_path)
    if src is None:
        return {}
    tree = ast.parse(src)
    values = {}
    for name in names:
        node = find_member(tree, [name])
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            values[name] = ast.unparse(node.value)
    return values


@dataclass
class ConfigField:
    name: str
    type: str
    default: str
    description: str


@dataclass
class ConfigClass:
    name: str
    doc: str
    fields: list[ConfigField]


def literal_text(node: ast.expr | None) -> str:
    if node is None:
        return ""
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return ""
    return value if isinstance(value, str) else ""


def describe_default(value: ast.expr | None) -> str:
    if value is None:
        return "required"
    if isinstance(value, ast.Call) and ast.unparse(value.func) in ("Field", "pydantic.Field"):
        keywords = {k.arg: k.value for k in value.keywords if k.arg}
        if "default" in keywords:
            return describe_default(keywords["default"])
        if value.args:
            first = value.args[0]
            if isinstance(first, ast.Constant) and first.value is Ellipsis:
                return "required"
            return ast.unparse(first)
        if "default_factory" in keywords:
            factory = keywords["default_factory"]
            if isinstance(factory, ast.Lambda):
                return ast.unparse(factory.body)
            return {"list": "[]", "dict": "{}", "set": "set()"}.get(ast.unparse(factory), ast.unparse(factory) + "()")
        return "required"
    return ast.unparse(value)


def extract_config(pkg: Package, module_path: str, class_names: list[str]) -> list[ConfigClass]:
    src = pkg.source(module_path)
    if src is None:
        return []
    tree = ast.parse(src)
    found = []
    for name in class_names:
        node = find_member(tree, [name])
        if not isinstance(node, ast.ClassDef):
            continue
        fields = []
        for item in node.body:
            if not (isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)):
                continue
            field_name = item.target.id
            annotation = ast.unparse(item.annotation)
            if field_name.startswith("_") or field_name == "model_config" or annotation.startswith("ClassVar"):
                continue
            description = ""
            if isinstance(item.value, ast.Call):
                description = literal_text(next((k.value for k in item.value.keywords if k.arg == "description"), None))
            fields.append(ConfigField(field_name, annotation, describe_default(item.value), description))
        found.append(ConfigClass(name, ast.get_docstring(node) or "", fields))
    return found


# ------------------------------------------------------------------- rendering

FORMATTER = HtmlFormatter(nowrap=True)


def highlight_python(code: str) -> Markup:
    return Markup(highlight(code, PythonLexer(), FORMATTER))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def inline(text: str) -> str:
    """Escape docstring text, then turn RST/Markdown code spans and bold into HTML."""
    text = html.escape(text, quote=False)
    text = re.sub(r"``(.+?)``", r"<code>\1</code>", text)
    text = re.sub(r"(?<![\w`])`([^`]+?)`(?!\w)", r"<code>\1</code>", text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def render_prose(lines: list[str]) -> str:
    out, paragraph, bullets, code = [], [], [], []

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{inline(' '.join(l.strip() for l in paragraph))}</p>")
            paragraph.clear()
        if bullets:
            out.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()
        if code:
            body = html.escape(textwrap.dedent("\n".join(code)).strip("\n"))
            out.append(f"<pre><code>{body}</code></pre>")
            code.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
        elif stripped.startswith(">>>") or (code and line.startswith(" ")) or line.startswith("    "):
            if paragraph or bullets:
                flush()
            code.append(line)
        elif re.match(r"^[-*] ", stripped):
            if paragraph or code:
                flush()
            bullets.append(stripped[2:])
        elif bullets and line.startswith(" "):
            bullets[-1] += " " + stripped
        else:
            if code or bullets:
                flush()
            paragraph.append(line)
    flush()
    return "".join(out)


SECTION = re.compile(
    r"^(Args|Arguments|Parameters|Params|Keyword Args|Keyword Arguments|Kwargs|Returns|Return|Yields|"
    r"Raises|Example|Examples|Usage|Note|Notes|Warning|Warnings|See Also)\s*:\s*$"
)
PARAM = re.compile(r"^(\*{0,2}[A-Za-z_][\w.]*)\s*(?:\(([^)]*)\))?\s*:\s*(.*)$")


def render_params(lines: list[str]) -> str:
    entries: list[list[str]] = []
    for line in lines:
        if not line.strip():
            continue
        match = PARAM.match(line) if not line.startswith(" ") else None
        if match:
            entries.append([match.group(1), match.group(2) or "", match.group(3)])
        elif entries:
            entries[-1][2] += " " + line.strip()
        else:
            entries.append(["", "", line.strip()])
    items = []
    for name, kind, text in entries:
        term = f"<code>{html.escape(name)}</code>" if name else ""
        if kind:
            term += f' <span class="type">{html.escape(kind)}</span>'
        items.append(f"<dt>{term}</dt><dd>{inline(text.strip())}</dd>")
    return '<dl class="params">' + "".join(items) + "</dl>"


def render_docstring(doc: str) -> Markup:
    if not doc.strip():
        return Markup("")
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in doc.expandtabs().splitlines():
        match = SECTION.match(line) if not line.startswith(" ") else None
        if match:
            sections.append((match.group(1), []))
        else:
            sections[-1][1].append(line)
    out = []
    for name, lines in sections:
        lines = textwrap.dedent("\n".join(lines)).splitlines()
        if not any(l.strip() for l in lines):
            continue
        if name is None:
            out.append(render_prose(lines))
            continue
        label = {"Arguments": "Args", "Parameters": "Args", "Params": "Args", "Return": "Returns"}.get(name, name)
        out.append(f'<p class="docsec">{html.escape(label)}</p>')
        if name in ("Args", "Arguments", "Parameters", "Params", "Keyword Args", "Keyword Arguments", "Kwargs", "Raises"):
            out.append(render_params(lines))
        elif name in ("Example", "Examples", "Usage"):
            body = html.escape(textwrap.dedent("\n".join(lines)).strip("\n"))
            out.append(f"<pre><code>{body}</code></pre>")
        else:
            out.append(render_prose(lines))
    return Markup("".join(out))


def first_sentence(doc: str) -> str:
    paragraph = doc.strip().split("\n\n")[0]
    return " ".join(paragraph.split())


TOKENS = re.compile(r"\{\{\s*(\w+)\.(\w+)\s*\}\}")


def substitute(text: str, packages: dict[str, Package]) -> str:
    """Replace {{ library.version }}-style tokens; leave anything else alone."""

    def replace(match: re.Match) -> str:
        pkg = packages.get(match.group(1))
        value = getattr(pkg, match.group(2), None) if pkg else None
        return str(value) if isinstance(value, str) else match.group(0)

    return TOKENS.sub(replace, text)


def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta, body


def make_markdown() -> markdown.Markdown:
    return markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "attr_list", "md_in_html", "admonition", "codehilite", "sane_lists"],
        extension_configs={
            "codehilite": {"css_class": "hl", "guess_lang": False, "wrapcode": True},
            "toc": {"permalink": False, "toc_depth": "2-3"},
        },
        output_format="html",
    )


def polish(body: str) -> str:
    # Tables scroll on their own on narrow screens; admonitions read as callouts.
    body = body.replace("<table>", '<div class="table"><table>').replace("</table>", "</table></div>")
    body = body.replace('<div class="admonition', '<div class="callout admonition')
    # Fenced code blocks come out as <div class="hl"><pre>; keep one <pre> style everywhere.
    return re.sub(r'<div class="hl"><pre>(.*?)</pre></div>', r'<pre class="hl">\1</pre>', body, flags=re.S)


# ------------------------------------------------------------------- the site


@dataclass
class Page:
    slug: str
    url: str
    title: str
    nav_title: str
    description: str
    body: str = ""
    toc: list[dict] = field(default_factory=list)
    unreleased: str = ""
    source: str = ""
    meta: dict = field(default_factory=dict)


def page_url(slug_: str) -> str:
    return "/docs/" if slug_ == "index" else f"/docs/{slug_}/"


def build_reference(pkg: Package, settings: dict) -> tuple[str, list[dict]]:
    classes = []
    constants: dict[str, str] = {}
    for entry in pkg.cfg.get("api", []):
        classes += extract_api(pkg, entry["module"], entry.get("classes", []))
        constants.update(extract_constants(pkg, entry["module"], entry.get("constants", [])))

    out = [
        '<div class="callout"><p>',
        f'Generated from <a href="{pkg.pypi_url}{pkg.version}/"><code>{pkg.dist}</code> {pkg.version}</a>, ',
        "the latest release on PyPI. This page is rebuilt from the published wheel after every release, ",
        "so it always matches what <code>pip install</code> gives you.</p></div>",
    ]
    toc = []
    if constants:
        out.append('<h2 id="constants">Constants</h2><div class="table"><table><tr><th>Name</th><th>Value</th></tr>')
        for name, value in constants.items():
            out.append(f"<tr><td><code>{html.escape(name)}</code></td><td><code>{html.escape(value)}</code></td></tr>")
        out.append("</table></div>")
        toc.append({"id": "constants", "name": "Constants"})
    for cls in classes:
        toc.append({"id": cls.name, "name": cls.name})
        out.append(f'<h2 id="{cls.name}">{cls.name}</h2>')
        out.append(f'<p class="module"><code>from {cls.module} import {cls.name}</code></p>')
        out.append(render_docstring(cls.doc))
        out.append('<div class="chips">')
        for member in cls.members:
            out.append(f'<a href="#{cls.name}.{member.name}">{member.name}</a>')
        out.append("</div>")
        for member in cls.members:
            kind = f' <span class="kind">{member.kind}</span>' if member.kind else ""
            out.append(f'<h3 id="{cls.name}.{member.name}" class="member"><code>{member.name}</code>{kind}</h3>')
            out.append(f'<pre class="hl sig"><code>{highlight_python(member.signature)}</code></pre>')
            out.append(render_docstring(member.doc) or '<p class="muted">No description.</p>')
    if not classes:
        out.append(f"<p>No public classes were found in {pkg.dist} {pkg.version}.</p>")
    return "".join(out), toc


TYPE_LINK = re.compile(r"\b([A-Z]\w*Config)\b")


def build_config_reference(pkg: Package) -> tuple[str, list[dict]]:
    groups = []
    for entry in pkg.cfg.get("config", []):
        found = extract_config(pkg, entry["module"], entry["classes"])
        groups.append((entry, found))
    known = {cls.name for _, found in groups for cls in found}

    def type_html(annotation: str) -> str:
        escaped = html.escape(annotation)
        return TYPE_LINK.sub(lambda m: f'<a href="#{m.group(1)}">{m.group(1)}</a>' if m.group(1) in known else m.group(1), escaped)

    out = [
        '<div class="callout"><p>',
        f'Every field and default below is read from <a href="{pkg.pypi_url}{pkg.version}/"><code>{pkg.dist}</code> ',
        f"{pkg.version}</a> on PyPI and regenerated after each release. Pass any of these to ",
        "<code>Memory.from_config({...})</code> as nested dictionaries.</p></div>",
    ]
    toc = []
    missing = []
    for entry, found in groups:
        if not found:
            missing.append(entry["title"])
            continue
        anchor = slug(entry["title"])
        toc.append({"id": anchor, "name": entry["title"]})
        out.append(f'<h2 id="{anchor}">{html.escape(entry["title"])}</h2>')
        if entry.get("key"):
            out.append(f'<p class="module">Set under <code>{html.escape(entry["key"])}</code> in the config.</p>')
        for cls in found:
            out.append(f'<h3 id="{cls.name}"><code>{cls.name}</code></h3>')
            if cls.doc:
                out.append(f"<p>{inline(first_sentence(cls.doc))}</p>")
            out.append('<div class="table"><table><tr><th>Field</th><th>Type</th><th>Default</th><th>Description</th></tr>')
            for f in cls.fields:
                out.append(
                    f"<tr><td><code>{html.escape(f.name)}</code></td><td><code>{type_html(f.type)}</code></td>"
                    f"<td><code>{html.escape(f.default)}</code></td><td>{inline(' '.join(f.description.split()))}</td></tr>"
                )
            out.append("</table></div>")
    if missing:
        out.append('<h2 id="not-released">Not in this release</h2>')
        out.append(
            f"<p>These settings are documented in the guides but are not in {pkg.dist} {pkg.version} yet. "
            f"They will appear here after the release that ships them: {html.escape(', '.join(missing))}.</p>"
        )
        toc.append({"id": "not-released", "name": "Not in this release"})
    return "".join(out), toc


class Site:
    def __init__(self, offline: bool) -> None:
        self.config = tomllib.loads((ROOT / "site.toml").read_text())
        self.settings = self.config["site"]
        self.packages = {key: load_package(key, cfg, offline) for key, cfg in self.config["packages"].items()}
        self.env = Environment(
            loader=FileSystemLoader(ROOT / "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["python"] = highlight_python
        self.asset_version = hashlib.sha256(
            b"".join(p.read_bytes() for p in sorted((ROOT / "static").glob("*")))
        ).hexdigest()[:10]
        self.pages: dict[str, Page] = {}
        self.written: dict[str, str] = {}

    # ---- pages

    def load_pages(self) -> None:
        generated = {
            "reference/library": ("library", "Library API", "Library API reference"),
            "reference/sdk": ("sdk", "Cloud SDK API", "Cloud SDK API reference"),
        }
        for section in self.config["nav"]:
            for slug_ in section["pages"]:
                if slug_ in generated:
                    key, nav_title, title = generated[slug_]
                    pkg = self.packages[key]
                    body, toc = build_reference(pkg, self.settings)
                    self.pages[slug_] = Page(
                        slug_, page_url(slug_), title, nav_title,
                        f"Every public class and method in {pkg.dist} {pkg.version}, generated from the release on PyPI.",
                        body, toc,
                    )
                elif slug_ == "reference/config":
                    pkg = self.packages["library"]
                    body, toc = build_config_reference(pkg)
                    self.pages[slug_] = Page(
                        slug_, page_url(slug_), "Configuration reference", "Configuration",
                        f"Every MemoryConfig field and default in {pkg.dist} {pkg.version}, generated from the release on PyPI.",
                        body, toc,
                    )
                else:
                    self.pages[slug_] = self.load_markdown(slug_)

    def load_markdown(self, slug_: str) -> Page:
        path = CONTENT / "docs" / f"{slug_}.md"
        meta, text = parse_front_matter(path.read_text())
        text = substitute(text, self.packages)
        md = make_markdown()
        body = polish(md.convert(text))
        toc = [{"id": t["id"], "name": t["name"]} for t in md.toc_tokens if t["level"] == 2]
        page = Page(
            slug_, page_url(slug_), meta["title"], meta.get("nav", meta["title"]), meta.get("description", ""),
            body, toc, source=str(path.relative_to(ROOT)), meta=meta,
        )
        requires = meta.get("requires")
        if requires and not requirement_met(self.packages, requires):
            pkg = next(p for p in self.packages.values() if requires.split(".")[0] == p.import_name)
            page.unreleased = f"{pkg.dist} {pkg.version}"
        return page

    def nav(self, current: str) -> list[dict]:
        sections = []
        for section in self.config["nav"]:
            items = []
            for slug_ in section["pages"]:
                page = self.pages[slug_]
                if page.unreleased and not self.settings.get("show_unreleased", True):
                    continue
                items.append({"page": page, "current": slug_ == current})
            if items:
                sections.append({"title": section["section"], "items": items})
        return sections

    def neighbours(self, current: str) -> tuple[Page | None, Page | None]:
        order = [p for p in (item["page"] for s in self.nav(current) for item in s["items"])]
        index = next(i for i, p in enumerate(order) if p.slug == current)
        return (order[index - 1] if index else None, order[index + 1] if index + 1 < len(order) else None)

    # ---- output

    def context(self, **extra) -> dict:
        return {
            "site": self.settings,
            "packages": self.packages,
            "library": self.packages["library"],
            "sdk": self.packages["sdk"],
            "asset_version": self.asset_version,
            "year": dt.date.today().year,
            **extra,
        }

    def write(self, url: str, template: str, **extra) -> None:
        html_text = self.env.get_template(template).render(self.context(path=url, **extra))
        target = OUT / url.lstrip("/") / "index.html" if url.endswith("/") else OUT / url.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text)
        self.written[url] = html_text

    def build(self) -> None:
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir()
        shutil.copytree(ROOT / "static", OUT / "static")
        self.load_pages()

        self.write(
            "/", "home.html",
            quickstart=(CONTENT / "snippets" / "quickstart.py").read_text().strip(),
            unreleased={
                slug_: self.pages[slug_].unreleased
                for slug_ in ("context-graph", "personalized-retrieval", "tenants", "decay-and-versioning")
            },
        )
        for slug_, page in self.pages.items():
            if page.unreleased and not self.settings.get("show_unreleased", True):
                continue
            previous, following = self.neighbours(slug_)
            self.write(
                page.url, "doc.html", page=page, nav=self.nav(slug_), previous=previous, following=following,
                body=Markup(page.body),
            )
        self.write("/changelog/", "changelog.html", releases=self.changelog())
        self.write("/404.html", "404.html")
        self.write_extras()

    def changelog(self) -> list[dict]:
        rows = []
        for pkg in self.packages.values():
            for release in pkg.releases:
                notes = polish(make_markdown().convert(release.notes)) if release.notes else ""
                rows.append({"pkg": pkg, "release": release, "notes": Markup(notes), "id": f"{pkg.key}-{release.version}"})
        rows.sort(key=lambda r: (r["release"].date, sort_key(r["release"].version)), reverse=True)
        return rows

    def write_extras(self) -> None:
        base = self.settings["base_url"].rstrip("/")
        (OUT / "CNAME").write_text(base.split("://", 1)[1] + "\n")
        (OUT / ".nojekyll").write_text("")
        (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
        urls = [u for u in self.written if u.endswith("/")]
        sitemap = "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls)
        (OUT / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap}</urlset>\n'
        )
        (OUT / "release.json").write_text(json.dumps(release_manifest(self.packages), indent=2) + "\n")

    # ---- checks

    def check(self) -> list[str]:
        """Broken internal links and Python blocks that do not parse fail the build."""
        problems = []
        ids = {url: set(re.findall(r'\sid="([^"]+)"', text)) for url, text in self.written.items()}
        for url, text in self.written.items():
            for href in re.findall(r'href="(/[^"]*)"', text):
                path, _, anchor = href.partition("#")
                path = path.split("?")[0]
                if path.startswith("/static/") or path in ("/release.json", "/sitemap.xml"):
                    if not (OUT / path.lstrip("/")).exists():
                        problems.append(f"{url}: missing file {href}")
                    continue
                if path not in ids:
                    problems.append(f"{url}: broken link {href}")
                elif anchor and anchor not in ids[path]:
                    problems.append(f"{url}: missing anchor {href}")
            for anchor in re.findall(r'href="#([^"]+)"', text):
                if anchor not in ids[url]:
                    problems.append(f"{url}: missing anchor #{anchor}")
        for path in sorted((CONTENT / "docs").rglob("*.md")):
            for index, block in enumerate(re.findall(r"```python\n(.*?)```", path.read_text(), re.S)):
                try:
                    ast.parse(block)
                except SyntaxError as err:
                    problems.append(f"{path.relative_to(ROOT)}: python block {index + 1} line {err.lineno}: {err.msg}")
        for path in sorted((CONTENT / "snippets").glob("*.py")):
            try:
                ast.parse(path.read_text())
            except SyntaxError as err:
                problems.append(f"{path.relative_to(ROOT)} line {err.lineno}: {err.msg}")
        return problems


def release_manifest(packages: dict[str, Package]) -> dict:
    return {
        "packages": {
            key: {"dist": p.dist, "version": p.version, "released": p.released, "pypi": p.pypi_url}
            for key, p in packages.items()
        }
    }


# ------------------------------------------------------------------------- CLI


def check_live(offline: bool) -> None:
    """Say whether a scheduled run has anything to publish."""
    config = tomllib.loads((ROOT / "site.toml").read_text())
    current = {key: pypi_json(cfg["dist"], offline)["info"]["version"] for key, cfg in config["packages"].items()}
    try:
        live = json.loads(http_get(config["site"]["base_url"].rstrip("/") + "/release.json", attempts=2))
        deployed = {key: value["version"] for key, value in live["packages"].items()}
    except Exception as err:  # the site is down, new, or moved: rebuild
        print(f"could not read the live release.json ({err})")
        deployed = {}
    changed = current != deployed
    print(f"PyPI: {current}\nlive: {deployed}\nchanged={'true' if changed else 'false'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"changed={'true' if changed else 'false'}\n")


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    print(f"Serving {OUT} on http://localhost:{port}")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use .cache/ instead of calling PyPI")
    parser.add_argument("--serve", action="store_true", help="serve _site/ after building")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check-live", action="store_true", help="compare PyPI with the deployed site")
    args = parser.parse_args()

    if args.check_live:
        check_live(args.offline)
        return

    started = time.time()
    site = Site(args.offline)
    site.build()
    problems = site.check()
    for pkg in site.packages.values():
        print(f"{pkg.dist} {pkg.version} ({pkg.released}), {len(pkg.releases)} releases")
    unreleased = [p.slug for p in site.pages.values() if p.unreleased]
    if unreleased:
        print(f"not in the latest release yet: {', '.join(unreleased)}")
    print(f"built {len(site.written)} pages into {OUT.relative_to(ROOT)}/ in {time.time() - started:.1f}s")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(f"{len(problems)} problem(s)")
    if args.serve:
        serve(args.port)


if __name__ == "__main__":
    main()

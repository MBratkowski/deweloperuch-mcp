"""The images and the homepage that published copies of the project point at.

- PyPI and GitHub keep the README of every release. Released READMEs link
  ``assets/icon.svg`` by an absolute URL on ``main`` (since 0.1.1), and README.md, which
  every release publishes, links ``assets/icon-on-light.png`` and ``assets/icon-on-dark.png``
  the same way: those files stay where they are and stay images, whatever README.md links
  later. Every raw URL of this repository in README.md is one of them, on ``main``.
- ``make icons`` writes exactly ``assets/icons/icon-<N>.png`` (the extension's build ships
  every PNG there), each N x N pixels as ``packaging/mcpb/build.py`` reads the PNG header for
  the bundle's ``icons`` sizes; it copies ``icon-512.png`` to ``icon.png`` and the
  hand-drawn ``icon-tiny.png`` to ``icon-16.png``, and wraps ``icon.png`` in ``icon.svg``.
- The homepage is one URL in every manifest that names it.

Offline: only files of the repository are read.
"""

import base64
import filecmp
import functools
import json
import re
import runpy
import tomllib
from pathlib import Path
from typing import Any

import pytest

from support.paths import PACKAGING, PLUGIN_MANIFESTS, REPO

ASSETS = REPO / "assets"
TOKEN = re.compile(r"[^\s\"'()<>`]+")
"""A run of text without spaces, quotes, brackets or backticks: where a URL ends in HTML,
Markdown and code spans."""
OF_THIS_REPOSITORY = re.compile(
    r"(?i)raw\.githubusercontent\.com/MBratkowski/deweloperuch-mcp/"
    r"|github\.com/MBratkowski/deweloperuch-mcp/raw/"
)
"""A raw link to a file of this repository in either form, ``raw.githubusercontent.com/...``
or ``github.com/.../raw/``, on any branch or tag. Not seen: ``github.com/.../blob/...?raw=true``
and CDN mirrors (jsDelivr)."""
RAW_ON_MAIN = re.compile(
    r"https://raw\.githubusercontent\.com/(?i:MBratkowski/deweloperuch-mcp)/(?:refs/heads/)?main/"
    r"([^\s\"'()<>?#]+)"
)
"""A raw URL of a file on ``main``; the group is the file's path in the repository (GitHub
ignores the case of the owner and the repository, not of the path)."""
PUBLISHED = ("assets/icon.svg", "assets/icon-on-light.png", "assets/icon-on-dark.png")
"""Linked by absolute URLs on ``main`` from released READMEs (``icon.svg`` since 0.1.1) and
from README.md, which every release publishes (``icon-on-*.png``)."""
ICON_SIZES = (16, 32, 64, 128, 256, 512)
COPIES = [
    ("icon.png", "icons/icon-512.png"),  # the bundle's `icon`, for hosts without `icons`
    ("icons/icon-16.png", "icon-tiny.png"),  # drawn by hand, not rendered from the source
]
"""``make icons``: (the copy, its original), both under ``assets/``."""


def json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@functools.cache
def build_script() -> dict[str, Any]:
    """``packaging/mcpb/build.py`` run once as a module (not ``__main__``: nothing is built),
    on first use, so a broken script fails only the tests that use it. Its ``png_size``
    reads width and height from the PNG header and stops on anything else."""
    return runpy.run_path(str(PACKAGING / "mcpb" / "build.py"), run_name="build")


def test_the_readme_links_by_raw_url_only_published_files_on_main() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    urls = [token for token in TOKEN.findall(readme) if OF_THIS_REPOSITORY.search(token)]
    matches = [RAW_ON_MAIN.fullmatch(url) for url in urls]
    linked = sorted({match[1] for match in matches if match})
    unread = [url for url, match in zip(urls, matches, strict=True) if not match]

    assert linked, "no raw URL of a file on main found in README.md: are the patterns right?"
    assert unread == [], (
        "README.md links files of this repository in a form RAW_ON_MAIN does not read; "
        "use https://raw.githubusercontent.com/MBratkowski/deweloperuch-mcp/main/<path>"
    )
    assert [path for path in linked if not (REPO / path).is_file()] == [], (
        "README.md links files missing from the repository; released READMEs keep linking main"
    )
    assert set(linked) <= set(PUBLISHED), (
        "every release publishes README.md: add the file to PUBLISHED (and CONTRIBUTING.md)"
    )


@pytest.mark.parametrize("path", PUBLISHED)
def test_the_images_published_readmes_link_are_kept(path: str) -> None:
    assert (REPO / path).is_file(), f"published READMEs link {path}: never rename or delete it"


@pytest.mark.parametrize("path", [path for path in PUBLISHED if path.endswith(".png")])
def test_the_published_png_images_are_png_files(path: str) -> None:
    width, height = build_script()["png_size"](REPO / path)

    assert width > 0 and height > 0


def test_the_svg_icon_wraps_the_png_icon() -> None:
    embedded = base64.b64encode((ASSETS / "icon.png").read_bytes()).decode("ascii")
    # A bool first: on failure pytest would print both texts (about 130 kB).
    wraps = embedded in (ASSETS / "icon.svg").read_text(encoding="utf-8")

    assert wraps, "assets/icon.svg must embed assets/icon.png: run `make icons`"


def test_the_extension_icons_are_exactly_one_per_size() -> None:
    # The glob of packaging/mcpb/build.py.
    shipped = sorted(path.name for path in (ASSETS / "icons").glob("*.png"))

    assert shipped == sorted(f"icon-{size}.png" for size in ICON_SIZES), (
        "packaging/mcpb/build.py ships every PNG in assets/icons: run `make icons` "
        "or update ICON_SIZES"
    )


@pytest.mark.parametrize("size", ICON_SIZES, ids=[f"icon-{size}" for size in ICON_SIZES])
def test_every_extension_icon_is_square_at_its_size(size: int) -> None:
    size_read = build_script()["png_size"](ASSETS / "icons" / f"icon-{size}.png")

    assert size_read == (size, size), "run `make icons`"


@pytest.mark.parametrize(("copy", "original"), COPIES, ids=[copy for copy, _ in COPIES])
def test_the_copies_make_icons_writes_equal_their_originals(copy: str, original: str) -> None:
    # filecmp, not read_bytes(): pytest -v would diff the bytes as text for minutes.
    same = filecmp.cmp(ASSETS / copy, ASSETS / original, shallow=False)

    assert same, f"{copy} is not a copy of {original}: run `make icons`"


def test_the_homepage_is_one_url_in_every_manifest() -> None:
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    plugins = json_file(PLUGIN_MANIFESTS / "marketplace.json")["plugins"]
    # Not packaging/registry/server.json: its websiteUrl is the English documentation
    # (docs/mcp/README.md) on purpose, not the homepage.
    homepages = {
        "pyproject.toml": project["project"]["urls"]["Homepage"],
        "packaging/mcpb/manifest.json": json_file(PACKAGING / "mcpb" / "manifest.json")["homepage"],
        ".claude-plugin/plugin.json": json_file(PLUGIN_MANIFESTS / "plugin.json")["homepage"],
        **{
            f".claude-plugin/marketplace.json plugins[{index}]": plugin["homepage"]
            for index, plugin in enumerate(plugins)
        },
    }
    urls = set(homepages.values())

    assert len(urls) == 1, f"one homepage everywhere: {homepages}"

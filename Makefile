# Quality gates and packaging. No target sends a request to the service (the live e2e
# suite is a separate, opt-in run; see CONTRIBUTING.md and docs/decisions.md D10). The
# quality gates are offline; package, mcpb and smoke fetch tools and dependencies from
# npm and PyPI.

.PHONY: fast check lint format-check types imports test dead complexity duplicates \
	package mcpb smoke icons skill

## fast: what to run before every hand-over (a few seconds)
fast: lint format-check types imports

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

types:
	uv run mypy src tests recon packaging .github/scripts

imports:
	uv run lint-imports

## check: fast + the offline tests + dead code + reports (complexity, duplication)
check: fast test dead complexity duplicates

# DEWELOPERUCH_LIVE is dropped so tests/e2e stays skipped whatever the shell has set.
test:
	env -u DEWELOPERUCH_LIVE uv run pytest -q

# Unused code at 80% confidence; the whitelist is [tool.vulture] in pyproject.toml.
dead:
	uv run vulture

# Report, not a gate (stage 2 gates it): blocks above rank B (radon cyclomatic
# complexity, which also counts boolean operators), modules above A.
complexity:
	@echo "== complexity report: blocks ranked C or worse (not a gate yet)"
	-@uv run xenon --max-absolute B --max-modules A --max-average A src recon

# Report, not a gate (stage 3 gates it): similar blocks of at least 4 lines.
duplicates:
	@echo "== duplicate-code report (not a gate yet)"
	@uv run pylint --disable=all --enable=duplicate-code --exit-zero --score=n src recon

## package: the wheel, the sdist and the Claude Desktop extension (.mcpb) in dist/
package:
	uv build --clear
	uv run python packaging/mcpb/build.py

## mcpb: only the extension, dist/deweloperuch-mcp-<version>.mcpb (needs Node.js for npx)
mcpb:
	uv run python packaging/mcpb/build.py

## icons: the images in assets/ (committed) from the official raster assets/icon-source.webp;
## needs ImageMagick 7 (`magick`) with WebP support. The extension's icons are white rounded
## tiles; at 32 and 64 px the strokes grow (erosion kernel) before downscaling and the
## contrast rises so they stay legible; from 128 px the kernel is Unity and the contrast 0,
## which both mean none (Disk:0 is not a no-op: it falls back to the default disk). The
## 16 px one is hand-drawn (assets/icon-tiny.png). icon-on-light.png and icon-on-dark.png are
## transparent, with dark and light ink, for the README; icon.svg only wraps icon.png. The
## published READMEs link icon-on-*.png and icon.svg by absolute URLs: never rename or
## delete them.
INK = magick assets/icon-source.webp -colorspace gray -level 15%,85% -trim +repage
icons:
	for spec in "32 28 Disk:6 5" "64 54 Disk:4 4" "128 102 Unity 0" "256 205 Unity 0" \
			"512 410 Unity 0"; do \
		set -- $$spec; edge=$$(($$1 - 1)); radius=$$(($$1 * 22 / 100)); \
		$(INK) -morphology Erode $$3 -filter Mitchell -resize x$$2 \
			-sigmoidal-contrast $$4x50% -background white -gravity center -extent $$1x$$1 \
			\( -size $$1x$$1 xc:black -fill white \
				-draw "roundrectangle 0,0 $$edge,$$edge $$radius,$$radius" \) \
			-alpha off -compose CopyOpacity -composite -strip PNG32:assets/icons/icon-$$1.png \
			|| exit 1; \
	done
	cp assets/icon-tiny.png assets/icons/icon-16.png
	cp assets/icons/icon-512.png assets/icon.png
	$(INK) -resize x474 -negate -background black -alpha shape -bordercolor none -border 19 \
		-strip PNG32:assets/icon-on-light.png
	$(INK) -resize x474 -negate -background white -alpha shape -bordercolor none -border 19 \
		-strip PNG32:assets/icon-on-dark.png
	b64=$$(base64 < assets/icon.png | tr -d '\n') && test -n "$$b64" || exit 1; \
	{ printf '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"'; \
		printf ' width="512" height="512"><title>deweloperuch-mcp</title>'; \
		printf '<image width="512" height="512" href="data:image/png;base64,'; \
		printf '%s' "$$b64"; printf '"/></svg>\n'; } > assets/icon.svg

## skill: the agent skill's skills/deweloperuch-cli/REFERENCE.md, generated from the CLI
## (tests/skill fails while it is out of date); SKILL.md and EXAMPLES.md are written by hand
skill:
	uv run python packaging/skill_reference.py

## smoke: start the built wheel and the unpacked extension as an MCP client does
## (initialize + tools/list, no tool call, so no request to the service), and install the
## wheel's agent skill into build/ (it must equal skills/); run `package` first
WHEEL = dist/deweloperuch_mcp-$(shell uv version --short)-py3-none-any.whl
smoke:
	uv run python packaging/smoke.py -- \
		uvx --isolated --refresh-package deweloperuch-mcp --from $(WHEEL) deweloperuch-mcp
	uvx --isolated --from $(WHEEL) deweloperuch --help > /dev/null
	rm -rf build/skill-smoke
	uvx --isolated --from $(WHEEL) deweloperuch skill install --dir build/skill-smoke > /dev/null
	diff -r -x .DS_Store skills/deweloperuch-cli build/skill-smoke/deweloperuch-cli
	uv run python packaging/smoke.py -- uv run --directory build/mcpb-unpacked src/server.py

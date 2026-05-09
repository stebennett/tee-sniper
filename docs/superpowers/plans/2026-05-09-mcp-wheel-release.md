# MCP Server Wheel Release Plan

**Goal:** On every existing `v*.*.*` git tag, build `tee-sniper-mcp` as a Python
wheel + sdist and attach the artefacts to the GitHub Release. MetaMCP and other
clients install with `uv tool install` / `uvx` directly from the private-repo
Release URL using a GitHub PAT, no separate index required.

**Spec source:** answers to plan-clarification questions on
`claude/plan-mcp-release-zPj8d`:

- Format: Python wheel + sdist (no separate Docker release; existing GHCR build
  in `release.yml` stays untouched).
- Hosting: GitHub Releases (private repo, PAT-gated download).
- Versioning: reuse existing `v*.*.*` tag — extend `release.yml`, do **not**
  create an MCP-specific tag scheme.

## Existing state (do not re-do)

- `.github/workflows/release.yml` already runs on `v*.*.*`, creates the GitHub
  Release, uploads the Go binary, and pushes three GHCR images
  (`-`, `-api`, `-mcp`).
- `mcp/pyproject.toml` uses hatchling with hardcoded `version = "0.1.0"`.
- `mcp/Dockerfile` does `pip install .` from the source tree — version drift
  there is invisible until released.
- `.github/workflows/mcp-build.yml` runs `pytest` and a Docker build on PRs but
  does **not** build the wheel.

## Phase / PR workflow

Per `CLAUDE.md`, each phase ships in its own PR. Phase 1 must merge before 2,
3, and 4 — they all depend on dynamic versioning. Phases 2 and 3 are
independent of each other; 4 depends on 3 having shipped at least one Release
asset to point users at.

---

## Phase 1 — Dynamic versioning from git tag

**Branch:** `mcp/release-phase1-dynamic-version`
**Why:** the wheel filename and `tee_sniper_mcp.__version__` must reflect the
tag the workflow is building, without manual `pyproject.toml` edits per
release.

### Tasks

- [ ] **1.1 Add `hatch-vcs` to the build backend.** In `mcp/pyproject.toml`:
  - `[build-system].requires` becomes `["hatchling", "hatch-vcs"]`.
  - Replace `version = "0.1.0"` with `dynamic = ["version"]`.
  - Add:
    ```toml
    [tool.hatch.version]
    source = "vcs"
    raw-options = { root = "..", tag-pattern = "^v(?P<version>\\d+\\.\\d+\\.\\d+)$" }

    [tool.hatch.build.hooks.vcs]
    version-file = "src/tee_sniper_mcp/_version.py"
    ```
    `root = ".."` is required because `hatch-vcs` runs from `mcp/` but the
    git repo root is one level up. The tag pattern only matches the existing
    `v*.*.*` shape so unrelated tags (e.g. `mcp-vX.Y.Z`, RC tags) cannot
    accidentally drive the version.
- [ ] **1.2 Generated version file.** Add `src/tee_sniper_mcp/_version.py` to
  `.gitignore` (the file is generated at build time). Update
  `src/tee_sniper_mcp/__init__.py` to do
  `from ._version import __version__` inside a try/except that falls back to
  `"0.0.0+unknown"` when the file is absent (editable installs without a
  build).
- [ ] **1.3 Verify locally.**
  - `cd mcp && uv build` — expect a `dist/tee_sniper_mcp-<dev-version>.tar.gz`
    and matching `.whl`. Untagged HEAD should produce a PEP 440 dev version
    like `0.1.0.dev3+g<sha>` (whatever the most recent matching tag is, plus
    commit count).
  - `uv run pytest -v` — must still pass.
- [ ] **1.4 Update `mcp/Dockerfile` if needed.** `pip install .` requires git
  history to be present in the build context for `hatch-vcs` to resolve the
  version. The repo `.dockerignore` (verify; add one in `mcp/` if missing
  that does NOT exclude `.git`) and the `docker build context` must include
  `.git`. Easiest fix: change the GHCR Docker build in `release.yml` and
  `mcp-build.yml` to use the **repo root** as build context with
  `file: mcp/Dockerfile`, so `.git/` is available; update the Dockerfile
  `COPY` paths to `mcp/pyproject.toml`, `mcp/README.md`, `mcp/src`. Confirm
  `docker build -f mcp/Dockerfile .` succeeds locally and the resulting
  image's `tee-sniper-mcp` reports a non-`0.0.0+unknown` version (add a
  trivial `--version` flag if there isn't one — see 1.5).
- [ ] **1.5 Optional but recommended: `--version` CLI flag.** Add a
  `--version` argument to the `tee-sniper-mcp` entry point (`server.main`)
  that prints `tee_sniper_mcp.__version__` and exits 0. Lets CI smoke-test the
  installed wheel without importing.
- [ ] **1.6 Commit + PR.** Single commit; PR title:
  `mcp: derive package version from git tag via hatch-vcs`.

### Risks / things to double-check

- **`tag-pattern` regex.** Must use an actual regex (Python `re`), not a glob.
  Test by tagging a throwaway commit `git tag v9.9.9 && cd mcp && uv build`
  and confirming the wheel is named `tee_sniper_mcp-9.9.9-…`. Delete the tag
  after.
- **Dirty working tree.** `hatch-vcs` appends `.dirty` to versions built off a
  dirty tree, which breaks PEP 440 wheel filenames in some toolchains. The
  release workflow checks out a clean tag commit, so this is fine; just
  document it for local dev.

---

## Phase 2 — CI wheel build on PRs

**Branch:** `mcp/release-phase2-ci-wheel-smoke`
**Why:** catch packaging regressions (missing files, broken
`hatch-vcs` config) on every PR, before tagging.

### Tasks

- [ ] **2.1 Extend `.github/workflows/mcp-build.yml`.** Add a `wheel` job that
  `needs: test` and runs after the existing test job:
  - `actions/checkout@v6` with `fetch-depth: 0` and `fetch-tags: true` so
    `hatch-vcs` can resolve a version. Untagged main builds will produce a
    dev version — that is fine, we only assert that build succeeds.
  - `astral-sh/setup-uv@v3` + `actions/setup-python@v6` (3.14) as in the
    existing `test` job.
  - `cd mcp && uv build`.
  - Smoke-install: create a fresh venv, `uv pip install dist/*.whl`, run
    `tee-sniper-mcp --version` (depends on 1.5; otherwise `python -c "import
    tee_sniper_mcp; print(tee_sniper_mcp.__version__)"`).
  - `actions/upload-artifact@v4` to retain the wheel + sdist for 7 days for
    debugging — name `mcp-dist-${{ github.sha }}`.
- [ ] **2.2 Verify the workflow on the PR itself.** The PR adding the job
  should also exercise it. If the smoke step fails, fix Phase 1 issues
  before merging.

---

## Phase 3 — Attach wheel + sdist to GitHub Release

**Branch:** `mcp/release-phase3-release-artefacts`
**Why:** the actual user-visible deliverable.

### Tasks

- [ ] **3.1 Patch `.github/workflows/release.yml`.**
  - On the existing checkout step add `fetch-depth: 0` and
    `fetch-tags: true` (required for `hatch-vcs` and a no-op for the Go
    build).
  - After `Set up Go` (or in a parallel preparatory block — order does not
    matter as long as it runs before the upload steps) add:
    - `actions/setup-python@v6` with `python-version: '3.14'`.
    - `astral-sh/setup-uv@v3`.
    - `Build MCP wheel + sdist`: `cd mcp && uv build`.
  - Add two new `actions/upload-release-asset@v1` steps after the existing
    "Upload Linux Binary" step, one for the wheel (`./mcp/dist/*.whl`) and
    one for the sdist (`./mcp/dist/*.tar.gz`). Use a glob-resolving shell
    step first to capture exact filenames into outputs (the deprecated
    action does not glob):
    ```yaml
    - name: Resolve MCP artefact paths
      id: mcp_artefacts
      run: |
        echo "wheel=$(ls mcp/dist/*.whl)" >> "$GITHUB_OUTPUT"
        echo "sdist=$(ls mcp/dist/*.tar.gz)" >> "$GITHUB_OUTPUT"
        echo "wheel_name=$(basename mcp/dist/*.whl)" >> "$GITHUB_OUTPUT"
        echo "sdist_name=$(basename mcp/dist/*.tar.gz)" >> "$GITHUB_OUTPUT"
    ```
  - Use the `upload_url` from the existing `create_release` step for both
    uploads. `asset_content_type`: `application/zip` for the wheel,
    `application/gzip` for the sdist.
- [ ] **3.2 Sanity-check the version against the tag.** Add a small step
  before upload:
  ```yaml
  - name: Verify wheel version matches tag
    run: |
      tag="${GITHUB_REF#refs/tags/v}"
      whl=$(ls mcp/dist/*.whl)
      case "$whl" in
        *tee_sniper_mcp-${tag}-*) echo "ok: $whl";;
        *) echo "wheel $whl does not match tag $tag"; exit 1;;
      esac
  ```
  Catches `hatch-vcs` mis-configuration the moment we tag, instead of
  shipping a wrongly-named wheel.
- [ ] **3.3 Test before tagging.** Verify on a throwaway branch via
  `workflow_dispatch` (temporarily add `workflow_dispatch:` to the trigger
  block on the test branch only — do **not** merge that), or push a
  pre-release tag like `v0.1.0-test1` and confirm the wheel + sdist appear on
  the resulting Release. Delete the test tag and Release after.
  - **Note on the deprecation:** `actions/create-release@v1` and
    `actions/upload-release-asset@v1` are unmaintained but still functional.
    Migrating to `softprops/action-gh-release@v2` is **out of scope** —
    captured in "Follow-ups" below.

---

## Phase 4 — Install docs for MetaMCP

**Branch:** `mcp/release-phase4-docs`
**Why:** users need to know the install command, and that they need a PAT.

### Tasks

- [ ] **4.1 Add "Install from GitHub Releases" section to `mcp/README.md`,
  immediately after the existing "Running" section.** Cover:
  - PAT requirement: GitHub PAT with `repo` scope (classic) or a fine-grained
    PAT with `Contents: Read` on this repo. Private-repo Release assets are
    PAT-gated.
  - `uv tool install` against the asset URL using a token:
    ```bash
    uv tool install \
      "https://${GH_TOKEN}@github.com/<owner>/tee-sniper/releases/download/v<X.Y.Z>/tee_sniper_mcp-<X.Y.Z>-py3-none-any.whl"
    tee-sniper-mcp --version
    ```
  - One-shot via `uvx --from <url> tee-sniper-mcp` (no install).
- [ ] **4.2 Update the "MetaMCP config" snippet in `mcp/README.md`.** Add a
  second example using `uvx --from <wheel-url>` alongside the existing
  Docker example, so MetaMCP installs that prefer a Python entry point can
  use it. Make the PAT requirement explicit in the snippet's environment
  block.
- [ ] **4.3 Update `CLAUDE.md` MCP section.** One sentence noting that wheel
  + sdist are attached to each `v*.*.*` GitHub Release alongside the Docker
  image. Do **not** duplicate the install instructions — link to
  `mcp/README.md`.
- [ ] **4.4 No code changes.** Pure docs PR.

---

## Out of scope / follow-ups

- Migrating `release.yml` from `actions/create-release@v1` +
  `actions/upload-release-asset@v1` (both deprecated) to
  `softprops/action-gh-release@v2`. Worth doing for the whole workflow at once
  rather than piecemeal — track separately.
- Publishing to a private PyPI-style index (CodeArtifact, Gemfury, self-hosted
  devpi). Not needed unless we outgrow Release-asset distribution.
- Signing wheels (PEP 740 / Sigstore).
- Bumping the existing `0.1.0` baseline to `0.2.0` to mark the first
  Release-shipped version cleanly. Cosmetic; decide at release time.

## Verification checklist (run before declaring "shipped")

- [ ] `cd mcp && uv build` on a clean checkout of the tag produces wheel and
  sdist named `tee_sniper_mcp-<tag without v>.*`.
- [ ] `uv tool install <wheel-url-with-token>` followed by
  `tee-sniper-mcp --version` prints the tag's version.
- [ ] `uvx --from <wheel-url-with-token> tee-sniper-mcp --help` works without
  a prior install.
- [ ] The Release page shows three new assets in addition to the Go binary:
  the wheel, the sdist, and (unchanged) the Linux Go binary; GHCR shows the
  three Docker tags as before.
- [ ] `mcp-build.yml` wheel job is green on a non-tag PR (i.e. dev versioning
  works).

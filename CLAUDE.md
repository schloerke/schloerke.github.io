# schloerke.github.io

Personal site for Barret Schloerke, served by GitHub Pages at schloerke.com (`CNAME`).
Other repos under `schloerke/` are served as `schloerke.com/<repo>/` (e.g. talk slides).

**Keep this file current.** When you add a feature, data source, script, make target,
or change an approach below, update this file in the same change.

## Design

- Simple like hadley.nz: one column, plain prose, system fonts, no framework.
- Data-rich like samuelbharti.com: stats and small charts, all driven by `data.json`.
- No build step for the page. `index.html` holds all markup, CSS, and JS.
- Colors are CSS custom properties in `:root` using `light-dark()`. They follow the system
  by default; the button in the page's top-right corner cycles system (◐) → light (☀) → dark (☾), setting `data-theme` on `<html>` and saves it in `localStorage.theme`.
  Link/accent blue must stay **WCAG AAA (≥ 7:1)** against `--bg` in both modes.
  Current ratios are noted in comments next to the variables. Recheck them when changing colors.
- Charts follow the dataviz skill: one hue, thin 2px lines, a hover tooltip on every mark
  (shared `#tip`, driven by `data-tip`), each sparkline scaled to itself.

## Data pipeline

`scripts/build_data.py` (stdlib only, run with `uv`) writes `data.json`:

- `merged_prs` / `repos`: GitHub search for merged PRs by schloerke, one query per year
  (search caps results at 1000).
- `packages`: repos with ≥ `MIN_PRS` merged PRs that contain an R package (`DESCRIPTION`,
  `pkg-r/DESCRIPTION`), a Python package (`pyproject.toml`, `pkg-py/pyproject.toml`, `setup.cfg`),
  or a TypeScript package (non-private `package.json` / `pkg-js/package.json` that mentions `typescript`).
  Monthly downloads for the last 6 full months come from cranlogs (R), pypistats (Python), or npm.
  `role` is maintainer / author / contributor: R `cre` / `aut` in `Authors@R`, Python
  `maintainers` / `authors`, npm `maintainers` / `author`. Every package in a repo gets the
  strongest role found in any of its manifests (e.g. shinyreact's `cre` in R covers its npm package).
  Hand overrides live at the top of the script: `HIDE` (repos to leave out, e.g. react-ace) and
  `ROLE` (a minimum role when the manifests don't list you, e.g. py-shiny → author).
  6 months because pypistats keeps only 180 days. A package counts as published if it has
  any downloads in that window, including the current month, so new releases show as "new".
  `reviews` per package: search count of `reviewed-by:schloerke -author:schloerke` in that repo.
  `feedstock` is the `conda-forge/<name>-feedstock` repo for Python packages, if one exists
  (`py-<name>`, then `<name>`). R packages are skipped on purpose. The table shows it as an anvil icon (Simple Icons, CC0).
- `other`: every other public repo with ≥ `MIN_PRS` merged PRs (not a listed package's repo,
  not a talk), with its GitHub description. Private repos are skipped so their names stay off the site,
  and forks (e.g. `schloerke/leaflet`) are skipped. `HIDE_OTHER` hand-lists repos to leave out.
- `contributions`: GitHub GraphQL contribution calendar (needs a token).
- `talks`: `schloerke/presentation-*` and `workshop-*` repos. The date comes from the repo
  name. The title is the repo description, then the README's first `# ` heading, then the name
  slug. Markdown and HTML are stripped out.

cranlogs and pypistats don't send CORS headers, which is why the data is fetched at build time
rather than in the browser. `.github/workflows/data.yml` runs `make data` nightly and commits
`data.json`. Its `keepalive` job re-enables the workflow via the API each run, because GitHub
disables scheduled workflows after 60 days without non-bot activity. The job fails after a
hard-coded date on purpose; bump it yearly.

## Commands

```sh
make data    # rebuild data.json (uses `gh auth token` if GITHUB_TOKEN is unset)
make serve   # preview at http://localhost:8000 (override with PORT=...)
```

In Conductor, `.conductor/settings.toml` defines a `site` run script (`make serve` on
`$CONDUCTOR_PORT`) that starts automatically when a new workspace finishes setup.

## Hand-edited content

The bio, papers list, and nav links are hand-written in `index.html`.
Papers are low priority, so that section is a `<details>` that starts collapsed.

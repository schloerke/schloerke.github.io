# schloerke.github.io

Personal site for Barret Schloerke, served by GitHub Pages at schloerke.com (`CNAME`).
Other repos under `schloerke/` are served as `schloerke.com/<repo>/` (e.g. talk slides).

**Keep this file current.** When you add a feature, data source, script, make target,
or change an approach below, update this file in the same change.

## Design

- Simple like hadley.nz: one column, plain prose, system fonts, no framework.
- Data-rich like samuelbharti.com: stats and small charts, all driven by the JSON files in `data/`.
- No build step for the page. `index.html` holds all markup, CSS, and JS.
- Colors are CSS custom properties in `:root` using `light-dark()`. They follow the system
  by default; the button in the page's top-right corner cycles system (◐) → light (☀) → dark (☾), setting `data-theme` on `<html>` and saves it in `localStorage.theme`.
  Link/accent blue must stay **WCAG AAA (≥ 7:1)** against `--bg` in both modes.
  Current ratios are noted in comments next to the variables. Recheck them when changing colors.
- Charts follow the dataviz skill: one hue, thin 2px lines, a hover tooltip on every mark
  (shared `#tip`, driven by `data-tip`), each sparkline scaled to itself.

## Data pipeline

`scripts/build_data.py` (stdlib only, run with `uv`) writes one file per section to `data/`, and
only rewrites files whose contents changed. The page fetches each file on its own.
Each file puts one list item or top-level key per line (`dump()`), so a changed row is a one-line diff.

- `summary.json`: `updated`, `merged_prs` / `repos` totals since `SINCE` (shown at the top of the
  "since 2018" dialog, so they cover the same years), and `years` (the contribution calendars).
  The package / other tables still count merged PRs from every year.
- `merged_prs.json`: `{year: {repo: merged PRs}}` from GitHub search, one query per year
  (search caps results at 1000). The page doesn't read it; it is a cache so each run only
  searches this year and last year. Delete it to refetch every year (e.g. a repo went private).
- `packages.json`: repos with ≥ `MIN_PRS` merged PRs that contain an R package (`DESCRIPTION`,
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
  (`py-<name>`, then `<name>`). R packages are skipped on purpose.
  `homepage` is the GitHub repo's website field (pkgdown / docs site), or null.
  The table's first columns are icons: the language icon (links to CRAN / PyPI / npm), then GitHub (octocat)
  and homepage (Lucide globe, stroke 1.5, scaled to the octocat's height). The package name after them is plain `<code>`.
  `feedstock` is fetched but not shown for now (the conda-forge anvil icon was removed; it's in git history).
  `epics` (only on packages listed in `scripts/epics.toml`): big pieces of work, hand-written there
  (first drafted from LinkedIn projects). Each has a `match` regex that is run against the titles of
  my merged PRs in the repo (one search per repo that has epics), plus optional `since` / `until` months
  to drop stray matches. The shown `start` / `end` months and `prs` count come from the PRs that match.
  GitHub search can't do this itself: it allows only 5 `OR`s and matches words loosely. An epic with no
  matches gets skipped and a warning is printed. In the table, a ▸ after the package name opens a row
  listing its epics, newest first. Each epic has a bar on a small timeline, styled like the talks timeline. A package's
  epics share one scale (whole years, at most ~4 year labels), and the dates (ISO `YYYY-MM`) appear in the tooltip and in visually hidden text. The "Show all" CSS counts rows with `:nth-child(n+13 of :not(.epics))`.
- `other.json`: every other public repo with ≥ `MIN_PRS` merged PRs (not a listed package's repo,
  not a talk), with its GitHub description. Private repos are skipped so their names stay off the site,
  and forks (e.g. `schloerke/leaflet`) are skipped. `HIDE_OTHER` hand-lists repos to leave out.
- `contributions/last.json` and `contributions/<year>.json`: GitHub GraphQL contribution calendars
  (needs a token), the rolling last year plus each year since `SINCE` (one `from`/`to` query each).
  Years before last year keep their committed file and aren't refetched; delete a file to refetch it.
  Commit contributions to `BOT_COMMITS` (rstudio/shinycoreci) are subtracted per day: its nightly
  `build-results.yml` commits to `gh-pages` as `GITHUB_ACTOR` (the last person to edit the cron, i.e. me),
  which added 1 to every weekday. `commitContributionsByRepository` gives per-day counts; the calendar can't
  filter by repo. `gh-pages` history there is trimmed, so matching commit messages doesn't work for old years.
  The page shows the last year, scaled to itself. Its "(since 2018)" link opens a `<dialog>` that
  loads every year and stacks them, sharing one color scale so years compare. The shared `#tip` moves
  into the dialog while it's open, since a modal dialog sits in the top layer above any z-index.
- `talks.json`: `schloerke/presentation-*` and `workshop-*` repos. The date comes from the repo
  name. The title is the repo description, then the README's first `# ` heading (via the `/readme` API, so
  `Readme.md` counts too), then the name slug. The link is the repo homepage (`http://` upgraded to `https://`), else the repo. Markdown and HTML are stripped out. `TALKS` (top of the script) hand-writes the entries for a repo
  whose name has no date (e.g. `workshop-rinpharma24-shinylive`) or that holds several talks (shinydevseries
  → 3 episodes). `TALK_VIDEO` (top of the script) hand-maps a talk repo to
  its opensource.posit.co recording, because the video's date and title rarely match the talk's. That video
  moves out of `videos.json` and into the talk's `video` field. The page shows it on the talk row as a film + arrow-up-right icon
  link (Lucide, ISC) that opens in a new tab, and the Videos summary count still includes it.
  The talks and videos lists show 6 rows with a "Show all" / "Show fewer" button (`showAll()`, shared with Other repos).
  A timeline dot links to its row (`#talk-<i>`), opens the list if that row is hidden, and highlights the row for 5s.
- `videos.json` / `posts.json`: pages on opensource.posit.co that credit `FULL_NAME` in their front matter
  `people:` list (Shiny Team posts list their contributors there since posit-dev/open-source-website#417).
  The site repo is 2 GB, so the script does a shallow, blobless, sparse `git clone` that fetches only
  `content/blog/**/index.{md,markdown,html}` and `content/resources/videos/*/_index.md` (a few seconds).
  Titles, dates, durations, and YouTube view counts come from the site's `blog/item-index.json` and
  `resources/videos/item-index.json`, joined by permalink. Blog permalinks are rebuilt with the site's
  `hugo.toml` rule `/blog/<date>_<slug or dir>/`, lowercased. Credit comes from the source files, not the site's JSON. Links go to the opensource.posit.co page, not YouTube.
  Video titles have the speaker name and channel ("| RStudio", "| Posit") removed.

Before writing, the script compares row counts (packages per language, `other`, `talks`, `videos`,
`posts`) against the committed `data/` and exits with an error if any drops by more than half.
A source that is down (a 404 reads as "not published") then turns the nightly run red instead of
committing a gap. The page's "Data updated" date shows how stale the data is. If a big drop is real
(e.g. after adding to `HIDE`), delete that file in `data/` and rerun its section (e.g. `make data-packages`).

cranlogs and pypistats don't send CORS headers, which is why the data is fetched at build time
rather than in the browser. `.github/workflows/data.yml` runs `make data` nightly and commits
`data/`. Its `keepalive` job re-enables the workflow via the API each run, because GitHub
disables scheduled workflows after 60 days without non-bot activity. The job fails after a
hard-coded date on purpose; bump it yearly.

## Commands

```sh
make data                         # rebuild all of data/ (uses `gh auth token` if GITHUB_TOKEN is unset)
make data-packages                # rebuild one section; also data-prs, data-other, data-talks, data-contributions
make data ONLY="packages other"   # rebuild several sections in one run
make serve                        # preview at http://localhost:8000 (override with PORT=...); scripts/serve.py sends Cache-Control: no-store
```

**During development, don't run a full `make data`.** It is slow and its output is long. Rebuild only the
section you changed with its `make data-<section>` target (`talks` also covers `videos` and `posts`). The
sections you skip are read from the committed `data/`. `prs` falls back to the `merged_prs.json` cache.
A partial run keeps the old `summary.updated` date. Leave full runs to the nightly workflow. A new section
needs both an entry in `SECTIONS` (`scripts/build_data.py`) and a `data-<section>` target in the `Makefile`.

In Conductor, `.conductor/settings.toml` defines a `site` run script (`make serve` on
`$CONDUCTOR_PORT`) that starts automatically when a new workspace finishes setup.

## Hand-edited content

The bio, papers list, and nav links are hand-written in `index.html`. The nav is all icons in two groups:
GitHub / Bluesky / ORCID (filled, Simple Icons, CC0), then CV / Talks / Writing (outline, Lucide, ISC,
styled by `.links .line`). Each icon link has `aria-label` and `title`.
Papers are low priority, so that section is a `<details>` that starts collapsed.

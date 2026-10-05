# /// script
# requires-python = ">=3.11"
# ///
"""Fetch stats for the homepage and write data/*.json.

cranlogs / pypistats have no CORS headers, so the browser can't fetch them
directly; this runs nightly in GitHub Actions instead. Needs GITHUB_TOKEN.

    make data
    make data ONLY="packages other"   # just those sections, the rest stay as committed
"""

import base64
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from collections import Counter

USER = "schloerke"
NAME = "Schloerke"  # matched against package author fields for `role`
FULL_NAME = "Barret Schloerke"  # matched against opensource.posit.co `people`
OSS_REPO = "https://github.com/posit-dev/open-source-website"
ROLES = ["contributor", "author", "maintainer"]
HIDE = {"securingsincity/react-ace"}  # repos to leave out of the package table
HIDE_OTHER = {"rstudio/shinycoreci-apps", "schloerke/schloerke.github.io"}  # repos to leave out of the other work table
OTHER_GROUP = {  # other work table filter; unlisted repos go in "Community"
    "Shiny": {
        "posit-dev/shinylive", "quarto-ext/shinylive", "posit-dev/py-shiny-site", "posit-dev/py-shiny-templates",
        "rstudio/shiny-examples", "posit-dev/shiny-showcase-bioinformatics", "DivadNojnarg/outstanding-shiny-ui",
        "DivadNojnarg/OSUICode", "rstudio/gradethis", "rstudio/shinycannon",
    },
    "Testing & CI": {
        "rstudio/shinycoreci", "schloerke/shinyjster", "rstudio/shiny-workflows", "posit-dev/shiny-issue-triage",
        "rstudio/shiny-testing-gha-example", "r-lib/actions", "r-wasm/actions",
    },
}
ROLE = {"posit-dev/py-shiny": "author"}  # role when the manifests don't list me
LOGO = {  # repo -> logo, for repos with no pkgdown hex
    "posit-dev/chatlas": "https://posit-dev.github.io/chatlas/logos/hex/logo.png",
    "narwhals-dev/narwhals": "https://narwhals-dev.github.io/narwhals/assets/image.png",
    "posit-dev/brand-yml": "https://posit-dev.github.io/brand-yml/logos/tall/brand-yml-tall-color.svg",
}
EPICS = tomllib.loads(pathlib.Path(__file__).with_name("epics.toml").read_text())  # {lang: {package: [epic]}}
TALKS = {  # talk repo -> hand-written entries, for repos with no date in the name, several talks in one,
    # or no real title in the repo (older talks; titles and venues from the LaTeX CV, schloerke/curriculum_vitae)
    "presentation-2020-08-14-shinydevseries": [
        {"date": "2020-09-09", "title": "Episode 12: reactlog", "venue": "Shiny Developer Series",
         "url": "https://shinydevseries.com/interview/ep012/"},
        {"date": "2020-09-17", "title": "Episode 13: Inside Plumber 1.0", "venue": "Shiny Developer Series",
         "url": "https://shinydevseries.com/interview/ep013/"},
        {"date": "2020-10-03", "title": "Episode 14: Shining a Light on learnr", "venue": "Shiny Developer Series",
         "url": "https://shinydevseries.com/interview/ep014/"},
    ],
    "presentation-2018-08-20-nasa-shiny-lightning": [
        {"date": "2018-08-20", "title": "Shiny", "venue": "NASA Datanauts"},
    ],
    "presentation-2017_03_29-web_scraping": [
        {"date": "2017-03-29", "title": "Web Scraping with R"},  # not in the CV; title from the slides
    ],
    "presentation-2017_01_26-tidyverse": [
        {"date": "2017-01-26", "title": 'tidyverse[c("magrittr", "dplyr", "tidyr")]',
         "venue": "Purdue Graduate Statistics Seminar"},
    ],
    "presentation-2016_06_30-ggduo": [
        {"date": "2016-06-30", "title": "ggduo: Pairs plot for two group data", "venue": "useR! 2016"},
    ],
    "presentation-2016_03-trelliscope": [  # the repo's slides.txt links all three
        {"date": "2016-04-07", "title": "Analysis and Visualization of Large Complex Data with Tessera",
         "venue": "Purdue Graduate Statistics Seminar", "url": "https://slides.com/schloerke/tessera-purdue-2016-4-7"},
        {"date": "2016-03-24", "title": "Analysis and Visualization of Large Complex Data with Tessera",
         "venue": "Iowa State Graphics Research Group", "url": "https://slides.com/schloerke/tessera-isu-2016-3"},
        {"date": "2016-03-04", "title": "Analysis and Visualization of Large Complex Data with Tessera",
         "venue": "NUMBAT Seminar, Monash University", "url": "https://slides.com/schloerke/tessera-monash-2016"},
    ],
    "presentation-2015_10_20-web_scraping": [
        {"date": "2015-10-20", "title": "Web Scraping with R", "venue": "American Credit Acceptance"},
    ],
    "presentation-2015_02_24-trelliscope": [
        {"date": "2015-02-24", "title": "Trelliscope: D&R visualization tool",
         "venue": "Fields Institute Big Data Visualization",
         "url": "https://www.fields.utoronto.ca/programs/scientific/14-15/bigdata/optimization/"},
    ],
    "presentation-2014_10_21-ggplot2_spatial_statistics": [
        {"date": "2014-10-21", "title": "ggplot2: displaying spatial and temporal data",
         "venue": "Purdue Spatial Statistics Seminar"},
    ],
    "presentation-2014_06_27-Git": [
        {"date": "2014-06-27", "title": "git", "venue": "Purdue Working Group"},
    ],
    "presentation-2014_02_14-minimize-work-inefficiencies": [
        {"date": "2014-02-14", "title": "Reducing Working Environment Inefficiencies",
         "venue": "Purdue Graduate Statistics Seminar"},
    ],
    "workshop-rinpharma24-shinylive": [
        {"date": "2024-10-25", "title": "{shinylive}: Serverless Shiny applications workshop. An exercise in deploying your app to GitHub Pages", "venue": "R/Pharma 2024",
         "url": "https://schloerke.com/workshop-rinpharma24-shinylive/"},
    ],
}
TALKS_NO_REPO = [  # talks from the LaTeX CV with no talk repo
    {"date": "2016-06-01", "title": "Analysis and Visualization of Large Complex Data with Tessera",
     "venue": "Spring Research Conference, IIT", "url": "https://slides.com/schloerke/tessera-src-2016-5-25"},
    {"date": "2010-09-01", "title": "helpr: Help for R", "venue": "Iowa State Working Group",
     "url": "https://schloerke.com/talks/2010-09-helpr.pdf"},
    {"date": "2010-08-01", "title": "GGally: A Plot Matrix for All Variable Types", "venue": "JSM 2010", "url": None},
]
TALK_VIDEO = {  # talk repo -> its opensource.posit.co recording (or a YouTube URL); shown with the talk, not under Videos
    "presentation-2021-08-12-harvard-plumber-async": "https://www.youtube.com/watch?v=eHrzsIGY0so",
    "presentation-2021-08-05-harvard-plumber-beginner": "https://www.youtube.com/watch?v=GPNFP7qIxHc",
    "presentation-2025-11-12-ggplot2-extenders-GGally": "https://www.youtube.com/watch?v=Q4Cf_pIr4gs",
    "presentation-2025-09-17-posit-conf-otel": "2025-11-07_observability-at-scale-barret-schloerke-posit-positconf2025",
    "presentation-2025-08-09-user-plumber2": "2025-10-29_plumber2-streamlining-web-api-development-in-r-barret-schloerke",
    "presentation-2024-08-13-posit-shiny-data-frame": "2024-10-31_barret-schloerke-editable-data-frames-in-py-shiny-updating-original-data-in-real-time",
    "presentation-2024-04-18-appsilon-shinylive": "2024-06-06_shinylive-serverless-shiny-apps-barret-schloerke-posit",
    "presentation-2023-03-15-appsilon-nightly-testing": "2023-04-18_barret-schloerke-lessons-learned-testing-2500-shiny-apps-every-day",
    "presentation-2022-07-28-rstudioconf22-shinytest2": "2022-10-24_barret-schloerke-shinytest2-unit-testing-for-shiny-applications-rstudio-2022",
    "presentation-2021-01-rstudio-global-plumber-async": "2021-02-18_barret-schloerke-plumber-future-async-web-apis-rstudio",
    "presentation-2020-10-28-integrating-plumber": "2021-03-01_james-blair-barret-schloerke-integrating-r-with-plumber-apis-rstudio-2020",
    "workshop-rinpharma24-shinylive": "2025-03-11_shinylive-serverless-shiny-applications-workshop",
    "presentation-2019-01-18-reactlog": "2019-09-03_barret-schloerke-reactlog-20-debugging-the-state-of-shiny-rstudio-2019",
}
VENUES = {  # regex on a talk repo name (or video title) -> venue; {y} is the talk's year
    r"posit-conf|posit-shiny-data-frame": "posit::conf({y})",
    r"posit::conf\(\d{4}\)": "posit::conf({y})",
    r"rstudioconf|2019-01-18-reactlog": "rstudio::conf({y})",
    r"rstudio-global": "rstudio::global({y})",
    r"-user-|ggduo": "useR! {y}",
    r"shinyconf|appsilon": "ShinyConf {y}",
    r"rinpharma": "R/Pharma {y}",
    r"jsm|2016_08_03_cognostics": "JSM {y}",
    r"2017_04_14-cognostics": "CSESC {y}",
    r"2019-05-02-shiny-reactlog-sparklyr": "Advanced R workshop, Northeastern University",
    r"2020-04-29-reactlog": "Statistical Programming DC",
    r"jnj22": "Johnson & Johnson Shiny Day",
    r"shinymeta": "ABACUS {y}",
    r"ggplot2-extenders": "ggplot2 extenders",
    r"open-source-pharma": "Open Source in Pharma",
    r"harvard": "Harvard R User Group",
    r"integrating-plumber": "RStudio Webinar",
    r"Data Science Lab": "Data Science Lab",
    r"2016_02_18-graphql": "WOMBAT {y}",
}
VENUE_URL = {  # venue -> its home page; the page links the venue name
    "ggplot2 extenders": "https://exts.ggplot2.tidyverse.org/",
    "WOMBAT 2016": "https://wombat.numbat.space/",
    "Shiny Developer Series": "https://shinydevseries.com/",
}
MIN_PRS = 3  # repos with fewer merged PRs are drive-by fixes
MONTHS = 6  # pypistats only keeps 180 days
SINCE = 2018  # first year of contribution calendars
# its nightly workflow commits results to gh-pages as whoever last touched the cron (me);
# ponytail: drops all my commit contributions there, hand-made ones too; PRs and reviews still count
BOT_COMMITS = "rstudio/shinycoreci"
DATA = pathlib.Path("data")
TOKEN = os.environ["GITHUB_TOKEN"]


def fetch(url, body=None, auth=False, raw=False):
    headers = {"User-Agent": USER}
    if auth:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode() if raw else json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def gh(path):
    try:
        return fetch(f"https://api.github.com/{path}", auth=True)
    except urllib.error.HTTPError as e:
        if e.code not in (403, 429) or not (reset := e.headers.get("x-ratelimit-reset")):
            raise
        time.sleep(max(int(reset) - time.time(), 0) + 1)  # rate limited: wait for the window
        return fetch(f"https://api.github.com/{path}", auth=True)


def read(name):
    """A committed data/<name>.json, or None."""
    path = DATA / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def dump(v):
    """JSON with one list item or top-level key per line, so a changed row is a one-line diff."""
    c = lambda x: json.dumps(x, separators=(",", ":"))
    rows = [c(x) for x in v] if isinstance(v, list) else [f"{c(k)}:{c(x)}" for k, x in v.items()]
    ends = "[]" if isinstance(v, list) else "{}"
    return ends[0] + "\n" + ",\n".join(rows) + "\n" + ends[1] + "\n"


def month_range():
    end = dt.date.today().replace(day=1) - dt.timedelta(days=1)  # last full month
    y, m = divmod(end.year * 12 + end.month - 1 - (MONTHS - 1), 12)
    return dt.date(y, m + 1, 1), end


def monthly(days):
    """[(YYYY-MM-DD, n)] -> ([{month, downloads}] for the last MONTHS full months,
    downloads since then including the current partial month)."""
    start, end = month_range()
    months, y, m = {}, start.year, start.month
    for _ in range(MONTHS):
        months[f"{y}-{m:02}"] = 0
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    recent = 0
    for day, n in days:
        if day >= str(start):
            recent += n
            if day[:7] in months:
                months[day[:7]] += n
    return [{"month": m, "downloads": n} for m, n in months.items()], recent


def search(q):
    """Every issue / PR matching a search query (the API stops at 1000)."""
    page = 1
    while True:
        res = gh(f"search/issues?q={q}&per_page=100&page={page}")
        time.sleep(2)  # search API: 30 req/min
        yield from res["items"]
        if len(res["items"]) < 100:
            break
        page += 1


def merged_pr_counts():
    """{year: {repo: merged PRs}}. Years before last year come from the committed file."""
    # ponytail: old years are never refetched; delete data/merged_prs.json if a repo moves or goes private
    by_year = read("merged_prs") or {}
    this = dt.date.today().year
    for year in range(2010, this + 1):
        if year < this - 1 and str(year) in by_year:
            continue
        # search caps at 1000 results, so query one year at a time
        q = f"author:{USER}+type:pr+is:merged+merged:{year}-01-01..{year}-12-31"
        by_year[str(year)] = dict(Counter(i["repository_url"].split("/repos/")[1] for i in search(q)))
    return by_year


def epics(lang, name, repo):
    """The package's epics from epics.toml, dated and counted by my merged PR titles they match."""
    listed = EPICS.get(lang, {}).get(name)
    if not listed:
        return None
    # ponytail: one query, so a repo past 1000 merged PRs of mine loses the oldest; split by year then
    prs = [(i["closed_at"][:7], i["title"]) for i in search(f"author:{USER}+type:pr+is:merged+repo:{repo}")]
    out = []
    for e in listed:
        months = sorted(m for m, title in prs if re.search(e["match"], title, re.I)
                        and e.get("since", "") <= m <= e.get("until", "9999"))
        if not months:
            print(f"epic {lang} {name} {e['title']!r} matches no PRs; skipped")
            continue
        out.append({"title": e["title"], "about": e["about"], "prs": len(months), "start": months[0], "end": months[-1]})
    return out


def r_role(txt):
    if re.search(rf"^Maintainer:.*{NAME}", txt, re.M):
        return "maintainer"
    if (i := txt.find(NAME)) < 0:
        return "contributor"
    roles = txt[i:].split("person(")[0]  # this person's entry in Authors@R
    return "maintainer" if '"cre"' in roles else "author" if '"aut"' in roles else "contributor"


def listed_role(maintainers, authors):
    return "maintainer" if NAME in str(maintainers) else "author" if NAME in str(authors) else "contributor"


def reviews(repo):
    """PRs by others that I reviewed."""
    time.sleep(2)  # search API: 30 req/min
    q = f"reviewed-by:{USER}+-author:{USER}+type:pr+repo:{repo}"
    return gh(f"search/issues?q={q}&per_page=1")["total_count"]


def manifests(repo):
    """Yield (lang, package name, role, description) for R / Python / TypeScript packages in a repo."""
    raw = lambda p: fetch(f"https://raw.githubusercontent.com/{repo}/HEAD/{p}", raw=True)
    for path in ["DESCRIPTION", "pkg-r/DESCRIPTION"]:
        if (txt := raw(path)) and (m := re.search(r"^Package:\s*(\S+)", txt, re.M)):
            title = re.search(r"^Title:\s*(.+(?:\n[ \t]+.+)*)", txt, re.M)  # may wrap onto indented lines
            yield "R", m.group(1), r_role(txt), title and " ".join(title.group(1).split())
            break
    for path in ["pyproject.toml", "pkg-py/pyproject.toml"]:
        if (txt := raw(path)) and (proj := tomllib.loads(txt).get("project", {})).get("name"):
            yield "Python", proj["name"], listed_role(proj.get("maintainers"), proj.get("authors")), proj.get("description")
            break
    else:
        if (txt := raw("setup.cfg")) and (m := re.search(r"^name\s*=\s*([\w.-]+)", txt, re.M)):
            yield "Python", m.group(1), listed_role(re.findall(r"^maintainer\s*=.*", txt, re.M),
                                                     re.findall(r"^author\s*=.*", txt, re.M)), \
                  (d := re.search(r"^description\s*=\s*(.+)", txt, re.M)) and d.group(1).strip()
    for path in ["package.json", "pkg-js/package.json"]:
        # ponytail: TypeScript only; plain JS packages are skipped until one needs an icon
        if (txt := raw(path)) and '"typescript"' in txt:
            pkg = json.loads(txt)
            if pkg.get("name") and not pkg.get("private"):
                yield "TypeScript", pkg["name"], listed_role(pkg.get("maintainers"), pkg.get("author")), pkg.get("description")
                break


def cran(names):
    start, _ = month_range()
    end = dt.date.today()  # through today, so brand-new packages count as published
    out = {}
    # cranlogs 404s the whole batch on an invalid CRAN name (e.g. "rstudio-hex")
    names = sorted(n for n in names if re.fullmatch(r"[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]", n))
    for i in range(0, len(names), 20):
        batch = ",".join(names[i:i + 20])
        for p in fetch(f"https://cranlogs.r-pkg.org/downloads/daily/{start}:{end}/{batch}"):
            out[p["package"]] = monthly((d["day"], d["downloads"]) for d in p["downloads"] or [])
    return out


def pypi(name):
    time.sleep(1)  # pypistats is rate limited
    res = fetch(f"https://pypistats.org/api/packages/{name.lower()}/overall?mirrors=false")
    return monthly((d["date"], d["downloads"]) for d in res["data"]) if res else ([], 0)


def npm(name):
    start, _ = month_range()
    res = fetch(f"https://api.npmjs.org/downloads/range/{start}:{dt.date.today()}/{name}")
    return monthly((d["day"], d["downloads"]) for d in res["downloads"]) if res else ([], 0)


def feedstock(lang, name):
    """conda-forge feedstock repo for a Python package, if one exists."""
    if lang != "Python":
        return None
    name = name.lower().replace("_", "-")
    for cand in [f"py-{name}", name]:
        if gh(f"repos/conda-forge/{cand}-feedstock"):
            return f"conda-forge/{cand}-feedstock"


def logo(repo):
    """The repo's pkgdown hex logo, if it has one."""
    if repo in LOGO:
        return LOGO[repo]
    for path in ["man/figures/logo.svg", "man/figures/logo.png", "pkg-r/man/figures/logo.svg", "pkg-r/man/figures/logo.png"]:
        if gh(f"repos/{repo}/contents/{path}"):
            return f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"


def packages(pr_counts):
    # (lang, name) -> (prs, repo, description); forks of the same package keep the busiest repo
    found, role = {}, Counter()
    for repo, prs in pr_counts.items():
        if prs < MIN_PRS or repo in HIDE or re.match(rf"{USER}/(presentation|workshop)-", repo):
            continue
        for lang, name, r, desc in manifests(repo):
            # a repo's packages share a role: the strongest one any manifest gives
            role[repo] = max(role[repo], ROLES.index(r), ROLES.index(ROLE.get(repo, "contributor")))
            if (lang, name) not in found or found[lang, name][0] < prs:
                found[lang, name] = (prs, repo, desc)
    r_dl = cran(name for lang, name in found if lang == "R")
    downloads = {"R": lambda n: r_dl.get(n, ([], 0)), "Python": pypi, "TypeScript": npm}
    out = []
    for (lang, name), (prs, repo, desc) in found.items():
        series, recent = downloads[lang](name)
        if recent == 0:
            continue  # not published
        info = gh(f"repos/{repo}") or {}
        out.append({"name": name, "lang": lang, "repo": repo, "prs": prs, "role": ROLES[role[repo]],
                    "reviews": reviews(repo), "monthly": series, "recent": recent,
                    "description": desc or info.get("description") or "",
                    "homepage": info.get("homepage") or None,
                    "feedstock": feedstock(lang, name), "logo": logo(repo),
                    **({"epics": ep} if (ep := epics(lang, name, repo)) else {})})
    # a Python package without a hex borrows its R namesake's (py-shiny -> shiny)
    r_logos = {p["name"].lower(): p["logo"] for p in out if p["lang"] == "R"}
    for p in out:
        if p["lang"] == "Python" and not p["logo"]:
            p["logo"] = r_logos.get(p["name"].lower().replace("_", "-"))
    return sorted(out, key=lambda p: -p["prs"])


def other_work(pr_counts, pkgs):
    """Repos with >= MIN_PRS merged PRs not already shown as a package or talk."""
    shown = {p["repo"] for p in pkgs}
    out = []
    for repo, prs in pr_counts.items():
        if prs < MIN_PRS or repo in shown | HIDE_OTHER or re.match(rf"{USER}/(presentation|workshop)-", repo):
            continue
        info = gh(f"repos/{repo}")
        if not info or info["private"] or info["fork"]:
            continue  # private: keep names off the site; fork: my copy of someone else's repo
        group = next((g for g, repos in OTHER_GROUP.items() if info["full_name"] in repos), "Community")
        out.append({"repo": info["full_name"], "prs": prs, "description": info["description"] or "", "group": group})
    return sorted(out, key=lambda r: -r["prs"])


def contributions():
    """Contribution calendars: {"last": the last year, "<year>": each year since SINCE}.

    Years before last year keep their committed file, so each run fetches only the rolling
    year, this year, and last year (refetched so a run on Dec 31 can't freeze a partial day).
    """
    q = """query($u:String!,$from:DateTime,$to:DateTime,$after:String){user(login:$u){contributionsCollection(from:$from,to:$to){
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}
      commitContributionsByRepository(maxRepositories:100){repository{nameWithOwner}
        contributions(first:100,after:$after){pageInfo{hasNextPage endCursor} nodes{occurredAt commitCount}}}}}}"""

    def get(**span):
        bot, after = Counter(), None
        while True:  # page through BOT_COMMITS' days, 100 at a time
            res = fetch("https://api.github.com/graphql",
                        {"query": q, "variables": {"u": USER, "after": after, **span}}, auth=True)
            col = res["data"]["user"]["contributionsCollection"]
            repo = next((r["contributions"] for r in col["commitContributionsByRepository"]
                         if r["repository"]["nameWithOwner"] == BOT_COMMITS), None)
            for n in repo["nodes"] if repo else []:
                bot[n["occurredAt"][:10]] += n["commitCount"]  # local midnight, so the date matches
            if not repo or not repo["pageInfo"]["hasNextPage"]:
                break
            after = repo["pageInfo"]["endCursor"]
        cal = col["contributionCalendar"]
        days = [[d["date"], d["contributionCount"] - bot[d["date"]]] for w in cal["weeks"] for d in w["contributionDays"]]
        return {"total": cal["totalContributions"] - sum(bot.values()), "days": days}

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {"last": get()}
    this = dt.date.today().year
    for y in range(this, SINCE - 1, -1):
        # ponytail: old years are never refetched; delete a file if GitHub backfills that year
        if y < this - 1 and (old := read(f"contributions/{y}")):
            out[str(y)] = old
        else:
            out[str(y)] = get(**{"from": f"{y}-01-01T00:00:00Z", "to": min(f"{y}-12-31T23:59:59Z", now)})
    return out


def venue(text, year):
    """Venue for a talk repo name or video title, from VENUES, or None."""
    return next((v.format(y=year) for k, v in VENUES.items() if re.search(k, text)), None)


def youtube(url):
    """A video not on opensource.posit.co: date, title, length, and views from its YouTube watch page."""
    page = fetch(url, raw=True) or ""
    # ponytail: scrapes the page's embedded player JSON; use the YouTube Data API if this breaks
    get = lambda k: json.loads(re.search(rf'"{k}":("[^"]*")', page).group(1))
    try:
        return {"date": get("publishDate")[:10], "title": get("title"), "venue": None, "url": url,
                "minutes": round(int(get("lengthSeconds")) / 60), "views": int(get("viewCount"))}
    except AttributeError:  # GitHub's runners get a "confirm you're not a bot" page: keep the committed video
        print(f"warning: no video data on {url}, keeping the committed one", file=sys.stderr)
        return next((t["video"] for t in read("talks") or [] if (t.get("video") or {}).get("url") == url), None)


def talks(videos):
    """Presentation / workshop repos (or TALKS entries). Moves each TALK_VIDEO recording out of `videos` onto its talk."""
    repos, page = [], 1
    while batch := gh(f"users/{USER}/repos?per_page=100&page={page}"):
        repos += batch
        page += 1
    out = [{"kind": "presentation", "repo": None, **t} for t in TALKS_NO_REPO]
    for r in repos:
        if r["name"] in TALKS:
            talks_ = [{"kind": r["name"].split("-")[0], "repo": r["full_name"], **t} for t in TALKS[r["name"]]]
        elif m := re.match(r"(presentation|workshop)-(\d{4})[-_](\d{2})(?:[-_](\d{2}))?[-_]?(.*)", r["name"]):
            kind, y, mo, d, slug = m.groups()
            readme = gh(f"repos/{r['full_name']}/readme")  # any case: README.md, Readme.md, ...
            readme = readme and base64.b64decode(readme["content"]).decode(errors="replace")
            h1 = re.search(r"^# (.+)", readme or "", re.M)
            title = r["description"] or (h1 and h1.group(1)) or slug.replace("-", " ").replace("_", " ")
            title = re.sub(r"<.*|[`*]", "", title).strip()  # plain text: drop html + markdown
            if v := venue(r["name"], y):  # the venue gets its own field: "rstudio::conf(2022) - {shinytest2}"
                title = title.removeprefix(f"{v} - ").removesuffix(f" - {v}")
            home = re.sub(r"^http://", "https://", r["homepage"] or "")
            talks_ = [{"date": f"{y}-{mo}-{d or '01'}", "kind": kind, "title": title, "venue": v, "repo": r["full_name"],
                       "url": home if home and "github.com/" not in home else None}]  # the repo has its own link
        else:
            continue
        if (slug := TALK_VIDEO.get(r["name"], "")).startswith("https://www.youtube.com/"):
            talks_[0]["video"] = youtube(slug)
        elif slug:
            url = f"https://opensource.posit.co/resources/videos/{slug}/"
            if video := next((v for v in videos if v["url"] == url), None):
                videos.remove(video)
                talks_[0]["video"] = video
        out += talks_
    return sorted(out, key=lambda t: t["date"], reverse=True)


def credited(path):
    """True if a Hugo page's front matter lists me in `people`."""
    fm = path.read_text(errors="replace").split("\n---", 1)[0] + "\n"
    if not fm.startswith("---"):
        return False
    for inline, items in re.findall(r"^people:[ \t]*(.*)\n((?:[ \t]*- .*\n)*)", fm, re.M):
        names = re.findall(r"[^\[\],'\"]+", inline) + re.findall(r"- (.*)", items)
        if FULL_NAME in (n.strip(" '\"") for n in names):
            return True
    return False


def opensource():
    """Blog posts and videos crediting me on opensource.posit.co.

    Credit comes from the source front matter, display fields from the site's item-index.json, joined by permalink.
    """
    with tempfile.TemporaryDirectory() as tmp:
        git = lambda *a: subprocess.run(["git", "-C", tmp, *a], check=True, capture_output=True)
        git("clone", "-q", "--depth=1", "--filter=blob:none", "--no-checkout", "--sparse", OSS_REPO, ".")
        git("sparse-checkout", "set", "--no-cone", "/content/blog/**/index.md",
            "/content/blog/**/index.markdown", "/content/blog/**/index.html", "/content/resources/videos/*/_index.md")
        git("checkout", "-q")
        root = pathlib.Path(tmp, "content")
        mine = set()
        for f in (root / "resources/videos").glob("*/_index.md"):
            if credited(f):
                mine.add(f"/resources/videos/{f.parent.name}/")
        for f in (root / "blog").rglob("index.*"):
            if f.suffix in (".md", ".markdown", ".html") and credited(f):
                fm = f.read_text(errors="replace")
                date = re.search(r"^date:\s*['\"]?(\d{4}-\d{2}-\d{2})", fm, re.M)
                slug = re.search(r"^slug:\s*['\"]?([^'\"\n]+)", fm, re.M)
                if date:  # permalink rule from the site's hugo.toml
                    mine.add(f"/blog/{date[1]}_{slug[1].strip() if slug else f.parent.name}/".lower())
    site = "https://opensource.posit.co"
    posts = [{"date": p["date"], "title": p["title"], "url": site + p["permalink"],
              "image": site + p["image"]["src"] if p.get("image") else None}
             for p in fetch(f"{site}/blog/item-index.json") if p["permalink"].lower() in mine]
    videos = []
    for v in fetch(f"{site}/resources/videos/item-index.json"):
        if v["permalink"] in mine:
            # YouTube titles repeat the speaker and channel: "Barret Schloerke | Talk | RStudio (2022)"
            title = re.sub(rf"^{FULL_NAME}\s*[-:]\s*|\s*\({FULL_NAME}[^)]*\)", "", v["title"])
            parts = [p.strip() for p in re.split(rf"\s+\|\|?\s+|\s+-\s+(?={FULL_NAME})", title)]
            parts = [p for p in parts if FULL_NAME not in p and not re.match(r"RStudio|Posit\b|posit::conf|Data Science Lab", p)]
            videos.append({"date": v["date"], "title": " · ".join(parts) or title,
                           "venue": venue(v["title"], v["date"][:4]), "url": site + v["permalink"],
                           "minutes": round(v["duration"] / 60), "views": v["views"]})
    return posts, videos


# `build_data.py packages talks` rebuilds only those sections; the rest are read back from data/
SECTIONS = {"prs", "packages", "other", "talks", "contributions"}  # talks also covers videos + posts
only = set(sys.argv[1:])
if only - SECTIONS:
    raise SystemExit(f"unknown sections: {' '.join(only - SECTIONS)} (choose from {' '.join(sorted(SECTIONS))})")
want = lambda s: not only or s in only

prs_by_year = merged_pr_counts() if want("prs") else read("merged_prs")
pr_counts = sum((Counter(c) for c in prs_by_year.values()), Counter())
# the summary's totals match the calendars' years, since they're shown in the "since SINCE" dialog
recent_prs = sum((Counter(c) for y, c in prs_by_year.items() if int(y) >= SINCE), Counter())
pkgs = packages(pr_counts) if want("packages") else read("packages")
if want("talks"):
    posts, videos = opensource()
    talk_rows = talks(videos)  # also removes the talk recordings from `videos`
    for t in talk_rows + videos:
        if url := VENUE_URL.get(t.get("venue")):
            t["venue_url"] = url
else:
    posts, videos, talk_rows = read("posts"), read("videos"), read("talks")
if want("contributions"):
    cals = contributions()
else:
    cals = {p.stem: read(f"contributions/{p.stem}") for p in (DATA / "contributions").glob("*.json")}
# one file per section under data/, path -> contents
files = {
    "merged_prs": prs_by_year,  # cache for merged_pr_counts(); the page doesn't read it
    # a partial run keeps the old date, since the sections it skipped weren't refreshed
    "summary": {"updated": read("summary")["updated"] if only else dt.date.today().isoformat(),
                "merged_prs": sum(recent_prs.values()), "repos": len(recent_prs),
                "years": sorted((int(y) for y in cals if y != "last"), reverse=True)},
    "packages": pkgs,
    "other": other_work(pr_counts, pkgs) if want("other") else read("other"),
    "talks": talk_rows,
    "videos": videos,
    "posts": posts,
    **{f"contributions/{k}": v for k, v in cals.items()},
}


def sizes(get):
    """Row counts per section (packages per language), to catch a source that came back empty."""
    out = Counter(f"packages {p['lang']}" for p in get("packages") or [])
    out.update({k: len(get(k) or []) for k in ("other", "talks", "videos", "posts")})
    return out


# fail before writing, so the workflow goes red and keeps the last good data/
old, new = sizes(read), sizes(files.get)
if shrunk := [f"{k}: {old[k]} -> {new[k]}" for k in old if new[k] < old[k] / 2]:
    raise SystemExit("data/ shrank by more than half, a source is probably down:\n  " + "\n  ".join(shrunk))
(DATA / "contributions").mkdir(parents=True, exist_ok=True)
path = lambda name: DATA / f"{name}.json"
changed = [name for name, v in files.items() if not path(name).exists() or path(name).read_text() != dump(v)]
for name in changed:
    path(name).write_text(dump(files[name]))
print(f"{len(pkgs)} packages, {len(files['other'])} other, {len(files['talks'])} talks, "
      f"{len(videos)} videos, {len(posts)} posts, {len(cals)} calendars")
print("updated data/:", ", ".join(changed) or "nothing")

# /// script
# requires-python = ">=3.11"
# ///
"""Fetch stats for the homepage and write data/*.json.

cranlogs / pypistats have no CORS headers, so the browser can't fetch them
directly; this runs nightly in GitHub Actions instead. Needs GITHUB_TOKEN.

    make data
"""

import datetime as dt
import json
import os
import pathlib
import re
import subprocess
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
HIDE_OTHER = {"rstudio/shinycoreci-apps"}  # repos to leave out of the other work table
ROLE = {"posit-dev/py-shiny": "author"}  # role when the manifests don't list me
TALKS = {  # talk repo -> hand-written entries, for repos with no date in the name or several talks in one
    "presentation-2020-08-14-shinydevseries": [
        {"date": "2020-09-09", "title": "Shiny Developer Series #12: reactlog",
         "url": "https://shinydevseries.com/interview/ep012/"},
        {"date": "2020-09-17", "title": "Shiny Developer Series #13: Inside Plumber 1.0",
         "url": "https://shinydevseries.com/interview/ep013/"},
        {"date": "2020-10-03", "title": "Shiny Developer Series #14: Shining a Light on learnr",
         "url": "https://shinydevseries.com/interview/ep014/"},
    ],
    "workshop-rinpharma24-shinylive": [
        {"date": "2024-10-25", "title": "{shinylive}: Serverless Shiny applications workshop (R/Pharma 2024)",
         "url": "http://schloerke.com/workshop-rinpharma24-shinylive/"},
    ],
}
TALK_VIDEO = {  # talk repo -> its opensource.posit.co recording; shown with the talk, not under Videos
    "presentation-2025-09-17-posit-conf-otel": "2025-11-07_observability-at-scale-barret-schloerke-posit-positconf2025",
    "presentation-2025-08-09-user-plumber2": "2025-10-29_plumber2-streamlining-web-api-development-in-r-barret-schloerke",
    "presentation-2024-08-13-posit-shiny-data-frame": "2024-10-31_barret-schloerke-editable-data-frames-in-py-shiny-updating-original-data-in-real-time",
    "presentation-2024-04-18-appsilon-shinylive": "2024-06-06_shinylive-serverless-shiny-apps-barret-schloerke-posit",
    "presentation-2023-03-15-appsilon-nightly-testing": "2023-04-18_barret-schloerke-lessons-learned-testing-2500-shiny-apps-every-day",
    "presentation-2022-07-28-rstudioconf22-shinytest2": "2022-10-24_barret-schloerke-shinytest2-unit-testing-for-shiny-applications-rstudio-2022",
    "presentation-2021-01-rstudio-global-plumber-async": "2021-02-18_barret-schloerke-plumber-future-async-web-apis-rstudio",
    "workshop-rinpharma24-shinylive": "2025-03-11_shinylive-serverless-shiny-applications-workshop",
    "presentation-2019-01-18-reactlog": "2019-09-03_barret-schloerke-reactlog-20-debugging-the-state-of-shiny-rstudio-2019",
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


def merged_pr_counts():
    """{year: {repo: merged PRs}}. Years before last year come from the committed file."""
    # ponytail: old years are never refetched; delete data/merged_prs.json if a repo moves or goes private
    by_year = read("merged_prs") or {}
    this = dt.date.today().year
    for year in range(2010, this + 1):
        if year < this - 1 and str(year) in by_year:
            continue
        # search caps at 1000 results, so query one year at a time
        counts, page = Counter(), 1
        while True:
            q = f"author:{USER}+type:pr+is:merged+merged:{year}-01-01..{year}-12-31"
            res = gh(f"search/issues?q={q}&per_page=100&page={page}")
            time.sleep(2)  # search API: 30 req/min
            for item in res["items"]:
                counts[item["repository_url"].split("/repos/")[1]] += 1
            if len(res["items"]) < 100:
                break
            page += 1
        by_year[str(year)] = dict(counts)
    return by_year


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
    """Yield (lang, package name, role) for R / Python / TypeScript packages in a repo."""
    raw = lambda p: fetch(f"https://raw.githubusercontent.com/{repo}/HEAD/{p}", raw=True)
    for path in ["DESCRIPTION", "pkg-r/DESCRIPTION"]:
        if (txt := raw(path)) and (m := re.search(r"^Package:\s*(\S+)", txt, re.M)):
            yield "R", m.group(1), r_role(txt)
            break
    for path in ["pyproject.toml", "pkg-py/pyproject.toml"]:
        if (txt := raw(path)) and (proj := tomllib.loads(txt).get("project", {})).get("name"):
            yield "Python", proj["name"], listed_role(proj.get("maintainers"), proj.get("authors"))
            break
    else:
        if (txt := raw("setup.cfg")) and (m := re.search(r"^name\s*=\s*([\w.-]+)", txt, re.M)):
            yield "Python", m.group(1), listed_role(re.findall(r"^maintainer\s*=.*", txt, re.M),
                                                     re.findall(r"^author\s*=.*", txt, re.M))
    for path in ["package.json", "pkg-js/package.json"]:
        # ponytail: TypeScript only; plain JS packages are skipped until one needs an icon
        if (txt := raw(path)) and '"typescript"' in txt:
            pkg = json.loads(txt)
            if pkg.get("name") and not pkg.get("private"):
                yield "TypeScript", pkg["name"], listed_role(pkg.get("maintainers"), pkg.get("author"))
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


def packages(pr_counts):
    # (lang, name) -> (prs, repo); forks of the same package keep the busiest repo
    found, role = {}, Counter()
    for repo, prs in pr_counts.items():
        if prs < MIN_PRS or repo in HIDE or re.match(rf"{USER}/(presentation|workshop)-", repo):
            continue
        for lang, name, r in manifests(repo):
            # a repo's packages share a role: the strongest one any manifest gives
            role[repo] = max(role[repo], ROLES.index(r), ROLES.index(ROLE.get(repo, "contributor")))
            if (lang, name) not in found or found[lang, name][0] < prs:
                found[lang, name] = (prs, repo)
    r_dl = cran(name for lang, name in found if lang == "R")
    downloads = {"R": lambda n: r_dl.get(n, ([], 0)), "Python": pypi, "TypeScript": npm}
    out = []
    for (lang, name), (prs, repo) in found.items():
        series, recent = downloads[lang](name)
        if recent == 0:
            continue  # not published
        out.append({"name": name, "lang": lang, "repo": repo, "prs": prs, "role": ROLES[role[repo]],
                    "reviews": reviews(repo), "monthly": series, "recent": recent,
                    "feedstock": feedstock(lang, name)})
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
        out.append({"repo": info["full_name"], "prs": prs, "description": info["description"] or ""})
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


def talks(videos):
    """Presentation / workshop repos (or TALKS entries). Moves each TALK_VIDEO recording out of `videos` onto its talk."""
    repos, page = [], 1
    while batch := gh(f"users/{USER}/repos?per_page=100&page={page}"):
        repos += batch
        page += 1
    out = []
    for r in repos:
        if r["name"] in TALKS:
            talks_ = [{"kind": r["name"].split("-")[0], **t} for t in TALKS[r["name"]]]
        elif m := re.match(r"(presentation|workshop)-(\d{4})[-_](\d{2})(?:[-_](\d{2}))?[-_]?(.*)", r["name"]):
            kind, y, mo, d, slug = m.groups()
            readme = fetch(f"https://raw.githubusercontent.com/{r['full_name']}/HEAD/README.md", raw=True)
            h1 = re.search(r"^# (.+)", readme or "", re.M)
            title = r["description"] or (h1 and h1.group(1)) or slug.replace("-", " ").replace("_", " ")
            title = re.sub(r"<.*|[`*]", "", title).strip()  # plain text: drop html + markdown
            talks_ = [{"date": f"{y}-{mo}-{d or '01'}", "kind": kind, "title": title,
                       "url": r["homepage"] or r["html_url"]}]
        else:
            continue
        if r["name"] in TALK_VIDEO:
            url = f"https://opensource.posit.co/resources/videos/{TALK_VIDEO[r['name']]}/"
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
    posts = [{"date": p["date"], "title": p["title"], "url": site + p["permalink"]}
             for p in fetch(f"{site}/blog/item-index.json") if p["permalink"].lower() in mine]
    videos = []
    for v in fetch(f"{site}/resources/videos/item-index.json"):
        if v["permalink"] in mine:
            # YouTube titles repeat the speaker and channel: "Barret Schloerke | Talk | RStudio (2022)"
            title = re.sub(rf"^{FULL_NAME}\s*[-:]\s*|\s*\({FULL_NAME}[^)]*\)", "", v["title"])
            parts = [p.strip() for p in re.split(rf"\s+\|\|?\s+|\s+-\s+(?={FULL_NAME})", title)]
            parts = [p for p in parts if FULL_NAME not in p and not re.match(r"RStudio|Posit\b|posit::conf|Data Science Lab", p)]
            videos.append({"date": v["date"], "title": " · ".join(parts) or title, "url": site + v["permalink"],
                           "minutes": round(v["duration"] / 60), "views": v["views"]})
    return posts, videos


prs_by_year = merged_pr_counts()
pr_counts = sum((Counter(c) for c in prs_by_year.values()), Counter())
pkgs = packages(pr_counts)
posts, videos = opensource()
cals = contributions()
# one file per section under data/, path -> contents
files = {
    "merged_prs": prs_by_year,  # cache for merged_pr_counts(); the page doesn't read it
    "summary": {"updated": dt.date.today().isoformat(), "merged_prs": sum(pr_counts.values()),
                "repos": len(pr_counts), "years": [int(y) for y in cals if y != "last"]},
    "packages": pkgs,
    "other": other_work(pr_counts, pkgs),
    "talks": talks(videos),  # also removes the talk recordings from `videos`
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

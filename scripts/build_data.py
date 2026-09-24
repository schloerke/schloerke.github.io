# /// script
# requires-python = ">=3.11"
# ///
"""Fetch stats for the homepage and write data.json.

cranlogs / pypistats have no CORS headers, so the browser can't fetch them
directly; this runs nightly in GitHub Actions instead. Needs GITHUB_TOKEN.

    make data
"""

import datetime as dt
import json
import os
import re
import time
import tomllib
import urllib.error
import urllib.request
from collections import Counter

USER = "schloerke"
NAME = "Schloerke"  # matched against package author fields for `role`
ROLES = ["contributor", "author", "maintainer"]
HIDE = {"securingsincity/react-ace"}  # repos to leave out of the package table
HIDE_OTHER = {"rstudio/shinycoreci-apps"}  # repos to leave out of the other work table
ROLE = {"posit-dev/py-shiny": "author"}  # role when the manifests don't list me
MIN_PRS = 3  # repos with fewer merged PRs are drive-by fixes
MONTHS = 6  # pypistats only keeps 180 days
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
    # search caps at 1000 results, so query one year at a time
    counts = Counter()
    for year in range(2010, dt.date.today().year + 1):
        page = 1
        while True:
            q = f"author:{USER}+type:pr+is:merged+merged:{year}-01-01..{year}-12-31"
            res = gh(f"search/issues?q={q}&per_page=100&page={page}")
            time.sleep(2)  # search API: 30 req/min
            for item in res["items"]:
                counts[item["repository_url"].split("/repos/")[1]] += 1
            if len(res["items"]) < 100:
                break
            page += 1
    return counts


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
                    "reviews": reviews(repo), "monthly": series, "recent": recent})
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
    q = """query($u:String!){user(login:$u){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    cal = fetch("https://api.github.com/graphql", {"query": q, "variables": {"u": USER}}, auth=True)
    cal = cal["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [[d["date"], d["contributionCount"]] for w in cal["weeks"] for d in w["contributionDays"]]
    return {"total": cal["totalContributions"], "days": days}


def talks():
    repos, page = [], 1
    while batch := gh(f"users/{USER}/repos?per_page=100&page={page}"):
        repos += batch
        page += 1
    out = []
    for r in repos:
        m = re.match(r"(presentation|workshop)-(\d{4})[-_](\d{2})(?:[-_](\d{2}))?[-_]?(.*)", r["name"])
        if not m:
            continue
        kind, y, mo, d, slug = m.groups()
        readme = fetch(f"https://raw.githubusercontent.com/{r['full_name']}/HEAD/README.md", raw=True)
        h1 = re.search(r"^# (.+)", readme or "", re.M)
        title = r["description"] or (h1 and h1.group(1)) or slug.replace("-", " ").replace("_", " ")
        title = re.sub(r"<.*|[`*]", "", title).strip()  # plain text: drop html + markdown
        out.append({"date": f"{y}-{mo}-{d or '01'}", "kind": kind, "title": title,
                    "url": r["homepage"] or r["html_url"]})
    return sorted(out, key=lambda t: t["date"], reverse=True)


pr_counts = merged_pr_counts()
pkgs = packages(pr_counts)
data = {
    "updated": dt.date.today().isoformat(),
    "merged_prs": sum(pr_counts.values()),
    "repos": len(pr_counts),
    "packages": pkgs,
    "other": other_work(pr_counts, pkgs),
    "contributions": contributions(),
    "talks": talks(),
}
with open("data.json", "w") as f:
    json.dump(data, f, separators=(",", ":"))
print(f"wrote data.json: {len(pkgs)} packages, {len(data['other'])} other, {len(data['talks'])} talks")

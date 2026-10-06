# /// script
# requires-python = ">=3.11"
# ///
"""Write plain rows from data/*.json and cv/cv.json into index.html's table bodies.

Crawlers that don't run JS (most AI ones) then see every package, talk, video, post,
and paper. The page's JS replaces these rows with the full ones on load.

    make html
"""

import json
import pathlib
import re
from html import escape

INDEX = pathlib.Path("index.html")
read = lambda path: json.loads(pathlib.Path(path).read_text())
link = lambda href, text: f'<a href="{escape(href)}">{escape(text)}</a>' if href else escape(text)
about = lambda text: f'<span class="about">{escape(text)}</span>' if text else ""
date = lambda d: f'<td class="date"><time datetime="{d}">{d[:7]}</time></td>'
venue = lambda r: f'<td class="venue">{link(r.get("venue_url"), r.get("venue") or "")}</td>'
# icon cells stay empty, so the columns line up with the JS rows
row = lambda *cells: "<tr>" + "".join(cells) + "</tr>"
td = lambda html="", cls="": f'<td class="{cls}">{html}</td>' if cls else f"<td>{html}</td>"
gh = lambda repo: f"https://github.com/{repo}"


def name(href, text, desc):
    return td(f"<code>{link(href, text)}</code>{about(desc)}", "name")


def epics(p):
    """The package's epics row, newest first, shown open (the JS rows start closed)."""
    if not p.get("epics"):
        return []
    # same shape as the JS: dates where the timeline bar goes, then the text
    lis = "".join(
        f'<li><time class="track">{e["start"] if e["start"] == e["end"] else f"{e['start']} – {e['end']}"}</time>'
        f"<span>{escape(e['title'])}{about(f' · {e['about']}')} · {e['prs']} PR{'' if e['prs'] == 1 else 's'}</span></li>"
        for e in sorted(p["epics"], key=lambda e: (e["start"], e["end"]), reverse=True))
    return [f'<tr class="epics"><td colspan="3"></td><td colspan="3"><ul>{lis}</ul></td></tr>']


cv = read("cv/cv.json")
rows = {
    "pkgs": [tr for p in read("data/packages.json") for tr in [
        row(td(), td(), td(), name(p["homepage"] or gh(p["repo"]), p["name"], p["description"]),
            td(p["prs"], "num"), td()),
        *epics(p)]],
    "other": [row(td(), name(gh(r["repo"]), r["repo"], r["description"]), td(r["prs"], "num"))
              for r in read("data/other.json")],
    "earlier": [row(td(), name(r["url"], r["name"], r["about"]), td(escape(r["org"]), "venue"), date(r["start"]))
                for r in cv["research"]],
    "talks-list": [row(td(), td(link(t.get("url") or (t.get("repo") and gh(t["repo"])), t["title"])), venue(t), date(t["date"]))
                   for t in read("data/talks.json")],
    "videos-list": [row(td(), td(link(v["url"], v["title"])), venue(v), date(v["date"]))
                    for v in read("data/videos.json")],
    "posts": [row(td(), td(link(p["url"], p["title"])), date(p["date"])) for p in read("data/posts.json")],
    "papers": [row(td(), td(link(p["url"], p["title"])), td(f"<i>{escape(p['venue'])}</i>", "venue"),
                   date(str(p["year"])))
               for p in cv["publications"]],
}

html = INDEX.read_text()
for id, trs in rows.items():
    # one row per line, so a changed row is a one-line diff
    body = "".join(f"\n{tr}" for tr in trs) + "\n        "
    html, n = re.subn(rf'(<table id="{id}"[^>]*>.*?<tbody>).*?(</tbody>)',
                      lambda m: m[1] + body + m[2], html, count=1, flags=re.S)
    assert n == 1, f"no <tbody> for table #{id} in {INDEX}"
if html != INDEX.read_text():
    INDEX.write_text(html)
    print(f"updated {INDEX}")

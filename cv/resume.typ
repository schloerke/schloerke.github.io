// Build with `make cv`. A one-page cut of cv.typ: same data, same look, fewer rows.
#import "style.typ": *
#let talks = json("/data/talks.json")
#let videos = json("/data/videos.json")
#let posts = json("/data/posts.json")

#show: style.with("Resume", size: 9pt, margin: (x: 0.6in, y: 0.5in))
#show heading.where(level: 2): it => block(above: 1.4em, below: 0.6em, width: 100%, stroke: (bottom: 0.5pt + rule), inset: (bottom: 0.3em))[
  #text(10pt, weight: "semibold", it.body)
]
#let row = row.with(above: 0.75em)

// no tagline and fewer contacts than the CV, to keep the top quiet
#header(spacing: 0.3em, tagline: false, contact: ("mail", "globe", "github", "linkedin"))
// fails the build if it outgrows one page
#context assert(counter(page).final().first() == 1, message: "resume.typ is longer than one page")

== Summary
#cv.summary

== Experience
// the two current roles in full, a line each for the rest, minus the internship
#for (i, e) in cv.experience.filter(e => not e.role.ends-with("Intern")).enumerate() {
  row([*#e.role*, #maybe-link(e.at("url", default: none), e.org) #dim[· #e.place]], span(e.start, e.end),
    below: list(..if i < 2 { e.bullets } else { e.bullets.slice(0, 1) }))
}

== Open source software
#approx(summary.merged_prs, 100) merged pull requests across #approx(summary.repos, 10) GitHub repositories since #calc.min(..summary.years). Top packages I maintain or author:
// by merged PRs, GGally (pre-Posit) last. Repos sharing a name (R and Python shiny) are one row,
// with each repo's link on its languages and the name linking the R repo's homepage (shiny.posit.co).
#let top = repos.filter(r => r.role != "contributor").slice(0, 8)
#let names = top.map(r => r.name).dedup()
#let names = names.filter(n => n != "GGally") + names.filter(n => n == "GGally")
#let gh(r, body) = link("https://github.com/" + r.repo, body)
#for n in names {
  let g = top.filter(r => r.name == n).sorted(key: r => if "R" in r.langs { 0 } else { 1 })
  if g.len() == 1 {
    let r = g.first()
    row([#gh(r, raw(n)) #r.description #dim[· #r.langs.join(", ")]], "")
  } else {
    let about = if n == "shiny" [A web application framework for #g.map(r => r.langs.first()).join[ and ]] else { g.first().description }
    row([#maybe-link(g.first().at("homepage", default: none), raw(n)) #about #dim[· #g.map(r => gh(r, r.langs.join(", "))).join[ · ]]], "")
  }
}

== Education
#for e in cv.education.filter(e => e.degree.starts-with("PhD,") or e.degree.starts-with("BS")) {
  row([*#maybe-link(e.at("url", default: none), e.degree)*, #e.org #dim[· #e.place]], years(e.start, e.end))
}

== Talks, awards & teaching
#row([#talks.len() talks & workshops, #videos.len() videos, and #posts.len() blog posts, listed at #link("https://schloerke.com")[schloerke.com]], "")
#for a in cv.awards.filter(a => a.at("url", default: none) != none).slice(0, 2) { row(link(a.url, a.title), years(a.start, a.end)) }
#for t in cv.teaching.slice(0, 1) { row([*#t.role*, #maybe-link(t.at("url", default: none), t.org) #note(t)], years(t.start, t.end)) }

== Skills
#grid(columns: (auto, 1fr), column-gutter: 1em, row-gutter: 0.5em,
  ..cv.skills.map(s => (text(fill: muted, s.group), s.items)).flatten())

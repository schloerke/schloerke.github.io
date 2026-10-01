// Build with `make cv`. Reads the same JSON as cv/index.html: cv/cv.json by hand, the rest from data/.
// Only the fonts in cv/fonts are used, so a build here and in CI give the same bytes.
#import "style.typ": *
#let talks = json("/data/talks.json")
#let videos = json("/data/videos.json")
#let posts = json("/data/posts.json")

#show: style.with("CV")
#header()

== Summary
#cv.summary

== Experience
#for e in cv.experience {
  row([*#e.role*, #maybe-link(e.at("url", default: none), e.org) #dim[· #e.place]], span(e.start, e.end),
    below: list(..e.bullets))
}

== Education
#for e in cv.education {
  row([*#maybe-link(e.at("url", default: none), e.degree)*, #e.org #dim[· #e.place]], years(e.start, e.end),
    below: if e.notes.len() > 0 { list(..e.notes) })
}

== Open source software
#dim[#approx(summary.merged_prs, 100) merged pull requests across #approx(summary.repos, 10) GitHub repositories since #calc.min(..summary.years). Packages I maintain or author, by merged PRs:]
#for r in repos.filter(r => r.role != "contributor") {
  let epics = r.epics.sorted(key: e => e.start).rev()
  row([#link("https://github.com/" + r.repo, raw(r.name)) #dim[#r.langs.join(", ") · #r.role · #approx(r.prs, 10) PRs · #r.description]], "",
    below: if epics.len() > 0 { text(9pt, fill: text-2, list(..epics.map(e => [#if r.langs.len() > 1 [#e.lang: ]#e.title (#years(e.start, e.end)): #e.about]))) })
}
#v(0.4em)
#dim[Also contributed to: #repos.filter(r => r.role == "contributor").map(r => link("https://github.com/" + r.repo, r.name)).join(", ").]

== Earlier research software
#for r in cv.research {
  row([#link(r.url, raw(r.name)), #r.org #dim[· #r.about]], years(r.start, r.end))
}

== Publications
#show regex("Schloerke, B\\.|B\\. Schloerke"): strong
#for p in cv.publications {
  block(above: 0.8em)[#p.authors (#p.year). #link(p.url, p.title). _#p.venue;_.]
}

== Talks & workshops
#for t in talks {
  let extra = (t.at("venue", default: none), if t.at("video", default: none) != none { link(t.video.url)[video] }).filter(x => x != none)
  let url = t.at("url", default: none)
  if url == none and t.repo != none { url = "https://github.com/" + t.repo }
  row([#maybe-link(url, t.title) #if extra.len() > 0 { dim[· #extra.join[ · ]] }],
    month(t.date.slice(0, 7)))
}

== Videos
#for v in videos { row(link(v.url, v.title), month(v.date.slice(0, 7))) }

== Blog posts
#for p in posts { row(link(p.url, p.title), month(p.date.slice(0, 7))) }

== Honors & awards
#for a in cv.awards {
  row([#maybe-link(a.at("url", default: none), a.title) #note(a)], years(a.start, a.end))
}

== Teaching & mentoring
#for t in cv.teaching {
  row([*#t.role*, #maybe-link(t.at("url", default: none), t.org) #note(t)], years(t.start, t.end))
}

== Service
#for s in cv.service {
  row([*#s.role*, #s.org #note(s)], years(s.start, s.end))
}

== Skills
#grid(columns: (auto, 1fr), column-gutter: 1em, row-gutter: 0.6em,
  ..cv.skills.map(s => (text(fill: muted, s.group), s.items)).flatten())

// Build with `make cv`. Reads the same JSON as cv/index.html: cv/cv.json by hand, the rest from data/.
// Only the fonts in cv/fonts are used, so a build here and in CI give the same bytes.
#let cv = json("cv.json")
#let icons = json("icons.json")
#let pkgs = json("/data/packages.json")
#let talks = json("/data/talks.json")
#let videos = json("/data/videos.json")
#let posts = json("/data/posts.json")
#let summary = json("/data/summary.json")

// the site's light-mode colors (../index.html :root)
#let text-1 = rgb("#0b0b0b")
#let text-2 = rgb("#52514e")
#let muted = rgb("#5f5e59")
#let rule = rgb("#dddcd6")
#let accent = rgb("#174e9c")

#let months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
#let month(ym) = months.at(int(ym.slice(5, 7)) - 1) + " " + ym.slice(0, 4)

// No creation date, a month (not a day) in the footer, and rounded counts: the PDF's bytes only
// change when something shown changes, so the nightly workflow commits it only then.
// keywords: the build month, which the nightly workflow greps for to rebuild once a month
#set document(title: cv.name + " CV", author: cv.name, date: none, keywords: ("built " + summary.updated.slice(0, 7),))
#set page(paper: "us-letter", margin: (x: 0.75in, y: 0.7in), footer: context text(8pt, fill: muted)[
  #cv.name · CV #h(1fr) Updated #month(summary.updated.slice(0, 7)) · #counter(page).display() / #counter(page).final().first()
])
#set text(font: "Inter", size: 9.5pt, fill: text-1)
// the vendored fonts have no emoji (talk and video titles have a few)
#show regex("[\\p{Extended_Pictographic}\\x{FE0F}]"): none
#set par(leading: 0.55em, spacing: 0.7em)
#set list(indent: 0.4em, body-indent: 0.5em, spacing: 0.45em)
#show link: set text(fill: accent)
// raw text is already 0.8em by default; 1.25em brings code back to the size of the text around it
#show raw: set text(font: "DejaVu Sans Mono", size: 1.25em)
#show heading.where(level: 2): it => block(above: 1.4em, below: 0.6em, width: 100%, stroke: (bottom: 0.5pt + rule), inset: (bottom: 0.3em))[
  #text(10.5pt, weight: "semibold", it.body)
]

#let span(a, b) = if a == b { month(a) } else { month(a) + " – " + if b == none { "Present" } else { month(b) } }
#let years(a, b) = if b != none and a.slice(0, 4) == b.slice(0, 4) { a.slice(0, 4) } else {
  a.slice(0, 4) + " – " + if b == none { "Present" } else { b.slice(0, 4) }
}
// 2336 -> "2,300+": rounded down to `step`, so a new merged PR rarely changes the PDF
#let approx(n, step) = if n < 2 * step { str(n) } else {
  let r = str(calc.floor(n / step) * step)
  (if r.len() > 3 { r.slice(0, -3) + "," + r.slice(-3) } else { r }) + "+"
}
// cv/icons.json, the same icons as cv/index.html, in the muted color
#let icon(name) = {
  let i = icons.at(name)
  let paint = if i.at("line", default: false) {
    "fill='none' stroke='" + muted.to-hex() + "' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'"
  } else { "fill='" + muted.to-hex() + "'" }
  box(baseline: 0.1em, image(bytes("<svg xmlns='http://www.w3.org/2000/svg' viewBox='-1 -1 26 26'><path " + paint + " d='" + i.d + "'/></svg>"), format: "svg", height: 0.95em))
}
// a note with some of its words as links, same as linkify() in cv/index.html
#let linkify(note, links) = {
  if links.len() == 0 { return note }
  let (text, url) = links.pairs().first()
  let rest = links
  let _ = rest.remove(text)
  if text not in note { return linkify(note, rest) }
  // only the first match, like String.replace in the page
  let parts = note.split(text)
  (linkify(parts.first(), rest), link(url, text), linkify(parts.slice(1).join(text), rest)).join()
}
#let maybe-link(url, body) = if url == none { body } else { link(url, body) }
// gray secondary text (not `sub`, which is Typst's subscript)
#let dim(body) = text(fill: text-2, body)
#let note(x) = if "note" in x { dim[· #linkify(x.note, x.at("links", default: (:)))] }
#let when(body) = text(8.5pt, fill: muted, number-type: "lining", body)
// a row: content on the left, date flush right
#let row(left, date, below: none) = block(breakable: false, above: 0.8em)[
  #grid(columns: (1fr, auto), column-gutter: 1em, left, when(date))
  #if below != none { v(-0.35em); below }
]

// one entry per repo, same as byRepo() in cv/index.html
#let rank = (maintainer: 0, author: 1, contributor: 2)
#let repos = (:)
#for p in pkgs {
  let r = repos.at(p.repo, default: p + (langs: (), epics: ()))
  if p.lang not in r.langs { r.langs.push(p.lang) }
  if rank.at(p.role) < rank.at(r.role) { r.role = p.role }
  let epics = p.at("epics", default: none)
  if epics != none { r.epics += epics.map(e => e + (lang: p.lang)) }
  repos.insert(p.repo, r)
}
#let repos = repos.values().sorted(key: r => -r.prs)

#grid(columns: (1fr, auto), column-gutter: 1.5em, [
  #text(22pt, weight: "bold", cv.name)
  #v(-0.6em)
  #text(11pt, cv.title) \
  #text(fill: text-2, raw(cv.tagline))
], align(right, text(8.5pt, stack(spacing: 0.6em, ..cv.contact.map(c => {
  let (body, url) = if "email" in c { (c.email.join("@"), "mailto:" + c.email.join("@")) } else { (c.text, c.url) }
  [#link(url, text(fill: text-2, body)) #h(0.3em) #icon(c.icon)]
})))))

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
  row([#link(if t.at("url", default: none) != none { t.url } else { "https://github.com/" + t.repo }, t.title) #if extra.len() > 0 { dim[· #extra.join[ · ]] }],
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

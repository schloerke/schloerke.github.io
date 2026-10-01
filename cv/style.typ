// Shared by cv.typ and resume.typ: the site's light-mode look, helpers, and the header.
#let cv = json("cv.json")
#let icons = json("icons.json")
#let pkgs = json("/data/packages.json")
#let summary = json("/data/summary.json")

// the site's light-mode colors (../index.html :root)
#let text-1 = rgb("#0b0b0b")
#let text-2 = rgb("#52514e")
#let muted = rgb("#5f5e59")
#let rule = rgb("#dddcd6")
#let accent = rgb("#174e9c")

#let months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
#let month(ym) = months.at(int(ym.slice(5, 7)) - 1) + " " + ym.slice(0, 4)

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
#let row(left, date, below: none, above: 0.8em) = block(breakable: false, above: above)[
  #grid(columns: (1fr, auto), column-gutter: 1em, left, when(date))
  #if below != none { v(-0.35em); below }
]

// one entry per repo, same as byRepo() in cv/index.html
#let rank = (maintainer: 0, author: 1, contributor: 2)
#let repos = {
  let repos = (:)
  for p in pkgs {
    let r = repos.at(p.repo, default: p + (langs: (), epics: ()))
    if p.lang not in r.langs { r.langs.push(p.lang) }
    if rank.at(p.role) < rank.at(r.role) { r.role = p.role }
    let epics = p.at("epics", default: none)
    if epics != none { r.epics += epics.map(e => e + (lang: p.lang)) }
    repos.insert(p.repo, r)
  }
  repos.values().sorted(key: r => -r.prs)
}

// No creation date, a month (not a day) in the footer, and rounded counts: the PDF's bytes only
// change when something shown changes, so the nightly workflow commits it only then.
#let style(kind, size: 9.5pt, margin: (x: 0.75in, y: 0.7in), body) = {
  set document(title: cv.name + " " + kind, author: cv.name, date: none)
  set page(paper: "us-letter", margin: margin, footer: context text(8pt, fill: muted)[
    #cv.name · #kind #h(1fr) Updated #month(summary.updated.slice(0, 7))#if counter(page).final().first() > 1 [ · #counter(page).display() / #counter(page).final().first()]
  ])
  set text(font: "Inter", size: size, fill: text-1)
  // the vendored fonts have no emoji (talk and video titles have a few)
  show regex("[\\p{Extended_Pictographic}\\x{FE0F}]"): none
  set par(leading: 0.55em, spacing: 0.7em)
  set list(indent: 0.4em, body-indent: 0.5em, spacing: 0.45em)
  show link: set text(fill: accent)
  // raw text is already 0.8em by default; 1.25em brings code back to the size of the text around it
  show raw: set text(font: "DejaVu Sans Mono", size: 1.25em)
  show heading.where(level: 2): it => block(above: 1.4em, below: 0.6em, width: 100%, stroke: (bottom: 0.5pt + rule), inset: (bottom: 0.3em))[
    #text(10.5pt, weight: "semibold", it.body)
  ]
  body
}

// `contact`: the icons of the contact rows to show (default all)
#let header(spacing: 0.6em, tagline: true, contact: none) = grid(columns: (1fr, auto), column-gutter: 1.5em, [
  #text(22pt, weight: "bold", cv.name)
  #v(-0.6em)
  #text(11pt, cv.title)
  #if tagline { linebreak(); text(fill: text-2, cv.tagline.map(raw).join(linebreak())) }
], align(right, text(8.5pt, stack(spacing: spacing, ..cv.contact.filter(c => contact == none or c.icon in contact).map(c => {
  let (body, url) = if "email" in c { (c.email.join("@"), "mailto:" + c.email.join("@")) } else { (c.text, c.url) }
  [#link(url, text(fill: text-2, body)) #h(0.3em) #icon(c.icon)]
})))))

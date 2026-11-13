// The front page reads top to bottom: a story, show or announcement is shown once, in the highest section
// that carries it. Section pages (/kr/exhibitions, ...) keep their full lists; only the home view is thinned.

const norm = (s: string | null | undefined) =>
  (s || "").toLowerCase().replace(/\b(19|20)\d\d\b/g, "").replace(/[^\p{L}\p{N}]/gu, "");

const core = (s: string | null | undefined) => {
  const inner = [...(s || "").matchAll(/[《<「『〈](.+?)[》>」』〉]/g)].map((m) => m[1]);
  return norm(inner.length ? inner.sort((a, b) => b.length - a.length)[0] : s);
};

const MIN_KEY = 6; // shorter titles ("별, 괘", "개인전") are matched by link only

export class Seen {
  urls = new Set<string>();
  keys = new Set<string>();

  add(url?: string | null, title?: string | null) {
    if (url) this.urls.add(url);
    const k = core(title);
    if (k.length >= MIN_KEY) this.keys.add(k);
  }

  has(url?: string | null, title?: string | null) {
    if (url && this.urls.has(url)) return true;
    const k = core(title);
    const n = norm(title);
    if (k.length >= MIN_KEY && this.keys.has(k)) return true;
    for (const x of this.keys) if (n.includes(x) || (k.length >= MIN_KEY && x.includes(k))) return true;
    return false;
  }

  // keep the items not shown above, and mark them as shown
  keep<T>(items: T[] | null | undefined, url: (x: T) => string | null | undefined, title: (x: T) => string | null | undefined): T[] {
    const all = items || [];
    const out = all.filter((x) => !this.has(url(x), title(x)));
    all.forEach((x) => this.add(url(x), title(x))); // a dropped duplicate's own wording still marks the story as shown
    return out;
  }
}

export function homeView(page: any) {
  const seen = new Seen();
  const top = page.top || {};
  for (const c of [top.rookie, top.gallery]) if (c) seen.add(c.url, c.title);
  for (const t of top.trending || []) seen.add(t.url, t.title);
  for (const i of top.hero || []) if (page.headlines[i]) seen.add(null, page.headlines[i].title);

  const early = seen.keep(page.early, (e: any) => e.url, (e: any) => e.title);

  let briefing = page.briefing;
  if (briefing) {
    const insights = (briefing.insights || []).filter((t: string) => !seen.has(null, t.split(" → ")[0]));
    const major = seen.keep(briefing.major, (m: any) => m.sources?.[0]?.url, (m: any) => m.headline);
    for (const m of major) for (const s of m.sources || []) seen.add(s.url, null);
    briefing = insights.length || major.length ? { ...briefing, insights, major } : null;
  }
  // a gallery's own announcement belongs to Gallery Moves, not to the institutions' list above it
  const galleryNews = new Set((page.galleries?.news || []).map((n: any) => n.url));
  const official = seen.keep(
    (page.official || []).filter((o: any) => !galleryNews.has(o.url)),
    (o: any) => o.url,
    (o: any) => o.title_ko || o.title,
  );
  let rank = 0;
  const stories = seen
    .keep(page.stories, (s: any) => s.url, (s: any) => s.title_ko || s.title)
    .map((s: any) => (s.short ? s : { ...s, rank: ++rank }));
  const exhibitions = page.exhibitions && { ...page.exhibitions, featured: seen.keep(page.exhibitions.featured, (e: any) => e.url, (e: any) => e.title) };
  const galleries = page.galleries && { ...page.galleries, openings: seen.keep(page.galleries.openings, (e: any) => e.url, (e: any) => e.title) };
  return { ...page, early, briefing, official, stories, exhibitions, galleries };
}

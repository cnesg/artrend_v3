"use client";

import { useCallback, useEffect, useState } from "react";

// Instagram-story style artist viewer: a row of rings; tapping one opens a full-screen card that says why the name is up,
// with the official exhibition images and public-collection works (shown from their source URLs, internal preview only).
// Any link to "#artist-<n>" on the page opens the same viewer.

type Show = { title: string; venue: string; city?: string; start?: string; end?: string; url?: string; image?: string | null; status: string };
type Work = { title: string; date?: string; url?: string; image: string; holder?: string };
type Press = { title: string; url: string; outlet: string; date: string; n_outlets: number; excerpt?: string | null };
type Career = { year: string; kind: string; title: string; venue?: string | null; url?: string | null };
export type Artist = {
  name: string;
  cats?: string[];
  where?: string;
  image?: string | null;
  summary?: string[];
  shows?: Show[];
  works?: Work[];
  press?: Press[];
  why?: [string, string];
  profile?: string | null;
  record?: string | null;
  career?: Career[];
};

const SWATCH = ["#c8371f", "#1f2f4a", "#2f4a3a", "#6b2a3a", "#d9a441", "#3c3c3c", "#8aa1b1"];
function swatch(seed: string) {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return SWATCH[h % SWATCH.length];
}
function initials(name: string) {
  const t = name.trim();
  if (/^[\u3131-\uD79D]/.test(t)) return t.slice(0, 1);
  return t
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
function md(d?: string) {
  if (!d) return "";
  const [, m, day] = d.split("-");
  return `${Number(m)}.${Number(day)}`;
}

type Frame = { image?: string | null; caption?: string; href?: string };
function framesOf(a: Artist): Frame[] {
  const f: Frame[] = [];
  for (const s of a.shows || []) if (s.image) f.push({ image: s.image, caption: `${s.venue} 《${s.title}》`, href: s.url });
  for (const w of a.works || []) f.push({ image: w.image, caption: [w.title, w.date, w.holder].filter(Boolean).join(" · "), href: w.url });
  return f.length ? f : [{ image: null }];
}

export function ArtistStories({ artists, kicker = "ARTISTS IN FOCUS", title = "지금 주목받는 작가" }: { artists: Artist[]; kicker?: string; title?: string }) {
  const [open, setOpen] = useState<number | null>(null);
  const [frame, setFrame] = useState(0);
  const list = artists || [];

  const show = useCallback((i: number | null) => {
    setOpen(i);
    setFrame(0);
  }, []);

  useEffect(() => {
    const fromHash = () => {
      const m = window.location.hash.match(/^#artist-(\d+)$/);
      if (m && Number(m[1]) < list.length) show(Number(m[1]));
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, [list.length, show]);

  const close = useCallback(() => {
    setOpen(null);
    if (window.location.hash.startsWith("#artist-")) history.replaceState(null, "", window.location.pathname + window.location.search);
  }, []);

  const step = useCallback(
    (dir: 1 | -1) => {
      if (open === null) return;
      const n = framesOf(list[open]).length;
      if (frame + dir >= 0 && frame + dir < n) return setFrame(frame + dir);
      const next = open + dir;
      if (next < 0 || next >= list.length) return close();
      setOpen(next);
      setFrame(dir === 1 ? 0 : framesOf(list[next]).length - 1);
    },
    [open, frame, list, close],
  );

  useEffect(() => {
    if (open === null) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") step(1);
      if (e.key === "ArrowLeft") step(-1);
    };
    window.addEventListener("keydown", key);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", key);
      document.body.style.overflow = "";
    };
  }, [open, step, close]);

  if (!list.length) return null;
  const a = open !== null ? list[open] : null;
  const frames = a ? framesOf(a) : [];
  const fr = frames[frame];

  return (
    <section id="artists">
      <div className="section-title">
        <span className="kicker">{kicker}</span>
        <h2>{title}</h2>
        <span className="rule" />
        <span className="aside">눌러서 왜 뜨는지 보기</span>
      </div>
      <div className="stories-row">
        {list.map((p, i) => (
          <button key={i} className="story-ring" onClick={() => show(i)} aria-label={`${p.name} 스토리 열기`}>
            <span className="ring">
              {p.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.image} alt="" referrerPolicy="no-referrer" loading="lazy" />
              ) : (
                <span className="ring-ini" style={{ background: swatch(p.name) }}>
                  {initials(p.name)}
                </span>
              )}
            </span>
            <b>{p.name}</b>
            <small>{p.why ? p.why[0] : (p.cats || []).join(" · ")}</small>
          </button>
        ))}
      </div>

      {a && (
        <div className="story-overlay" role="dialog" aria-modal="true" aria-label={`${a.name} — 왜 지금`}>
          <div className="story-card">
            <div className="story-bars">
              {list.map((_, i) => (
                <span key={i} className={i < (open as number) ? "done" : i === open ? "on" : ""} />
              ))}
            </div>
            <button className="story-x" onClick={close} aria-label="닫기">
              ×
            </button>
            <div className="story-media">
              {fr?.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={fr.image} alt="" referrerPolicy="no-referrer" />
              ) : (
                <div className="story-ph" style={{ background: swatch(a.name) }}>
                  {initials(a.name)}
                </div>
              )}
              {frames.length > 1 && (
                <div className="story-dots">
                  {frames.map((_, i) => (
                    <span key={i} className={i === frame ? "on" : ""} />
                  ))}
                </div>
              )}
              {fr?.caption && (
                <div className="story-cap">
                  {fr.href ? (
                    <a href={fr.href} target="_blank" rel="noreferrer">
                      {fr.caption}
                    </a>
                  ) : (
                    fr.caption
                  )}
                  <span> · 이미지: 기관 공식 페이지</span>
                </div>
              )}
              <button className="story-tap l" onClick={() => step(-1)} aria-label="이전" />
              <button className="story-tap r" onClick={() => step(1)} aria-label="다음" />
            </div>
            <div className="story-body">
              <div className="story-cats">
                {(a.cats || []).map((c, i) => (
                  <span key={i}>{c}</span>
                ))}
              </div>
              <h3>{a.name}</h3>
              {a.profile && <p className="story-profile">{a.profile}</p>}
              {a.record && <p className="story-record">기록 · {a.record}</p>}
              <h4>왜 지금{a.why ? ` — ${a.why[0]}` : ""}</h4>
              <ul className="story-why">
                {(a.summary || []).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
              {(a.shows || []).length > 0 && (
                <>
                  <h4>전시</h4>
                  <ul className="story-list">
                    {a.shows!.map((s, i) => (
                      <li key={i}>
                        <span className="tag">{s.status}</span>{" "}
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noreferrer">
                            {s.title}
                          </a>
                        ) : (
                          s.title
                        )}
                        <small>
                          {" "}
                          · {s.venue} · {md(s.start)}–{md(s.end)}
                        </small>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {(a.career || []).length > 0 && (
                <>
                  <h4>이력</h4>
                  <ul className="story-list story-career">
                    {a.career!.map((c, i) => (
                      <li key={i}>
                        <span className="yr">{c.year}</span> <span className="tag">{c.kind}</span>{" "}
                        {c.url ? (
                          <a href={c.url} target="_blank" rel="noreferrer">
                            {c.title}
                          </a>
                        ) : (
                          c.title
                        )}
                        {c.venue && <small> · {c.venue}</small>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {(a.works || []).length > 0 && (
                <>
                  <h4>소장 작품</h4>
                  <div className="story-works">
                    {a.works!.map((w, i) => (
                      <a key={i} href={w.url || w.image} target="_blank" rel="noreferrer" title={w.title}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={w.image} alt={w.title} referrerPolicy="no-referrer" loading="lazy" />
                      </a>
                    ))}
                  </div>
                </>
              )}
              {(a.press || []).length > 0 && (
                <>
                  <h4>관련 기사</h4>
                  <ul className="story-list">
                    {a.press!.map((p, i) => (
                      <li key={i}>
                        <a href={p.url} target="_blank" rel="noreferrer">
                          {p.title}
                        </a>
                        <small>
                          {" "}
                          · {p.outlet} {md(p.date)}
                          {p.n_outlets > 1 ? ` 외 ${p.n_outlets - 1}곳` : ""}
                        </small>
                        {p.excerpt && <p className="story-ex">{p.excerpt}</p>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
          <button className="story-backdrop" onClick={close} aria-label="닫기" />
        </div>
      )}
    </section>
  );
}

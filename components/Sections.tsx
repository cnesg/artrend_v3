import Link from "next/link";
import { Masthead, SECTIONS } from "./Top";
import { ArtistStories } from "./ArtistStories";
import { CritOutlets, CritRecent } from "./Criticism";
import {
  CHECK_LABEL,
  RookiePoints,
  CriticismAndFairs,
  EarlySignal,
  ExCard,
  ExList,
  Exhibitions,
  Footer,
  News,
  Official,
  SectionTitle,
  Sources,
  shortDate,
} from "./Front";
import { Edition, Site, initials, period, swatch } from "@/lib/data";

// One page per tab. The home page is the insight summary; each tab opens the full material behind it.

export const SECTION_KEYS = SECTIONS.map(([k]) => k).filter((k) => k !== "insight");

const TOPIC_ORDER = ["전시·프로그램", "수상·인물", "기관·정책·제도", "시장·경매·아트페어", "비평·리뷰", "그 밖의 소식"];

function WeekNews({ rows, only, title, kicker }: { rows: any[]; only?: string[]; title: string; kicker: string }) {
  const list = (rows || []).filter((r) => !only || only.includes(r.topic));
  const groups = TOPIC_ORDER.map((t) => [t, list.filter((r) => r.topic === t)] as [string, any[]]).filter(([, l]) => l.length);
  const rest = list.filter((r) => !TOPIC_ORDER.includes(r.topic));
  if (rest.length) groups.push(["기타", rest]);
  return (
    <section id="all-news">
      <SectionTitle kicker={kicker} title={title} aside={`최근 7일 · ${list.length}건`} />
      {!list.length && <p className="fine">이번 주 수집된 소식이 없습니다.</p>}
      {groups.length > 1 && (
        <div className="topics">
          {groups.map(([t, l]) => (
            <a key={t} href={`#t-${t}`} className="chip">
              {t} · {l.length}
            </a>
          ))}
        </div>
      )}
      {groups.map(([t, l]) => (
        <div key={t} className="wk-group" id={`t-${t}`}>
          <h4>{t}</h4>
          <ul className="wk-list">
            {l.map((r, i) => (
              <li key={i}>
                <span className="sdate">{shortDate(r.date)}</span>
                <div>
                  <a href={r.url} target="_blank" rel="noreferrer">
                    {r.title_ko || r.title}
                  </a>
                  {r.title_ko && r.title_ko !== r.title && <div className="ko">원문: {r.title}</div>}
                  <div className="meta">
                    <Sources n={r.n_outlets} list={r.sources} label={r.n_outlets > 1 ? `출처 ${r.n_outlets}곳` : r.sources?.[0]?.outlet || "출처"} />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function ArtistCards({ artists }: { artists: any[] }) {
  return (
    <section id="artist-cards">
      <SectionTitle kicker="ARTIST FILES" title="작가별로 왜 지금인지" aside={`${artists.length}명`} />
      <div className="af-list">
        {artists.map((a, i) => {
          const imgs = [...(a.shows || []).filter((s: any) => s.image).map((s: any) => ({ src: s.image, cap: `${s.venue} 《${s.title}》`, href: s.url })),
            ...(a.works || []).map((w: any) => ({ src: w.image, cap: [w.title, w.date, w.holder].filter(Boolean).join(" · "), href: w.url }))];
          return (
            <article key={i} className="af" id={`a-${i}`}>
              <div className="af-head">
                <span className="af-ini" style={{ background: swatch(a.name) }}>
                  {initials(a.name)}
                </span>
                <div>
                  <h3>
                    <a href={`#artist-${i}`}>{a.name}</a>
                  </h3>
                  <div className="story-cats">
                    {(a.cats || []).map((c: string, j: number) => (
                      <span key={j}>{c}</span>
                    ))}
                  </div>
                </div>
              </div>
              <ul className="story-why">
                {(a.summary || []).map((s: string, j: number) => (
                  <li key={j}>{s}</li>
                ))}
              </ul>
              {imgs.length > 0 && (
                <div className="af-imgs">
                  {imgs.slice(0, 6).map((m, j) => (
                    <a key={j} href={m.href || m.src} target="_blank" rel="noreferrer" title={m.cap}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={m.src} alt={m.cap} referrerPolicy="no-referrer" loading="lazy" />
                    </a>
                  ))}
                </div>
              )}
              <div className="af-cols">
                {(a.shows || []).length > 0 && (
                  <div>
                    <h4>전시</h4>
                    <ul className="story-list">
                      {a.shows.map((s: any, j: number) => (
                        <li key={j}>
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
                            · {s.venue} · {period(s.start, s.end)}
                          </small>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {(a.press || []).length > 0 && (
                  <div>
                    <h4>관련 기사</h4>
                    <ul className="story-list">
                      {a.press.map((p: any, j: number) => (
                        <li key={j}>
                          <a href={p.url} target="_blank" rel="noreferrer">
                            {p.title}
                          </a>
                          <small>
                            {" "}
                            · {p.outlet} {shortDate(p.date)}
                            {p.n_outlets > 1 ? ` 외 ${p.n_outlets - 1}곳` : ""}
                          </small>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function ExGrid({ title, kicker, rows, aside }: { title: string; kicker: string; rows: any[]; aside?: string }) {
  if (!rows?.length) return null;
  return (
    <section>
      <SectionTitle kicker={kicker} title={title} aside={aside || `${rows.length}개`} />
      <div className="ex-grid">
        {rows.map((e: any) => (
          <ExCard key={e.id} e={e} />
        ))}
      </div>
    </section>
  );
}

function GalleryNews({ news }: { news: any[] }) {
  return (
    <section>
      <SectionTitle kicker="GALLERY NEWS" title="갤러리 발표·소식" aside={`최근 7일 · ${news.length}건`} />
      <ul className="wk-list">
        {news.map((n, i) => (
          <li key={i}>
            <span className="sdate">{shortDate(n.date)}</span>
            <div>
              <a href={n.url} target="_blank" rel="noreferrer">
                {n.title}
              </a>
              <div className="meta">{n.source}</div>
            </div>
          </li>
        ))}
        {!news.length && <li className="fine">이번 주 수집된 갤러리 소식이 없습니다.</li>}
      </ul>
    </section>
  );
}

function RookieFull({ rookie }: { rookie: any }) {
  const people = rookie.people || [];
  return (
    <>
      <section>
        <SectionTitle kicker="ROOKIE RADAR" title="지켜볼 신진 — 전체" aside="공식 선정 · 초기 경력 · 후속 지원 확인" />
        {!people.length && <p className="fine">최근 30일 판단한 수상·선정이 없습니다.</p>}
        <div className="rookies full">
          {people.map((p: any, i: number) => (
            <article key={i} className={`rookie ${p.watch ? "" : "ref"}`}>
              <div className="avatar sm" style={{ background: swatch(p.name) }}>
                {initials(p.name)}
              </div>
              <div>
                <div className="meta">
                  <span className="tag red">{p.watch ? p.status : `참고 · ${p.status}`}</span>
                  <span>상의 무게 {p.weight.level}</span>
                  {p.track && <span>{p.track}</span>}
                </div>
                <b>{p.name}</b> <span className="fine">{p.genre || ""}</span>
                <p className="rk-award">{p.award}</p>
                <RookiePoints points={p.points} />
              </div>
            </article>
          ))}
        </div>
      </section>
      <section>
        <SectionTitle kicker="AWARDS" title="이번 달 판단한 수상·선정" aside={`${(rookie.awards || []).length}건`} />
        <table className="awards-table">
          <thead>
            <tr>
              <th>상</th>
              <th>주최</th>
              <th>무게</th>
              <th>트랙</th>
              <th>수상자</th>
              <th>날짜</th>
            </tr>
          </thead>
          <tbody>
            {(rookie.awards || []).map((a: any, i: number) => (
              <tr key={i}>
                <td>{a.url ? <a href={a.url} target="_blank" rel="noreferrer">{a.award}</a> : a.award}</td>
                <td>{a.organizer || ""}</td>
                <td>
                  {a.weight.level} {a.weight.points}
                </td>
                <td title={a.track_reason || ""}>{a.track}</td>
                <td>{a.winners.join(", ") || "—"}</td>
                <td>{shortDate(a.date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Link className="more" href="/rookie">
          누적 관찰 명단 →
        </Link>
      </section>
    </>
  );
}

const TITLES: Record<string, string> = {
  news: "News — 이번 주 소식 전체",
  exhibitions: "Exhibitions — 열린 전시와 열릴 전시",
  artists: "Artists — 지금 이름이 오르는 작가",
  galleries: "Galleries — 갤러리 움직임",
  rookie: "Rookie — 신진 작가 레이더",
  criticism: "Criticism — 비평과 비평 매체",
  market: "Market — 페어·비엔날레·시장",
};

export function SectionPage({ site, edition, page, section }: { site: Site; edition: Edition; page: any; section: string }) {
  const ex = page.exhibitions || {};
  const all = ex.all || {};
  const gal = page.galleries || {};
  return (
    <main>
      <Masthead site={site} edition={edition} date={page.date} page={page} active={section} />
      <div className="section-page">
        <h1 className="sp-title">{TITLES[section]}</h1>
        {section === "news" && (
          <>
            <Official items={page.official} />
            <News stories={page.stories} topics={page.topics} />
            <WeekNews rows={page.news_week} kicker="ALL NEWS" title="이번 주 소식 전체 — 분야별" />
          </>
        )}
        {section === "exhibitions" && (
          <>
            <EarlySignal items={page.early} />
            <Exhibitions ex={ex} />
            <ExGrid kicker="OPEN NOW" title="지금 열려 있는 전시" rows={all.open_now} aside={`마감 순 · 전체 ${ex.open_count}개 중 ${(all.open_now || []).length}`} />
            <div className="ex-columns">
              <ExList title="이번 주 개막" rows={all.opened || []} limit={60} />
              <ExList title="2주 안 개막" rows={all.upcoming || []} limit={60} />
              <ExList title="7일 안 종료" rows={all.closing || []} limit={40} />
            </div>
          </>
        )}
        {section === "artists" && (
          <>
            <ArtistStories artists={page.artists} />
            <ArtistCards artists={page.artists || []} />
          </>
        )}
        {section === "galleries" && (
          <>
            <ExGrid kicker="GALLERY OPENINGS" title="갤러리 새 전시" rows={(gal.all || gal).openings} aside="최근 14일" />
            <GalleryNews news={(gal.all || gal).news || []} />
          </>
        )}
        {section === "rookie" && <RookieFull rookie={page.rookie || {}} />}
        {section === "criticism" && (
          <>
            <CritRecent rows={(page.critique || {}).recent || page.criticism || []} days={(page.critique || {}).days || 14} />
            <CritOutlets outlets={(page.critique || {}).outlets || []} />
          </>
        )}
        {section === "market" && (
          <>
            <CriticismAndFairs criticism={page.criticism || []} fairs={page.fairs || []} limit={10} critLink={`/${edition.slug}/criticism`} />
            <WeekNews rows={page.news_week} only={["시장·경매·아트페어"]} kicker="MARKET NEWS" title="시장·경매·아트페어 소식" />
          </>
        )}
      </div>
      <Footer site={site} />
    </main>
  );
}

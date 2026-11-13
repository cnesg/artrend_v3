import Link from "next/link";
import { getShorts, getSite } from "@/lib/data";
import { Footer } from "@/components/Front";

export const metadata = { title: "ARTREND Shorts — 오늘의 트렌드 영상" };

const ED: Record<string, string> = { KR: "한국", JP: "일본", AMERICAS: "미주", EUROPE: "유럽" };

export default function ShortsPage() {
  const site = getSite();
  const list = getShorts();
  const days = Array.from(new Set(list.map((m) => m.date)));
  return (
    <main className="section-page shorts-page">
      <nav className="shorts-nav">
        <Link href="/kr" className="mh-logo">
          <span>.artrend</span>
        </Link>
        <Link href="/kr">← 매거진으로</Link>
      </nav>
      <h1 className="sp-title">Shorts — 매일 자동으로 만드는 트렌드 영상</h1>
      <p className="fine">
        매일 아침 업데이트가 끝나면 판마다 그날 가장 뜨는 작가·전시로 15초 안팎 세로 영상(1080×1920)을 만듭니다. 이미지는 기관 공식 페이지에서 가져온 것이라
        내부 검토용입니다 — 외부에 올리기 전에 이미지 사용 허락을 받아야 합니다. 설명 문구는 그대로 복사해 쓸 수 있습니다.
      </p>
      {!list.length && <p className="fine">아직 만들어진 영상이 없습니다.</p>}
      {days.map((d) => (
        <section key={d}>
          <h2 className="shorts-day">{d.replace(/-/g, ".")}</h2>
          <div className="shorts-grid">
            {list
              .filter((m) => m.date === d)
              .map((m) => (
                <article key={m.src} className="short-card">
                  <video src={m.src} controls playsInline preload="metadata" />
                  <div className="short-meta">
                    <span className="tag">{ED[m.edition] || m.edition}</span> <span className="fine">{m.seconds}초</span>
                    <h3>{m.title}</h3>
                    <ol>
                      {m.script.map((s: string, i: number) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                    <details>
                      <summary>업로드용 설명 문구</summary>
                      <textarea readOnly value={m.caption} rows={6} />
                    </details>
                    <details>
                      <summary>근거 {m.sources.length}</summary>
                      <ul>
                        {m.sources.map((u: string, i: number) => (
                          <li key={i}>
                            <a href={u} target="_blank" rel="noreferrer">
                              {u.replace(/^https?:\/\//, "").slice(0, 60)}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </details>
                    <p className="fine">{m.image_credit ? `이미지: ${m.image_credit} · ` : ""}내부 검토용</p>
                    <a href={m.src} download className="more">
                      mp4 내려받기
                    </a>
                  </div>
                </article>
              ))}
          </div>
        </section>
      ))}
      <Footer site={site} />
    </main>
  );
}

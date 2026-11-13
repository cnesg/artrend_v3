import Link from "next/link";
import { getCardnews, getSite } from "@/lib/data";
import { Footer } from "@/components/Front";

export const metadata = { title: "ARTREND 카드뉴스 — 오늘의 트렌드" };

const ED: Record<string, string> = { KR: "한국", JP: "일본", AMERICAS: "미주", EUROPE: "유럽" };

export default function CardnewsPage() {
  const site = getSite();
  const list = getCardnews();
  const days = Array.from(new Set(list.map((m) => m.date)));
  return (
    <main className="section-page shorts-page">
      <nav className="shorts-nav">
        <Link href="/kr" className="mh-logo">
          <span>.artrend</span>
        </Link>
        <span>
          <Link href="/shorts">Shorts</Link> · <Link href="/kr">← 매거진으로</Link>
        </span>
      </nav>
      <h1 className="sp-title">카드뉴스 — 매일 자동으로 만드는 트렌드 카드</h1>
      <p className="fine">
        요일 시리즈 — 월 신진 · 화 갤러리 · 수 기관 발표 · 목 작가 · 금 주말 전시 · 토 페어·비엔날레·시장 · 일 한 주 정리. 그날 주제로 3~4장을
        먼저 싣고(소재가 부족한 날은 섞은 세트로 대신), 나머지는 다른 종류로 채웁니다. 매일 아침 업데이트가 끝나면 판마다 1080×1350 카드 8~9장을 만듭니다. 한 세트 안에서 인사이트·먼저 가볼 전시·작가·기관 발표·뉴스·신진·페어·갤러리를 한
        장씩 섞고, 같은 대상은 두 번 싣지 않으며, 최근 3일 카드에 나온 대상과 오늘 Shorts의 작가는 피해서 고릅니다. 이미지는 기관 공식 페이지에서 가져온 것이라
        내부 검토용입니다.
      </p>
      {!list.length && <p className="fine">아직 만들어진 카드뉴스가 없습니다.</p>}
      {days.map((d) => (
        <section key={d}>
          <h2 className="shorts-day">{d.replace(/-/g, ".")}</h2>
          {list
            .filter((m) => m.date === d)
            .map((m) => (
              <article key={m.edition} className="cn-set">
                <div className="cn-head">
                  <span className="tag">{ED[m.edition] || m.edition}</span> {m.series && <span className="tag red">{m.series}</span>} <b>{m.slides[0].title}</b>{" "}
                  <span className="fine">{m.srcs.length}장</span>
                </div>
                <div className="cn-strip">
                  {m.srcs.map((src: string, i: number) => (
                    <a key={src} href={src} target="_blank" rel="noreferrer" title={m.slides[i]?.title}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={src} alt={m.slides[i]?.title || ""} loading="lazy" />
                    </a>
                  ))}
                </div>
                <details>
                  <summary>업로드용 설명 문구</summary>
                  <textarea readOnly value={m.caption} rows={10} />
                </details>
              </article>
            ))}
        </section>
      ))}
      <Footer site={site} />
    </main>
  );
}

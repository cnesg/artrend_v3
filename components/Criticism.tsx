import { CRIT_LABEL, SectionTitle, shortDate } from "./Front";

// The criticism tab: what critics wrote in the last two weeks, and the outlet directory from ARTREND's own research.

const STATUS_CLASS: Record<string, string> = { active: "ok", changed: "chg", inactive: "off", unknown: "unk" };

export function CritRecent({ rows, days = 14 }: { rows: any[]; days?: number }) {
  const outlets = Array.from(new Set(rows.map((r) => r.outlet)));
  return (
    <section id="crit-recent">
      <SectionTitle kicker="CRITICISM" title={`최근 ${days === 14 ? "2주" : `${days}일`} 비평·리뷰·인터뷰`} aside={`${rows.length}편 · 매체 ${outlets.length}곳`} />
      {!rows.length && <p className="fine">이 기간에 수집된 비평이 없습니다.</p>}
      <ul className="crit crit-full">
        {rows.map((c, i) => (
          <li key={i}>
            <span className="tag">{CRIT_LABEL[c.type] || c.type}</span>{" "}
            <a href={c.url} target="_blank" rel="noreferrer">
              {c.title_ko || c.title}
            </a>
            <span className="fine">
              {" "}
              · {c.outlet}
              {c.author ? ` · ${c.author}` : ""} · {shortDate(c.date)}
            </span>
            {c.title_ko && <div className="ko">원문: {c.title}</div>}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function CritOutlets({ outlets }: { outlets: any[] }) {
  const live = outlets.filter((o) => o.status === "active" || o.status === "changed");
  const collected = outlets.filter((o) => o.use === "ARTREND 수집 중");
  return (
    <section id="crit-outlets">
      <SectionTitle
        kicker="CRITIQUE OUTLETS"
        title="비평 매체 지도"
        aside={`${outlets.length}곳 · 운영 ${live.length} · ARTREND 수집 ${collected.length}`}
      />
      <p className="fine crit-about">
        ARTREND 편집부가 매체마다 현재 주소와 운영 상태를 직접 확인한 목록입니다(확인일 {outlets[0]?.checked || "-"}). 주소가 바뀐 매체는 바뀐 주소로
        연결합니다. 이용 허락이 없거나 자동 접근을 막은 매체는 글을 모으지 않고 링크만 둡니다.
      </p>
      <table className="awards-table crit-table">
        <thead>
          <tr>
            <th>매체</th>
            <th>지역</th>
            <th>상태</th>
            <th>ARTREND</th>
            <th>최근 30일 수집</th>
            <th>확인 메모</th>
          </tr>
        </thead>
        <tbody>
          {outlets.map((o) => (
            <tr key={o.name + o.url} className={o.status === "inactive" ? "dim" : ""}>
              <td>
                <a href={o.url} target="_blank" rel="noreferrer">
                  {o.name}
                </a>
                {o.focus === "news" && <span className="fine"> · 보도 중심</span>}
              </td>
              <td>{o.region}</td>
              <td>
                <span className={`st st-${STATUS_CLASS[o.status] || "unk"}`}>{o.status_label}</span>
              </td>
              <td className="fine">{o.use}</td>
              <td>{o.n30 ? `${o.n30}편 · ${shortDate(o.latest)}` : "-"}</td>
              <td className="fine">{o.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

import { useState, useEffect } from "react";
import api from "../api";

const MONTHS = [
  { value: "2026-08", label: "Август 2026" },
  { value: "2026-07", label: "Июль 2026" },
  { value: "2026-06", label: "Июнь 2026" },
  { value: "2026-05", label: "Май 2026" },
  { value: "2026-04", label: "Апрель 2026" },
  { value: "2026-03", label: "Март 2026" },
  { value: "2026-02", label: "Февраль 2026" },
  { value: "2026-01", label: "Январь 2026" },
];

export default function RatingPage({ user }) {
  const [month, setMonth] = useState("2026-02");
  const [rating, setRating] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadRating(month);
  }, [month]);

  async function loadRating(m) {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/reports/rating/${m}`);
      setRating(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || "Нет данных за этот месяц");
      setRating([]);
    }
    setLoading(false);
  }

  return (
    <div className="page">
      <h1 className="page-title">Рейтинг сбережений</h1>

      <div className="card">
        <select
          className="input"
          value={month}
          onChange={e => setMonth(e.target.value)}
        >
          {MONTHS.map(m => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      {loading && <div className="center-text">Загрузка...</div>}
      {error && <div className="card error-text">{error}</div>}

      {!loading && rating.length > 0 && (
        <div className="card rating-list">
          {rating.map(r => (
            <div
              key={r.pid}
              className={"rating-row" + (r.is_me ? " rating-me" : "")}
            >
              <span className="rank">{rankEmoji(r.rank)}</span>
              <span className="rating-pid">
                {r.pid}
                {r.is_me && <span className="rating-me-badge">Вы</span>}
              </span>
              <span className="rating-pct">{r.savings_pct.toFixed(1)}%</span>
              <span className="rating-inv">{r.invest_pct ? "📈" : ""}</span>
              {r.delta_pct !== null && (
                <span className={"delta " + (r.delta_pct >= 0 ? "up" : "down")}>
                  {r.delta_pct >= 0 ? "▲" : "▼"}{Math.abs(r.delta_pct).toFixed(1)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {!loading && rating.length === 0 && !error && (
        <div className="card center-text">Нет отчётов за этот месяц</div>
      )}
    </div>
  );
}

function rankEmoji(rank) {
  if (rank === 1) return "🥇";
  if (rank === 2) return "🥈";
  if (rank === 3) return "🥉";
  return `${rank}.`;
}

import { useState, useEffect } from "react";
import api from "../api";

const CURRENT_MONTH = new Date().toISOString().slice(0, 7);

export default function ReportPage({ user }) {
  const [month, setMonth] = useState(CURRENT_MONTH);
  const [budgetYes, setBudgetYes] = useState(false);
  const [incomeGt, setIncomeGt] = useState(false);
  const [savingsPct, setSavingsPct] = useState("");
  const [investPct, setInvestPct] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [existing, setExisting] = useState(null);

  useEffect(() => {
    loadExisting(month);
  }, [month]);

  async function loadExisting(m) {
    try {
      const res = await api.get(`/reports/my/${m}`);
      if (res.data) {
        setExisting(res.data);
        setBudgetYes(res.data.budget_yes);
        setIncomeGt(res.data.income_gt_expense);
        setSavingsPct(String(res.data.savings_pct));
        setInvestPct(String(res.data.invest_pct));
      } else {
        setExisting(null);
        resetForm();
      }
    } catch {
      setExisting(null);
      resetForm();
    }
  }

  function resetForm() {
    setBudgetYes(false);
    setIncomeGt(false);
    setSavingsPct("");
    setInvestPct("");
  }

  async function submit() {
    setMsg(null);
    const sav = parseFloat(savingsPct);
    const inv = parseFloat(investPct || "0");
    if (isNaN(sav) || sav < 0 || sav > 100) {
      setMsg("Норма сбережений: число от 0 до 100");
      return;
    }
    if (isNaN(inv) || inv < 0 || inv > 100) {
      setMsg("Инвестиции: число от 0 до 100");
      return;
    }
    setSaving(true);
    try {
      await api.post("/reports", {
        month,
        budget_yes: budgetYes,
        income_gt_expense: incomeGt,
        savings_pct: sav,
        invest_pct: inv,
      });
      setMsg(existing ? "Отчёт обновлён!" : "Отчёт сохранён!");
      setExisting({ month, budget_yes: budgetYes, income_gt_expense: incomeGt, savings_pct: sav, invest_pct: inv });
    } catch (e) {
      setMsg("Ошибка: " + (e.response?.data?.detail || e.message));
    }
    setSaving(false);
  }

  return (
    <div className="page">
      <h1 className="page-title">Отчёт за месяц</h1>

      <div className="card">
        <label className="field-label">Месяц</label>
        <select
          className="input"
          value={month}
          onChange={e => setMonth(e.target.value)}
        >
          <option value="2026-08">Август 2026</option>
          <option value="2026-07">Июль 2026</option>
          <option value="2026-06">Июнь 2026</option>
          <option value="2026-05">Май 2026</option>
          <option value="2026-04">Апрель 2026</option>
          <option value="2026-03">Март 2026</option>
          <option value="2026-02">Февраль 2026</option>
          <option value="2026-01">Январь 2026</option>
        </select>
      </div>

      {existing && (
        <div className="card info-banner">
          Отчёт за этот месяц уже подан. Можно обновить.
        </div>
      )}

      <div className="card">
        <p className="section-title">1. Вёл(а) ли ты бюджет?</p>
        <div className="toggle-row">
          <button
            className={"toggle-btn" + (budgetYes ? " selected" : "")}
            onClick={() => setBudgetYes(true)}
          >
            Да
          </button>
          <button
            className={"toggle-btn" + (!budgetYes ? " selected" : "")}
            onClick={() => setBudgetYes(false)}
          >
            Нет
          </button>
        </div>
      </div>

      <div className="card">
        <p className="section-title">2. Доходы были больше расходов?</p>
        <div className="toggle-row">
          <button
            className={"toggle-btn" + (incomeGt ? " selected" : "")}
            onClick={() => setIncomeGt(true)}
          >
            Да
          </button>
          <button
            className={"toggle-btn" + (!incomeGt ? " selected" : "")}
            onClick={() => setIncomeGt(false)}
          >
            Нет
          </button>
        </div>
      </div>

      <div className="card">
        <label className="field-label">3. Норма сбережений (%)</label>
        <input
          className="input"
          type="number"
          min="0"
          max="100"
          step="0.1"
          value={savingsPct}
          onChange={e => setSavingsPct(e.target.value)}
          placeholder="Например: 30"
        />
        <p className="hint-text">
          Сколько % от дохода отложено. Если не было — 0.
        </p>
      </div>

      <div className="card">
        <label className="field-label">4. Инвестировано (%)</label>
        <input
          className="input"
          type="number"
          min="0"
          max="100"
          step="0.1"
          value={investPct}
          onChange={e => setInvestPct(e.target.value)}
          placeholder="Например: 10"
        />
        <p className="hint-text">
          Сколько % от дохода инвестировано в активы (0–100%).
        </p>
      </div>

      {msg && (
        <div className={"card " + (msg.startsWith("Ошибка") ? "error-text" : "success-text")}>
          {msg}
        </div>
      )}

      <div className="card">
        <button
          className="btn btn-primary btn-full"
          onClick={submit}
          disabled={saving}
        >
          {saving ? "Отправляю..." : existing ? "Обновить отчёт" : "Отправить отчёт"}
        </button>
      </div>
    </div>
  );
}

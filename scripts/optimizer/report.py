"""
report.py — Generates a self-contained HTML report from optimization results.

The report contains:
  - Summary banner (pairs optimized, compliance rate, best/worst score)
  - Sortable per-pair table with all best params + metrics
  - Copy-to-clipboard button per row
  - How-to-apply instructions for TradingView
  - Dark theme, Inter font, no external dependencies at runtime
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import BacktestResult

from .config import RESULTS_DIR, PROP_FIRM_MAX_DD_PCT


def generate_html_report(
    best_per_pair: dict[str, "BacktestResult"],
    all_results: list["BacktestResult"],
    dd_limit: float = PROP_FIRM_MAX_DD_PCT,
) -> Path:
    """
    Generate a self-contained HTML file and return its path.
    Auto-opens in the default browser.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"report_{timestamp}.html"

    # ── Collect all unique param keys across pairs ────────────────────────────
    all_param_keys: list[str] = []
    seen: set[str] = set()
    for res in best_per_pair.values():
        for k in res.params:
            if k not in seen:
                all_param_keys.append(k)
                seen.add(k)

    # ── Prepare row data ──────────────────────────────────────────────────────
    ranked = sorted(best_per_pair.items(), key=lambda kv: kv[1].score, reverse=True)

    compliant_count = sum(
        1 for _, r in ranked if r.max_drawdown_pct <= dd_limit and r.net_profit > 0
    )
    total_pairs = len(ranked)

    rows_html = _build_rows(ranked, all_param_keys, dd_limit)
    param_headers_html = "".join(
        f'<th class="sortable" onclick="sortTable({i + 8})">{_fmt_param_header(k)}</th>'
        for i, k in enumerate(all_param_keys)
    )

    # ── Build the full HTML ───────────────────────────────────────────────────
    html = _HTML_TEMPLATE.format(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        total_pairs=total_pairs,
        compliant_count=compliant_count,
        dd_limit=dd_limit,
        best_score=f"{ranked[0][1].score:.2f}" if ranked else "—",
        best_pair=ranked[0][0] if ranked else "—",
        param_headers=param_headers_html,
        param_count=len(all_param_keys),
        rows=rows_html,
        all_param_keys_json=json.dumps(all_param_keys),
    )

    report_path.write_text(html, encoding="utf-8")
    return report_path


def _fmt_param_header(name: str) -> str:
    """Convert param_name_like_this to a short readable header."""
    short = (
        name
        .replace("liq_max_distance_pips_", "liq_dist_")
        .replace("max_", "mx_")
        .replace("min_", "mn_")
        .replace("enable_", "")
        .replace("use_", "")
        .replace("_pips", "p")
        .replace("_bars", "b")
        .replace("_perc", "%")
        .replace("_pct", "%")
    )
    return short


def _build_rows(
    ranked: list[tuple[str, "BacktestResult"]],
    param_keys: list[str],
    dd_limit: float,
) -> str:
    parts: list[str] = []
    for rank, (sym, res) in enumerate(ranked, 1):
        compliant = res.max_drawdown_pct <= dd_limit and res.net_profit > 0
        if compliant:
            row_class = "row-ok"
            badge = '<span class="badge badge-ok">✅ Pass</span>'
        elif res.max_drawdown_pct <= dd_limit * 1.2:
            row_class = "row-warn"
            badge = '<span class="badge badge-warn">⚠️ Marginal</span>'
        else:
            row_class = "row-fail"
            badge = '<span class="badge badge-fail">❌ Fail</span>'

        params_json = json.dumps(res.params, indent=2)
        params_escaped = params_json.replace("`", "\\`").replace("\\", "\\\\")

        param_cells = "".join(
            f"<td>{_fmt_val(res.params.get(k, '—'))}</td>"
            for k in param_keys
        )

        parts.append(f"""
        <tr class="{row_class}" data-score="{res.score:.4f}">
            <td class="rank">#{rank}</td>
            <td class="symbol">{sym}</td>
            <td>{badge}</td>
            <td class="num {'good' if res.score > 0 else ''}">{res.score:.2f}</td>
            <td class="num {'good' if res.profit_factor >= 1.5 else ''}">{res.profit_factor:.2f}</td>
            <td class="num">{res.win_rate:.1f}%</td>
            <td class="num">{res.total_trades}</td>
            <td class="num {'bad' if res.max_drawdown_pct > dd_limit else ''}">{res.max_drawdown_pct:.1f}%</td>
            {param_cells}
            <td>
                <button class="copy-btn" onclick="copyParams(this, `{params_escaped}`)">
                    📋 Copy
                </button>
            </td>
        </tr>""")

    return "\n".join(parts)


def _fmt_val(v) -> str:
    if isinstance(v, float):
        return f"{v:.1f}"
    if isinstance(v, bool):
        return "✓" if v else "✗"
    return str(v)


# ─────────────────────────────────── HTML template ───────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strategy Optimizer Report — {generated_at}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #1c2128;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #7d8590;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
    --blue: #58a6ff;
    --purple: #bc8cff;
    --font: 'Inter', system-ui, sans-serif;
    --mono: 'JetBrains Mono', 'Courier New', monospace;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    line-height: 1.6;
    padding: 24px;
    min-height: 100vh;
  }}

  /* ── Header ── */
  .header {{
    max-width: 1600px;
    margin: 0 auto 32px;
  }}

  .header h1 {{
    font-size: 24px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 4px;
  }}

  .header .subtitle {{
    color: var(--muted);
    font-size: 13px;
  }}

  /* ── Stats banner ── */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    max-width: 1600px;
    margin: 0 auto 32px;
  }}

  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }}

  .stat-card .label {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }}

  .stat-card .value {{
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }}

  .stat-card .value.green {{ color: var(--green); }}
  .stat-card .value.blue  {{ color: var(--blue);  }}

  /* ── Controls ── */
  .controls {{
    max-width: 1600px;
    margin: 0 auto 16px;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }}

  .filter-input {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 8px 14px;
    font-family: var(--font);
    font-size: 13px;
    outline: none;
    width: 220px;
  }}

  .filter-input:focus {{ border-color: var(--blue); }}

  .filter-label {{
    color: var(--muted);
    font-size: 13px;
  }}

  .toggle-btn {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 8px 14px;
    font-family: var(--font);
    font-size: 13px;
    cursor: pointer;
    transition: border-color 0.15s;
  }}

  .toggle-btn:hover, .toggle-btn.active {{
    border-color: var(--blue);
    color: var(--blue);
  }}

  /* ── Table wrapper ── */
  .table-wrap {{
    max-width: 1600px;
    margin: 0 auto;
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 12px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}

  thead {{
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--surface2);
  }}

  th {{
    padding: 12px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    white-space: nowrap;
    border-bottom: 1px solid var(--border);
    user-select: none;
  }}

  th.sortable {{
    cursor: pointer;
    transition: color 0.15s;
  }}

  th.sortable:hover {{ color: var(--blue); }}
  th.sorted-asc::after  {{ content: " ↑"; color: var(--blue); }}
  th.sorted-desc::after {{ content: " ↓"; color: var(--blue); }}

  td {{
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }}

  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: var(--surface2); }}

  /* Row classes */
  tr.row-ok   {{ border-left: 3px solid var(--green);  }}
  tr.row-warn {{ border-left: 3px solid var(--yellow); }}
  tr.row-fail {{ border-left: 3px solid var(--red);    }}

  .rank   {{ color: var(--muted); font-weight: 600; font-size: 12px; }}
  .symbol {{ font-weight: 700; font-size: 14px; color: var(--blue); }}
  .num    {{ font-family: var(--mono); }}
  .num.good {{ color: var(--green); font-weight: 600; }}
  .num.bad  {{ color: var(--red);   font-weight: 600; }}

  /* Badges */
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
  }}
  .badge-ok   {{ background: rgba(63,185,80,.15);  color: var(--green); }}
  .badge-warn {{ background: rgba(210,153,34,.15); color: var(--yellow); }}
  .badge-fail {{ background: rgba(248,81,73,.15);  color: var(--red); }}

  /* Copy button */
  .copy-btn {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--muted);
    padding: 4px 10px;
    font-family: var(--font);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }}

  .copy-btn:hover {{
    border-color: var(--blue);
    color: var(--blue);
  }}

  .copy-btn.copied {{
    border-color: var(--green);
    color: var(--green);
  }}

  /* ── How to apply ── */
  .how-to {{
    max-width: 1600px;
    margin: 40px auto 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
  }}

  .how-to h2 {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--blue);
  }}

  .how-to ol {{
    padding-left: 20px;
    color: var(--muted);
    line-height: 2;
  }}

  .how-to ol li strong {{ color: var(--text); }}

  /* ── Toast ── */
  .toast {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: var(--green);
    color: #000;
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    opacity: 0;
    transform: translateY(8px);
    transition: all 0.2s;
    pointer-events: none;
  }}

  .toast.show {{
    opacity: 1;
    transform: translateY(0);
  }}
</style>
</head>
<body>

<div class="header">
  <h1>📊 Strategy Optimizer Report</h1>
  <p class="subtitle">Generated {generated_at} · Prop-firm DD limit: {dd_limit}% · Calmar scoring</p>
</div>

<div class="stats-grid">
  <div class="stat-card">
    <div class="label">Pairs Optimized</div>
    <div class="value blue">{total_pairs}</div>
  </div>
  <div class="stat-card">
    <div class="label">Prop-Firm Compliant</div>
    <div class="value green">{compliant_count} / {total_pairs}</div>
  </div>
  <div class="stat-card">
    <div class="label">DD Limit</div>
    <div class="value">{dd_limit}%</div>
  </div>
  <div class="stat-card">
    <div class="label">Best Score</div>
    <div class="value green">{best_score}</div>
  </div>
  <div class="stat-card">
    <div class="label">Best Pair</div>
    <div class="value blue">{best_pair}</div>
  </div>
</div>

<div class="controls">
  <input class="filter-input" id="filterInput" placeholder="🔍  Filter by pair name..." oninput="filterRows()">
  <span class="filter-label">Show:</span>
  <button class="toggle-btn active" id="btnAll" onclick="filterCompliance('all')">All</button>
  <button class="toggle-btn" id="btnOk" onclick="filterCompliance('ok')">✅ Compliant only</button>
  <button class="toggle-btn" id="btnFail" onclick="filterCompliance('fail')">❌ Non-compliant</button>
</div>

<div class="table-wrap">
  <table id="resultsTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)" class="sortable">#</th>
        <th onclick="sortTable(1)" class="sortable">Pair</th>
        <th>Prop Firm</th>
        <th onclick="sortTable(3)" class="sortable">Score</th>
        <th onclick="sortTable(4)" class="sortable">PF</th>
        <th onclick="sortTable(5)" class="sortable">Win Rate</th>
        <th onclick="sortTable(6)" class="sortable">Trades</th>
        <th onclick="sortTable(7)" class="sortable">Max DD%</th>
        {param_headers}
        <th>Params</th>
      </tr>
    </thead>
    <tbody id="tableBody">
      {rows}
    </tbody>
  </table>
</div>

<div class="how-to">
  <h2>📋 How to Apply in TradingView</h2>
  <ol>
    <li><strong>Click "📋 Copy"</strong> next to the pair you want to configure — params are copied to clipboard as JSON.</li>
    <li>Open <strong>TradingView</strong> and navigate to the chart for that pair.</li>
    <li><strong>Double-click "S&amp;D Algo [Pro]"</strong> in the legend to open the settings dialog.</li>
    <li>Click the <strong>"Inputs" tab</strong> inside the dialog.</li>
    <li>Set each parameter shown in the JSON to the corresponding input field.</li>
    <li>Click <strong>OK</strong> and wait for the strategy to recalculate.</li>
    <li>Verify the backtest results match what this report shows.</li>
  </ol>
</div>

<div class="toast" id="toast">✅ Params copied to clipboard!</div>

<script>
  const allParamKeys = {all_param_keys_json};
  let currentFilter = 'all';
  let sortCol = 3;
  let sortAsc = false;

  function copyParams(btn, paramsStr) {{
    navigator.clipboard.writeText(paramsStr).then(() => {{
      btn.textContent = '✅ Copied';
      btn.classList.add('copied');
      showToast();
      setTimeout(() => {{
        btn.textContent = '📋 Copy';
        btn.classList.remove('copied');
      }}, 2000);
    }});
  }}

  function showToast() {{
    const t = document.getElementById('toast');
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2500);
  }}

  function filterRows() {{
    const q = document.getElementById('filterInput').value.toLowerCase();
    const rows = document.querySelectorAll('#tableBody tr');
    rows.forEach(row => {{
      const sym = row.querySelector('.symbol')?.textContent.toLowerCase() || '';
      const complianceMatch =
        currentFilter === 'all' ? true :
        currentFilter === 'ok'  ? row.classList.contains('row-ok') :
        !row.classList.contains('row-ok');
      row.style.display = sym.includes(q) && complianceMatch ? '' : 'none';
    }});
  }}

  function filterCompliance(mode) {{
    currentFilter = mode;
    ['btnAll','btnOk','btnFail'].forEach(id => document.getElementById(id).classList.remove('active'));
    document.getElementById('btn' + mode.charAt(0).toUpperCase() + mode.slice(1)).classList.add('active');
    filterRows();
  }}

  function sortTable(col) {{
    const tbody = document.getElementById('tableBody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    if (sortCol === col) sortAsc = !sortAsc;
    else {{ sortCol = col; sortAsc = false; }}

    rows.sort((a, b) => {{
      const aVal = a.cells[col]?.textContent.replace(/[^0-9.\-]/g, '') || '';
      const bVal = b.cells[col]?.textContent.replace(/[^0-9.\-]/g, '') || '';
      const aNum = parseFloat(aVal);
      const bNum = parseFloat(bVal);
      const cmp = isNaN(aNum) || isNaN(bNum)
        ? aVal.localeCompare(bVal)
        : aNum - bNum;
      return sortAsc ? cmp : -cmp;
    }});

    // Update sort indicators
    document.querySelectorAll('th').forEach((th, i) => {{
      th.classList.remove('sorted-asc', 'sorted-desc');
      if (i === col) th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
    }});

    rows.forEach(r => tbody.appendChild(r));
  }}
</script>
</body>
</html>
"""

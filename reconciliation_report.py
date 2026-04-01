"""
HTML report generator — runs reconciliation and writes a self-contained
report.html that can be opened directly in any browser. No dependencies.
Run: python3 reconciliation_report.py
Then open: reconciliation_report.html
"""

import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from reconciliation_system import (
    generate_platform_transactions,
    generate_bank_settlements,
    reconcile,
)

# ── run the engine ────────────────────────────────────────────────────────────
txns        = generate_platform_transactions(30)
settlements = generate_bank_settlements(txns)
result      = reconcile(txns, settlements)

eligible  = [t for t in txns if t.status in ("SUCCESS", "REFUND")]
failed    = [t for t in txns if t.status == "FAILED"]
plat_amt  = round(sum(t.amount for t in eligible), 2)
bank_amt  = round(sum(s.settled_amount for s in settlements
                       if not s.txn_id.startswith("TXN_PHANTOM")), 2)
net_diff  = round(plat_amt - bank_amt, 2)

summary = {
    "total_platform":   len(txns),
    "eligible":         len(eligible),
    "failed_excluded":  len(failed),
    "bank_records":     len(settlements),
    "platform_amount":  plat_amt,
    "bank_amount":      bank_amt,
    "net_difference":   net_diff,
    "matched":          len(result.matched),
    "rounding":         len(result.rounding_differences),
    "mismatches":       len(result.amount_mismatches),
    "unsettled":        len(result.unmatched_platform),
    "phantom":          len(result.unmatched_bank),
    "duplicates":       len(result.duplicates),
}

data = {
    "summary":   summary,
    "matched":   result.matched,
    "rounding":  result.rounding_differences,
    "mismatches":result.amount_mismatches,
    "unsettled": result.unmatched_platform,
    "phantom":   result.unmatched_bank,
    "duplicates":result.duplicates,
}

# ── HTML template ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reconciliation Report — June 2024</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:       #f7f6f3;
    --surface:  #ffffff;
    --border:   #e4e2da;
    --text:     #1a1a18;
    --muted:    #6b6b67;
    --hint:     #a0a09a;
    --green:    #1d9e75;  --green-bg:  #e1f5ee;  --green-t:  #085041;
    --amber:    #ba7517;  --amber-bg:  #faeeda;  --amber-t:  #412402;
    --red:      #e24b4a;  --red-bg:    #fcebeb;  --red-t:    #501313;
    --blue:     #378add;  --blue-bg:   #e6f1fb;  --blue-t:   #042c53;
    --purple:   #7f77dd;  --purple-bg: #eeedfe;  --purple-t: #26215c;
    --gray-bg:  #f1efe8;  --gray-t:    #2c2c2a;
    --radius:   10px;
    --radius-sm: 6px;
  }
  body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg);
         color: var(--text); font-size: 14px; line-height: 1.6; padding: 32px 20px; }
  h1   { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  h2   { font-size: 13px; font-weight: 500; color: var(--muted);
         text-transform: uppercase; letter-spacing: .05em; margin-bottom: 12px; }
  .page { max-width: 960px; margin: 0 auto; }
  .header { margin-bottom: 28px; }
  .header p { color: var(--muted); font-size: 13px; margin-top: 2px; }

  /* summary cards */
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px,1fr));
           gap: 10px; margin-bottom: 28px; }
  .card  { background: var(--surface); border: 0.5px solid var(--border);
           border-radius: var(--radius); padding: 14px 16px; }
  .card .num   { font-size: 26px; font-weight: 600; line-height: 1.1; }
  .card .label { font-size: 12px; color: var(--muted); margin-top: 3px; }
  .card.c-green  { background: var(--green-bg);  border-color: transparent; }
  .card.c-green  .num { color: var(--green-t); }
  .card.c-amber  { background: var(--amber-bg);  border-color: transparent; }
  .card.c-amber  .num { color: var(--amber-t); }
  .card.c-red    { background: var(--red-bg);    border-color: transparent; }
  .card.c-red    .num { color: var(--red-t); }
  .card.c-purple { background: var(--purple-bg); border-color: transparent; }
  .card.c-purple .num { color: var(--purple-t); }
  .card.c-blue   { background: var(--blue-bg);   border-color: transparent; }
  .card.c-blue   .num { color: var(--blue-t); }

  /* amount banner */
  .amounts { display: grid; grid-template-columns: 1fr 1fr 1fr;
             gap: 10px; margin-bottom: 28px; }
  .amt-card { background: var(--surface); border: 0.5px solid var(--border);
              border-radius: var(--radius); padding: 14px 16px; }
  .amt-card .lbl { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
  .amt-card .val { font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .amt-card.diff .val { color: var(--red); }

  /* section blocks */
  .section { background: var(--surface); border: 0.5px solid var(--border);
             border-radius: var(--radius); margin-bottom: 16px; overflow: hidden; }
  .sec-head { display: flex; align-items: center; justify-content: space-between;
              padding: 12px 16px; cursor: pointer; user-select: none;
              border-bottom: 0.5px solid var(--border); }
  .sec-head:hover { background: var(--bg); }
  .sec-title { display: flex; align-items: center; gap: 10px; font-weight: 500; font-size: 14px; }
  .sec-badge { font-size: 11px; font-weight: 600; padding: 2px 8px;
               border-radius: 20px; }
  .bg-green  { background: var(--green-bg);  color: var(--green-t); }
  .bg-amber  { background: var(--amber-bg);  color: var(--amber-t); }
  .bg-red    { background: var(--red-bg);    color: var(--red-t); }
  .bg-purple { background: var(--purple-bg); color: var(--purple-t); }
  .bg-blue   { background: var(--blue-bg);   color: var(--blue-t); }
  .bg-gray   { background: var(--gray-bg);   color: var(--gray-t); }
  .chevron   { font-size: 12px; color: var(--hint); transition: transform .2s; }
  .chevron.open { transform: rotate(180deg); }
  .sec-body  { overflow-x: auto; }

  /* tables */
  table  { width: 100%; border-collapse: collapse; font-size: 13px; }
  th     { text-align: left; padding: 8px 14px; font-size: 11px; font-weight: 600;
           color: var(--muted); text-transform: uppercase; letter-spacing: .04em;
           border-bottom: 0.5px solid var(--border); white-space: nowrap;
           background: var(--bg); }
  td     { padding: 9px 14px; border-bottom: 0.5px solid var(--border);
           white-space: nowrap; font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--bg); }
  .mono  { font-family: ui-monospace, monospace; font-size: 12px; }
  .right { text-align: right; }
  .diff-pos { color: var(--green); font-weight: 500; }
  .diff-neg { color: var(--red);   font-weight: 500; }
  .diff-neu { color: var(--amber); font-weight: 500; }
  .empty { padding: 20px 16px; color: var(--hint); font-size: 13px; font-style: italic; }

  /* status pill */
  .pill { display: inline-block; font-size: 11px; font-weight: 600;
          padding: 1px 7px; border-radius: 20px; }

  @media (max-width: 600px) {
    .amounts { grid-template-columns: 1fr; }
    .cards   { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <h1>Payment Reconciliation Report</h1>
    <p>Platform vs Bank &nbsp;·&nbsp; June 2024 &nbsp;·&nbsp; Generated by reconciliation_system.py</p>
  </div>

  <!-- ── SUMMARY CARDS ── -->
  <h2>Overview</h2>
  <div class="cards" id="cards"></div>

  <!-- ── AMOUNT BANNER ── -->
  <div class="amounts" id="amounts"></div>

  <!-- ── DETAIL SECTIONS ── -->
  <h2>Detailed results</h2>
  <div id="sections"></div>

</div>

<script>
const D = __DATA__;

/* ── helpers ──────────────────────────────────────────────────────────────── */
const fmt = n => {
  const v = parseFloat(n);
  return isNaN(v) ? (n || '—') : '₹\u202f' + v.toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2});
};
const fmtDiff = (n, el) => {
  const v = parseFloat(n);
  if (isNaN(v)) return;
  el.textContent = fmt(Math.abs(v));
  el.className += v > 0.05 ? ' diff-neg' : v < -0.05 ? ' diff-pos' : ' diff-neu';
};
const pill = (txt, cls) => `<span class="pill ${cls}">${txt}</span>`;
const toggle = id => {
  const body = document.getElementById('body-' + id);
  const chev = document.getElementById('chev-' + id);
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : '';
  chev.classList.toggle('open', !open);
};

/* ── summary cards ────────────────────────────────────────────────────────── */
const s = D.summary;
const cardDefs = [
  { num: s.matched,          label: 'Matched',           cls: 'c-green'  },
  { num: s.rounding,         label: 'Rounding diffs',    cls: 'c-amber'  },
  { num: s.mismatches,       label: 'Mismatches',        cls: 'c-red'    },
  { num: s.unsettled,        label: 'Unsettled',         cls: 'c-red'    },
  { num: s.phantom,          label: 'Phantom entries',   cls: 'c-purple' },
  { num: s.duplicates,       label: 'Duplicates',        cls: 'c-blue'   },
  { num: s.eligible,         label: 'Eligible txns',     cls: ''         },
  { num: s.failed_excluded,  label: 'Failed (excluded)', cls: ''         },
];
document.getElementById('cards').innerHTML = cardDefs.map(c =>
  `<div class="card ${c.cls}"><div class="num">${c.num}</div><div class="label">${c.label}</div></div>`
).join('');

/* ── amount banner ────────────────────────────────────────────────────────── */
document.getElementById('amounts').innerHTML = `
  <div class="amt-card"><div class="lbl">Platform eligible amount</div>
    <div class="val">${fmt(s.platform_amount)}</div></div>
  <div class="amt-card"><div class="lbl">Total bank settled amount</div>
    <div class="val">${fmt(s.bank_amount)}</div></div>
  <div class="amt-card diff"><div class="lbl">Net difference</div>
    <div class="val">${fmt(s.net_difference)}</div></div>
`;

/* ── table builder ────────────────────────────────────────────────────────── */
function buildTable(rows, cols) {
  if (!rows.length) return `<div class="empty">No records in this category.</div>`;
  const head = `<tr>${cols.map(c => `<th>${c.label}</th>`).join('')}</tr>`;
  const body = rows.map(row => {
    const cells = cols.map(c => {
      const v = row[c.key];
      if (c.key === 'difference') {
        return `<td class="right"><span id="d_${Math.random().toString(36).slice(2)}" data-diff="${v}"></span></td>`;
      }
      if (c.fmt === 'money') return `<td class="right">${fmt(v)}</td>`;
      if (c.fmt === 'mono')  return `<td class="mono">${v ?? '—'}</td>`;
      return `<td>${v ?? '—'}</td>`;
    }).join('');
    return `<tr>${cells}</tr>`;
  }).join('');
  return `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

/* ── section definitions ──────────────────────────────────────────────────── */
const sections = [
  {
    id: 'matched', title: 'Matched transactions', badge: s.matched,
    badgeCls: 'bg-green', defaultOpen: false,
    rows: D.matched,
    cols: [
      { key:'txn_id',          label:'TXN ID',           fmt:'mono' },
      { key:'merchant_id',     label:'Merchant'                     },
      { key:'platform_amount', label:'Platform amt',     fmt:'money' },
      { key:'settled_amount',  label:'Settled amt',      fmt:'money' },
      { key:'platform_date',   label:'Txn date'                     },
      { key:'settlement_date', label:'Settled date'                  },
      { key:'bank_ref',        label:'Bank ref',         fmt:'mono' },
    ]
  },
  {
    id: 'mismatches', title: 'Amount mismatches', badge: s.mismatches,
    badgeCls: 'bg-red', defaultOpen: true,
    rows: D.mismatches,
    cols: [
      { key:'txn_id',          label:'TXN ID',       fmt:'mono'  },
      { key:'merchant_id',     label:'Merchant'                  },
      { key:'platform_amount', label:'Platform amt',  fmt:'money' },
      { key:'settled_amount',  label:'Settled amt',   fmt:'money' },
      { key:'difference',      label:'Difference'                },
      { key:'bank_ref',        label:'Bank ref',      fmt:'mono'  },
      { key:'issue',           label:'Note'                      },
    ]
  },
  {
    id: 'unsettled', title: 'Unsettled platform transactions', badge: s.unsettled,
    badgeCls: 'bg-red', defaultOpen: true,
    rows: D.unsettled,
    cols: [
      { key:'txn_id',          label:'TXN ID',       fmt:'mono'  },
      { key:'merchant_id',     label:'Merchant'                  },
      { key:'platform_amount', label:'Amount',        fmt:'money' },
      { key:'platform_date',   label:'Txn date'                  },
      { key:'issue',           label:'Note'                      },
    ]
  },
  {
    id: 'phantom', title: 'Phantom bank entries', badge: s.phantom,
    badgeCls: 'bg-purple', defaultOpen: true,
    rows: D.phantom,
    cols: [
      { key:'bank_ref',        label:'Bank ref',      fmt:'mono'  },
      { key:'txn_id',          label:'TXN ID',        fmt:'mono'  },
      { key:'settled_amount',  label:'Amount',        fmt:'money' },
      { key:'settlement_date', label:'Settled date'              },
      { key:'issue',           label:'Note'                      },
    ]
  },
  {
    id: 'duplicates', title: 'Duplicate settlements', badge: s.duplicates,
    badgeCls: 'bg-blue', defaultOpen: true,
    rows: D.duplicates,
    cols: [
      { key:'txn_id',           label:'TXN ID',        fmt:'mono'  },
      { key:'merchant_id',      label:'Merchant'                   },
      { key:'platform_amount',  label:'Platform amt',  fmt:'money' },
      { key:'settlement_count', label:'# settlements'             },
      { key:'total_settled',    label:'Total settled', fmt:'money' },
      { key:'bank_refs',        label:'Bank refs',     fmt:'mono'  },
    ]
  },
  {
    id: 'rounding', title: 'Rounding differences (within ₹0.05)', badge: s.rounding,
    badgeCls: 'bg-amber', defaultOpen: false,
    rows: D.rounding,
    cols: [
      { key:'txn_id',          label:'TXN ID',       fmt:'mono'  },
      { key:'merchant_id',     label:'Merchant'                  },
      { key:'platform_amount', label:'Platform amt',  fmt:'money' },
      { key:'settled_amount',  label:'Settled amt',   fmt:'money' },
      { key:'difference',      label:'Difference'                },
      { key:'bank_ref',        label:'Bank ref',      fmt:'mono'  },
    ]
  },
];

const container = document.getElementById('sections');
sections.forEach(sec => {
  const div = document.createElement('div');
  div.className = 'section';
  div.innerHTML = `
    <div class="sec-head" onclick="toggle('${sec.id}')">
      <div class="sec-title">
        <span>${sec.title}</span>
        <span class="sec-badge ${sec.badgeCls}">${sec.badge}</span>
      </div>
      <span class="chevron ${sec.defaultOpen ? 'open' : ''}" id="chev-${sec.id}">▼</span>
    </div>
    <div class="sec-body" id="body-${sec.id}" style="display:${sec.defaultOpen ? '' : 'none'}">
      ${buildTable(sec.rows, sec.cols)}
    </div>`;
  container.appendChild(div);
});

/* ── apply difference colouring after render ─────────────────────────────── */
document.querySelectorAll('[data-diff]').forEach(el => {
  fmtDiff(el.dataset.diff, el);
});
</script>
</body>
</html>
"""

# ── inject data and write file ────────────────────────────────────────────────
html = HTML.replace('__DATA__', json.dumps(data, default=str))
out  = "reconciliation_report.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n  Report written to:  {out}")
print(f"  Open it in any browser — no server needed.\n")
print(f"  Summary:")
print(f"    Matched        : {summary['matched']}")
print(f"    Mismatches     : {summary['mismatches']}")
print(f"    Unsettled      : {summary['unsettled']}")
print(f"    Phantom        : {summary['phantom']}")
print(f"    Duplicates     : {summary['duplicates']}")
print(f"    Rounding diffs : {summary['rounding']}")

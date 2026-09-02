// Demo UI for the BNR Exchange Rate API.
// API base: same origin when served by the app at /demo; override with ?api=https://host
// when hosting the page separately from the API.
const API_BASE = new URLSearchParams(location.search).get("api") || "";

const $ = (id) => document.getElementById(id);
const els = {
  amount: $("amount"),
  from: $("from"),
  to: $("to"),
  swap: $("swap"),
  result: $("result"),
  asOf: $("as-of"),
  base: $("base"),
  body: $("rates-body"),
};

let currencies = {}; // code -> name

async function api(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function fmt(n) {
  if (n === undefined || n === null) return "—";
  const abs = Math.abs(n);
  const digits = abs !== 0 && abs < 1 ? 6 : 2;
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function fillSelect(select, selected) {
  select.innerHTML = "";
  for (const [code, name] of Object.entries(currencies)) {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${code} — ${name}`;
    if (code === selected) opt.selected = true;
    select.append(opt);
  }
}

async function convert() {
  const amount = parseFloat(els.amount.value || "0");
  const from = els.from.value;
  const to = els.to.value;
  if (!from || !to || !(amount >= 0)) return;
  els.result.textContent = "…";
  try {
    const data = await api(`/latest?base=${from}&symbols=${to}&amount=${amount}`);
    const value = data.rates[to];
    els.result.textContent = `${fmt(amount)} ${from} = ${fmt(value)} ${to}`;
    els.asOf.textContent = `Rate as of ${data.date} (BNR reference/mid rate)`;
  } catch (err) {
    els.result.innerHTML = `<span class="error">Could not load rate (${err.message})</span>`;
  }
}

async function loadTable() {
  const base = els.base.value || "RWF";
  els.body.innerHTML = `<tr><td colspan="3" class="muted">Loading…</td></tr>`;
  try {
    const data = await api(`/latest?base=${base}`);
    const rows = Object.entries(data.rates).sort((a, b) => a[0].localeCompare(b[0]));
    els.body.innerHTML = "";
    for (const [code, rate] of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${currencies[code] || code}</td>` +
        `<td><span class="code-badge">${code}</span></td>` +
        `<td class="num">${fmt(rate)}</td>`;
      els.body.append(tr);
    }
  } catch (err) {
    els.body.innerHTML = `<tr><td colspan="3" class="error">Could not load rates (${err.message})</td></tr>`;
  }
}

function swap() {
  const a = els.from.value;
  els.from.value = els.to.value;
  els.to.value = a;
  convert();
}

async function init() {
  try {
    currencies = await api("/currencies");
  } catch (err) {
    els.result.innerHTML = `<span class="error">API unavailable (${err.message})</span>`;
    return;
  }
  fillSelect(els.from, "USD");
  fillSelect(els.to, "RWF");
  fillSelect(els.base, "RWF");

  els.amount.addEventListener("input", convert);
  els.from.addEventListener("change", convert);
  els.to.addEventListener("change", convert);
  els.swap.addEventListener("click", swap);
  els.base.addEventListener("change", loadTable);

  convert();
  loadTable();
}

init();

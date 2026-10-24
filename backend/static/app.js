/* TrustSphere AI web app: Analyze, report, History, How it works. No dependencies. */
"use strict";
const $ = (s, r) => (r || document).querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x, d = 0) => (x == null ? "n/a" : (x * 100).toFixed(d) + "%");
const AUTH = 0.75, FAKE = 0.40;   // decision-engine thresholds (core/decision_engine.py)

async function api(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (e) { /* not JSON */ }
  if (!r.ok) throw new Error((body && (body.detail || body.message)) || `${r.status} ${r.statusText}`);
  return body;
}

/* ───────────── header badges ───────────── */
async function loadBadges() {
  const el = $("#badges");
  try {
    await api("/health");
    const list = await api("/api/evidence?limit=500");
    el.innerHTML = `<span class="badge ok">backend online</span><span class="badge">${list.length} analys${list.length === 1 ? "is" : "es"} stored</span>`;
  } catch (e) { el.innerHTML = '<span class="badge bad">backend unreachable</span>'; }
}

/* ───────────── helpers ───────────── */
const AGENTS = {
  metadata: ["Metadata", "EXIF fields, editing or generator software tags, timestamp and GPS anomalies."],
  image_forensics: ["Image forensics", "A trained EfficientNet-B0 detector on multi-quality error-level maps; ELA, frequency analysis and Grad-CAM are shown as supporting evidence."],
  security: ["Provenance (C2PA and watermark)", "Content-credential validation and invisible AI-generator watermark detection."],
};
const agentName = (n) => (AGENTS[n] ? AGENTS[n][0] : n);
const urlOf = (p) => (p ? "/" + String(p).replace(/\\/g, "/").replace(/^\.?\//, "") : null);
// The database stores some timestamps without a zone; they are UTC, so say so before parsing.
const when = (iso) => { try { const z = /(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : iso + "Z"; return new Date(z).toLocaleString(); } catch (e) { return iso || ""; } };
const extOf = (name) => { const m = /\.[A-Za-z0-9]{1,8}$/.exec(name || ""); return m ? m[0] : ""; };
const evidenceUrl = (r) => esc(`/uploads/${r.file_hash}${extOf(r.filename)}`);

function gaugeSvg(score01) {
  const score = Math.max(0, Math.min(1, score01 ?? 0)) * 100;
  const cx = 150, cy = 140, r = 112;
  const pt = (s, rad = r) => { const a = Math.PI * (1 - s / 100); return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)]; };
  const arc = (a, b, col) => { const [x0, y0] = pt(a), [x1, y1] = pt(b);
    return `<path d="M${x0.toFixed(1)} ${y0.toFixed(1)} A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}" fill="none" stroke="${col}" stroke-width="20"/>`; };
  const [nx, ny] = pt(score, r - 30);
  return `<svg class="gauge" viewBox="0 0 300 175" role="img" aria-label="Authenticity score ${score.toFixed(0)} out of 100">
    ${arc(0, FAKE * 100, "#c0392b")}${arc(FAKE * 100, AUTH * 100, "#d9a21b")}${arc(AUTH * 100, 100, "#1a8f4c")}
    <line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="8" fill="currentColor"/>
    <text x="${cx}" y="${cy + 30}" text-anchor="middle" font-size="30" font-weight="800" style="fill:currentColor">${score.toFixed(1)}</text>
    <text x="22" y="164" font-size="11" fill="#6b7a90">0</text><text x="${cx - 8}" y="22" font-size="11" fill="#6b7a90">50</text><text x="268" y="164" font-size="11" fill="#6b7a90">100</text>
  </svg>`;
}

/* ───────────── Analyze page ───────────── */
const STAGES = [
  ["Upload and hash", "SHA-256 of the exact bytes; the original is kept as evidence."],
  ["Forensic agents", "Metadata, image forensics and provenance run on the file."],
  ["Decision engine", "Agent scores are weighted and fused into one verdict."],
  ["Sign", "Ed25519 signature over the canonical record."],
  ["Anchor", "Verdict and file hash written to the Polygon Amoy contract when configured."],
];
const ACCEPT = ".jpg,.jpeg,.png,.webp,.gif,.bmp,.tif,.tiff";

function stageHtml(states) {
  return `<ol class="stages">${STAGES.map((s, i) => `<li class="${states[i] || ""}"><div class="n">${states[i] === "done" ? "&#10003;" : i + 1}</div>
    <div><b>${s[0]}</b><span>${s[1]}</span></div></li>`).join("")}</ol>`;
}

function analyzePage() {
  $("#view").innerHTML = `
  <div class="page-head"><div class="eyebrow">Analyze</div>
    <h1>Is this file authentic or manipulated?</h1>
    <p>Upload an image. Independent forensic agents score it, a decision engine fuses the scores into a
    verdict, and the record is hashed, signed and, when configured, anchored on a public blockchain.</p></div>
  <div class="grid g-upload">
    <section class="card">
      <div class="eyebrow">Input</div>
      <div class="drop" id="drop" tabindex="0" role="button" aria-label="Choose a file">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 16V4m0 0L7 9m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></svg>
        <div style="margin-top:8px"><b>Choose a file</b> or drop it here</div>
        <div class="small muted">Maximum 100 MB</div>
        <input id="file" type="file" accept="${ACCEPT}" hidden>
      </div>
      <div class="types">
        <span class="chip">JPG</span><span class="chip">PNG</span><span class="chip">WebP</span><span class="chip">GIF</span><span class="chip">BMP</span><span class="chip">TIFF</span>
      </div>
      <div class="preview hidden" id="preview"><img id="prevImg" alt="" class="hidden"><div class="meta" id="fileNote"></div></div>
      <div style="margin-top:16px"><button class="btn" id="run" disabled>Run analysis</button></div>
      <div id="err" class="err hidden" style="margin-top:14px"></div>
    </section>
    <section class="card">
      <div class="eyebrow">Pipeline</div><h2>Analysis stages</h2>
      <p class="small muted" style="margin-top:0">A stage is marked complete only after the backend confirms it in the finished record.</p>
      <div id="stages">${stageHtml([])}</div>
      <div class="elapsed hidden" id="elapsed"></div>
    </section>
  </div>`;
  const drop = $("#drop"), file = $("#file"), run = $("#run");
  let chosen = null;
  const pick = (f) => {
    if (!f) return;
    chosen = f; run.disabled = false; $("#err").classList.add("hidden");
    $("#preview").classList.remove("hidden");
    $("#fileNote").innerHTML = `<b>${esc(f.name)}</b><br>${(f.size / 1024).toFixed(0)} KB &middot; ${esc(f.type || "unknown type")}`;
    const img = $("#prevImg");
    if (f.type.startsWith("image/")) { img.src = URL.createObjectURL(f); img.classList.remove("hidden"); } else img.classList.add("hidden");
  };
  drop.onclick = () => file.click();
  drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); file.click(); } };
  file.onchange = () => pick(file.files[0]);
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("drag"); }));
  drop.addEventListener("drop", (e) => pick(e.dataTransfer.files[0]));
  run.onclick = () => startAnalysis(chosen);
}

async function startAnalysis(f) {
  const run = $("#run"), err = $("#err"), el = $("#elapsed");
  run.disabled = true; err.classList.add("hidden");
  $("#stages").innerHTML = stageHtml(["run"]);
  el.classList.remove("hidden");
  const t0 = performance.now();
  const timer = setInterval(() => { el.textContent = `Analyzing... ${((performance.now() - t0) / 1000).toFixed(0)} s`; }, 250);
  try {
    const fd = new FormData(); fd.append("file", f);
    const up = await api("/api/upload", { method: "POST", body: fd });
    $("#stages").innerHTML = stageHtml(["done", "run"]);
    // The backend may finish before the upload call returns (inline mode) or after it (worker mode): poll either way.
    let status = "pending";
    for (let i = 0; i < 900; i++) {
      status = (await api(`/api/status/${up.file_id}`)).status;
      if (status === "done" || status === "failed") break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    if (status !== "done") throw new Error(`Analysis ${status}. Check the server window for the reason.`);
    $("#stages").innerHTML = stageHtml(["done", "done", "done", "done", "done"]);
    el.textContent = `Finished in ${((performance.now() - t0) / 1000).toFixed(1)} s`;
    location.hash = `#/report/${up.file_id}`;
  } catch (e) {
    $("#stages").innerHTML = stageHtml(["bad"]);
    err.textContent = e.message; err.classList.remove("hidden"); run.disabled = false;
  } finally { clearInterval(timer); loadBadges(); }
}

/* ───────────── Report page ───────────── */
function findingsTable(a) {
  if (!a.findings || !a.findings.length) return '<div class="muted small">No findings recorded.</div>';
  return `<table class="f">${a.findings.map((f) => `<tr><td>${esc(f.check)}</td><td><span class="pill ${esc(f.status)}">${esc(f.status)}</span></td>
    <td>${esc(f.note)}</td><td>${f.score == null ? "" : Number(f.score).toFixed(2)}</td></tr>`).join("")}</table>`;
}

function importanceChart(items) {
  if (!items || !items.length) return "";
  const max = Math.max(...items.map((i) => Math.abs(i.contribution || 0)), 0.0001);
  return `<div class="fi"><h3 style="font-size:14px">What moved the score (Shapley contribution)</h3>${items.map((i) => {
    const w = Math.min(50, (Math.abs(i.contribution || 0) / max) * 50);
    const side = (i.contribution || 0) >= 0 ? "authentic" : "fake";
    return `<div class="fi-row" title="${esc(i.note)}"><span>${esc(i.feature)}</span>
      <div class="fi-track"><div class="fi-bar ${side}" style="width:${w}%"></div></div>
      <span class="mono small">${(i.contribution >= 0 ? "+" : "") + Number(i.contribution || 0).toFixed(3)}</span></div>`;
  }).join("")}<div class="small muted" style="margin-top:4px">Right = pushes towards authentic, left = towards fake.</div></div>`;
}

function agentCard(a, rep) {
  const meta = AGENTS[a.agent_name] || [a.agent_name, ""];
  const ex = a.extras || {};
  const conf = a.confidence_score;
  let body = "";
  const figs = [];
  if (rep.file_type === "image" && a.agent_name === "image_forensics") {
    figs.push(`<figure><img src="${evidenceUrl(rep)}" alt="Submitted image"><figcaption><b>Input</b><br>The submitted file.</figcaption></figure>`);
    if (a.heatmap_path) figs.push(`<figure><img src="${esc(urlOf(a.heatmap_path))}" alt="Error level analysis"><figcaption><b>Error-level analysis</b><br>Brighter areas recompress differently from the rest of the image.</figcaption></figure>`);
    if (ex.gradcam_path) figs.push(`<figure><img src="${esc(urlOf(ex.gradcam_path))}" alt="Model attention"><figcaption><b>Model attention (${esc(ex.gradcam_method || "Grad-CAM")})</b><br>Where the deep classifier looked.</figcaption></figure>`);
  }
  if (figs.length) body += `<div class="figs">${figs.join("")}</div>`;
  body += findingsTable(a);
  if (ex.deep_predictions && ex.deep_predictions.length)
    body += `<div class="small muted" style="margin-top:8px">Classifier output: ${ex.deep_predictions.map((p) => `${esc(p.label)} ${pct(p.score, 1)}`).join(" &middot; ")}</div>`;
  body += importanceChart(ex.feature_importance);
  return `<div class="agent"><div class="agent-h"><h3>${esc(meta[0])}</h3>
      ${conf == null ? '<span class="excl">no authenticity signal (excluded from the weighted verdict)</span>' : `<span class="pill neutral">authenticity ${pct(conf, 1)}</span>`}</div>
    <div class="small muted">${esc(meta[1])}</div>
    ${conf == null ? "" : `<div class="bar"><i style="left:${Math.max(0, Math.min(100, conf * 100))}%"></i></div>`}${body}</div>`;
}

function chainCard(label, status, cls, detail) {
  return `<div><small>${label}</small><div class="st ${cls}">${esc(status)}</div>${detail}</div>`;
}

async function reportPage(id) {
  $("#view").innerHTML = '<div class="card"><div class="muted">Loading report&hellip;</div></div>';
  let rep, ver = null;
  try { rep = await api(`/api/report/${encodeURIComponent(id)}`); }
  catch (e) { $("#view").innerHTML = `<div class="err">${esc(e.message)}</div><p><a href="#/history">Back to history</a></p>`; return; }
  try { ver = await api(`/api/verify/${encodeURIComponent(id)}`); } catch (e) { /* shown as unavailable */ }
  const v = rep.verdict, label = v.label || "Inconclusive";
  const why = (v.reasoning || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const custody = ((rep.audit && rep.audit.chain_of_custody) || []).map((c) => `<li><b>${esc(c.event.replace(/_/g, " "))}</b><div class="small muted">${esc(when(c.timestamp))}${c.key_fingerprint ? " &middot; key " + esc(c.key_fingerprint.slice(0, 12)) + "&hellip;" : ""}${c.tx_hash ? " &middot; tx " + esc(c.tx_hash.slice(0, 12)) + "&hellip;" : ""}</div></li>`).join("");
  const anchor = ver ? ver.blockchain_anchor : null;
  $("#view").innerHTML = `
  <div class="page-head"><div class="eyebrow">Report</div><h1>${esc(rep.filename)}</h1>
    <p class="small muted mono">${esc(rep.file_id)} &middot; ${esc(rep.file_type)} &middot; uploaded ${esc(when(rep.upload_time))}</p></div>
  <section class="card"><div class="eyebrow">Verdict</div>
    <div class="verdict"><div>${gaugeSvg(v.overall_score)}<div class="small muted" style="text-align:center">Authenticity score (0 = fake, 100 = authentic)</div></div>
      <div><div class="v-title ${esc(label)}">${esc(label)}</div>
        <div><span class="pill ${esc(label)}">${esc(label)}</span>${v.manipulation_type ? `<span class="pill neutral">${esc(v.manipulation_type)}</span>` : ""}</div>
        <dl class="kv">
          <dt>Authenticity</dt><dd>${v.overall_score == null ? "n/a" : v.overall_score.toFixed(3)} &middot; Authentic at or above ${AUTH}, Fake at or below ${FAKE}, otherwise Inconclusive</dd>
          ${v.manipulation_type ? `<dt>Manipulation</dt><dd>${esc(v.manipulation_type)} (confidence ${pct(v.manipulation_confidence)})</dd>` : ""}
          ${v.gan_attribution ? `<dt>Generator family</dt><dd>${esc(v.gan_attribution)} (confidence ${pct(v.gan_confidence)})</dd>` : ""}
          <dt>SHA-256</dt><dd class="mono small" style="word-break:break-all">${esc(rep.file_hash)}</dd>
        </dl>
        ${why ? `<ul class="why">${why}</ul>` : ""}
        ${v.llm_summary ? `<div class="summary"><b>Plain-language summary.</b> ${esc(v.llm_summary)}</div>` : ""}
      </div></div></section>
  <section class="card"><div class="eyebrow">Forensic agents</div><h2>Agent breakdown</h2>
    ${(rep.agent_results || []).map((a) => agentCard(a, rep)).join("") || '<div class="muted">No agent results.</div>'}</section>
  <section class="card"><div class="eyebrow">Evidence chain</div><h2>Integrity, signature and anchor</h2>
    <div class="chain" id="chain">
      ${ver ? chainCard("File integrity", ver.file_integrity.status, ver.file_integrity.status === "intact" ? "ok" : "bad", `<code>${esc((ver.file_integrity.current_hash || "").slice(0, 40))}&hellip;</code>`) : chainCard("File integrity", "unavailable", "warn", "")}
      ${ver ? chainCard("Ed25519 signature", ver.record_signature.status, ver.record_signature.status === "valid" ? "ok" : "bad", `<code>${esc(ver.record_signature.algorithm || "")} key ${esc((ver.record_signature.key_fingerprint || "").slice(0, 16))}&hellip;</code>`) : chainCard("Ed25519 signature", "unavailable", "warn", "")}
      ${anchor ? chainCard("Blockchain anchor", anchor.status, ["verified", "anchored"].includes(anchor.status) ? "ok" : (anchor.status === "MISMATCH" ? "bad" : "warn"),
        `<code>${esc(anchor.network || "no network")}${anchor.tx_hash ? "<br>tx " + esc(anchor.tx_hash.slice(0, 40)) + "&hellip;" : ""}</code>`) : chainCard("Blockchain anchor", "unavailable", "warn", "")}
    </div>
    ${custody ? `<h3 style="margin-top:18px">Chain of custody</h3><ul class="timeline">${custody}</ul>` : ""}
    <div class="actions"><a class="btn" href="/api/report/${esc(rep.file_id)}/pdf" target="_blank" rel="noopener">Download evidence PDF</a>
      <a class="btn ghost" href="/api/report/${esc(rep.file_id)}" target="_blank" rel="noopener">Raw report (JSON)</a>
      <button class="btn ghost" id="reverify">Re-verify now</button><a class="btn ghost" href="#/analyze">Analyze another file</a></div>
  </section>`;
  $("#reverify").onclick = () => reportPage(id);
}

/* ───────────── History page ───────────── */
async function historyPage() {
  $("#view").innerHTML = '<div class="page-head"><div class="eyebrow">History</div><h1>Past analyses</h1><p>Every analysis stored by this server, newest first. Select a row to open its report.</p></div><div class="card" id="hist"><div class="muted">Loading&hellip;</div></div>';
  try {
    const rows = await api("/api/evidence?limit=200");
    if (!rows.length) { $("#hist").innerHTML = '<div class="empty">No analyses yet. <a href="#/analyze">Analyze a file</a>.</div>'; return; }
    $("#hist").innerHTML = `<table class="t"><thead><tr><th>Time</th><th>File</th><th>Type</th><th>Verdict</th><th>Score</th><th>Manipulation</th></tr></thead><tbody>${rows.map((r) => `
      <tr class="row" data-id="${esc(r.file_id)}"><td>${esc(when(r.upload_time))}</td><td>${esc(r.filename)}</td><td>${esc(r.file_type)}</td>
      <td>${r.verdict ? `<span class="pill ${esc(r.verdict)}">${esc(r.verdict)}</span>` : `<span class="pill neutral">${esc(r.status)}</span>`}</td>
      <td class="mono">${r.overall_score == null ? "" : r.overall_score.toFixed(2)}</td><td>${esc(r.manipulation_type || "")}</td></tr>`).join("")}</tbody></table>`;
    document.querySelectorAll("tr.row").forEach((tr) => tr.onclick = () => { location.hash = `#/report/${tr.dataset.id}`; });
  } catch (e) { $("#hist").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}

/* ───────────── How it works ───────────── */
function pipelinePage() {
  const W = [["Image forensics", 0.30], ["Provenance", 0.25], ["Metadata", 0.20]];
  $("#view").innerHTML = `
  <div class="page-head"><div class="eyebrow">How it works</div><h1>From upload to signed verdict</h1>
    <p>Each file type is routed to the agents that apply to it. Agents that have no signal for a file are excluded from the weighted verdict instead of voting on missing evidence.</p></div>
  <section class="card"><div class="eyebrow">Agents</div>
    <div class="grid g2">
      ${Object.entries(AGENTS).map(([k, a]) => `<div class="node"><h3>${esc(a[0])}</h3><p>${esc(a[1])}</p><span class="tag">${esc(k)}</span></div>`).join("")}
    </div></section>
  <section class="card"><div class="eyebrow">Decision engine</div><h2>Weighted fusion</h2>
    ${W.map((w) => `<div class="w"><span>${w[0]}</span><div class="track"><i style="width:${(w[1] / 0.30 * 100).toFixed(0)}%"></i></div><b>${(w[1] * 100).toFixed(0)}%</b></div>`).join("")}
    <p class="small muted" style="margin-bottom:0">Score &ge; ${AUTH} is <b>Authentic</b>, &le; ${FAKE} is <b>Fake</b>, in between is <b>Inconclusive</b> and goes to human review.
    The engine also names the likely manipulation type and a generator family when the evidence supports it.</p></section>
  <section class="card"><div class="eyebrow">Evidence chain</div>
    <div class="grid g3">
      <div class="node"><h3>1 &middot; Hash</h3><p>SHA-256 of the exact uploaded bytes. The original file is kept and re-hashed on every verification.</p></div>
      <div class="node"><h3>2 &middot; Sign</h3><p>The verdict record is signed with an Ed25519 key. Anyone with the public key can check it was not edited.</p></div>
      <div class="node"><h3>3 &middot; Anchor</h3><p>When a wallet is configured, the file hash and verdict are written to a smart contract on Polygon Amoy for a public timestamp.</p></div>
    </div>
    <p class="small muted" style="margin-bottom:0">The evidence PDF bundles the findings, heatmaps, chain of custody and blockchain proof for each analysis.</p></section>`;
}

/* ───────────── router ───────────── */
function route() {
  const parts = (location.hash.replace(/^#\/?/, "") || "analyze").split("/");
  const p = parts[0];
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.p === (p === "report" ? "history" : p)));
  window.scrollTo(0, 0);
  if (p === "report" && parts[1]) reportPage(parts[1]);
  else if (p === "history") historyPage();
  else if (p === "pipeline") pipelinePage();
  else analyzePage();
}
window.addEventListener("hashchange", route);
loadBadges();
route();

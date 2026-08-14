/* =====================================================================
   Financial Auditor — Frontend Logic
   ===================================================================== */

// ── State & DOM refs ──────────────────────────────────────────────────────
const state = {
  currentFile: null,
  currentJobId: null,
  stepIndex: 0,   // 1-based current pipeline step
};

const $ = (id) => document.getElementById(id);

// ── Step message keywords → step number mapping ───────────────────────────
const STEP_KEYWORDS = [
  { n: 1, keys: ['Sub-Agent 1', 'OCR', 'ocr'] },
  { n: 2, keys: ['Sub-Agent 2', 'Vision', 'visual', 'stempel'] },
  { n: 3, keys: ['Sub-Agent 3', 'Audit', 'kalkulasi', 'anomali'] },
  { n: 4, keys: ['Sub-Agent 4', 'Reporter', 'laporan', 'database'] },
];

function msgToStep(msg) {
  const m = msg.toLowerCase();
  for (const { n, keys } of STEP_KEYWORDS)
    if (keys.some(k => m.includes(k.toLowerCase()))) return n;
  return null;
}

// ── File Icons ─────────────────────────────────────────────────────────────
function fileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  return { pdf:'📕', png:'🖼️', jpg:'🖼️', jpeg:'🖼️', txt:'📝', json:'🗂️' }[ext] || '📄';
}
function fmt(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 ** 2).toFixed(2) + ' MB';
}
function fmtRp(n) {
  return 'Rp ' + Number(n || 0).toLocaleString('id-ID');
}

// ── Upload Zone ────────────────────────────────────────────────────────────
function onDragOver(e)  { e.preventDefault(); $('upload-zone').classList.add('drag-over'); }
function onDragLeave(e) { $('upload-zone').classList.remove('drag-over'); }
function onDrop(e) {
  e.preventDefault();
  $('upload-zone').classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
}
function onFileSelect(e) { const f = e.target.files[0]; if (f) setFile(f); }

function setFile(file) {
  const ALLOWED = ['application/pdf','image/png','image/jpeg','text/plain','application/json'];
  if (!ALLOWED.includes(file.type) && !file.name.match(/\.(pdf|png|jpg|jpeg|txt|json)$/i)) {
    alert('Format tidak didukung. Gunakan PDF, PNG, JPG, TXT, atau JSON.');
    return;
  }
  state.currentFile = file;
  $('file-icon').textContent = fileIcon(file.name);
  $('file-name').textContent  = file.name;
  $('file-size').textContent  = fmt(file.size);
  $('upload-zone').classList.add('hidden');
  $('upload-selected').classList.remove('hidden');
}

function resetUpload() {
  state.currentFile = null;
  $('file-input').value = '';
  $('upload-zone').classList.remove('hidden');
  $('upload-selected').classList.add('hidden');
}

function resetAudit() {
  state.currentJobId = null;
  state.stepIndex = 0;
  $('section-audit').classList.add('hidden');
  $('section-upload').classList.remove('hidden');
  resetUpload();
  resetSteps();
  $('results-placeholder').classList.remove('hidden');
  $('results-content').classList.add('hidden');
  $('results-content').innerHTML = '';
}

// ── Pipeline Steps UI ──────────────────────────────────────────────────────
function resetSteps() {
  for (let i = 1; i <= 4; i++) {
    const el = $(`step-${i}`);
    el.classList.remove('running', 'done');
    $(`step-${i}-status`).textContent = 'Menunggu…';
  }
  setProgress(0, '0%');
}

function setStep(n, status) {
  // Mark previous steps as done
  for (let i = 1; i < n; i++) {
    $(`step-${i}`).classList.remove('running');
    $(`step-${i}`).classList.add('done');
    $(`step-${i}-status`).textContent = '✓ Selesai';
  }
  // Mark current step
  if (n >= 1 && n <= 4) {
    $(`step-${n}`).classList.remove('done');
    $(`step-${n}`).classList.add('running');
    $(`step-${n}-status`).textContent = status || 'Memproses…';
  }
}

function setProgress(pct, label) {
  $('progress-fill').style.width = pct + '%';
  $('progress-label').textContent = label || pct + '%';
}

function markAllDone() {
  for (let i = 1; i <= 4; i++) {
    $(`step-${i}`).classList.remove('running');
    $(`step-${i}`).classList.add('done');
    $(`step-${i}-status`).textContent = '✓ Selesai';
  }
  setProgress(100, '100%');
}

// ── Start Audit ────────────────────────────────────────────────────────────
async function startAudit() {
  if (!state.currentFile) return;

  // Transition to audit view
  $('section-upload').classList.add('hidden');
  $('section-audit').classList.remove('hidden');
  resetSteps();

  // Show file preview
  const preview = $('file-preview');
  const isImage = state.currentFile.type.startsWith('image/');
  if (isImage) {
    const url = URL.createObjectURL(state.currentFile);
    preview.innerHTML = `<img src="${url}" alt="preview" />`;
  } else {
    preview.innerHTML = `
      <div class="file-preview-placeholder">
        <span>${fileIcon(state.currentFile.name)}</span>
        <span>${state.currentFile.name}</span>
      </div>`;
  }

  // Upload file
  const fd = new FormData();
  fd.append('file', state.currentFile);

  let jobId;
  try {
    setStep(1, 'Mengunggah file…');
    const resp = await fetch('/api/audit', { method: 'POST', body: fd });
    if (!resp.ok) throw new Error(`Upload gagal: ${resp.status}`);
    const data = await resp.json();
    jobId = data.job_id;
    state.currentJobId = jobId;
  } catch (err) {
    showError(err.message);
    return;
  }

  // Stream progress via SSE
  streamProgress(jobId);
}

// ── SSE Streaming ──────────────────────────────────────────────────────────
function streamProgress(jobId) {
  const es = new EventSource(`/api/audit/${jobId}/stream`);

  es.onmessage = (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch { return; }

    if (data.type === 'progress') {
      const step = msgToStep(data.msg || '') || state.stepIndex;
      state.stepIndex = step;
      setStep(step, data.msg);
      setProgress(data.pct, data.pct + '%');
    }

    if (data.type === 'done') {
      es.close();
      markAllDone();
      renderResults(data.results);
      loadStats(); // refresh header counts
    }

    if (data.type === 'error') {
      es.close();
      showError(data.msg || 'Pipeline error.');
    }
  };

  es.onerror = () => {
    es.close();
    // Don't show error — server may have closed cleanly
  };
}

// ── Render Results ─────────────────────────────────────────────────────────
function renderResults(results) {
  const ocr   = results.ocr_result   || {};
  const vis   = results.vision_result || {};
  const audit = results.audit_result  || {};
  const final = results.final_result  || {};

  const status   = audit.status || 'ANOMALY_DETECTED';
  const isValid  = status === 'VALID';
  const risk     = audit.risk_level || 'LOW';
  const anomalies = audit.anomalies || [];
  const mathOk   = audit.math_check_passed;

  let html = '';

  // ── Status Banner ───────────────────────────────────────────────────────
  html += `
  <div class="status-banner ${isValid ? 'valid' : 'anomaly'}">
    <div class="status-icon">${isValid ? '✅' : '⚠️'}</div>
    <div class="status-text">
      <div class="status-label">${isValid ? 'DOKUMEN VALID' : 'ANOMALI DITEMUKAN'}</div>
      <div class="status-sub">${audit.audit_summary || ''}</div>
    </div>
    <div class="risk-badge risk-${risk}">${riskLabel(risk)}</div>
  </div>`;

  // ── Warnings ────────────────────────────────────────────────────────────
  if (ocr.is_simulated) html += `<div class="anomaly-item warning"><span>⚠️</span><span>OCR Agent: ${ocr.raw_notes || 'Mode fallback aktif.'}</span></div>`;
  if (results.pipeline_errors && results.pipeline_errors.length) {
    results.pipeline_errors.forEach(e => {
      html += `<div class="anomaly-item critical"><span>🔴</span><span>Pipeline Error: ${e}</span></div>`;
    });
  }

  // ── Extracted Data ──────────────────────────────────────────────────────
  html += `<div class="results-section-title">📄 Data yang Diekstrak</div>`;
  html += `<div class="data-grid">
    ${card('🏢 Vendor', ocr.vendor_name || '—')}
    ${card('📄 Nomor Invoice', ocr.invoice_number || '—')}
    ${card('📅 Tanggal', ocr.invoice_date || '—')}
    ${card('💰 Subtotal', fmtRp(ocr.subtotal))}
    ${card(`🧾 Pajak${audit.tax_rate_percent ? ' ('+audit.tax_rate_percent+'%)' : ''}`, fmtRp(ocr.tax_amount))}
    ${card('💵 Total', fmtRp(ocr.total_amount))}
  </div>`;

  // ── Line Items ──────────────────────────────────────────────────────────
  const items = ocr.line_items || [];
  if (items.length) {
    html += `<div class="results-section-title">📋 Rincian Item</div>`;
    html += `<table class="items-table"><thead><tr>
      <th>Deskripsi</th><th class="num">Qty</th><th class="num">Harga Satuan</th><th class="num">Total</th>
    </tr></thead><tbody>`;
    items.forEach(it => {
      const qty = it.qty ?? it.quantity ?? '—';
      const up  = it.unit_price ?? '—';
      const tot = it.total ?? it.total_price ?? '—';
      html += `<tr>
        <td>${it.description || '—'}</td>
        <td class="num">${qty}</td>
        <td class="num rp">${up !== '—' ? fmtRp(up) : '—'}</td>
        <td class="num rp">${tot !== '—' ? fmtRp(tot) : '—'}</td>
      </tr>`;
    });
    html += `</tbody></table>`;
  }

  // ── Visual Inspection ───────────────────────────────────────────────────
  html += `<div class="results-section-title">🔍 Inspeksi Visual</div>`;
  html += `<div class="visual-row">
    ${visualCard('Stempel', vis.has_company_stamp, vis.stamp_quality || '')}
    ${visualCard('Tanda Tangan', vis.has_signature, vis.signature_status || '')}
    ${visualCard('Logo / Layout', vis.logo_detected, vis.layout_integrity || '')}
  </div>`;
  if (vis.visual_notes && !vis.is_simulated)
    html += `<p style="font-size:0.78rem;color:var(--text-3);margin-top:-8px">💬 ${vis.visual_notes}</p>`;

  // ── Math Check ──────────────────────────────────────────────────────────
  html += `<div class="results-section-title">🔢 Audit Matematis</div>`;
  if (mathOk) {
    html += `<div class="math-check ok">✅ Kalkulasi Valid — Subtotal + Pajak = ${fmtRp(audit.expected_total)}</div>`;
  } else {
    const diff = Math.abs((audit.actual_total || 0) - (audit.expected_total || 0));
    html += `<div class="math-check fail">
      ❌ Ketidaksesuaian!&nbsp; Dinyatakan: ${fmtRp(audit.actual_total)} &nbsp;|&nbsp;
      Seharusnya: ${fmtRp(audit.expected_total)} &nbsp;|&nbsp; Selisih: ${fmtRp(diff)}
    </div>`;
  }

  // ── Anomalies ───────────────────────────────────────────────────────────
  if (anomalies.length) {
    html += `<div class="results-section-title">⚠️ Anomali (${anomalies.length})</div>`;
    html += `<div class="anomaly-list">`;
    anomalies.forEach(a => {
      const isCrit = a.includes('DISCREPANCY') || a.toUpperCase().includes('ERROR');
      html += `<div class="anomaly-item ${isCrit ? 'critical' : 'warning'}">
        <span>${isCrit ? '🔴' : '🟡'}</span><span>${a}</span>
      </div>`;
    });
    html += `</div>`;
  }

  // ── Risk Reasoning ──────────────────────────────────────────────────────
  if (audit.risk_reasoning) {
    html += `<details class="report-expander">
      <summary>📊 Analisis Risiko Detail</summary>
      <div class="report-expander-body">${audit.risk_reasoning}</div>
    </details>`;
  }

  // ── LLM Executive Report ────────────────────────────────────────────────
  const report = final.executive_report || '';
  if (report && !report.startsWith('⚠️ Laporan tidak dapat dibuat')) {
    html += `<details class="report-expander">
      <summary>📝 Laporan Eksekutif Lengkap (AI-Generated)</summary>
      <div class="report-expander-body">${report}</div>
    </details>`;
  }

  // Render
  const content = $('results-content');
  content.innerHTML = html;
  $('results-placeholder').classList.add('hidden');
  content.classList.remove('hidden');
}

// ── Helper renderers ───────────────────────────────────────────────────────
function card(label, value) {
  return `<div class="data-card">
    <div class="data-card-label">${label}</div>
    <div class="data-card-value">${value}</div>
  </div>`;
}

function visualCard(label, val, sub) {
  let icon, cls, text;
  if (val === true)  { icon = '✅'; cls = 'vc-ok';   text = sub || 'Ada'; }
  else if (val === false) { icon = '❌'; cls = 'vc-fail'; text = sub || 'Tidak Ada'; }
  else               { icon = '—';  cls = 'vc-na';   text = sub || 'Tidak Diperiksa'; }
  return `<div class="visual-card">
    <div class="vc-icon">${icon}</div>
    <div class="vc-label">${label}</div>
    <div class="vc-value ${cls}">${text}</div>
  </div>`;
}

function riskLabel(risk) {
  return { LOW: '🟢 Rendah', MEDIUM: '🟡 Sedang', HIGH: '🔴 Tinggi' }[risk] || risk;
}

function showError(msg) {
  $('results-placeholder').classList.add('hidden');
  const content = $('results-content');
  content.innerHTML = `
    <div class="anomaly-item critical" style="padding:20px">
      <span>🔴</span>
      <div>
        <strong>Pipeline Error</strong><br/>
        <span style="opacity:0.8">${msg}</span>
      </div>
    </div>`;
  content.classList.remove('hidden');
}

// ── History Modal ──────────────────────────────────────────────────────────
async function openHistory() {
  $('modal-overlay').classList.remove('hidden');
  $('history-body').innerHTML = '<p class="text-muted">Memuat data…</p>';
  try {
    const resp = await fetch('/api/history');
    const data = await resp.json();
    renderHistory(data.records || []);
  } catch (e) {
    $('history-body').innerHTML = `<p class="text-muted">Gagal memuat data: ${e.message}</p>`;
  }
}

function closeHistory() {
  $('modal-overlay').classList.add('hidden');
}

function renderHistory(records) {
  if (!records.length) {
    $('history-body').innerHTML = '<p class="text-muted">Belum ada riwayat audit.</p>';
    return;
  }
  let html = `<table class="history-table"><thead><tr>
    <th>#</th><th>File</th><th>Vendor</th><th>No. Invoice</th>
    <th>Tanggal</th><th class="text-right">Total (Rp)</th><th>Status</th><th>Waktu Audit</th>
  </tr></thead><tbody>`;
  records.forEach(r => {
    const isV = r.status === 'VALID';
    const ts  = r.created_at ? new Date(r.created_at).toLocaleString('id-ID') : '—';
    html += `<tr>
      <td>${r.id}</td>
      <td>${r.file_name || '—'}</td>
      <td>${r.vendor_name || '—'}</td>
      <td>${r.invoice_number || '—'}</td>
      <td>${r.invoice_date || '—'}</td>
      <td class="text-right rp">${Number(r.total_amount || 0).toLocaleString('id-ID')}</td>
      <td><span class="badge ${isV ? 'badge-valid' : 'badge-anomaly'}">${isV ? 'VALID' : 'ANOMALI'}</span></td>
      <td style="color:var(--text-3);font-size:0.72rem">${ts}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  $('history-body').innerHTML = html;
}

async function exportExcel() {
  const btn = $('btn-export');
  btn.textContent = '⏳ Mengekspor…';
  btn.disabled = true;
  try {
    const resp = await fetch('/api/export', { method: 'POST' });
    if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
    const blob = await resp.blob();
    const cd   = resp.headers.get('content-disposition') || '';
    const fname = (cd.match(/filename="?([^";\r\n]+)"?/) || [])[1] || 'audit_report.xlsx';
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = fname; a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('Export gagal: ' + e.message);
  } finally {
    btn.textContent = '📥 Export Excel';
    btn.disabled = false;
  }
}

async function clearHistory() {
  if (!confirm('Apakah Anda yakin ingin menghapus semua riwayat audit yang tersimpan di database?')) {
    return;
  }
  const btn = $('btn-clear-history');
  btn.textContent = '⏳ Menghapus…';
  btn.disabled = true;
  try {
    const resp = await fetch('/api/history', { method: 'DELETE' });
    if (!resp.ok) throw new Error('Gagal menghapus riwayat.');
    renderHistory([]);
    loadStats();
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    btn.textContent = '🗑️ Hapus Riwayat';
    btn.disabled = false;
  }
}

// ── Header Stats ───────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const resp = await fetch('/api/history');
    const { counts } = await resp.json();
    $('stat-n-total').textContent   = counts.total   ?? '–';
    $('stat-n-valid').textContent   = counts.valid   ?? '–';
    $('stat-n-anomaly').textContent = counts.anomaly ?? '–';
  } catch { /* non-critical */ }
}

// ── Model Status Badges ────────────────────────────────────────────────────
async function checkModels() {
  try {
    const resp = await fetch('/api/models');
    const data = await resp.json();
    if (data.error) { setAllBadges('error'); return; }
    const avail = data.available || [];
    const cfg   = data.configured || {};
    Object.entries(cfg).forEach(([role, id]) => {
      const badgeId = { ocr: 'badge-ocr', vision: 'badge-vision', auditor: 'badge-auditor', reporter: 'badge-reporter' }[role];
      if (badgeId) {
        const el = $(badgeId);
        el.classList.remove('loading');
        el.classList.add(avail.includes(id) ? 'ready' : 'error');
      }
    });
  } catch {
    setAllBadges('error');
  }
}

function setAllBadges(cls) {
  ['badge-ocr','badge-vision','badge-auditor','badge-reporter'].forEach(id => {
    const el = $(id);
    el.classList.remove('loading', 'ready', 'error');
    el.classList.add(cls);
  });
}

// ── Init ───────────────────────────────────────────────────────────────────
loadStats();
checkModels();

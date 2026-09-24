const $ = (sel) => document.querySelector(sel);

// ---------- Auth ----------

const AUTH = {
  required: false,
  authenticated: true,
};

async function checkAuth() {
  try {
    const r = await fetch("/api/auth/status");
    const data = await r.json();
    AUTH.required = data.required;
    AUTH.authenticated = data.authenticated;
    return data;
  } catch {
    AUTH.required = false;
    AUTH.authenticated = true;
    return { required: false, authenticated: true };
  }
}

function showLoginOverlay() {
  const overlay = document.getElementById("login-overlay");
  if (overlay) overlay.classList.remove("hidden");
  const input = document.getElementById("login-password");
  if (input) {
    input.value = "";
    setTimeout(() => input.focus(), 50);
  }
}

function hideLoginOverlay() {
  const overlay = document.getElementById("login-overlay");
  if (overlay) overlay.classList.add("hidden");
  const err = document.getElementById("login-error");
  if (err) err.classList.add("hidden");
}

async function submitLogin(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("login-password");
  const errEl = document.getElementById("login-error");
  const btn = document.getElementById("login-btn");
  const pw = input ? input.value : "";
  if (!pw) return;

  if (btn) { btn.disabled = true; btn.textContent = "Signing in..."; }
  if (errEl) errEl.classList.add("hidden");

  try {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      if (errEl) {
        errEl.textContent = data.detail || "Incorrect password";
        errEl.classList.remove("hidden");
      }
      return;
    }

    AUTH.authenticated = true;
    hideLoginOverlay();
    await boot();
  } catch (err) {
    if (errEl) {
      errEl.textContent = `Network error: ${err.message}`;
      errEl.classList.remove("hidden");
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Sign in"; }
  }
}

async function logout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {}
  AUTH.authenticated = false;
  if (ws) { try { ws.close(); } catch {} ws = null; }
  showLoginOverlay();
}

function wireLoginUI() {
  const form = document.getElementById("login-form");
  if (form) form.addEventListener("submit", submitLogin);
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) logoutBtn.addEventListener("click", logout);
}

function updateLogoutVisibility() {
  const btn = document.getElementById("logout-btn");
  if (!btn) return;
  if (AUTH.required && AUTH.authenticated) {
    btn.classList.remove("hidden");
  } else {
    btn.classList.add("hidden");
  }
}

// ---------- Element refs ----------

const els = {
  folder:        $("#folder-input"),
  scanBtn:       $("#scan-btn"),
  organizeBtn:   $("#organize-btn"),
  undoBtn:       $("#undo-btn"),
  clearBtn:      $("#clear-btn"),
  status:        $("#status"),
  summary:       $("#summary"),
  summaryFolder: $("#summary-folder"),
  summaryCounts: $("#summary-counts"),
  preview:       $("#preview"),
  previewBody:   $("#preview-body"),
  actions:       $("#actions"),
  lastRun:       $("#last-run"),
  toggleRules:   $("#toggle-rules"),
  rulesBody:     $("#rules-body"),
  rulesList:     $("#rules-list"),
  newCategory:   $("#new-category-input"),
  addCategoryBtn:$("#add-category-btn"),
  modeHint:      $("#mode-hint"),
  modeBtns:      document.querySelectorAll(".mode-btn"),
  wsStatus:      $("#ws-status"),
  // watch
  watchBadge:    $("#watch-badge"),
  watchStartBtn: $("#watch-start-btn"),
  watchStopBtn:  $("#watch-stop-btn"),
  watchStatus:   $("#watch-status"),
  watchRuns:     $("#watch-runs"),
  watchRunsList: $("#watch-runs-list"),
  // history
  historyBody:   $("#history-body"),
  historyTable:  $("#history-table"),
  historyEmpty:  $("#history-empty"),
  historyCount:  $("#history-count"),
  historyRefresh:$("#history-refresh"),
  // duplicates
  findDupesBtn:  $("#find-dupes-btn"),
  quarantineBtn: $("#quarantine-dupes-btn"),
  trashDupesBtn: $("#trash-dupes-btn"),
  dupesBadge:    $("#dupes-badge"),
  dupesStatus:   $("#dupes-status"),
  dupesGroups:   $("#dupes-groups"),
  // large files
  findLargeBtn:        $("#find-largefiles-btn"),
  quarantineLargeBtn:  $("#quarantine-largefiles-btn"),
  trashLargeBtn:       $("#trash-largefiles-btn"),
  largeMinMb:          $("#largefiles-min-mb"),
  largeBadge:          $("#largefiles-badge"),
  largeStatus:         $("#largefiles-status"),
  largeTableWrap:      $("#largefiles-table-wrap"),
  largeBody:           $("#largefiles-body"),
  largeSelectAll:      $("#largefiles-select-all"),
  // schedules
  schedBadge:       $("#scheduler-badge"),
  schedFolder:      $("#sched-folder"),
  schedMode:        $("#sched-mode"),
  schedInterval:    $("#sched-interval"),
  addScheduleBtn:   $("#add-schedule-btn"),
  schedEmpty:       $("#schedules-empty"),
  schedList:        $("#schedules-list"),
  // settings
  toggleSettings:   $("#toggle-settings"),
  settingsBody:     $("#settings-body"),
  setDefaultMode:   $("#set-default-mode"),
  setCollisionStyle:$("#set-collision-style"),
  setDateFormat:    $("#set-date-format"),
  skipNamesChips:   $("#skip-names-chips"),
  skipPrefixesChips:$("#skip-prefixes-chips"),
  newSkipName:      $("#new-skip-name"),
  addSkipName:      $("#add-skip-name"),
  newSkipPrefix:    $("#new-skip-prefix"),
  addSkipPrefix:    $("#add-skip-prefix"),
  settingsSaved:    $("#settings-saved"),
  newPassword:      $("#new-password"),
  setPasswordBtn:   $("#set-password-btn"),
  clearPasswordBtn: $("#clear-password-btn"),
  passwordStatus:   $("#password-status"),
  // backup
  exportConfigBtn:  $("#export-config-btn"),
  importFileInput:  $("#import-file-input"),
  resetConfigBtn:   $("#reset-config-btn"),
  // backups
  createBackupBtn:  $("#create-backup-btn"),
  backupsBody:      $("#backups-body"),
  backupsTable:     $("#backups-table"),
  backupsEmpty:     $("#backups-empty"),
  backupsCount:     $("#backups-count"),
  // folder rules
  toggleFolderRules: $("#toggle-folder-rules"),
  folderRulesBody:   $("#folder-rules-body"),
  newFolderRulePath: $("#new-folder-rule-path"),
  addFolderRuleBtn:  $("#add-folder-rule-btn"),
  folderRulesEmpty:  $("#folder-rules-empty"),
  folderRulesList:   $("#folder-rules-list"),
};

let latestUndoableLog = null;
let rulesVisible = false;
let settingsVisible = false;
let folderRulesVisible = false;
let currentMode = "extension";
let currentSettings = null;
let dateFormatOptions = [];
let lastDupeResult = null;
let trashSupported = false;
let folderRules = [];
let largeFilesResult = null;
let largeFilesSelected = new Set();

let ws = null;
let wsReconnectTimer = null;
let wsConnected = false;
let watchPollTimer = null;

const MODE_HINTS = {
  extension: "Files go to folders like Images/, Documents/, Code/",
  date: "Files go to folders like 2026-09/, 2026-08/ (by modified date)",
};

function showStatus(msg, kind = "info") {
  els.status.textContent = msg;
  els.status.className = `status ${kind}`;
  els.status.classList.remove("hidden");
}

function hideStatus() { els.status.classList.add("hidden"); }

function hideResults() {
  els.summary.classList.add("hidden");
  els.preview.classList.add("hidden");
  els.actions.classList.add("hidden");
  els.previewBody.innerHTML = "";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------- WebSocket ----------

function setWsState(state) {
  els.wsStatus.className = `ws-status ${state}`;
  els.wsStatus.textContent = state === "connected" ? "live" :
                             state === "connecting" ? "connecting…" :
                             "offline";
}

function connectWs() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  setWsState("connecting");
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    wsConnected = true;
    setWsState("connected");
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
    stopWatchPolling();
  };

  ws.onclose = (e) => {
    wsConnected = false;
    if (e && e.code === 1008) {
      setWsState("disconnected");
      checkAuth().then(s => {
        if (s.required && !s.authenticated) {
          AUTH.required = true;
          AUTH.authenticated = false;
          showLoginOverlay();
        }
      });
      return;
    }
    setWsState("disconnected");
    refreshWatch();
    startWatchPolling();
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(connectWs, 2000);
  };

  ws.onerror = () => {};

  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    handleWsEvent(msg);
  };
}

function handleWsEvent(msg) {
  const { type, data } = msg;

  switch (type) {
    case "hello": break;
    case "watch_run": appendWatchRun(data); flashWatchPanel(); loadLogs(); break;
    case "watch_error": showStatus(`Watch error on ${data.file}: ${data.error}`, "error"); break;
    case "watch_started": refreshWatch(); showStatus(`Watching ${data.folder}`, "success"); break;
    case "watch_stopped": refreshWatch(); break;
    case "organize": loadLogs(); break;
    case "undo": loadLogs(); break;
    case "quarantine": loadLogs(); break;
    case "trash":
      if (data.trashed) showStatus(`Trashed ${data.trashed} file(s)`, "success");
      break;
    case "backup_created":
    case "backup_deleted":
      loadBackups();
      break;
    case "schedule_run":
      loadSchedules(); loadLogs();
      showStatus(`Scheduled run — ${data.moved} file(s) from ${data.folder}`, "success");
      break;
    case "schedule_error":
      loadSchedules();
      showStatus(`Scheduled run failed: ${data.error}`, "error");
      break;
    case "schedule_added":
    case "schedule_updated":
    case "schedule_removed":
      loadSchedules();
      break;
    case "settings_updated":
      if (settingsVisible) loadSettings();
      break;
    case "rules_updated":
      if (rulesVisible) loadRules();
      break;
    case "folder_rules_updated":
      if (folderRulesVisible) loadFolderRules();
      break;
    case "config_imported":
    case "config_reset":
      loadSettings();
      if (rulesVisible) loadRules();
      if (folderRulesVisible) loadFolderRules();
      loadSchedules();
      loadBackups();
      break;
  }
}

function appendWatchRun(run) {
  if (els.watchRuns.classList.contains("hidden")) {
    els.watchRuns.classList.remove("hidden");
    els.watchRunsList.innerHTML = "";
  }
  const li = document.createElement("li");
  li.className = "row-flash";
  li.innerHTML = `<span class="time">${escapeHtml(run.time)}</span>${escapeHtml(run.file)}<span class="cat">→ ${escapeHtml(run.category)}</span>`;
  els.watchRunsList.insertBefore(li, els.watchRunsList.firstChild);
}

function flashWatchPanel() {
  const panel = els.watchRuns.closest(".watch-panel");
  if (!panel) return;
  panel.classList.add("row-flash");
  setTimeout(() => panel.classList.remove("row-flash"), 1200);
}

// ---------- mode toggle ----------

function setMode(mode) {
  currentMode = mode;
  els.modeBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.mode === mode));
  els.modeHint.textContent = MODE_HINTS[mode] || "";
  hideStatus();
  hideResults();
}

els.modeBtns.forEach(btn => btn.addEventListener("click", () => setMode(btn.dataset.mode)));

// ---------- logs + history ----------

async function loadLogs() {
  try {
    const res = await fetch("/api/logs");
    const data = await res.json();
    const logs = data.logs || [];

    const undoable = logs.find(l => !l.undone);
    if (undoable) {
      latestUndoableLog = undoable.file;
      els.undoBtn.disabled = false;
      els.lastRun.textContent =
        `Last run: ${undoable.file}  ·  ${undoable.total} file(s)  ·  mode: ${undoable.mode}  ·  ${undoable.folder}`;
      els.lastRun.classList.remove("hidden");
    } else {
      latestUndoableLog = null;
      els.undoBtn.disabled = true;
      els.lastRun.classList.add("hidden");
    }

    renderHistory(logs);
  } catch {}
}

function formatTimestamp(ts) {
  if (!ts || ts.length !== 15) return ts || "";
  const y = ts.slice(0,4), mo = ts.slice(4,6), d = ts.slice(6,8);
  const h = ts.slice(9,11), mi = ts.slice(11,13), s = ts.slice(13,15);
  return `${y}-${mo}-${d} ${h}:${mi}:${s}`;
}

function renderHistory(logs) {
  els.historyCount.textContent = logs.length ? `${logs.length} run${logs.length === 1 ? "" : "s"}` : "";

  if (logs.length === 0) {
    els.historyTable.classList.add("hidden");
    els.historyEmpty.classList.remove("hidden");
    return;
  }

  els.historyEmpty.classList.add("hidden");
  els.historyTable.classList.remove("hidden");

  els.historyBody.innerHTML = logs.map(log => `
    <tr class="${log.undone ? "done" : ""}" data-log="${escapeHtml(log.file)}">
      <td>${escapeHtml(formatTimestamp(log.timestamp))}</td>
      <td>${log.total}</td>
      <td class="mode-cell">${escapeHtml(log.mode || "extension")}</td>
      <td class="folder-cell" title="${escapeHtml(log.folder)}">${escapeHtml(log.folder)}</td>
      <td class="status-cell">
        <span class="status-pill ${log.undone ? "done" : "active"}">${log.undone ? "UNDONE" : "ACTIVE"}</span>
      </td>
      <td class="actions-cell">
        ${log.undone
          ? `<button class="secondary tiny" disabled>Undo</button>`
          : `<button class="danger tiny history-undo-btn" data-log="${escapeHtml(log.file)}">Undo</button>`}
      </td>
    </tr>
  `).join("");
}

els.historyBody.addEventListener("click", async (e) => {
  const btn = e.target.closest(".history-undo-btn");
  if (!btn) return;
  await undoLog(btn.dataset.log);
});

els.historyRefresh.addEventListener("click", () => loadLogs());

// ---------- scan ----------

async function scan() {
  const path = els.folder.value.trim();
  if (!path) { showStatus("Enter a folder path first.", "error"); return; }

  els.scanBtn.disabled = true;
  els.scanBtn.textContent = "Scanning...";
  hideStatus();
  hideResults();

  try {
    const url = `/api/scan?path=${encodeURIComponent(path)}&mode=${currentMode}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    renderPlan(data);
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.scanBtn.disabled = false;
    els.scanBtn.textContent = "Scan";
  }
}

async function organize() {
  const path = els.folder.value.trim();
  if (!path) return;

  const confirmed = confirm(
    `Move all files in:\n${path}\n\nMode: ${currentMode}\n\nYou can undo this from the History panel. Continue?`
  );
  if (!confirmed) return;

  els.organizeBtn.disabled = true;
  els.organizeBtn.textContent = "Organizing...";
  hideStatus();

  try {
    const res = await fetch("/api/organize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, mode: currentMode }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    showStatus(`${data.message}` + (data.log_file ? ` — log: ${data.log_file}` : ""), "success");
    await scan();
    await loadLogs();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.organizeBtn.disabled = false;
    els.organizeBtn.textContent = "Organize";
  }
}

async function undoLog(logFile) {
  const confirmed = confirm(`Undo this run?\n${logFile}\n\nAll moved files will be restored.`);
  if (!confirmed) return;

  hideStatus();
  try {
    const res = await fetch("/api/undo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ log_file: logFile }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    const errCount = (data.errors || []).length;
    const kind = errCount > 0 ? "error" : "success";
    showStatus(
      `Undone: ${data.restored} file(s) restored` + (errCount > 0 ? `, ${errCount} error(s)` : ""),
      kind
    );
    await scan();
    await loadLogs();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  }
}

async function undoLatest() {
  if (!latestUndoableLog) return;
  await undoLog(latestUndoableLog);
}

// ---------- plan rendering ----------

function renderPlan(plan) {
  els.summaryFolder.textContent = plan.folder;
  const parts = [`${plan.total} file${plan.total === 1 ? "" : "s"}`];
  if (plan.renamed > 0) parts.push(`${plan.renamed} renamed`);
  if (plan.skipped.length > 0) parts.push(`${plan.skipped.length} skipped`);
  els.summaryCounts.textContent = parts.join(" · ");

  els.summary.classList.remove("hidden");
  els.preview.classList.remove("hidden");
  els.actions.classList.remove("hidden");

  if (plan.items.length === 0) {
    els.previewBody.innerHTML = `
      <tr><td colspan="5" style="text-align:center; color:var(--muted); padding:24px;">
        Nothing to organize — folder is already clean.
      </td></tr>`;
    els.organizeBtn.disabled = true;
    return;
  }

  els.organizeBtn.disabled = false;

  const rows = plan.items.map(it => {
    const hasThumb = it.is_image || it.is_video;
    const badge = filetypeBadge(it.source_name);
    const cell = hasThumb
      ? `<div class="thumb-wrap">
           <span class="filetype">${badge}</span>
           <img class="thumb" src="/api/thumbnail?path=${encodeURIComponent(it.source)}"
                alt="" loading="lazy" onerror="this.style.display='none'" />
         </div>`
      : `<span class="filetype">${badge}</span>`;

    return `
      <tr class="${it.renamed ? "renamed" : ""}">
        <td class="thumb-cell">${cell}</td>
        <td>${escapeHtml(it.source_name)}</td>
        <td class="arrow">→</td>
        <td class="destination">${escapeHtml(it.destination_rel)}</td>
        <td class="category">${escapeHtml(it.category)}</td>
      </tr>
    `;
  });
  els.previewBody.innerHTML = rows.join("");
}

function filetypeBadge(filename) {
  const ext = (filename.split(".").pop() || "").toUpperCase();
  return ext.length <= 4 ? ext : ext.slice(0, 4);
}

// ---------- watch ----------

function renderWatch(status) {
  const watching = status.watching;
  els.watchBadge.textContent = watching ? "ON" : "OFF";
  els.watchBadge.className = `watch-badge ${watching ? "on" : "off"}`;

  els.watchStartBtn.disabled = watching;
  els.watchStopBtn.disabled = !watching;

  if (watching) {
    els.watchStatus.textContent =
      `Watching: ${status.folder}  ·  mode: ${status.mode}  ·  started ${status.started_at}  ·  ${status.total} file(s) organized`;
    els.watchStatus.classList.remove("hidden");
  } else {
    els.watchStatus.classList.add("hidden");
  }

  if (status.recent_runs && status.recent_runs.length > 0) {
    els.watchRuns.classList.remove("hidden");
    els.watchRunsList.innerHTML = status.recent_runs.slice().reverse().map(r => `
      <li><span class="time">${escapeHtml(r.time)}</span>${escapeHtml(r.file)}<span class="cat">→ ${escapeHtml(r.category)}</span></li>
    `).join("");
  } else {
    els.watchRuns.classList.add("hidden");
  }
}

async function refreshWatch() {
  try {
    const res = await fetch("/api/watch/status");
    const data = await res.json();
    renderWatch(data);
  } catch {}
}

async function watchStart() {
  const path = els.folder.value.trim();
  if (!path) { showStatus("Enter a folder path first.", "error"); return; }
  els.watchStartBtn.disabled = true;
  try {
    const res = await fetch("/api/watch/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, mode: currentMode }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    renderWatch(data);
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  }
}

async function watchStop() {
  els.watchStopBtn.disabled = true;
  try {
    const res = await fetch("/api/watch/stop", { method: "POST" });
    const data = await res.json();
    renderWatch(data);
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  }
}

function startWatchPolling() {
  if (wsConnected) return;
  stopWatchPolling();
  watchPollTimer = setInterval(refreshWatch, 3000);
}

function stopWatchPolling() {
  if (watchPollTimer) { clearInterval(watchPollTimer); watchPollTimer = null; }
}

els.watchStartBtn.addEventListener("click", watchStart);
els.watchStopBtn.addEventListener("click", watchStop);

// ---------- format helpers ----------

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

// ---------- duplicates ----------

function renderDuplicates(result) {
  lastDupeResult = result;

  if (result.total_groups === 0) {
    els.dupesBadge.textContent = "CLEAN";
    els.dupesBadge.className = "dupes-badge clean";
    els.dupesStatus.textContent = `Scanned ${result.total_files} file(s) — no duplicates found.`;
    els.dupesStatus.classList.remove("hidden");
    els.dupesGroups.classList.add("hidden");
    els.quarantineBtn.disabled = true;
    els.trashDupesBtn.disabled = true;
    return;
  }

  els.dupesBadge.textContent = `${result.total_groups} GROUP${result.total_groups === 1 ? "" : "S"}`;
  els.dupesBadge.className = "dupes-badge found";
  els.dupesStatus.textContent =
    `Scanned ${result.total_files} file(s) — ${result.total_groups} duplicate group(s), ${formatBytes(result.wasted_bytes)} wasted.`;
  els.dupesStatus.classList.remove("hidden");
  els.quarantineBtn.disabled = false;
  els.trashDupesBtn.disabled = !trashSupported;

  const html = result.groups.map(g => `
    <div class="dupe-group">
      <div class="dupe-group-header">
        <span>${g.files.length} copies · ${formatBytes(g.size)} each</span>
        <span class="waste-tag">${formatBytes(g.wasted_bytes)} wasted</span>
      </div>
      ${g.files.map((f, i) => `
        <div class="dupe-file ${i === 0 ? "kept" : "moved"}">
          <span class="path" title="${escapeHtml(f.path)}">${escapeHtml(f.rel_path)}</span>
          <span class="size">${formatBytes(f.size)}</span>
        </div>
      `).join("")}
    </div>
  `).join("");

  els.dupesGroups.innerHTML = html;
  els.dupesGroups.classList.remove("hidden");
}

async function findDuplicates() {
  const path = els.folder.value.trim();
  if (!path) { showStatus("Enter a folder path first.", "error"); return; }

  els.findDupesBtn.disabled = true;
  els.findDupesBtn.textContent = "Scanning...";
  els.dupesStatus.classList.add("hidden");
  els.dupesGroups.classList.add("hidden");
  els.quarantineBtn.disabled = true;
  els.trashDupesBtn.disabled = true;

  try {
    const res = await fetch(`/api/duplicates?path=${encodeURIComponent(path)}`);
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    renderDuplicates(data);
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.findDupesBtn.disabled = false;
    els.findDupesBtn.textContent = "Find duplicates";
  }
}

async function quarantineDuplicates() {
  const path = els.folder.value.trim();
  if (!path || !lastDupeResult || lastDupeResult.total_groups === 0) return;

  const moved = lastDupeResult.groups.reduce((n, g) => n + (g.files.length - 1), 0);
  const confirmed = confirm(
    `Move ${moved} duplicate file(s) into _duplicates/?\n\n` +
    `The newest copy in each group is kept. Nothing is deleted.\n` +
    `You can undo this from the History panel.`
  );
  if (!confirmed) return;

  els.quarantineBtn.disabled = true;
  els.quarantineBtn.textContent = "Moving...";
  hideStatus();

  try {
    const res = await fetch("/api/duplicates/quarantine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    showStatus(`${data.message}` + (data.log_file ? ` — log: ${data.log_file}` : ""), "success");
    await findDuplicates();
    await loadLogs();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.quarantineBtn.disabled = false;
    els.quarantineBtn.textContent = "Quarantine duplicates";
  }
}

async function trashDuplicates() {
  const path = els.folder.value.trim();
  if (!path || !lastDupeResult || lastDupeResult.total_groups === 0) return;

  const moved = lastDupeResult.groups.reduce((n, g) => n + (g.files.length - 1), 0);
  const confirmed = confirm(
    `Send ${moved} duplicate file(s) to the OS Recycle Bin / Trash?\n\n` +
    `The newest copy in each group is kept.\n` +
    `Files can be restored from your system Recycle Bin or Trash — but not from this app.`
  );
  if (!confirmed) return;

  els.trashDupesBtn.disabled = true;
  els.trashDupesBtn.textContent = "Sending...";
  hideStatus();

  try {
    const res = await fetch("/api/duplicates/trash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    showStatus(data.message, "success");
    await findDuplicates();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.trashDupesBtn.disabled = false;
    els.trashDupesBtn.textContent = "Send to trash";
  }
}

els.findDupesBtn.addEventListener("click", findDuplicates);
els.quarantineBtn.addEventListener("click", quarantineDuplicates);
els.trashDupesBtn.addEventListener("click", trashDuplicates);

// ---------- large files ----------

function updateLargeFilesButtons() {
  const count = largeFilesSelected.size;
  els.quarantineLargeBtn.disabled = count === 0;
  els.trashLargeBtn.disabled = count === 0 || !trashSupported;
  els.quarantineLargeBtn.textContent = count > 0
    ? `Quarantine ${count} selected`
    : "Quarantine selected";
  els.trashLargeBtn.textContent = count > 0
    ? `Trash ${count} selected`
    : "Trash selected";
}

function renderLargeFiles(result) {
  largeFilesResult = result;
  largeFilesSelected.clear();
  updateLargeFilesButtons();

  if (result.matched === 0) {
    els.largeBadge.textContent = "CLEAN";
    els.largeBadge.className = "largefiles-badge clean";
    els.largeStatus.textContent =
      `Scanned ${result.total_scanned} file(s) — no files ≥ ${formatBytes(result.min_bytes)}.`;
    els.largeStatus.classList.remove("hidden");
    els.largeTableWrap.classList.add("hidden");
    return;
  }

  els.largeBadge.textContent = `${result.matched} FILE${result.matched === 1 ? "" : "S"}`;
  els.largeBadge.className = "largefiles-badge found";
  els.largeStatus.textContent =
    `Scanned ${result.total_scanned} file(s) — ${result.matched} large file(s), ${formatBytes(result.total_matched_bytes)} total`
    + (result.truncated ? " (top 500 shown)" : ".");
  els.largeStatus.classList.remove("hidden");
  els.largeTableWrap.classList.remove("hidden");
  els.largeSelectAll.checked = false;

  els.largeBody.innerHTML = result.files.map((f, i) => `
    <tr>
      <td class="lf-check">
        <input type="checkbox" class="lf-checkbox" data-index="${i}" />
      </td>
      <td><span class="lf-path" title="${escapeHtml(f.path)}">${escapeHtml(f.rel_path)}</span></td>
      <td class="lf-size">${formatBytes(f.size)}</td>
    </tr>
  `).join("");
}

async function findLargeFiles() {
  const path = els.folder.value.trim();
  if (!path) { showStatus("Enter a folder path first.", "error"); return; }

  const minMb = parseFloat(els.largeMinMb.value);
  if (isNaN(minMb) || minMb < 0) {
    showStatus("Minimum size must be a positive number.", "error");
    return;
  }

  els.findLargeBtn.disabled = true;
  els.findLargeBtn.textContent = "Scanning...";
  els.largeStatus.classList.add("hidden");
  els.largeTableWrap.classList.add("hidden");

  try {
    const url = `/api/large-files?path=${encodeURIComponent(path)}&min_mb=${minMb}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    renderLargeFiles(data);
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.findLargeBtn.disabled = false;
    els.findLargeBtn.textContent = "Scan";
  }
}

function selectedLargeFiles() {
  if (!largeFilesResult) return [];
  return Array.from(largeFilesSelected).map(i => largeFilesResult.files[i]);
}

async function quarantineLargeFiles() {
  const path = els.folder.value.trim();
  const files = selectedLargeFiles();
  if (!path || files.length === 0) return;

  const confirmed = confirm(
    `Move ${files.length} large file(s) into _large_files/?\n\n` +
    `Structure under _large_files/ mirrors the original paths. Nothing is deleted.\n` +
    `You can undo this from the History panel.`
  );
  if (!confirmed) return;

  els.quarantineLargeBtn.disabled = true;
  els.quarantineLargeBtn.textContent = "Moving...";
  hideStatus();

  try {
    const res = await fetch("/api/large-files/quarantine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, files }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    showStatus(`${data.message}` + (data.log_file ? ` — log: ${data.log_file}` : ""), "success");
    await findLargeFiles();
    await loadLogs();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    updateLargeFilesButtons();
  }
}

async function trashLargeFiles() {
  const files = selectedLargeFiles();
  if (files.length === 0) return;

  const confirmed = confirm(
    `Send ${files.length} large file(s) to the OS Recycle Bin / Trash?\n\n` +
    `Files can be restored from your system Recycle Bin or Trash — but not from this app.`
  );
  if (!confirmed) return;

  els.trashLargeBtn.disabled = true;
  els.trashLargeBtn.textContent = "Sending...";
  hideStatus();

  try {
    const res = await fetch("/api/large-files/trash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    showStatus(data.message, "success");
    await findLargeFiles();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    updateLargeFilesButtons();
  }
}

els.findLargeBtn.addEventListener("click", findLargeFiles);
els.quarantineLargeBtn.addEventListener("click", quarantineLargeFiles);
els.trashLargeBtn.addEventListener("click", trashLargeFiles);

els.largeBody.addEventListener("change", (e) => {
  const cb = e.target.closest(".lf-checkbox");
  if (!cb) return;
  const idx = parseInt(cb.dataset.index, 10);
  if (cb.checked) largeFilesSelected.add(idx);
  else largeFilesSelected.delete(idx);
  updateLargeFilesButtons();

  if (largeFilesResult) {
    els.largeSelectAll.checked = largeFilesSelected.size === largeFilesResult.files.length;
    els.largeSelectAll.indeterminate =
      largeFilesSelected.size > 0 && largeFilesSelected.size < largeFilesResult.files.length;
  }
});

els.largeSelectAll.addEventListener("change", () => {
  if (!largeFilesResult) return;
  if (els.largeSelectAll.checked) {
    largeFilesResult.files.forEach((_, i) => largeFilesSelected.add(i));
  } else {
    largeFilesSelected.clear();
  }
  els.largeBody.querySelectorAll(".lf-checkbox").forEach((cb, i) => {
    cb.checked = largeFilesSelected.has(i);
  });
  updateLargeFilesButtons();
});

// ---------- schedules ----------

async function loadSchedules() {
  try {
    const res = await fetch("/api/schedules");
    const data = await res.json();
    renderSchedules(data.schedules || [], data.scheduler_running);
  } catch {}
}

function renderSchedules(schedules, running) {
  els.schedBadge.textContent = running ? "RUNNING" : "STOPPED";
  els.schedBadge.className = `scheduler-badge ${running ? "on" : "off"}`;

  if (schedules.length === 0) {
    els.schedEmpty.classList.remove("hidden");
    els.schedList.innerHTML = "";
    return;
  }

  els.schedEmpty.classList.add("hidden");
  els.schedList.innerHTML = schedules.map(s => {
    const status = s.last_error
      ? `<div class="schedule-error">Last error: ${escapeHtml(s.last_error)}</div>`
      : s.last_run
        ? `<div class="schedule-meta">Last run: ${escapeHtml(s.last_run)} · ${s.last_moved} file(s) moved · next: ${escapeHtml(s.next_run || "—")}</div>`
        : `<div class="schedule-meta">Never run · next: ${escapeHtml(s.next_run || "—")}</div>`;

    return `
      <div class="schedule-item ${s.enabled ? "" : "disabled"}" data-id="${escapeHtml(s.id)}">
        <div class="schedule-row">
          <span class="schedule-folder" title="${escapeHtml(s.folder)}">${escapeHtml(s.folder)}</span>
          <div class="schedule-actions">
            <button class="secondary tiny sched-run" data-id="${escapeHtml(s.id)}">Run now</button>
            <button class="secondary tiny sched-toggle" data-id="${escapeHtml(s.id)}" data-enabled="${s.enabled}">${s.enabled ? "Disable" : "Enable"}</button>
            <button class="danger tiny sched-delete" data-id="${escapeHtml(s.id)}">Delete</button>
          </div>
        </div>
        <div class="schedule-meta">${escapeHtml(s.mode)} · every ${s.interval_minutes} min · ${s.enabled ? "enabled" : "disabled"}</div>
        ${status}
      </div>
    `;
  }).join("");
}

async function addSchedule() {
  const folder = els.schedFolder.value.trim() || els.folder.value.trim();
  if (!folder) { showStatus("Enter a folder path for the schedule.", "error"); return; }

  const interval = parseInt(els.schedInterval.value, 10);
  if (!interval || interval < 1) { showStatus("Interval must be at least 1 minute.", "error"); return; }

  els.addScheduleBtn.disabled = true;
  try {
    const res = await fetch("/api/schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        folder,
        mode: els.schedMode.value,
        interval_minutes: interval,
      }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    showStatus(`Schedule added for ${folder}`, "success");
    els.schedFolder.value = "";
    await loadSchedules();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.addScheduleBtn.disabled = false;
  }
}

els.schedList.addEventListener("click", async (e) => {
  const runBtn = e.target.closest(".sched-run");
  const toggleBtn = e.target.closest(".sched-toggle");
  const delBtn = e.target.closest(".sched-delete");
  if (!runBtn && !toggleBtn && !delBtn) return;

  const target = runBtn || toggleBtn || delBtn;
  const id = target.dataset.id;

  try {
    if (runBtn) {
      const res = await fetch(`/api/schedules/${id}/run`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
      showStatus(`Ran schedule — ${data.schedule.last_moved} file(s) moved`, "success");
      await loadLogs();
    } else if (toggleBtn) {
      const newEnabled = toggleBtn.dataset.enabled !== "true";
      const res = await fetch(`/api/schedules/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: newEnabled }),
      });
      const data = await res.json();
      if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    } else if (delBtn) {
      if (!confirm("Delete this schedule?")) return;
      const res = await fetch(`/api/schedules/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    }
    await loadSchedules();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  }
});

els.addScheduleBtn.addEventListener("click", addSchedule);

setInterval(() => {
  if (!document.hidden && !wsConnected) loadSchedules();
}, 30000);

// ---------- settings ----------

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    currentSettings = data.settings;
    dateFormatOptions = data.date_format_options || [];
    renderSettings();
  } catch {}
}

function renderSettings() {
  if (!currentSettings) return;

  els.setDefaultMode.value = currentSettings.default_mode || "extension";
  els.setCollisionStyle.value = currentSettings.collision_style || "numeric";

  const currentFmt = currentSettings.date_format;
  const known = dateFormatOptions.some(o => o.value === currentFmt);
  els.setDateFormat.innerHTML = dateFormatOptions.map(o =>
    `<option value="${escapeHtml(o.value)}" ${o.value === currentFmt ? "selected" : ""}>${escapeHtml(o.label)}</option>`
  ).join("");
  if (!known && currentFmt) {
    els.setDateFormat.insertAdjacentHTML(
      "beforeend",
      `<option value="${escapeHtml(currentFmt)}" selected>${escapeHtml(currentFmt)} (custom)</option>`
    );
  }

  renderChips(els.skipNamesChips, currentSettings.skip_names || [], "skip_names");
  renderChips(els.skipPrefixesChips, currentSettings.skip_prefixes || [], "skip_prefixes");

  if (currentSettings.has_password) {
    els.passwordStatus.textContent = "Password is set.";
    els.passwordStatus.className = "password-status ok";
    els.passwordStatus.classList.remove("hidden");
  } else {
    els.passwordStatus.textContent = "No password — the app is open to anyone who can reach it.";
    els.passwordStatus.className = "password-status";
    els.passwordStatus.classList.remove("hidden");
  }
}

function renderChips(container, values, field) {
  container.innerHTML = values.map(v => `
    <span class="skip-chip">
      ${escapeHtml(v)}
      <button data-field="${field}" data-value="${escapeHtml(v)}" title="Remove">×</button>
    </span>
  `).join("");
}

async function saveSettings(partial) {
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(partial),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    currentSettings = data.settings;
    renderSettings();
    flashSaved();
    await checkAuth();
    updateLogoutVisibility();
  } catch (err) {
    showStatus(`Settings: ${err.message}`, "error");
  }
}

let savedTimer = null;
function flashSaved() {
  els.settingsSaved.classList.remove("hidden");
  if (savedTimer) clearTimeout(savedTimer);
  savedTimer = setTimeout(() => els.settingsSaved.classList.add("hidden"), 1500);
}

els.setDefaultMode.addEventListener("change", () => {
  saveSettings({ default_mode: els.setDefaultMode.value });
});

els.setCollisionStyle.addEventListener("change", () => {
  saveSettings({ collision_style: els.setCollisionStyle.value });
});

els.setDateFormat.addEventListener("change", () => {
  saveSettings({ date_format: els.setDateFormat.value });
});

els.settingsBody.addEventListener("click", async (e) => {
  const btn = e.target.closest(".skip-chip button");
  if (!btn) return;
  const field = btn.dataset.field;
  const value = btn.dataset.value;
  const list = (currentSettings[field] || []).filter(v => v !== value);
  await saveSettings({ [field]: list });
});

els.addSkipName.addEventListener("click", async () => {
  const v = els.newSkipName.value.trim();
  if (!v) return;
  const list = [...(currentSettings.skip_names || [])];
  if (!list.includes(v)) list.push(v);
  els.newSkipName.value = "";
  await saveSettings({ skip_names: list });
});

els.newSkipName.addEventListener("keydown", (e) => {
  if (e.key === "Enter") els.addSkipName.click();
});

els.addSkipPrefix.addEventListener("click", async () => {
  const v = els.newSkipPrefix.value.trim();
  if (!v) return;
  const list = [...(currentSettings.skip_prefixes || [])];
  if (!list.includes(v)) list.push(v);
  els.newSkipPrefix.value = "";
  await saveSettings({ skip_prefixes: list });
});

els.newSkipPrefix.addEventListener("keydown", (e) => {
  if (e.key === "Enter") els.addSkipPrefix.click();
});

els.setPasswordBtn.addEventListener("click", async () => {
  const pw = els.newPassword.value;
  if (!pw) { showStatus("Enter a password first.", "error"); return; }
  if (pw.length < 6) { showStatus("Password must be at least 6 characters.", "error"); return; }
  els.setPasswordBtn.disabled = true;
  try {
    await saveSettings({ password: pw });
    els.newPassword.value = "";
    showStatus("Password set. Logins are now required.", "success");
  } finally {
    els.setPasswordBtn.disabled = false;
  }
});

els.newPassword.addEventListener("keydown", (e) => {
  if (e.key === "Enter") els.setPasswordBtn.click();
});

els.clearPasswordBtn.addEventListener("click", async () => {
  if (!currentSettings || !currentSettings.has_password) return;
  if (!confirm("Remove the password? Anyone who can reach this app will have full access.")) return;
  els.clearPasswordBtn.disabled = true;
  try {
    await saveSettings({ password: "" });
    els.newPassword.value = "";
    showStatus("Password removed. The app is open again.", "success");
  } finally {
    els.clearPasswordBtn.disabled = false;
  }
});

els.toggleSettings.addEventListener("click", () => {
  settingsVisible = !settingsVisible;
  els.settingsBody.classList.toggle("hidden", !settingsVisible);
  els.toggleSettings.textContent = settingsVisible ? "Hide" : "Show";
  if (settingsVisible) loadSettings();
});

// ---------- backup / restore ----------

function getImportStrategy() {
  const checked = document.querySelector('input[name="import-strategy"]:checked');
  return checked ? checked.value : "replace";
}

async function exportConfig() {
  try {
    window.location.href = "/api/config/export";
    showStatus("Downloading config bundle...", "info");
  } catch (err) {
    showStatus(`Export failed: ${err.message}`, "error");
  }
}

async function importConfigFile(file) {
  if (!file) return;

  const strategy = getImportStrategy();

  let bundle;
  try {
    const text = await file.text();
    bundle = JSON.parse(text);
  } catch (err) {
    showStatus(`Invalid JSON file: ${err.message}`, "error");
    return;
  }

  const confirmed = confirm(
    `Import "${file.name}" with strategy: ${strategy.toUpperCase()}?\n\n` +
    (strategy === "replace"
      ? "This will OVERWRITE your current rules, settings, schedules, and folder rules."
      : "Categories and schedules will be merged (existing preserved).")
  );
  if (!confirmed) return;

  try {
    const res = await fetch("/api/config/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bundle, strategy }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    const a = data.applied;
    showStatus(
      `Imported — ${a.rules} categories, ${a.folder_rules || 0} folder rule(s), settings ${a.settings ? "updated" : "skipped"}, ${a.schedules} schedule(s)`,
      "success"
    );

    await loadSettings();
    await loadRules();
    await loadFolderRules();
    await loadSchedules();
    await checkAuth();
    updateLogoutVisibility();
  } catch (err) {
    showStatus(`Import failed: ${err.message}`, "error");
  }
}

async function resetConfig() {
  const confirmed = confirm(
    "Reset rules, settings, schedules, and folder rules to defaults?\n\n" +
    "This does NOT touch your files or history logs."
  );
  if (!confirmed) return;

  try {
    const res = await fetch("/api/config/reset", { method: "POST" });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    showStatus("Config reset to defaults.", "success");
    await loadSettings();
    await loadRules();
    await loadFolderRules();
    await loadSchedules();
    await checkAuth();
    updateLogoutVisibility();
  } catch (err) {
    showStatus(`Reset failed: ${err.message}`, "error");
  }
}

els.exportConfigBtn.addEventListener("click", exportConfig);

els.importFileInput.addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  await importConfigFile(file);
  e.target.value = "";
});

els.resetConfigBtn.addEventListener("click", resetConfig);

// ---------- config backups ----------

async function loadBackups() {
  try {
    const res = await fetch("/api/backups");
    const data = await res.json();
    renderBackups(data.backups || []);
  } catch {}
}

function renderBackups(backups) {
  els.backupsCount.textContent = backups.length
    ? `${backups.length} snapshot${backups.length === 1 ? "" : "s"}`
    : "";

  if (backups.length === 0) {
    els.backupsTable.classList.add("hidden");
    els.backupsEmpty.classList.remove("hidden");
    return;
  }

  els.backupsEmpty.classList.add("hidden");
  els.backupsTable.classList.remove("hidden");

  els.backupsBody.innerHTML = backups.map(b => {
    const sizeKb = (b.size_bytes / 1024).toFixed(1);
    return `
      <tr data-filename="${escapeHtml(b.filename)}">
        <td>${escapeHtml(b.created_at)}</td>
        <td>${sizeKb} KB</td>
        <td class="filename-cell" title="${escapeHtml(b.filename)}">${escapeHtml(b.filename)}</td>
        <td class="actions-cell">
          <button class="primary backup-restore" data-file="${escapeHtml(b.filename)}">Restore</button>
          <button class="secondary backup-download" data-file="${escapeHtml(b.filename)}">Download</button>
          <button class="danger backup-delete" data-file="${escapeHtml(b.filename)}">Delete</button>
        </td>
      </tr>
    `;
  }).join("");
}

async function createBackup() {
  els.createBackupBtn.disabled = true;
  els.createBackupBtn.textContent = "Creating...";
  try {
    const res = await fetch("/api/backups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    showStatus(`Backup created: ${data.backup.filename}`, "success");
    await loadBackups();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.createBackupBtn.disabled = false;
    els.createBackupBtn.textContent = "Create backup now";
  }
}

async function restoreBackup(filename) {
  const confirmed = confirm(
    `Restore configuration from:\n${filename}\n\n` +
    `This will replace your current rules, settings, schedules, and folder rules.`
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/backups/${encodeURIComponent(filename)}/restore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy: "replace" }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    showStatus("Backup restored.", "success");

    await loadSettings();
    if (rulesVisible) await loadRules();
    if (folderRulesVisible) await loadFolderRules();
    await loadSchedules();
    await checkAuth();
    updateLogoutVisibility();
  } catch (err) {
    showStatus(`Restore failed: ${err.message}`, "error");
  }
}

async function deleteBackup(filename) {
  if (!confirm(`Delete backup:\n${filename}?`)) return;
  try {
    const res = await fetch(`/api/backups/${encodeURIComponent(filename)}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }
    await loadBackups();
  } catch (err) {
    showStatus(`Delete failed: ${err.message}`, "error");
  }
}

function downloadBackup(filename) {
  window.location.href = `/api/backups/${encodeURIComponent(filename)}/download`;
}

els.createBackupBtn.addEventListener("click", createBackup);

els.backupsBody.addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  const filename = btn.dataset.file;
  if (btn.classList.contains("backup-restore")) return restoreBackup(filename);
  if (btn.classList.contains("backup-delete"))  return deleteBackup(filename);
  if (btn.classList.contains("backup-download")) return downloadBackup(filename);
});

// ---------- rules editor (global) ----------

async function loadRules() {
  try {
    const res = await fetch("/api/rules");
    const data = await res.json();
    renderRules(data);
  } catch (err) {
    els.rulesList.innerHTML = `<p class="rules-hint">Failed to load rules: ${escapeHtml(err.message)}</p>`;
  }
}

function renderRules(rules) {
  const entries = Object.entries(rules);
  if (entries.length === 0) {
    els.rulesList.innerHTML = `<p class="rules-hint">No categories yet. Add one below.</p>`;
    return;
  }

  els.rulesList.innerHTML = entries.map(([cat, cfg]) => {
    const exts = Array.isArray(cfg) ? cfg : (cfg.extensions || []);
    const split = Array.isArray(cfg) ? null : cfg.size_split_mb;
    const splitValue = split != null ? split : "";

    return `
      <div class="rules-row" data-category="${escapeHtml(cat)}">
        <div class="rules-cat">${escapeHtml(cat)}</div>
        <div class="rules-exts">
          ${exts.map(e => `
            <span class="ext-chip">
              ${escapeHtml(e)}
              <button class="chip-x" data-cat="${escapeHtml(cat)}" data-ext="${escapeHtml(e)}" title="Remove">×</button>
            </span>
          `).join("")}
          <input type="text" class="ext-input" placeholder="+ ext" spellcheck="false" />
          <button class="ext-add-btn secondary">Add</button>
          <button class="cat-del-btn danger">Delete category</button>
          <span class="size-split-cell" title="Files above this size go to {category}/large/, others to {category}/small/. Leave blank for no split.">
            Size split:
            <input type="number" class="size-split-input" data-cat="${escapeHtml(cat)}" min="1" step="1"
                   value="${escapeHtml(splitValue)}" placeholder="—" />
            MB
          </span>
        </div>
      </div>
    `;
  }).join("");
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
  return data;
}

els.rulesList.addEventListener("click", async (e) => {
  const row = e.target.closest(".rules-row");
  if (!row) return;
  const category = row.dataset.category;

  if (e.target.classList.contains("chip-x")) {
    try {
      await apiPost("/api/rules/remove-extension", { category, extension: e.target.dataset.ext });
      await loadRules();
    } catch (err) { showStatus(`Rules: ${err.message}`, "error"); }
    return;
  }

  if (e.target.classList.contains("ext-add-btn")) {
    const input = row.querySelector(".ext-input");
    const value = input.value.trim();
    if (!value) return;
    try {
      await apiPost("/api/rules/add-extension", { category, extension: value });
      await loadRules();
    } catch (err) { showStatus(`Rules: ${err.message}`, "error"); }
    return;
  }

  if (e.target.classList.contains("cat-del-btn")) {
    if (!confirm(`Delete category "${category}"?`)) return;
    try {
      await apiPost("/api/rules/remove-category", { name: category });
      await loadRules();
    } catch (err) { showStatus(`Rules: ${err.message}`, "error"); }
  }
});

els.rulesList.addEventListener("change", async (e) => {
  const input = e.target.closest(".size-split-input");
  if (!input) return;
  const category = input.dataset.cat;
  const raw = input.value.trim();
  const mb = raw === "" ? null : parseFloat(raw);
  if (mb !== null && (isNaN(mb) || mb <= 0)) {
    showStatus("Size split must be a positive number.", "error");
    return;
  }
  try {
    await apiPost("/api/rules/set-size-split", { category, size_split_mb: mb });
    showStatus(mb === null
      ? `Size split cleared for ${category}`
      : `${category} will split at ${mb} MB`, "success");
    await loadRules();
  } catch (err) {
    showStatus(`Size split: ${err.message}`, "error");
  }
});

els.rulesList.addEventListener("keydown", async (e) => {
  if (e.key === "Enter" && e.target.classList.contains("size-split-input")) {
    e.preventDefault();
    e.target.blur();
    return;
  }
  if (e.key !== "Enter" || !e.target.classList.contains("ext-input")) return;
  e.preventDefault();
  e.target.closest(".rules-row").querySelector(".ext-add-btn").click();
});

els.addCategoryBtn.addEventListener("click", async () => {
  const name = els.newCategory.value.trim();
  if (!name) { showStatus("Enter a category name.", "error"); return; }
  try {
    await apiPost("/api/rules/add-category", { name });
    els.newCategory.value = "";
    await loadRules();
    showStatus(`Category "${name}" added.`, "success");
  } catch (err) { showStatus(`Rules: ${err.message}`, "error"); }
});

els.newCategory.addEventListener("keydown", (e) => {
  if (e.key === "Enter") els.addCategoryBtn.click();
});

els.toggleRules.addEventListener("click", () => {
  rulesVisible = !rulesVisible;
  els.rulesBody.classList.toggle("hidden", !rulesVisible);
  els.toggleRules.textContent = rulesVisible ? "Hide" : "Show";
  if (rulesVisible) loadRules();
});

// ---------- folder rules editor ----------

async function loadFolderRules() {
  try {
    const res = await fetch("/api/folder-rules");
    const data = await res.json();
    folderRules = data.folders || [];
    renderFolderRules();
  } catch (err) {
    els.folderRulesList.innerHTML = `<p class="folder-rules-hint">Failed to load: ${escapeHtml(err.message)}</p>`;
  }
}

function renderFolderRules() {
  if (folderRules.length === 0) {
    els.folderRulesEmpty.classList.remove("hidden");
    els.folderRulesList.innerHTML = "";
    return;
  }
  els.folderRulesEmpty.classList.add("hidden");

  els.folderRulesList.innerHTML = folderRules.map(entry => {
    const path = entry.path;
    const rules = entry.rules || {};
    const catCount = Object.keys(rules).length;

    const ruleRows = Object.entries(rules).map(([cat, exts]) => `
      <div class="rules-row" data-category="${escapeHtml(cat)}">
        <div class="rules-cat">${escapeHtml(cat)}</div>
        <div class="rules-exts">
          ${exts.map(e => `
            <span class="ext-chip">
              ${escapeHtml(e)}
              <button class="fr-chip-x" data-cat="${escapeHtml(cat)}" data-ext="${escapeHtml(e)}" title="Remove">×</button>
            </span>
          `).join("")}
          <input type="text" class="ext-input fr-ext-input" placeholder="+ ext" spellcheck="false" />
          <button class="fr-ext-add secondary tiny">Add</button>
          <button class="fr-cat-del danger tiny">Delete category</button>
        </div>
      </div>
    `).join("") || `<p class="rules-hint">No categories yet. Add one below.</p>`;

    return `
      <div class="folder-rule-item" data-path="${escapeHtml(path)}">
        <div class="folder-rule-header">
          <span class="folder-rule-path" title="${escapeHtml(path)}">
            <span class="badge">${catCount}</span>${escapeHtml(path)}
          </span>
          <div class="folder-rule-actions">
            <button class="secondary tiny fr-toggle">Edit</button>
            <button class="danger tiny fr-delete">Delete</button>
          </div>
        </div>
        <div class="folder-rule-body hidden">
          ${ruleRows}
          <div class="rules-add-category">
            <input type="text" class="ext-input fr-new-cat" placeholder="New category name" spellcheck="false" />
            <button class="primary fr-add-cat">Add category</button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function saveFolderRule(path, rules) {
  const res = await fetch("/api/folder-rules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, rules }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
  return data.entry;
}

async function addFolderRule() {
  const path = els.newFolderRulePath.value.trim();
  if (!path) { showStatus("Enter a folder path.", "error"); return; }
  els.addFolderRuleBtn.disabled = true;
  try {
    await saveFolderRule(path, {});
    els.newFolderRulePath.value = "";
    showStatus(`Folder rule added for ${path}`, "success");
    await loadFolderRules();
  } catch (err) {
    showStatus(`Folder rules: ${err.message}`, "error");
  } finally {
    els.addFolderRuleBtn.disabled = false;
  }
}

els.addFolderRuleBtn.addEventListener("click", addFolderRule);

els.newFolderRulePath.addEventListener("keydown", (e) => {
  if (e.key === "Enter") els.addFolderRuleBtn.click();
});

els.toggleFolderRules.addEventListener("click", () => {
  folderRulesVisible = !folderRulesVisible;
  els.folderRulesBody.classList.toggle("hidden", !folderRulesVisible);
  els.toggleFolderRules.textContent = folderRulesVisible ? "Hide" : "Show";
  if (folderRulesVisible) loadFolderRules();
});

els.folderRulesList.addEventListener("click", async (e) => {
  const item = e.target.closest(".folder-rule-item");
  if (!item) return;
  const path = item.dataset.path;

  if (e.target.classList.contains("fr-toggle")) {
    const body = item.querySelector(".folder-rule-body");
    body.classList.toggle("hidden");
    e.target.textContent = body.classList.contains("hidden") ? "Edit" : "Done";
    return;
  }

  if (e.target.classList.contains("fr-delete")) {
    if (!confirm(`Delete folder rule for:\n${path}?`)) return;
    try {
      const res = await fetch(`/api/folder-rules?path=${encodeURIComponent(path)}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
      showStatus(`Folder rule removed for ${path}`, "success");
      await loadFolderRules();
    } catch (err) {
      showStatus(`Folder rules: ${err.message}`, "error");
    }
    return;
  }

  const entry = folderRules.find(f => f.path === path);
  if (!entry) return;
  const currentRules = { ...(entry.rules || {}) };

  if (e.target.classList.contains("fr-chip-x")) {
    const cat = e.target.dataset.cat;
    const ext = e.target.dataset.ext;
    if (!currentRules[cat]) return;
    currentRules[cat] = currentRules[cat].filter(x => x !== ext);
    try {
      await saveFolderRule(path, currentRules);
      await loadFolderRules();
    } catch (err) { showStatus(`Folder rules: ${err.message}`, "error"); }
    return;
  }

  if (e.target.classList.contains("fr-ext-add")) {
    const row = e.target.closest(".rules-row");
    const cat = row.dataset.category;
    const input = row.querySelector(".fr-ext-input");
    const value = input.value.trim();
    if (!value) return;
    const normalised = value.startsWith(".") ? value.toLowerCase() : "." + value.toLowerCase();
    const exts = new Set(currentRules[cat] || []);
    exts.add(normalised);
    currentRules[cat] = Array.from(exts).sort();
    try {
      await saveFolderRule(path, currentRules);
      await loadFolderRules();
    } catch (err) { showStatus(`Folder rules: ${err.message}`, "error"); }
    return;
  }

  if (e.target.classList.contains("fr-cat-del")) {
    const row = e.target.closest(".rules-row");
    const cat = row.dataset.category;
    if (!confirm(`Delete category "${cat}" for this folder?`)) return;
    delete currentRules[cat];
    try {
      await saveFolderRule(path, currentRules);
      await loadFolderRules();
    } catch (err) { showStatus(`Folder rules: ${err.message}`, "error"); }
    return;
  }

  if (e.target.classList.contains("fr-add-cat")) {
    const input = item.querySelector(".fr-new-cat");
    const name = input.value.trim();
    if (!name) return;
    if (currentRules[name]) {
      showStatus(`Category "${name}" already exists`, "error");
      return;
    }
    currentRules[name] = [];
    try {
      await saveFolderRule(path, currentRules);
      await loadFolderRules();
    } catch (err) { showStatus(`Folder rules: ${err.message}`, "error"); }
    return;
  }
});

els.folderRulesList.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  if (e.target.classList.contains("fr-ext-input")) {
    e.preventDefault();
    e.target.closest(".rules-row").querySelector(".fr-ext-add").click();
  } else if (e.target.classList.contains("fr-new-cat")) {
    e.preventDefault();
    e.target.closest(".folder-rule-item").querySelector(".fr-add-cat").click();
  }
});

// ---------- misc ----------

function clear() {
  els.folder.value = "";
  hideStatus();
  hideResults();
}

els.scanBtn.addEventListener("click", scan);
els.organizeBtn.addEventListener("click", organize);
els.undoBtn.addEventListener("click", undoLatest);
els.clearBtn.addEventListener("click", clear);
els.folder.addEventListener("keydown", (e) => { if (e.key === "Enter") scan(); });

// ---------- init ----------

async function boot() {
  const s = await fetch("/api/settings").then(r => r.json()).catch(() => null);
  const initialMode = s?.settings?.default_mode || "extension";
  setMode(initialMode);
  currentSettings = s?.settings || null;
  dateFormatOptions = s?.date_format_options || [];

  try {
    const t = await fetch("/api/trash/status").then(r => r.json());
    trashSupported = t.supported === true;
  } catch {
    trashSupported = false;
  }

  updateLogoutVisibility();

  loadLogs();
  loadSchedules();
  loadBackups();
  refreshWatch();

  connectWs();
}

async function init() {
  wireLoginUI();
  const status = await checkAuth();
  if (status.required && !status.authenticated) {
    showLoginOverlay();
    return;
  }
  await boot();
}

init();

window.addEventListener("beforeunload", () => {
  if (ws) { try { ws.close(); } catch {} }
});
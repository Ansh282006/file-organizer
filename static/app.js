const $ = (sel) => document.querySelector(sel);

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
  setDateFormat:    $("#set-date-format"),
  skipNamesChips:   $("#skip-names-chips"),
  skipPrefixesChips:$("#skip-prefixes-chips"),
  newSkipName:      $("#new-skip-name"),
  addSkipName:      $("#add-skip-name"),
  newSkipPrefix:    $("#new-skip-prefix"),
  addSkipPrefix:    $("#add-skip-prefix"),
  settingsSaved:    $("#settings-saved"),
  // backup
  exportConfigBtn:  $("#export-config-btn"),
  importFileInput:  $("#import-file-input"),
  resetConfigBtn:   $("#reset-config-btn"),
};

let latestUndoableLog = null;
let rulesVisible = false;
let settingsVisible = false;
let currentMode = "extension";
let watchPollTimer = null;
let currentSettings = null;
let dateFormatOptions = [];
let lastDupeResult = null;
let trashSupported = false;

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
    const thumb = it.is_image
      ? `<img class="thumb" src="/api/thumbnail?path=${encodeURIComponent(it.source)}" alt="" loading="lazy" onerror="this.style.display='none'" />`
      : `<span class="filetype">${filetypeBadge(it.source_name)}</span>`;

    return `
      <tr class="${it.renamed ? "renamed" : ""}">
        <td class="thumb-cell">${thumb}</td>
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
    startWatchPolling();
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
    stopWatchPolling();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  }
}

function startWatchPolling() {
  stopWatchPolling();
  watchPollTimer = setInterval(refreshWatch, 2000);
}

function stopWatchPolling() {
  if (watchPollTimer) { clearInterval(watchPollTimer); watchPollTimer = null; }
}

els.watchStartBtn.addEventListener("click", watchStart);
els.watchStopBtn.addEventListener("click", watchStop);

// ---------- duplicates ----------

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function renderDuplicates(result) {
  lastDupeResult = result;

  if (result.total_groups === 0) {
    els.dupesBadge.textContent = "CLEAN";
    els.dupesBadge.className = "dupes-badge clean";
    els.dupesStatus.textContent =
      `Scanned ${result.total_files} file(s) — no duplicates found.`;
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
  if (!document.hidden) loadSchedules();
}, 15000);

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
      ? "This will OVERWRITE your current rules, settings, and schedules."
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
      `Imported — ${a.rules} categories, settings ${a.settings ? "updated" : "skipped"}, ${a.schedules} schedule(s)`,
      "success"
    );

    await loadSettings();
    await loadRules();
    await loadSchedules();
  } catch (err) {
    showStatus(`Import failed: ${err.message}`, "error");
  }
}

async function resetConfig() {
  const confirmed = confirm(
    "Reset rules, settings, and schedules to defaults?\n\n" +
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
    await loadSchedules();
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

// ---------- rules editor ----------

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

  els.rulesList.innerHTML = entries.map(([cat, exts]) => `
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
      </div>
    </div>
  `).join("");
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

els.rulesList.addEventListener("keydown", async (e) => {
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

async function init() {
  const s = await fetch("/api/settings").then(r => r.json()).catch(() => null);
  const initialMode = s?.settings?.default_mode || "extension";
  setMode(initialMode);
  currentSettings = s?.settings || null;
  dateFormatOptions = s?.date_format_options || [];

  // Check trash support
  try {
    const t = await fetch("/api/trash/status").then(r => r.json());
    trashSupported = t.supported === true;
  } catch {
    trashSupported = false;
  }

  loadLogs();
  loadSchedules();
  refreshWatch().then(() => {
    fetch("/api/watch/status").then(r => r.json()).then(d => {
      if (d.watching) startWatchPolling();
    });
  });
}

init();
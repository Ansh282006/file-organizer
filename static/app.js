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
};

let latestUndoableLog = null;
let rulesVisible = false;
let currentMode = "extension";
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

// ---------- mode toggle ----------

function setMode(mode) {
  currentMode = mode;
  els.modeBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.mode === mode));
  els.modeHint.textContent = MODE_HINTS[mode] || "";
  hideStatus();
  hideResults();
}

els.modeBtns.forEach(btn => btn.addEventListener("click", () => setMode(btn.dataset.mode)));

// ---------- logs + undo ----------

async function loadLogs() {
  try {
    const res = await fetch("/api/logs");
    const data = await res.json();
    const undoable = (data.logs || []).find(l => !l.undone);
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
  } catch {}
}

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

// ---------- organize ----------

async function organize() {
  const path = els.folder.value.trim();
  if (!path) return;

  const confirmed = confirm(
    `Move all files in:\n${path}\n\nMode: ${currentMode}\n\nYou can undo this from the Undo button. Continue?`
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

// ---------- undo ----------

async function undo() {
  if (!latestUndoableLog) return;

  const confirmed = confirm(
    `Undo the last organize run?\n${latestUndoableLog}\n\nAll moved files will be restored.`
  );
  if (!confirmed) return;

  els.undoBtn.disabled = true;
  els.undoBtn.textContent = "Undoing...";
  hideStatus();

  try {
    const res = await fetch("/api/undo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ log_file: latestUndoableLog }),
    });
    const data = await res.json();
    if (!res.ok) { showStatus(data.detail || `Error ${res.status}`, "error"); return; }

    const errCount = (data.errors || []).length;
    const kind = errCount > 0 ? "error" : "success";
    showStatus(
      `Undone: ${data.restored} file(s) restored` +
      (errCount > 0 ? `, ${errCount} error(s)` : ""),
      kind
    );
    await scan();
    await loadLogs();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.undoBtn.textContent = "Undo";
  }
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
      <tr><td colspan="4" style="text-align:center; color:var(--muted); padding:24px;">
        Nothing to organize — folder is already clean.
      </td></tr>`;
    els.organizeBtn.disabled = true;
    return;
  }

  els.organizeBtn.disabled = false;

  const rows = plan.items.map(it => `
    <tr class="${it.renamed ? "renamed" : ""}">
      <td>${escapeHtml(it.source_name)}</td>
      <td class="arrow">→</td>
      <td class="destination">${escapeHtml(it.destination_rel)}</td>
      <td class="category">${escapeHtml(it.category)}</td>
    </tr>
  `);
  els.previewBody.innerHTML = rows.join("");
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
els.undoBtn.addEventListener("click", undo);
els.clearBtn.addEventListener("click", clear);
els.folder.addEventListener("keydown", (e) => { if (e.key === "Enter") scan(); });

// Initial state
setMode("extension");
loadLogs();
refreshWatch().then(() => {
  // If already watching (server restart), start polling
  fetch("/api/watch/status").then(r => r.json()).then(d => {
    if (d.watching) startWatchPolling();
  });
});
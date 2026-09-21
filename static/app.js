const $ = (sel) => document.querySelector(sel);

const els = {
  folder:        $("#folder-input"),
  scanBtn:       $("#scan-btn"),
  organizeBtn:   $("#organize-btn"),
  clearBtn:      $("#clear-btn"),
  status:        $("#status"),
  summary:       $("#summary"),
  summaryFolder: $("#summary-folder"),
  summaryCounts: $("#summary-counts"),
  preview:       $("#preview"),
  previewBody:   $("#preview-body"),
  actions:       $("#actions"),
};

function showStatus(msg, kind = "info") {
  els.status.textContent = msg;
  els.status.className = `status ${kind}`;
  els.status.classList.remove("hidden");
}

function hideStatus() {
  els.status.classList.add("hidden");
}

function hideResults() {
  els.summary.classList.add("hidden");
  els.preview.classList.add("hidden");
  els.actions.classList.add("hidden");
  els.previewBody.innerHTML = "";
}

async function scan() {
  const path = els.folder.value.trim();
  if (!path) {
    showStatus("Enter a folder path first.", "error");
    return;
  }

  els.scanBtn.disabled = true;
  els.scanBtn.textContent = "Scanning...";
  hideStatus();
  hideResults();

  try {
    const res = await fetch(`/api/scan?path=${encodeURIComponent(path)}`);
    const data = await res.json();

    if (!res.ok) {
      showStatus(data.detail || `Error ${res.status}`, "error");
      return;
    }

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
    `Move all files in:\n${path}\n\nThis can be undone from the log. Continue?`
  );
  if (!confirmed) return;

  els.organizeBtn.disabled = true;
  els.organizeBtn.textContent = "Organizing...";
  hideStatus();

  try {
    const res = await fetch("/api/organize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();

    if (!res.ok) {
      showStatus(data.detail || `Error ${res.status}`, "error");
      return;
    }

    showStatus(
      `${data.message}` + (data.log_file ? ` — log: ${data.log_file}` : ""),
      "success"
    );

    await scan();
  } catch (err) {
    showStatus(`Network error: ${err.message}`, "error");
  } finally {
    els.organizeBtn.disabled = false;
    els.organizeBtn.textContent = "Organize";
  }
}

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

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function clear() {
  els.folder.value = "";
  hideStatus();
  hideResults();
}

els.scanBtn.addEventListener("click", scan);
els.organizeBtn.addEventListener("click", organize);
els.clearBtn.addEventListener("click", clear);
els.folder.addEventListener("keydown", (e) => {
  if (e.key === "Enter") scan();
});
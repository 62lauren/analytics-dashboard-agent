// Session ID — persisted across page reloads
const sessionId = (() => {
  let id = localStorage.getItem("dashboard_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("dashboard_session_id", id);
  }
  return id;
})();

const TOOL_LABELS = {
  list_salesforce_objects: "Discovering available data sources",
  describe_salesforce_object: "Analyzing schema",
  query_salesforce: "Fetching data from Salesforce",
  generate_chart: "Building visualization",
  create_insight: "Generating action insight",
};

let isGenerating = false;

// ── DOM refs ──────────────────────────────────────────────────────────────────

const promptInput = document.getElementById("prompt-input");
const sendBtn = document.getElementById("send-btn");
const chatHistory = document.getElementById("chat-history");
const activityLog = document.getElementById("activity-log");
const chartsSection = document.getElementById("charts-section");
const insightsSection = document.getElementById("insights-section");
const chartsGrid = document.getElementById("charts-grid");
const insightsGrid = document.getElementById("insights-grid");
const emptyState = document.getElementById("empty-state");
const generatingBar = document.getElementById("generating-bar");

// ── Main entry point ──────────────────────────────────────────────────────────

async function generateDashboard() {
  const prompt = promptInput.value.trim();
  if (!prompt || isGenerating) return;

  isGenerating = true;
  sendBtn.disabled = true;
  promptInput.disabled = true;

  clearDashboard();
  addToHistory(prompt);
  activityLog.innerHTML = "";
  generatingBar.classList.add("visible");

  try {
    const res = await fetch("/api/dashboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, session_id: sessionId }),
    });

    if (!res.ok) {
      appendLog("error", "Request failed", `HTTP ${res.status}`);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            handleEvent(JSON.parse(line.slice(6)));
          } catch (_) { /* ignore malformed frames */ }
        }
      }
    }
  } catch (err) {
    appendLog("error", "Connection error", err.message);
  } finally {
    isGenerating = false;
    sendBtn.disabled = false;
    promptInput.disabled = false;
    generatingBar.classList.remove("visible");
    promptInput.value = "";
    promptInput.focus();
  }
}

// ── Event dispatcher ──────────────────────────────────────────────────────────

function handleEvent(event) {
  switch (event.type) {
    case "thinking":
      appendLog("thinking", "Reasoning…", event.text.slice(0, 120));
      break;

    case "text":
      appendLog("text", "Response", event.text.slice(0, 120));
      break;

    case "tool_call": {
      const label = TOOL_LABELS[event.name] || event.name;
      const detail = event.input && Object.keys(event.input).length
        ? JSON.stringify(event.input).slice(0, 100)
        : "";
      appendLog("tool-call", label + "…", detail);
      break;
    }

    case "tool_result": {
      const label = TOOL_LABELS[event.name] || event.name;
      const detail = event.is_error ? event.result : `✓ ${label}`;
      appendLog(event.is_error ? "tool-result error" : "tool-result", label, detail);
      break;
    }

    case "dashboard":
      renderDashboard(event.charts || [], event.insights || []);
      break;

    case "error":
      appendLog("error", "Error", event.message);
      break;
  }
}

// ── Render dashboard ──────────────────────────────────────────────────────────

function renderDashboard(charts, insights) {
  emptyState.style.display = "none";

  // Charts
  chartsGrid.innerHTML = "";
  if (charts.length > 0) {
    charts.forEach((fig, i) => {
      const card = document.createElement("div");
      card.className = "chart-card";
      const container = document.createElement("div");
      container.className = "chart-container";
      container.id = `chart-${i}`;
      card.appendChild(container);
      chartsGrid.appendChild(card);
      Plotly.newPlot(container.id, fig.data, fig.layout, { responsive: true, displayModeBar: false });
    });
    chartsSection.classList.add("visible");
  }

  // Insights
  insightsGrid.innerHTML = "";
  if (insights.length > 0) {
    insights.forEach((ins) => {
      const card = document.createElement("div");
      card.className = `insight-card priority-${ins.priority}`;
      card.innerHTML = `
        <div class="ic-header">
          <span class="priority-badge ${ins.priority}">${ins.priority}</span>
          <span class="ic-title">${escapeHtml(ins.title)}</span>
        </div>
        <div class="ic-finding">${escapeHtml(ins.finding)}</div>
        <div class="ic-rec-label">Recommendation</div>
        <div class="ic-rec">${escapeHtml(ins.recommendation)}</div>
      `;
      insightsGrid.appendChild(card);
    });
    insightsSection.classList.add("visible");
  }
}

// ── Chat history ──────────────────────────────────────────────────────────────

function addToHistory(prompt) {
  const empty = chatHistory.querySelector(".chat-history-empty");
  if (empty) empty.remove();

  // Deactivate previous active
  chatHistory.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));

  const item = document.createElement("div");
  item.className = "history-item active";
  const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  item.innerHTML = `
    <div class="hi-prompt">${escapeHtml(prompt)}</div>
    <div class="hi-time">${now}</div>
  `;
  chatHistory.appendChild(item);
  item.scrollIntoView({ block: "nearest" });
}

// ── Activity log ──────────────────────────────────────────────────────────────

function appendLog(type, label, detail) {
  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  entry.innerHTML = `<div class="le-label">${escapeHtml(label)}</div>`;
  if (detail) {
    const d = document.createElement("div");
    d.className = "le-detail";
    d.title = detail;
    d.textContent = detail;
    entry.appendChild(d);
  }
  activityLog.appendChild(entry);
  activityLog.scrollTop = activityLog.scrollHeight;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function clearDashboard() {
  chartsSection.classList.remove("visible");
  insightsSection.classList.remove("visible");
  chartsGrid.innerHTML = "";
  insightsGrid.innerHTML = "";
  emptyState.style.display = "";
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────

promptInput.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    generateDashboard();
  }
});

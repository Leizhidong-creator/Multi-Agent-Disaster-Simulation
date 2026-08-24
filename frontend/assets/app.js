const canvas = document.getElementById("sandbox");
const ctx = canvas.getContext("2d");

const state = {
  bootstrap: null,
  simulation: null,
  frameIndex: 0,
  animationHandle: null,
  running: false,
  currentDensity: 0,
  observedPeakDensity: 0,
  lastFrame: null,
  baselineReference: null,
  ripples: [],
  generatedRippleKeys: new Set(),
  selectedAgentId: null,
  hoveredAgentId: null,
  reportInterventions: [],
  activeIntervention: null,
  comparisonResult: null,
  reportRequestToken: 0,
  reportHistory: [],
  activeReportId: null,
  reportVersionSeed: 0,
  suppressReportModalUntil: 0,
  reportBaselineReference: null,
};

const elements = {
  dashboard: document.querySelector(".dashboard"),
  heroVideo: document.getElementById("hero-video"),
  workspacePanel: document.querySelector(".workspace-panel"),
  rightPanel: document.querySelector(".right-panel"),
  sandboxShell: document.getElementById("sandbox-shell"),
  canvasWrapper: document.querySelector(".canvas-wrapper"),
  agentInsightTag: document.getElementById("agent-insight-tag"),
  scenarioSelect: document.getElementById("scenario-select"),
  agentCount: document.getElementById("agent-count"),
  agentCountLabel: document.getElementById("agent-count-label"),
  northRate: document.getElementById("north-rate"),
  northRateLabel: document.getElementById("north-rate-label"),
  southRate: document.getElementById("south-rate"),
  southRateLabel: document.getElementById("south-rate-label"),
  normalPedestrianRatio: document.getElementById("normal-pedestrian-ratio"),
  normalPedestrianRatioLabel: document.getElementById("normal-pedestrian-ratio-label"),
  groupFamilyRatio: document.getElementById("group-family-ratio"),
  groupFamilyRatioLabel: document.getElementById("group-family-ratio-label"),
  vulnerableRatio: document.getElementById("vulnerable-ratio"),
  vulnerableRatioLabel: document.getElementById("vulnerable-ratio-label"),
  populationTotalLabel: document.getElementById("population-total-label"),
  mitigationStrategyGroup: document.getElementById("mitigation-strategy-group"),
  mitigationStrategy: document.getElementById("mitigation-strategy"),
  useApi: document.getElementById("use-api"),
  runButton: document.getElementById("run-button"),
  stopButton: document.getElementById("stop-button"),
  generateReportBtn: document.getElementById("generateReportBtn"),
  reportContent: document.getElementById("reportContent"),
  logStream: document.getElementById("log-stream"),
  simTime: document.getElementById("sim-time"),
  activeAgents: document.getElementById("active-agents"),
  peakDensity: document.getElementById("peak-density"),
  riskBadge: document.getElementById("risk-badge"),
  simPeakDensity: document.getElementById("sim-peak-density"),
  fitProgress: document.getElementById("fit-progress"),
  fitStatus: document.getElementById("fit-status"),
  historicalBaseline: document.getElementById("historical-baseline"),
  providerModel: document.getElementById("provider-model"),
  reportModal: document.getElementById("report-modal"),
  reportModalBackdrop: document.getElementById("report-modal-backdrop"),
  reportModalMeta: document.getElementById("report-modal-meta"),
  reportHistory: document.getElementById("report-history"),
  closeReportModal: document.getElementById("close-report-modal"),
  opsActiveTotal: document.getElementById("ops-active-total"),
  opsSystem1: document.getElementById("ops-system1"),
  opsSystem2: document.getElementById("ops-system2"),
  opsMarquee: document.getElementById("ops-marquee"),
  velDecay: document.getElementById("vel-decay"),
  conflictCount: document.getElementById("conflict-count"),
  exitRate: document.getElementById("exit-rate"),
  dwellSteps: document.getElementById("dwell-steps"),
  agentLockStatus: document.getElementById("agent-lock-status"),
  agentLockChip: document.getElementById("agent-lock-chip"),
  clearAgentLock: document.getElementById("clear-agent-lock"),
  fullscreenExitButton: document.getElementById("fullscreen-exit-button"),
};

const populationKeys = ["normal_pedestrian", "group_family", "vulnerable"];
const HERO_VIDEO_STREAM = "https://stream.mux.com/tLkHO1qZoaaQOUeVWo8hEBeGQfySP02EPS02BmnNFyXys.m3u8";
const BASE_CANVAS_WIDTH = 1200;
const BASE_CANVAS_HEIGHT = 800;

function getViewportScale() {
  return Math.min(canvas.width / BASE_CANVAS_WIDTH, canvas.height / BASE_CANVAS_HEIGHT);
}

function resizeCanvas() {
  const wrapper = elements.canvasWrapper;
  if (!wrapper) return;
  const rect = wrapper.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(BASE_CANVAS_WIDTH, Math.round(rect.width * dpr));
  const height = Math.max(BASE_CANVAS_HEIGHT, Math.round(rect.height * dpr));
  if (canvas.width === width && canvas.height === height) return;

  canvas.width = width;
  canvas.height = height;
  drawScene(getCurrentFrame() || { heatmap: [], agents: [] });
}

function initHeroVideo() {
  const video = elements.heroVideo;
  if (!video) return;
  const HlsCtor = window.Hls;
  if (HlsCtor?.isSupported()) {
    const hls = new HlsCtor({ enableWorker: false });
    hls.loadSource(HERO_VIDEO_STREAM);
    hls.attachMedia(video);
    return;
  }
  if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = HERO_VIDEO_STREAM;
  }
}

function getPopulationValues() {
  return {
    normal_pedestrian: Number(elements.normalPedestrianRatio.value),
    group_family: Number(elements.groupFamilyRatio.value),
    vulnerable: Number(elements.vulnerableRatio.value),
  };
}

function syncSimulationLimits() {
  const limits = state.bootstrap?.simulation_limits || {};
  const maxAgents = Number(limits.max_agents ?? 300);
  const maxArrivalRate = Number(limits.arrival_rate_max ?? 8);
  elements.agentCount.max = String(maxAgents);
  elements.northRate.max = String(maxArrivalRate);
  elements.southRate.max = String(maxArrivalRate);
  if (Number(elements.agentCount.value) > maxAgents) {
    elements.agentCount.value = String(maxAgents);
  }
  if (Number(elements.northRate.value) > maxArrivalRate) {
    elements.northRate.value = String(maxArrivalRate);
  }
  if (Number(elements.southRate.value) > maxArrivalRate) {
    elements.southRate.value = String(maxArrivalRate);
  }
  elements.agentCountLabel.textContent = elements.agentCount.value;
  elements.northRateLabel.textContent = Number(elements.northRate.value).toFixed(1);
  elements.southRateLabel.textContent = Number(elements.southRate.value).toFixed(1);
}

function setPopulationValues(values) {
  elements.normalPedestrianRatio.value = String(values.normal_pedestrian);
  elements.groupFamilyRatio.value = String(values.group_family);
  elements.vulnerableRatio.value = String(values.vulnerable);
  elements.normalPedestrianRatioLabel.textContent = `${values.normal_pedestrian}%`;
  elements.groupFamilyRatioLabel.textContent = `${values.group_family}%`;
  elements.vulnerableRatioLabel.textContent = `${values.vulnerable}%`;
  elements.populationTotalLabel.textContent = `${values.normal_pedestrian + values.group_family + values.vulnerable}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function sanitizeReportHtml(value) {
  const template = document.createElement("template");
  template.innerHTML = String(value ?? "");
  const allowedTags = new Set([
    "A", "BLOCKQUOTE", "BR", "CODE", "DIV", "EM", "H1", "H2", "H3", "H4", "H5", "H6",
    "HR", "IMG", "LI", "OL", "P", "PRE", "SPAN", "STRONG", "TABLE", "TBODY", "TD", "TH",
    "THEAD", "TR", "UL",
  ]);
  const allowedAttributes = {
    A: new Set(["href", "title"]),
    CODE: new Set(["class"]),
    IMG: new Set(["alt", "src", "title"]),
    TD: new Set(["colspan", "rowspan"]),
    TH: new Set(["colspan", "rowspan"]),
  };

  for (const element of [...template.content.querySelectorAll("*")]) {
    const tag = element.tagName.toUpperCase();
    if (!allowedTags.has(tag)) {
      element.replaceWith(...element.childNodes);
      continue;
    }

    const tagAttributes = allowedAttributes[tag] || new Set();
    for (const attribute of [...element.attributes]) {
      if (!tagAttributes.has(attribute.name.toLowerCase())) {
        element.removeAttribute(attribute.name);
      }
    }

    if (tag === "A") {
      const href = element.getAttribute("href") || "";
      if (!/^(https?:\/\/|#)/i.test(href)) {
        element.removeAttribute("href");
      } else {
        element.setAttribute("target", "_blank");
        element.setAttribute("rel", "noopener noreferrer");
      }
    }

    if (tag === "IMG") {
      const src = element.getAttribute("src") || "";
      if (!/^data:image\/png;base64,[a-z0-9+/=\s]+$/i.test(src) && !/^\/assets\//.test(src)) {
        element.removeAttribute("src");
      }
    }
  }

  return template.innerHTML;
}

function describeError(error) {
  if (error instanceof Error) return error.message;
  return String(error ?? "未知错误");
}

function buildSimulationReference(simulation = state.simulation, peakDensity = state.currentDensity) {
  if (!simulation?.summary) return null;
  const summaryPeakDensity = Number(simulation.summary?.peak_density ?? 0);
  const observedDensity = Number(peakDensity);
  return {
    peak_density: Number.isFinite(observedDensity) && observedDensity > 0 ? observedDensity : summaryPeakDensity,
    summary: simulation.summary,
    logs: simulation.logs || [],
    density_series: simulation.summary?.peak_density_series || [],
  };
}

function ensureBaselineReference() {
  if (state.baselineReference) return state.baselineReference;
  const snapshot = buildSimulationReference();
  if (snapshot) {
    state.baselineReference = snapshot;
  }
  return state.baselineReference;
}

function ensureReportBaselineReference(snapshot = null) {
  if (state.reportBaselineReference) return state.reportBaselineReference;
  const candidate = snapshot || buildSimulationReference();
  if (!candidate) return null;
  state.reportBaselineReference = candidate;
  if (!state.baselineReference) {
    state.baselineReference = candidate;
  }
  return state.reportBaselineReference;
}

function getBaselineReportEntry() {
  return state.reportHistory.find((entry) => !entry.interventionLabel) || null;
}

function getReportBaselineReference() {
  return getBaselineReportEntry()?.referenceSnapshot || state.reportBaselineReference || state.baselineReference || null;
}

function getReportEntryKey(entry) {
  if (!entry) return null;
  if (!entry.interventionLabel) return "baseline-report";
  return `mitigation:${entry.interventionType || entry.interventionLabel}`;
}

function upsertReportHistoryEntry(entry) {
  const entryKey = getReportEntryKey(entry);
  if (!entryKey) {
    state.reportHistory.push(entry);
    state.activeReportId = entry.id;
    return;
  }

  const existingIndex = state.reportHistory.findIndex((item) => getReportEntryKey(item) === entryKey);
  if (existingIndex === -1) {
    state.reportHistory.push(entry);
    state.activeReportId = entry.id;
    return;
  }

  const existingEntry = state.reportHistory[existingIndex];

  // 原始基线报告只保留第一次生成的那份，不再按时间重复追加或覆盖。
  if (entryKey === "baseline-report") {
    if (!state.reportBaselineReference && existingEntry.referenceSnapshot) {
      state.reportBaselineReference = existingEntry.referenceSnapshot;
    }
    state.activeReportId = existingEntry.id;
    return;
  }

  state.reportHistory[existingIndex] = {
    ...entry,
    id: existingEntry.id,
  };
  state.activeReportId = existingEntry.id;
}

function normalizeReportHistory() {
  const deduped = [];
  const indexByKey = new Map();

  state.reportHistory.forEach((entry) => {
    const key = getReportEntryKey(entry);
    if (!key) {
      deduped.push(entry);
      return;
    }
    if (!indexByKey.has(key)) {
      indexByKey.set(key, deduped.length);
      deduped.push(entry);
      return;
    }
    if (key === "baseline-report") {
      return;
    }
    const targetIndex = indexByKey.get(key);
    deduped[targetIndex] = {
      ...entry,
      id: deduped[targetIndex].id,
    };
  });

  state.reportHistory = deduped;
  if (!state.reportHistory.some((entry) => entry.id === state.activeReportId)) {
    state.activeReportId = state.reportHistory.at(-1)?.id || null;
  }
}

function getScenarioLabel(scenario) {
  if (scenario === "mitigation") return "干预推演";
  if (scenario === "baseline") return "基线推演";
  return scenario || "未知场景";
}

function formatTimestamp(timestamp) {
  return new Date(timestamp).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function buildComparisonSnapshot(rawComparison, simulationSummary, baselineReference) {
  const beforePeakDensity = baselineReference?.peak_density ?? rawComparison?.peak_density ?? null;
  const beforeSlowBrain = baselineReference?.summary?.slow_brain_triggers ?? rawComparison?.slow_brain_trigger_count ?? 0;
  const beforeDangerousSteps = baselineReference?.summary?.dangerous_steps ?? rawComparison?.dangerous_steps ?? 0;
  const afterPeakDensity = rawComparison?._after?.peak_density ?? simulationSummary?.peak_density ?? null;
  const afterSlowBrain = rawComparison?._after?.slow_brain_trigger_count ?? simulationSummary?.slow_brain_triggers ?? 0;
  const afterDangerousSteps = rawComparison?._after?.dangerous_steps ?? simulationSummary?.dangerous_steps ?? 0;

  if (beforePeakDensity === null || afterPeakDensity === null) {
    return rawComparison || null;
  }

  return {
    peak_density: beforePeakDensity,
    slow_brain_trigger_count: beforeSlowBrain,
    dangerous_steps: beforeDangerousSteps,
    _after: {
      peak_density: afterPeakDensity,
      slow_brain_trigger_count: afterSlowBrain,
      dangerous_steps: afterDangerousSteps,
    },
  };
}

function buildComparisonSummary(comparisonResult) {
  if (!comparisonResult?._after) return "";
  const beforeDensity = Number(comparisonResult.peak_density ?? 0);
  const afterDensity = Number(comparisonResult._after.peak_density ?? 0);
  const beforeDangerousSteps = Number(comparisonResult.dangerous_steps ?? 0);
  const afterDangerousSteps = Number(comparisonResult._after.dangerous_steps ?? 0);
  const densityDelta = beforeDensity > 0
    ? ((beforeDensity - afterDensity) / beforeDensity) * 100
    : 0;
  const densityVerb = afterDensity <= beforeDensity ? "下降" : "上升";

  return `加措施后实时涌现密度由 ${beforeDensity.toFixed(2)} 变为 ${afterDensity.toFixed(2)} 人/m²，${densityVerb} ${Math.abs(densityDelta).toFixed(1)}%；危险步数由 ${beforeDangerousSteps} 步变为 ${afterDangerousSteps} 步，说明人流控制效果${afterDangerousSteps <= beforeDangerousSteps ? "有所改善" : "仍需加强"}。`;
}

function createReportHistoryEntry(data) {
  const timestamp = Date.now();
  const currentSnapshot = buildSimulationReference();
  const interventionLabel = state.simulation?.scenario === "mitigation"
    ? (state.activeIntervention?.label || state.activeIntervention?.type || "已加措施")
    : null;
  const baselineReference = interventionLabel
    ? getReportBaselineReference()
    : ensureReportBaselineReference(currentSnapshot);
  const normalizedComparisonResult = interventionLabel
    ? buildComparisonSnapshot(data.comparison_targets, state.simulation?.summary, baselineReference)
    : null;
  const title = interventionLabel
    ? `方案对比报告 · ${interventionLabel}`
    : "原始基线报告";
  const tags = [
    getScenarioLabel(state.simulation?.scenario),
    interventionLabel ? "已加措施" : "未加措施",
    data.degraded ? "降级报告" : null,
  ].filter(Boolean);

  return {
    id: `report-${++state.reportVersionSeed}-${timestamp}`,
    title,
    scenario: state.simulation?.scenario || "unknown",
    timestamp,
    summaryLine: interventionLabel
      ? `对比原始推演，查看 ${interventionLabel} 对人口密度和风险的控制效果`
      : "保留未加措施时的原始 RAG 报告，作为后续方案对比基线",
    meta: `场景：${state.simulation?.scenario || "-"} | 实时涌现密度：${state.currentDensity.toFixed(2)} 人/m²${data.degraded ? " | 当前为降级报告" : ""}`,
    reportText: data.report || "报告生成失败，请检查后端配置。",
    recommendedInterventions: data.recommended_interventions || [],
    comparisonResult: normalizedComparisonResult,
    interventionLabel,
    interventionType: state.activeIntervention?.type || null,
    referenceSnapshot: currentSnapshot,
    tags,
  };
}

function getActiveReportEntry() {
  return state.reportHistory.find((entry) => entry.id === state.activeReportId) || null;
}

function renderReportHistory() {
  if (!elements.reportHistory) return;
  normalizeReportHistory();
  if (!state.reportHistory.length) {
    elements.reportHistory.innerHTML = `
      <div class="report-history-empty">
        <div class="report-history-empty-title">暂无历史报告</div>
        <div class="report-history-empty-text">生成第一份 RAG 报告后，这里会保留未加措施与各方案报告，方便来回切换对比。</div>
      </div>
    `;
    return;
  }

  const historyHtml = state.reportHistory
    .map((entry) => {
      const activeClass = entry.id === state.activeReportId ? "report-history-item-active" : "";
      const tags = entry.tags.map((tag) => `<span class="report-history-tag">${escapeHtml(tag)}</span>`).join("");
      return `
        <button type="button" class="report-history-item ${activeClass}" data-report-id="${entry.id}">
          <div class="report-history-item-title">${escapeHtml(entry.title)}</div>
          <div class="report-history-item-time">${escapeHtml(formatTimestamp(entry.timestamp))}</div>
          <div class="report-history-item-summary">${escapeHtml(entry.summaryLine)}</div>
          <div class="report-history-item-tags">${tags}</div>
        </button>
      `;
    })
    .join("");

  elements.reportHistory.innerHTML = `
    <div class="report-history-header">
      <h3>报告历史</h3>
      <span>${state.reportHistory.length} 份</span>
    </div>
    <div class="report-history-list">${historyHtml}</div>
  `;

  elements.reportHistory.querySelectorAll("[data-report-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectReportHistory(button.dataset.reportId);
    });
  });
}

function renderReportEntry(entry) {
  if (!entry) {
    elements.reportModalMeta.textContent = "等待生成...";
    elements.reportContent.innerHTML = "<p>请选择一份报告查看内容。</p>";
    state.reportInterventions = [];
    state.comparisonResult = null;
    return;
  }

  const markdownText = entry.reportText || "报告内容为空";
  let reportHtml = window.marked
    ? sanitizeReportHtml(window.marked.parse(markdownText))
    : `<pre>${escapeHtml(markdownText)}</pre>`;

  state.reportInterventions = entry.recommendedInterventions || [];
  const baselineReference = getReportBaselineReference();
  state.comparisonResult = entry.interventionLabel && baselineReference
    ? buildComparisonSnapshot(entry.comparisonResult, null, baselineReference)
    : entry.comparisonResult || null;

  if (state.reportInterventions.length > 0) {
    reportHtml += _buildInterventionCardsHtml(state.reportInterventions, state.comparisonResult);
  }

  elements.reportModalMeta.textContent = entry.meta;
  elements.reportContent.innerHTML = reportHtml;
  _bindInterventionCardEvents();
}

function selectReportHistory(reportId) {
  state.activeReportId = reportId;
  renderReportHistory();
  renderReportEntry(getActiveReportEntry());
}

async function safeReadJson(response) {
  try {
    return await response.clone().json();
  } catch {
    return null;
  }
}

function getSelectedAgentLatestLog() {
  if (!state.simulation || state.selectedAgentId === null) return null;
  const step = getCurrentFrameStep();
  const logs = state.simulation.logs.filter((log) => log.agent_id === state.selectedAgentId && log.step <= step);
  return logs.at(-1) || null;
}

function getFrameAgentById(agentId) {
  const frame = getCurrentFrame();
  return frame?.agents?.find((item) => item.id === agentId) || null;
}

function getNearbyAgents(agent, radius = 1.7) {
  const frame = getCurrentFrame();
  if (!frame || !agent) return [];
  return frame.agents
    .filter((other) => other.id !== agent.id)
    .map((other) => ({
      ...other,
      distance: Math.hypot(other.x - agent.x, other.y - agent.y),
      deltaX: other.x - agent.x,
      deltaY: other.y - agent.y,
    }))
    .filter((other) => other.distance <= radius)
    .sort((a, b) => a.distance - b.distance);
}

function buildInteractionSummary(agent, latestLog, options = {}) {
  const { concise = false } = options;
  const neighbors = getNearbyAgents(agent);
  const frontNeighbors = neighbors.filter((other) => Math.abs(other.deltaX) >= Math.abs(other.deltaY) && Math.sign(other.deltaX || 1) === Math.sign(agent.direction === "east" ? 1 : -1));
  const sideNeighbors = neighbors.filter((other) => Math.abs(other.deltaY) > Math.abs(other.deltaX));
  const heardMessages = Array.isArray(latestLog?.content?.heard_messages) ? latestLog.content.heard_messages : [];

  if (concise) {
    if (heardMessages.length) {
      return `听到${heardMessages.length}条近距呼喊，正与邻近人群挤压协调。`;
    }
    if (frontNeighbors.length && sideNeighbors.length) {
      return `前方受阻，侧向与${sideNeighbors.length}人贴靠调整。`;
    }
    if (frontNeighbors.length) {
      return `前方${frontNeighbors.length}人减速，正跟随缝隙微调。`;
    }
    if (sideNeighbors.length) {
      return `与侧向${sideNeighbors.length}人并行贴靠，保持微小间距。`;
    }
    if (neighbors.length) {
      return `周边${neighbors.length}人近距伴随，维持同步移动。`;
    }
    return "周边暂未形成强交互，以自主通行为主。";
  }

  const heardSummary = heardMessages.length
    ? `已接收到 ${heardMessages.length} 条近距语音/动作线索，最近信息为：${heardMessages[0]}`
    : "当前未捕捉到明确呼喊，但可见周边人群在近距状态下同步减速或避让。";
  const frontSummary = frontNeighbors.length
    ? `前向 ${frontNeighbors.length} 人形成减速/阻塞链，直接压缩了该 Agent 的前进缝隙。`
    : "前向暂未形成强阻塞链，主要通过局部空隙维持推进。";
  const sideSummary = sideNeighbors.length
    ? `侧向有 ${sideNeighbors.length} 人贴靠并行，说明其需要持续做肩并肩避让和站位修正。`
    : "侧向接触压力较弱，尚有余量进行小幅横向修正。";
  return `${frontSummary}${sideSummary}${heardSummary}`;
}

function scrollLogStreamToBottom() {
  if (!elements.logStream) return;
  elements.logStream.scrollTop = elements.logStream.scrollHeight;
}

function updateSelectedAgentTag() {
  const tag = elements.agentInsightTag;
  if (!tag) return;
  if (state.selectedAgentId === null) {
    tag.classList.add("hidden");
    return;
  }
  const frame = getCurrentFrame();
  const agent = frame?.agents?.find((item) => item.id === state.selectedAgentId) || null;
  if (!agent) {
    tag.classList.add("hidden");
    return;
  }

  const point = isoMap(agent.x, agent.y, 0.2);
  const canvasRect = canvas.getBoundingClientRect();
  const wrapperRect = elements.canvasWrapper.getBoundingClientRect();
  const cssX = ((point.x / canvas.width) * canvasRect.width) + (canvasRect.left - wrapperRect.left);
  const cssY = ((point.y / canvas.height) * canvasRect.height) + (canvasRect.top - wrapperRect.top);

  const profile = escapeHtml(agent.profile_label || agent.typology || "常态行人");
  const perception = escapeHtml(agent.perception_summary || "前方可通行。");
  const emotion = escapeHtml(agent.emotion_summary || "保持警觉，情绪基本稳定。");
  const intention = escapeHtml(agent.intention_summary || "继续沿当前方向稳步前进。");
  const action = escapeHtml(agent.action_summary || "跟随局部空隙缓慢移动。");
  const interaction = escapeHtml(buildInteractionSummary(agent, getSelectedAgentLatestLog(), { concise: true }));

  tag.innerHTML = `
    <div class="agent-card">
      <div class="agent-card-header">Agent #${agent.id} · ${profile}</div>
      <div class="agent-card-row"><span class="agent-card-label">感知</span><span>${perception}</span></div>
      <div class="agent-card-row"><span class="agent-card-label">情绪</span><span>${emotion}</span></div>
      <div class="agent-card-row"><span class="agent-card-label">意图</span><span>${intention}</span></div>
      <div class="agent-card-row"><span class="agent-card-label">动作</span><span>${action}</span></div>
      <div class="agent-card-row"><span class="agent-card-label">交互</span><span>${interaction}</span></div>
    </div>
  `;
  tag.classList.remove("hidden");

  const tagWidth = Math.min(280, Math.max(200, tag.offsetWidth || 240));
  const left = Math.min(Math.max(12, cssX + 18), Math.max(12, wrapperRect.width - tagWidth - 12));
  const top = Math.min(Math.max(12, cssY - 120), Math.max(12, wrapperRect.height - 160));
  tag.style.left = `${left}px`;
  tag.style.top = `${top}px`;
}

function rebalancePopulation(changedKey) {
  const values = getPopulationValues();
  const changedValue = Math.max(0, Math.min(100, values[changedKey]));
  const otherKeys = populationKeys.filter((key) => key !== changedKey);
  const otherTotal = otherKeys.reduce((sum, key) => sum + values[key], 0);
  const remaining = Math.max(0, 100 - changedValue);

  const next = { ...values, [changedKey]: changedValue };
  if (otherTotal === 0) {
    const evenChunk = Math.floor(remaining / otherKeys.length);
    let assigned = 0;
    otherKeys.forEach((key, index) => {
      if (index === otherKeys.length - 1) {
        next[key] = remaining - assigned;
      } else {
        next[key] = evenChunk;
        assigned += evenChunk;
      }
    });
  } else {
    let allocated = 0;
    otherKeys.forEach((key, index) => {
      if (index === otherKeys.length - 1) {
        next[key] = remaining - allocated;
      } else {
        const scaledValue = Math.round((values[key] / otherTotal) * remaining);
        next[key] = scaledValue;
        allocated += scaledValue;
      }
    });
  }
  setPopulationValues(next);
}

function syncMitigationControls() {
  const isMitigation = elements.scenarioSelect.value === "mitigation";
  elements.mitigationStrategyGroup.classList.toggle("hidden", !isMitigation);
}

function getLayout() {
  return state.bootstrap?.engine_layout || null;
}

function getCurrentFrame() {
  return state.lastFrame;
}

function getCurrentFrameStep() {
  return getCurrentFrame()?.step ?? -1;
}

function isoMap(x, y, z) {
  // Translate coordinate system so the alley center is roughly in the middle
  const scale = 20 * getViewportScale(); // 1 unit (1 meter) = 20px at base canvas size
  const cx = (x - 22.5) * scale;
  const cy = y * scale;
  const cz = z * scale;

  // Isometric projection:
  // x_iso = (cx - cy) * cos(30deg)
  // y_iso = (cx + cy) * sin(30deg) - cz
  const cos30 = 0.866025;
  const sin30 = 0.5;

  const ix = (cx - cy) * cos30;
  const iy = (cx + cy) * sin30 - cz;

  return { x: canvas.width / 2 + ix, y: canvas.height / 2 + iy };
}

function drawIsoPolygon(points, fillStyle, strokeStyle = null, lineWidth = 1) {
  if (!points.length) return;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.closePath();
  ctx.fillStyle = fillStyle;
  ctx.fill();
  if (strokeStyle) {
    ctx.strokeStyle = strokeStyle;
    ctx.lineWidth = lineWidth * Math.max(1, getViewportScale() * 0.95);
    ctx.stroke();
  }
}

// 3D Block renderer
function drawBlock(x1, y1, x2, y2, height, baseZ, topColor, leftColor, rightColor) {
  // Vertices of the base (x1,y1) to (x2,y2)
  const p1 = isoMap(x1, y1, baseZ); // Top-left
  const p2 = isoMap(x2, y1, baseZ); // Top-right
  const p3 = isoMap(x2, y2, baseZ); // Bottom-right
  const p4 = isoMap(x1, y2, baseZ); // Bottom-left

  const pt1 = isoMap(x1, y1, baseZ + height);
  const pt2 = isoMap(x2, y1, baseZ + height);
  const pt3 = isoMap(x2, y2, baseZ + height);
  const pt4 = isoMap(x1, y2, baseZ + height);

  // Right face (x2)
  drawIsoPolygon([p2, p3, pt3, pt2], rightColor, "rgba(255,255,255,0.05)", 1);

  // Left face (y2)
  drawIsoPolygon([p3, p4, pt4, pt3], leftColor, "rgba(255,255,255,0.05)", 1);

  // Top face
  drawIsoPolygon([pt1, pt2, pt3, pt4], topColor, "rgba(255,255,255,0.1)", 1);
}

function riskColor(level, alpha = 1) {
  const colors = {
    safe: `rgba(59, 244, 163, ${alpha})`,
    warning: `rgba(255, 204, 77, ${alpha})`,
    danger: `rgba(255, 99, 132, ${alpha})`,
    fatal: `rgba(255, 77, 109, ${alpha})`,
  };
  return colors[level] || colors.safe;
}

function drawScene(frame) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  drawBackground();
  drawCorridor();
  drawHeatmap(frame.heatmap);
  drawBarrier();
  drawRipples();
  drawAgents(frame.agents);
  updateSelectedAgentTag();
}

function drawBackground() {
  ctx.save();
  ctx.fillStyle = "#0a0a0a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.restore();
}

function drawCorridor() {
  const layout = getLayout();
  if (!layout) return;

  ctx.save();

  // Floor grid
  const p1 = isoMap(0, -3.2, 0);
  const p2 = isoMap(45, -3.2, 0);
  const p3 = isoMap(45, 3.2, 0);
  const p4 = isoMap(0, 3.2, 0);
  drawIsoPolygon([p1, p2, p3, p4], "#111213", "rgba(255,255,255,0.05)", 1);

  // Hazard Zone indicator
  if (layout.hazard_zone) {
    const hazardPts = layout.hazard_zone.map(([nx, ny]) => {
      const x = nx * 45;
      const y = ny * 6.4 - 3.2;
      return isoMap(x, y, 0.02);
    });
    drawIsoPolygon(hazardPts, "rgba(255, 77, 109, 0.05)", "rgba(255, 77, 109, 0.2)", 1);
  }

  // Draw Top Blocks (Hotel side wall - staggered for realistic street look)
  // Base blocks
  drawBlock(0, -6, 12, -3.2, 4.0, 0, "#2a2c2e", "#242527", "#1f2021"); // Shop 1
  drawBlock(12, -5, 25, -3.2, 6.0, 0, "#3a3c3e", "#343537", "#2f3031"); // Main Hotel structure
  drawBlock(25, -5.5, 45, -3.2, 3.5, 0, "#2a2c2e", "#242527", "#1f2021"); // Shop 2

  // Draw Bottom Blocks (Convenience store side wall)
  drawBlock(0, 3.2, 18, 5, 3.0, 0, "#2a2c2e", "#242527", "#1f2021");
  drawBlock(18, 3.2, 32, 5.5, 4.5, 0, "#3a3c3e", "#343537", "#2f3031");
  drawBlock(32, 3.2, 45, 5, 3.0, 0, "#2a2c2e", "#242527", "#1f2021");

  ctx.restore();
}

function drawHeatmap(heatmap) {
  heatmap.forEach((cell) => {
    const p1 = isoMap(cell.x, cell.y - 3.2, 0.05);
    const p2 = isoMap(cell.x + cell.width, cell.y - 3.2, 0.05);
    const p3 = isoMap(cell.x + cell.width, cell.y + cell.height - 3.2, 0.05);
    const p4 = isoMap(cell.x, cell.y + cell.height - 3.2, 0.05);
    const alpha = Math.min(0.05 + cell.density / 14, 0.6);
    drawIsoPolygon([p1, p2, p3, p4], riskColor(cell.level, alpha));
  });
}

function drawBarrier() {
  ctx.save();

  // 优先根据 activeIntervention 绘制
  if (state.activeIntervention) {
    const spec = state.activeIntervention.overlay_spec || {};
    const type = state.activeIntervention.type;

    if (type === "central_guardrail") {
      const xStart = spec.barrier_x_start || 14.5;
      const xEnd = spec.barrier_x_end || 30.5;
      const height = spec.barrier_height || 1.3;
      const halfWidth = spec.barrier_half_width || 0.18;
      drawBlock(xStart, -halfWidth, xEnd, halfWidth, height, 0, "#ffcc4d", "#e6b845", "#cca33d");
    } else if (type === "one_way_flow") {
      drawBlock(42.2, 0.0, 45.0, 3.2, 1.1, 0, "rgba(255,77,109,0.85)", "rgba(220,60,92,0.85)", "rgba(190,45,76,0.92)");
      drawBlock(0.0, -0.4, 4.5, 0.4, 0.3, 0, "rgba(59,244,163,0.68)", "rgba(50,210,140,0.68)", "rgba(42,180,120,0.72)");
    } else if (type === "widen_exits") {
      const segments = spec.widen_segments || [
        { x_start: 0.0, x_end: 8.0, extra_width: 0.95 },
        { x_start: 37.0, x_end: 45.0, extra_width: 0.95 },
      ];
      segments.forEach((seg) => {
        const w = seg.extra_width || 0.95;
        drawBlock(seg.x_start, -3.2 - w, seg.x_end, -3.2, 0.35, 0, "rgba(59,244,163,0.78)", "rgba(43,190,126,0.78)", "rgba(36,160,106,0.82)");
        drawBlock(seg.x_start, 3.2, seg.x_end, 3.2 + w, 0.35, 0, "rgba(59,244,163,0.78)", "rgba(43,190,126,0.78)", "rgba(36,160,106,0.82)");
      });
    }
    ctx.restore();
    return;
  }

  // 回退到原有逻辑
  if (!state.simulation || state.simulation.scenario !== "mitigation") {
    ctx.restore();
    return;
  }
  const strategy = state.simulation.summary?.mitigation_strategy;
  if (!strategy || strategy === "none") {
    ctx.restore();
    return;
  }

  if (strategy === "central_guardrail") {
    drawBlock(14.5, -0.18, 30.5, 0.18, 1.3, 0, "#ffcc4d", "#e6b845", "#cca33d");
  } else if (strategy === "one_way_flow") {
    drawBlock(42.2, 0.0, 45.0, 3.2, 1.1, 0, "rgba(255,77,109,0.85)", "rgba(220,60,92,0.85)", "rgba(190,45,76,0.92)");
    drawBlock(0.0, -0.4, 4.5, 0.4, 0.3, 0, "rgba(59,244,163,0.68)", "rgba(50,210,140,0.68)", "rgba(42,180,120,0.72)");
  } else if (strategy === "widen_exits") {
    drawBlock(0.0, -4.2, 8.0, -3.2, 0.35, 0, "rgba(59,244,163,0.78)", "rgba(43,190,126,0.78)", "rgba(36,160,106,0.82)");
    drawBlock(0.0, 3.2, 8.0, 4.2, 0.35, 0, "rgba(59,244,163,0.78)", "rgba(43,190,126,0.78)", "rgba(36,160,106,0.82)");
    drawBlock(37.0, -4.2, 45.0, -3.2, 0.35, 0, "rgba(59,244,163,0.78)", "rgba(43,190,126,0.78)", "rgba(36,160,106,0.82)");
    drawBlock(37.0, 3.2, 45.0, 4.2, 0.35, 0, "rgba(59,244,163,0.78)", "rgba(43,190,126,0.78)", "rgba(36,160,106,0.82)");
  }
  ctx.restore();
}

function drawAgents(agents) {
  const viewportScale = getViewportScale();
  const sorted = [...agents].sort((a, b) => {
    const depthA = a.x + a.y;
    const depthB = b.x + b.y;
    return depthA - depthB;
  });

  sorted.forEach((agent) => {
    ctx.save();
    const point = isoMap(agent.x, agent.y, 0.2);
    const isSelected = state.selectedAgentId === agent.id;
    const isHovered = state.hoveredAgentId === agent.id;
    const radiusBase = isSelected ? 5.8 : agent.slow_brain_active ? 4.8 : 3.8;
    const radius = radiusBase * Math.max(1, viewportScale * 0.98);

    if (agent.slow_brain_active) {
      ctx.shadowBlur = 16 * viewportScale;
      ctx.shadowColor = "#5ed29c";
    }

    if (agent.typology === "normal_pedestrian") {
      ctx.fillStyle = "#5e8cff";
    } else if (agent.typology === "group_family") {
      ctx.fillStyle = "#b85ed2";
    } else if (agent.typology === "vulnerable") {
      ctx.fillStyle = "#f4a261";
    } else {
      ctx.fillStyle = agent.direction === "east" ? "#5e6ad2" : "#7170ff";
    }

    if (agent.risk === "danger" || agent.risk === "fatal") {
      ctx.shadowBlur = 10 * viewportScale;
      ctx.shadowColor = "#ff4d6d";
    }

    if (isSelected || isHovered) {
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius + (isSelected ? 7 : 4) * viewportScale, 0, Math.PI * 2);
      ctx.strokeStyle = isSelected ? "rgba(94, 210, 156, 0.95)" : "rgba(255, 255, 255, 0.55)";
      ctx.lineWidth = (isSelected ? 2.2 : 1.2) * viewportScale;
      ctx.shadowBlur = isSelected ? 22 * viewportScale : 0;
      ctx.shadowColor = "rgba(94, 210, 156, 0.65)";
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(point.x - viewportScale, point.y - viewportScale, radius * 0.3, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  });
}

function drawRipples() {
  const viewportScale = getViewportScale();
  state.ripples.forEach((ripple) => {
    const point = isoMap(ripple.x, ripple.y, 0.18);
    const progress = ripple.age / ripple.maxAge;
    if (progress >= 1) return;
    const radiusPx = ripple.radiusMeters * 17 * viewportScale * (0.45 + progress * 1.2);
    const alpha = (1 - progress) * (ripple.kind === "heard" ? 0.42 : 0.34);
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(point.x, point.y, radiusPx, radiusPx * 0.46, 0, 0, Math.PI * 2);
    ctx.strokeStyle = ripple.kind === "heard"
      ? `rgba(255, 204, 77, ${alpha})`
      : `rgba(94, 210, 156, ${alpha})`;
    ctx.lineWidth = (ripple.kind === "heard" ? 2.1 : 1.6) * viewportScale;
    ctx.shadowBlur = 14 * viewportScale;
    ctx.shadowColor = ripple.kind === "heard"
      ? "rgba(255, 204, 77, 0.45)"
      : "rgba(94, 210, 156, 0.35)";
    ctx.stroke();
    ctx.restore();
  });
}

function syncRipples(frame) {
  if (!state.simulation) return;
  const step = frame.step ?? state.frameIndex;
  const frameAgents = new Map(frame.agents.map((agent) => [agent.id, agent]));
  const logsForStep = state.simulation.logs.filter((log) => log.step === step);

  logsForStep.forEach((log) => {
    const agent = frameAgents.get(log.agent_id);
    if (!agent) return;
    const heardMessages = Array.isArray(log.content?.heard_messages) ? log.content.heard_messages : [];
    const key = `${step}-${log.agent_id}-${heardMessages.length ? "heard" : "broadcast"}`;
    if (state.generatedRippleKeys.has(key)) return;
    state.generatedRippleKeys.add(key);
    state.ripples.push({
      agentId: log.agent_id,
      x: agent.x,
      y: agent.y,
      radiusMeters: Number(agent.broadcast_radius) || 2.4,
      age: 0,
      maxAge: heardMessages.length ? 26 : 22,
      kind: heardMessages.length ? "heard" : "broadcast",
    });
  });

  state.ripples = state.ripples
    .map((ripple) => ({ ...ripple, age: ripple.age + 1 }))
    .filter((ripple) => ripple.age < ripple.maxAge);
}

function updateMetrics(frame) {
  state.lastFrame = frame;
  state.observedPeakDensity = Math.max(state.observedPeakDensity, frame.stats.peak_density);
  const currentDensity = Number(frame.stats.peak_density ?? 0);
  state.currentDensity = currentDensity;
  elements.simTime.textContent = `${frame.stats.simulated_seconds.toFixed(1)}s`;
  elements.activeAgents.textContent = frame.stats.active_agents;
  elements.peakDensity.textContent = state.observedPeakDensity.toFixed(2);
  elements.opsActiveTotal.textContent = String(frame.stats.active_agents);
  elements.opsSystem1.textContent = String(frame.agents.length);
  elements.opsSystem2.textContent = String(frame.agents.filter((agent) => agent.slow_brain_active).length);

  // Update multi-dimensional metrics from summary
  const simSummary = state.simulation?.summary;
  if (simSummary) {
    elements.velDecay.textContent = (simSummary.velocity_decay_ratio ?? 1.0).toFixed(3);
    elements.conflictCount.textContent = String(simSummary.conflict_count ?? 0);
    elements.exitRate.textContent = `${((simSummary.exit_pass_rate ?? 0) * 100).toFixed(1)}%`;
    elements.dwellSteps.textContent = (simSummary.mean_dwell_time_danger ?? 0).toFixed(1);
  }

  const peak = state.observedPeakDensity;
  const densitySummary = state.bootstrap?.density_summary || {};
  const safeLimit = Number(densitySummary.safe_limit ?? 4);
  const criticalDensity = Number(densitySummary.critical_density ?? 5);
  const fatalRangeMin = Number(densitySummary.fatal_range_min ?? 12);
  const fatalRangeMax = Number(densitySummary.fatal_range_max ?? 16);
  elements.simPeakDensity.textContent = `${currentDensity.toFixed(2)} 人/m²`;

  let statusText = "安全";
  let statusColor = "var(--success)";

  if (currentDensity >= fatalRangeMin) {
    statusText = "高危警报";
    statusColor = "var(--danger)";
  } else if (currentDensity >= safeLimit) {
    statusText = "拥挤警告";
    statusColor = "var(--warning)";
  }

  elements.riskBadge.textContent = `状态：${statusText} [当前 ${currentDensity.toFixed(2)} / 峰值 ${peak.toFixed(2)} 人/m²]`;
  elements.riskBadge.style.color = statusColor;

  let progress = (currentDensity / fatalRangeMax) * 100;
  progress = Math.min(100, Math.max(0, progress));
  elements.fitProgress.style.width = `${progress}%`;

  if (currentDensity < safeLimit) {
    elements.fitProgress.style.background = "var(--success)";
    elements.fitStatus.textContent = "安全：远低于历史灾难密度";
  } else if (currentDensity < criticalDensity) {
    elements.fitProgress.style.background = "var(--warning)";
    elements.fitStatus.textContent = "注意：已超过安全密度上限，需持续监测";
  } else if (currentDensity < fatalRangeMin) {
    elements.fitProgress.style.background = "var(--warning)";
    elements.fitStatus.textContent = "警告：拥堵加剧，逼近历史灾难边界";
  } else {
    elements.fitProgress.style.background = "var(--danger)";
    elements.fitStatus.textContent = "高危警报：已达到历史灾难峰值密度区间";
  }
}

function renderCrossValidation(summary) {
  if (!summary) return;
  const providerMode = state.bootstrap?.llm_provider_ready
    ? "LLM Provider: Ready"
    : "LLM Provider: Disabled";
  elements.opsMarquee.textContent =
    `NumPy Local Engine | ${providerMode} | API Calls Used: ${summary.api_calls_used ?? 0} | System 2 Entries: ${summary.slow_brain_triggers ?? 0}`;
}

function syncProviderState(ready, providerName, modelName) {
  elements.useApi.checked = false;
  elements.useApi.disabled = !ready;
  elements.providerModel.textContent = ready
    ? `${modelName} · 可选启用慢脑`
    : "本地物理仿真模式";
  elements.opsMarquee.textContent = ready
    ? `NumPy Local Engine | ${providerName}: Ready | 慢脑默认关闭`
    : "NumPy Local Engine | 本地物理仿真模式 | LLM Provider: Disabled";
}

function enterFullscreenMode() {
  if (window.innerWidth <= 1280 || !elements.workspacePanel) return;
  elements.dashboard?.classList.add("simulation-active");
  elements.workspacePanel.classList.add("workspace-immersive");
  elements.sandboxShell.classList.add("fullscreen-mode");
  elements.fullscreenExitButton.classList.remove("hidden");
  requestAnimationFrame(resizeCanvas);
}

function exitFullscreenMode() {
  elements.dashboard?.classList.remove("simulation-active");
  elements.workspacePanel?.classList.remove("workspace-immersive");
  elements.sandboxShell.classList.remove("fullscreen-mode");
  elements.fullscreenExitButton.classList.add("hidden");
  requestAnimationFrame(resizeCanvas);
}

function buildLogEntryHtml(log, options = {}) {
  const { selected = false, compact = false } = options;
  const content = log.content || {};
  const highlightClass = selected ? " log-entry-selected" : "";
  const profile = escapeHtml(content.profile_label || content.typology || "unknown");
  const perception = escapeHtml(content.perception || "此刻主要以观察周边拥堵变化为主。");
  const emotion = escapeHtml(content.emotion || "情绪紧绷，正在维持稳定。");
  const intention = escapeHtml(content.intention || "优先保持平衡并寻找下一步可移动空间。");
  const dialogue = content.dialogue ? `<br>对话: ${escapeHtml(content.dialogue)}` : "";
  const action = content.action ? `<br>动作: ${escapeHtml(content.action)}` : "";
  const movement = content.movement_hint ? `<br>移动策略: ${escapeHtml(content.movement_hint)}` : "";
  const heard = Array.isArray(content.heard_messages) && content.heard_messages.length
    ? `<br><span class="log-heard">听到: ${escapeHtml(content.heard_messages.join("；"))}</span>`
    : "";
  return `<div class="log-entry${highlightClass}" data-agent-id="${log.agent_id}" data-step="${log.step}">
<div class="log-entry-tag">慢脑片段</div>
<div class="log-entry-header">[t=${log.step}] Agent ${log.agent_id} | ${log.density.toFixed(2)} 人/m² | ${escapeHtml(log.severity)}</div>
<div class="log-entry-profile">${profile}</div>
<div class="log-entry-content">
<div class="log-entry-perception">${perception}</div>
<div class="log-entry-emotion">${emotion}</div>
<div class="log-entry-intention">${intention}</div>
</div>${compact ? "" : `${heard}${dialogue}${action}${movement}`}</div>`;
}

function buildLockedAgentLogHtml(agentLogs, agentId) {
  if (!agentLogs.length) {
    return `<div class="log-detail-shell">
<div class="log-detail-head">
<div class="log-detail-label">第一人称慢脑视角</div>
<div class="log-detail-meta">Agent ${agentId} 暂未进入高压认知触发区，系统继续监听该个体在推演过程中的第一人称认知日志。</div>
</div>
</div>`;
  }
  const latest = agentLogs.at(-1);
  const content = latest.content || {};
  const profile = escapeHtml(content.profile_label || content.typology || "unknown");
  const heardMessages = Array.isArray(content.heard_messages) ? content.heard_messages : [];
  const heardSummary = heardMessages.length ? escapeHtml(heardMessages.join("；")) : "当前未捕捉到清晰的近距呼喊。";
  const currentAgent = getFrameAgentById(agentId);
  const interaction = escapeHtml(buildInteractionSummary(currentAgent, latest, { concise: false }));
  const recentEntries = agentLogs.slice(-6).reverse()
    .map((item) => buildLogEntryHtml(item, { selected: item.step === latest.step, compact: true }))
    .join("");
  return `<div class="log-detail-shell">
<div class="log-detail-head">
<div class="log-entry-tag">第一人称慢脑视角</div>
<div class="log-entry-header">Agent ${agentId} · ${profile}</div>
<div class="log-detail-meta">最近触发帧 t=${latest.step} | 局部密度 ${latest.density.toFixed(2)} 人/m² | 邻近人数 ${Number(content.neighbor_count || 0)} 人</div>
</div>
<div class="log-detail-grid">
<div class="log-detail-card"><div class="log-detail-label">感知</div><div class="log-detail-value">${escapeHtml(content.perception || "正在持续观察前方与侧向人群变化。")}</div></div>
<div class="log-detail-card"><div class="log-detail-label">情绪</div><div class="log-detail-value">${escapeHtml(content.emotion || "保持高度警觉。")}</div></div>
<div class="log-detail-card"><div class="log-detail-label">意图</div><div class="log-detail-value">${escapeHtml(content.intention || "优先维持平衡并选择下一步空间。")}</div></div>
<div class="log-detail-card"><div class="log-detail-label">动作</div><div class="log-detail-value">${escapeHtml(content.action || "根据周边缝隙微调位置。")}</div></div>
<div class="log-detail-card log-detail-card-wide"><div class="log-detail-label">与旁人交互</div><div class="log-detail-value">${interaction}</div></div>
<div class="log-detail-card log-detail-card-wide"><div class="log-detail-label">听到的现场信息</div><div class="log-detail-value">${heardSummary}</div></div>
<div class="log-detail-card log-detail-card-wide"><div class="log-detail-label">对话与移动策略</div><div class="log-detail-value">${escapeHtml(content.dialogue || "此刻更多通过身体调整应对拥堵。")} ${escapeHtml(content.movement_hint || "")}</div></div>
</div>
<div class="log-history">
<div class="log-history-title">最近认知片段</div>
${recentEntries}
</div>
</div>`;
}

function updateLogs() {
  if (!state.simulation) return;
  const step = getCurrentFrameStep();
  const selectedAgentId = state.selectedAgentId;
  const historicalLogs = state.simulation.logs.filter((log) => log.step <= step);
  updateLockPanel();

  if (!historicalLogs.length) {
    const triggerThreshold = Number(state.bootstrap?.density_summary?.critical_density ?? 5);
    elements.logStream.textContent = `系统就绪。等待局部密度超过 ${triggerThreshold.toFixed(1)} 人/m² 后生成慢脑认知流...`;
    updateSelectedAgentTag();
    return;
  }

  if (selectedAgentId !== null) {
    const agentLogs = historicalLogs.filter((log) => log.agent_id === selectedAgentId);
    elements.logStream.innerHTML = buildLockedAgentLogHtml(agentLogs, selectedAgentId);
    elements.logStream.scrollTop = 0;
  } else {
    const visibleLogs = historicalLogs.slice(-30);
    elements.logStream.innerHTML = visibleLogs
      .map((log) => buildLogEntryHtml(log))
      .join("");
    scrollLogStreamToBottom();
  }
  updateSelectedAgentTag();
}

function animateSimulation() {
  cancelAnimationFrame(state.animationHandle);

  return new Promise((resolve) => {
    function tick() {
      if (!state.simulation || !state.running) {
        resolve();
        return;
      }
      const frame = state.simulation.frames[state.frameIndex];
      if (!frame) {
        resolve();
        return;
      }
      syncRipples(frame);
      drawScene(frame);
      updateMetrics(frame);
      updateLogs();

      state.frameIndex += 1;
      if (state.frameIndex < state.simulation.frames.length) {
        state.animationHandle = requestAnimationFrame(() => {
          setTimeout(tick, 90);
        });
      } else {
        resolve();
      }
    }

    state.frameIndex = 0;
    tick();
  });
}

async function loadBootstrap() {
  const response = await fetch("/api/bootstrap");
  const data = await safeReadJson(response);
  if (!response.ok || !data) {
    throw new Error("初始化数据加载失败");
  }
  state.bootstrap = data;

  syncProviderState(
    data.llm_provider_ready,
    data.llm_provider_name,
    data.llm_model_name,
  );
  if (elements.historicalBaseline) {
    const fatalRange = data.density_summary?.fatal_range ?? "12-16";
    const observedPeak = Number(data.density_summary?.observed_peak_density ?? 16.4);
    elements.historicalBaseline.innerHTML = `${fatalRange} / ${observedPeak.toFixed(1)} <small>人/m²</small>`;
  }
  syncSimulationLimits();

  data.scenarios.forEach((scenario) => {
    const option = document.createElement("option");
    option.value = scenario.name;
    option.textContent = scenario.label;
    option.dataset.rate = String(scenario.arrival_rate_north + scenario.arrival_rate_south);
    elements.scenarioSelect.appendChild(option);
  });

  if (data.scenarios.some((scenario) => scenario.name === "accident")) {
    elements.scenarioSelect.value = "accident";
  }
  syncScenarioDefaults();
  setPopulationValues({ normal_pedestrian: 60, group_family: 25, vulnerable: 15 });
  drawScene({ heatmap: [], agents: [] });
}

function updateFlowRate() {
  // Deprecated in new layout, we now show individual north/south rates directly.
}

function syncScenarioDefaults() {
  syncMitigationControls();
  const scenario = elements.scenarioSelect.value;
  if (!state.bootstrap) return;
  const selectedScenario = state.bootstrap.scenarios.find((item) => item.name === scenario);
  if (!selectedScenario) return;
  elements.northRate.value = String(selectedScenario.arrival_rate_north);
  elements.southRate.value = String(selectedScenario.arrival_rate_south);
  elements.northRateLabel.textContent = Number(elements.northRate.value).toFixed(1);
  elements.southRateLabel.textContent = Number(elements.southRate.value).toFixed(1);
}

async function runSimulation() {
  if (state.running) return;

  let completed = false;
  state.running = true;
  state.currentDensity = 0;
  state.observedPeakDensity = 0;
  state.lastFrame = null;
  state.ripples = [];
  state.generatedRippleKeys = new Set();
  elements.runButton.disabled = true;
  elements.generateReportBtn.disabled = true;
  elements.logStream.textContent = "启动沙盒环境...\n[Engine] Load UCY/ETH Dataset: Mean Speed=1.34m/s, Std=0.26m/s\n[Engine] Calibrating pedestrian physical parameters...\n[Engine] 正在生成本轮推演结果与慢脑日志，请等待返回后自动开始播放。\n";
  elements.riskBadge.textContent = "正在生成推演结果与日志...";
  elements.riskBadge.style.color = "var(--text-secondary)";
  state.simulation = null;

  elements.runButton.textContent = "⏹ 停止推演";
  elements.canvasWrapper.classList.add("focus");
  enterFullscreenMode();
  const payload = {
    scenario: elements.scenarioSelect.value,
    max_agents: Number(elements.agentCount.value),
    duration_steps: (() => {
      const combinedRate = Number(elements.northRate.value) + Number(elements.southRate.value);
      const targetAgents = Number(elements.agentCount.value);
      const historicalCoreAgents = Number(state.bootstrap?.density_summary?.historical_core_agents ?? targetAgents);
      const minSteps = Number(state.bootstrap?.simulation_limits?.duration_steps_min ?? 40);
      const maxSteps = Number(state.bootstrap?.simulation_limits?.duration_steps_max ?? 360);
      const safeCapacity = Number(state.bootstrap?.density_summary?.safe_limit ?? 4) * 0.96;
      const overloadRatio = combinedRate / Math.max(safeCapacity, 0.1);
      const estimatedFillSeconds = Math.max(targetAgents, historicalCoreAgents) / Math.max(combinedRate, 0.1);
      const pressureMultiplier = overloadRatio >= 3 ? 5 : overloadRatio >= 2 ? 4 : overloadRatio >= 1.2 ? 3 : 2;
      const minimumCongestionSeconds = overloadRatio >= 3 ? 60 : overloadRatio >= 2 ? 45 : overloadRatio >= 1.2 ? 30 : 20;
      const steps = Math.ceil(Math.max(estimatedFillSeconds * pressureMultiplier, minimumCongestionSeconds) / 0.5);
      return Math.max(minSteps, Math.min(maxSteps, steps));
    })(),
    use_api: elements.useApi.checked,
    api_budget: (() => {
      const combinedRate = Number(elements.northRate.value) + Number(elements.southRate.value);
      const maxAgents = Number(elements.agentCount.value);
      const safeCapacity = Number(state.bootstrap?.density_summary?.safe_limit ?? 4) * 0.96;
      const overloadRatio = combinedRate / Math.max(safeCapacity, 0.1);
      return Math.max(24, Math.min(80, Math.ceil((maxAgents * 0.2) + (overloadRatio * 6))));
    })(),
    arrival_rate_north: Number(elements.northRate.value),
    arrival_rate_south: Number(elements.southRate.value),
    mitigation_strategy: elements.scenarioSelect.value === "mitigation" ? elements.mitigationStrategy.value : null,
    normal_pedestrian_ratio: Number(elements.normalPedestrianRatio.value),
    group_family_ratio: Number(elements.groupFamilyRatio.value),
    vulnerable_ratio: Number(elements.vulnerableRatio.value),
  };

  try {
    await requestAndPlaySimulation(payload);
    completed = true;
  } catch (error) {
    exitFullscreenMode();
    elements.logStream.textContent += `\n[Error] ${describeError(error)}`;
    elements.riskBadge.textContent = "演算失败";
    elements.riskBadge.style.color = "var(--danger)";
  } finally {
    state.running = false;
    elements.runButton.disabled = false;
    elements.runButton.textContent = "▶ 开始推演";
    elements.canvasWrapper.classList.remove("focus");
    if (completed && state.simulation?.scenario === "baseline") {
      state.baselineReference = buildSimulationReference();
    }
    if (completed) {
      elements.riskBadge.textContent = "演算完成：可生成 RAG 诊断报告";
      elements.riskBadge.style.color = "var(--success)";
      elements.generateReportBtn.disabled = false;
      // PDF下载按钮只在干预推演完成后启用
      // 普通推演不启用，需要用户先应用干预方案
    }
  }
}

async function requestAndPlaySimulation(payload) {
  const response = await fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const responseData = await safeReadJson(response);
  if (!response.ok) {
    throw new Error(responseData?.detail || "仿真请求失败");
  }
  if (!responseData?.frames || !responseData?.summary) {
    throw new Error("仿真响应缺少必要字段");
  }
  state.simulation = responseData;
  renderCrossValidation(state.simulation.summary);

  await animateSimulation();
}



elements.agentCount.addEventListener("input", () => {
  elements.agentCountLabel.textContent = elements.agentCount.value;
});

elements.northRate.addEventListener("input", () => {
  elements.northRateLabel.textContent = Number(elements.northRate.value).toFixed(1);
  updateFlowRate();
});

elements.southRate.addEventListener("input", () => {
  elements.southRateLabel.textContent = Number(elements.southRate.value).toFixed(1);
  updateFlowRate();
});

elements.normalPedestrianRatio.addEventListener("input", () => rebalancePopulation("normal_pedestrian"));
elements.groupFamilyRatio.addEventListener("input", () => rebalancePopulation("group_family"));
elements.vulnerableRatio.addEventListener("input", () => rebalancePopulation("vulnerable"));

elements.scenarioSelect.addEventListener("change", syncScenarioDefaults);
async function generateDiagnosticReport() {
  if (!state.simulation) return;
  if (Date.now() < state.suppressReportModalUntil) return;
  const reportBaselineReference = state.simulation?.scenario === "mitigation"
    ? getReportBaselineReference()
    : ensureReportBaselineReference(buildSimulationReference());
  const requestToken = ++state.reportRequestToken;

  elements.generateReportBtn.disabled = true;
  elements.generateReportBtn.textContent = "正在生成报告...";
  openReportModal();
  renderReportHistory();
  elements.reportModalMeta.textContent = `场景：${state.simulation.scenario} | 实时涌现密度：${state.currentDensity.toFixed(2)} 人/m²`;
  elements.reportContent.innerHTML = "<p>正在基于右侧实时仿真涌现密度、真实慢脑日志和 RAG 规范库生成报告...</p>";

  try {
    const response = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario: state.simulation.scenario,
        frontend_peak_density: state.currentDensity,
        mitigation_strategy: state.simulation.summary?.mitigation_strategy || "none",
        current_risk_level: state.lastFrame?.stats?.risk_level || null,
        summary: state.simulation.summary || null,
        logs: state.simulation.logs || [],
        density_series: state.simulation.summary?.peak_density_series || [],
        baseline_peak_density: reportBaselineReference?.peak_density || null,
        baseline_summary: reportBaselineReference?.summary || null,
        baseline_logs: reportBaselineReference?.logs || [],
        baseline_density_series: reportBaselineReference?.summary?.peak_density_series || [],
        velocity_series: state.simulation.summary?.velocity_series || [],
        baseline_velocity_series: reportBaselineReference?.summary?.velocity_series || [],
        risk_level_series: state.simulation.summary?.risk_level_series || [],
      }),
    });
    const data = await safeReadJson(response);
    if (requestToken !== state.reportRequestToken) return;
    if (response.ok && data) {
      const entry = createReportHistoryEntry(data);
      upsertReportHistoryEntry(entry);
      renderReportHistory();
      renderReportEntry(getActiveReportEntry());
    } else {
      const errorMessage = data?.detail || data?.error || "报告接口返回了无法解析的内容";
      elements.reportContent.innerHTML = `<p style="color: #ff7a7a">生成失败: ${escapeHtml(errorMessage)}</p>`;
    }
  } catch (error) {
    if (requestToken !== state.reportRequestToken) return;
    elements.reportContent.innerHTML = `<p style="color: #ff7a7a">请求错误: ${escapeHtml(describeError(error))}</p>`;
  } finally {
    if (requestToken !== state.reportRequestToken) return;
    elements.generateReportBtn.disabled = false;
    elements.generateReportBtn.textContent = "重新生成报告";
  }
}

function _buildInterventionCardsHtml(interventions, comparisonResult = null) {
  const cards = interventions.map((item, index) => {
    const isActive = state.activeIntervention?.type === item.type;
    return `
      <div class="intervention-card ${isActive ? 'intervention-card-active' : ''}" data-intervention-index="${index}">
        <div class="intervention-card-header">
          <span class="intervention-card-type">${escapeHtml(item.type)}</span>
          <span class="intervention-card-label">${escapeHtml(item.label)}</span>
        </div>
        <div class="intervention-card-reason">${escapeHtml(item.reason)}</div>
        <div class="intervention-card-effect">预期效果：${escapeHtml(item.expected_effect)}</div>
        <button class="intervention-apply-btn" data-intervention-index="${index}">
          ${isActive ? '已应用 ✓' : '应用此方案'}
        </button>
      </div>
    `;
  }).join('');

  return `
    <div class="intervention-section">
      <h3>整改方案建议</h3>
      <p class="intervention-hint">点击下方卡片会直接应用整改方案并自动进入推演，报告历史会继续保留，方便随时切换对比。</p>
      <div class="intervention-cards">${cards}</div>
      ${comparisonResult && comparisonResult._after ? `
        <div class="comparison-result">
          <h4>整改前后对比</h4>
          <p class="comparison-summary">${escapeHtml(buildComparisonSummary(comparisonResult))}</p>
          <div class="comparison-grid">
            <div class="comparison-item">
              <span class="comparison-label">实时涌现密度</span>
              <span class="comparison-before">${comparisonResult.peak_density?.toFixed(2) || '-'} 人/m²</span>
              <span class="comparison-arrow">→</span>
              <span class="comparison-after">${comparisonResult._after.peak_density?.toFixed(2) || '-'} 人/m²</span>
              ${comparisonResult._after.peak_density < comparisonResult.peak_density ?
                `<span class="comparison-delta comparison-positive">↓ ${((1 - comparisonResult._after.peak_density / Math.max(comparisonResult.peak_density, 0.01)) * 100).toFixed(1)}%</span>` :
                `<span class="comparison-delta comparison-negative">↑ ${((comparisonResult._after.peak_density / Math.max(comparisonResult.peak_density, 0.01) - 1) * 100).toFixed(1)}%</span>`
              }
            </div>
            <div class="comparison-item">
              <span class="comparison-label">慢脑触发</span>
              <span class="comparison-before">${comparisonResult.slow_brain_trigger_count || 0} 次</span>
              <span class="comparison-arrow">→</span>
              <span class="comparison-after">${comparisonResult._after.slow_brain_trigger_count || 0} 次</span>
            </div>
            <div class="comparison-item">
              <span class="comparison-label">危险步数</span>
              <span class="comparison-before">${comparisonResult.dangerous_steps || 0} 步</span>
              <span class="comparison-arrow">→</span>
              <span class="comparison-after">${comparisonResult._after.dangerous_steps || 0} 步</span>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;
}

function _bindInterventionCardEvents() {
  elements.reportContent.querySelectorAll(".intervention-apply-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const index = parseInt(e.target.dataset.interventionIndex, 10);
      const intervention = state.reportInterventions[index];
      if (!intervention) return;

      // 只在没有基线快照时才补齐，避免应用多个方案时覆盖掉“未加措施”的原始基线
      ensureBaselineReference();

      // 设置当前干预方案
      state.activeIntervention = intervention;

      // 应用方案后立即关闭报告，同时短暂屏蔽报告按钮，避免点击穿透又重新打开弹窗
      state.reportRequestToken += 1;
      state.suppressReportModalUntil = Date.now() + 800;
      closeReportModal();

      // 清空当前推演状态，重置画布
      state.simulation = null;
      state.lastFrame = null;
      state.frameIndex = 0;
      state.ripples = [];
      state.generatedRippleKeys = new Set();
      state.selectedAgentId = null;
      state.observedPeakDensity = 0;
      state.currentDensity = 0;

      // 重绘空白场景，只显示预防措施建模
      drawScene({ heatmap: [], agents: [] });

      // 更新UI状态
      elements.riskBadge.textContent = "正在执行干预推演...";
      elements.riskBadge.style.color = "var(--warning)";
      elements.generateReportBtn.disabled = true;

      // 自动开始干预推演
      await runInterventionSimulationDirect(intervention);
    });
  });
}

async function runInterventionSimulationDirect(intervention) {
  if (!intervention) return;

  const baselineReference = getReportBaselineReference() || ensureBaselineReference();

  state.reportRequestToken += 1;
  closeReportModal();
  elements.riskBadge.textContent = "正在执行干预推演...";
  elements.riskBadge.style.color = "var(--warning)";
  elements.runButton.disabled = true;
  elements.runButton.textContent = "⏹ 停止推演";

  try {
    // 自动设置场景和干预策略
    elements.scenarioSelect.value = "mitigation";
    syncMitigationControls();
    elements.mitigationStrategy.value = intervention.type;

    const payload = {
      scenario: "mitigation",
      max_agents: Number(elements.agentCount.value),
      duration_steps: (() => {
        const combinedRate = Number(elements.northRate.value) + Number(elements.southRate.value);
        const targetAgents = Number(elements.agentCount.value);
        const estimatedFillSeconds = Math.max(targetAgents, 300) / Math.max(combinedRate, 0.1);
        const steps = Math.ceil(Math.max(estimatedFillSeconds * 4, 45) / 0.5);
        return Math.max(40, Math.min(120, steps));
      })(),
      use_api: elements.useApi.checked,
      arrival_rate_north: state.simulation?.summary?.arrival_rate_north || Number(elements.northRate.value),
      arrival_rate_south: state.simulation?.summary?.arrival_rate_south || Number(elements.southRate.value),
      mitigation_strategy: intervention.type,
      intervention: intervention,
      normal_pedestrian_ratio: Number(elements.normalPedestrianRatio.value),
      group_family_ratio: Number(elements.groupFamilyRatio.value),
      vulnerable_ratio: Number(elements.vulnerableRatio.value),
    };

    await requestAndPlaySimulation(payload);

    // 构建对比结果
    state.comparisonResult = {
      peak_density: baselineReference?.peak_density ?? 0,
      slow_brain_trigger_count: baselineReference?.summary?.slow_brain_triggers || 0,
      dangerous_steps: baselineReference?.summary?.dangerous_steps || 0,
      _after: {
        peak_density: state.currentDensity,
        slow_brain_trigger_count: state.simulation.summary.slow_brain_triggers,
        dangerous_steps: state.simulation.summary.dangerous_steps,
      },
    };

    // 检查干预效果
    const afterDensity = state.currentDensity;
    const beforeDensity = baselineReference?.peak_density ?? afterDensity;
    const densityReduction = beforeDensity > 0
      ? ((beforeDensity - afterDensity) / beforeDensity * 100).toFixed(1)
      : "0.0";
    const safeLimit = state.bootstrap?.density_summary?.safe_limit || 4;

    // 启用PDF下载按钮
    document.getElementById("downloadPdfBtn").disabled = false;

    // 显示干预效果提示
    if (afterDensity <= safeLimit) {
      elements.riskBadge.textContent = `干预成功：实时涌现密度从 ${beforeDensity.toFixed(2)} 降至 ${afterDensity.toFixed(2)} 人/m²（降低 ${densityReduction}%），可导出PDF报告`;
      elements.riskBadge.style.color = "var(--success)";
    } else if (afterDensity < beforeDensity) {
      elements.riskBadge.textContent = `干预有效：实时涌现密度从 ${beforeDensity.toFixed(2)} 降至 ${afterDensity.toFixed(2)} 人/m²（降低 ${densityReduction}%），可导出PDF报告`;
      elements.riskBadge.style.color = "var(--success)";
    } else {
      elements.riskBadge.textContent = `干预效果不明显：实时涌现密度仍为 ${afterDensity.toFixed(2)} 人/m²，建议选择更强干预`;
      elements.riskBadge.style.color = "var(--warning)";
    }

    // 推演完成，提示用户手动点击"重新生成报告"查看对比结果
    elements.generateReportBtn.disabled = false;
    elements.generateReportBtn.textContent = "重新生成报告";
  } catch (error) {
    elements.logStream.textContent += `\n[Error] 干预推演失败: ${describeError(error)}`;
    elements.riskBadge.textContent = "干预推演失败";
    elements.riskBadge.style.color = "var(--danger)";
  } finally {
    elements.runButton.disabled = false;
    elements.runButton.textContent = "▶ 开始推演";
  }
}

function openReportModal() {
  elements.reportModal.classList.remove("hidden");
  elements.reportModal.setAttribute("aria-hidden", "false");
}

function closeReportModal() {
  elements.reportModal.classList.add("hidden");
  elements.reportModal.setAttribute("aria-hidden", "true");
}

function stopSimulation() {
  state.running = false;
  elements.runButton.disabled = false;
  elements.runButton.textContent = "▶ 开始推演";
  elements.canvasWrapper.classList.remove("focus");
  exitFullscreenMode();
  if (state.animationHandle) {
    cancelAnimationFrame(state.animationHandle);
  }
  elements.riskBadge.textContent = "演算已中止";
  elements.riskBadge.style.color = "var(--text-secondary)";
  elements.agentInsightTag?.classList.add("hidden");
}

function findNearestAgent(clientX, clientY) {
  const frame = getCurrentFrame();
  if (!frame?.agents?.length) return null;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const x = (clientX - rect.left) * scaleX;
  const y = (clientY - rect.top) * scaleY;

  let nearest = null;
  let nearestDistance = Infinity;
  frame.agents.forEach((agent) => {
    const point = isoMap(agent.x, agent.y, 0.2);
    const distance = Math.hypot(point.x - x, point.y - y);
    if (distance < nearestDistance) {
      nearest = agent;
      nearestDistance = distance;
    }
  });
  return nearestDistance <= 22 * getViewportScale() ? nearest : null;
}

function updateLockPanel() {
  const selectedAgentId = state.selectedAgentId;
  if (selectedAgentId === null) {
    elements.agentLockStatus.textContent = "全局滚动模式：显示全体 Agent 实时慢脑日志";
    elements.agentLockChip.classList.add("hidden");
    elements.clearAgentLock.classList.add("hidden");
    elements.rightPanel?.classList.remove("agent-locked");
    return;
  }

  const frame = getCurrentFrame();
  const selectedAgent = frame?.agents?.find((agent) => agent.id === selectedAgentId) || null;
  const profile = selectedAgent?.typology || "unknown";
  elements.agentLockStatus.textContent = `锁定 Agent ${selectedAgentId}，右侧已切换到该 Agent 的第一人称慢脑流。当前画像：${profile}`;
  elements.agentLockChip.textContent = `Agent #${selectedAgentId}`;
  elements.agentLockChip.classList.remove("hidden");
  elements.clearAgentLock.classList.remove("hidden");
  elements.rightPanel?.classList.add("agent-locked");
}

function handleCanvasClick(event) {
  const nearest = findNearestAgent(event.clientX, event.clientY);
  if (!nearest) {
    state.selectedAgentId = null;
    updateLockPanel();
    updateLogs();
    updateSelectedAgentTag();
    return;
  }
  state.selectedAgentId = nearest.id;
  updateLockPanel();
  drawScene(getCurrentFrame());
  updateLogs();
}

function handleCanvasHover(event) {
  const nearest = findNearestAgent(event.clientX, event.clientY);
  state.hoveredAgentId = nearest?.id ?? null;
  const frame = getCurrentFrame();
  if (frame) {
    drawScene(frame);
  }
}

elements.fullscreenExitButton.addEventListener("click", stopSimulation);
elements.closeReportModal.addEventListener("click", closeReportModal);
elements.reportModalBackdrop.addEventListener("click", closeReportModal);
canvas.addEventListener("click", handleCanvasClick);
canvas.addEventListener("mousemove", handleCanvasHover);
canvas.addEventListener("mouseleave", () => {
  state.hoveredAgentId = null;
  const frame = getCurrentFrame();
  if (frame) drawScene(frame);
});
elements.clearAgentLock.addEventListener("click", () => {
  state.selectedAgentId = null;
  updateLockPanel();
  const frame = getCurrentFrame();
  if (frame) drawScene(frame);
  updateLogs();
  updateSelectedAgentTag();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && elements.sandboxShell.classList.contains("fullscreen-mode")) {
    stopSimulation();
    return;
  }
  if (event.key === "Escape" && !elements.reportModal.classList.contains("hidden")) {
    closeReportModal();
  }
});
elements.generateReportBtn.addEventListener("click", generateDiagnosticReport);

// PDF下载按钮
document.getElementById("downloadPdfBtn").addEventListener("click", async () => {
  if (!state.simulation) return;
  const reportBaselineReference = state.simulation?.scenario === "mitigation"
    ? getReportBaselineReference()
    : ensureReportBaselineReference(buildSimulationReference());
  const btn = document.getElementById("downloadPdfBtn");
  btn.disabled = true;
  btn.textContent = "正在生成PDF...";

  try {
    const payload = {
      scenario: state.simulation.scenario,
      frontend_peak_density: state.currentDensity,
      mitigation_strategy: state.simulation.summary?.mitigation_strategy || "none",
      current_risk_level: state.lastFrame?.stats?.risk_level || null,
      summary: state.simulation.summary || null,
      logs: state.simulation.logs || [],
      density_series: state.simulation.summary?.peak_density_series || [],
      baseline_peak_density: reportBaselineReference?.peak_density || null,
      baseline_summary: reportBaselineReference?.summary || null,
      baseline_logs: reportBaselineReference?.logs || [],
      baseline_density_series: reportBaselineReference?.summary?.peak_density_series || [],
      velocity_series: state.simulation.summary?.velocity_series || [],
      baseline_velocity_series: reportBaselineReference?.summary?.velocity_series || [],
      risk_level_series: state.simulation.summary?.risk_level_series || [],
    };

    const response = await fetch("/api/report/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `diagnostic_report_${Date.now()}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else {
      console.error("PDF generation failed");
    }
  } catch (error) {
    console.error("PDF generation error:", error);
  } finally {
    btn.disabled = false;
    btn.textContent = "下载 PDF 报告";
  }
});

elements.runButton.addEventListener("click", () => {
  if (state.running) {
    stopSimulation();
    return;
  }
  runSimulation();
});
// Story and report modes are now integrated via generateDiagnosticReport
// elements.storyButton.addEventListener("click", runStoryMode);
// elements.reportButton.addEventListener("click", buildReport);

initHeroVideo();
resizeCanvas();
window.addEventListener("resize", resizeCanvas);
loadBootstrap().catch((error) => {
  elements.logStream.textContent = `初始化失败: ${describeError(error)}`;
  elements.riskBadge.textContent = "初始化失败";
  elements.riskBadge.style.color = "var(--danger)";
});

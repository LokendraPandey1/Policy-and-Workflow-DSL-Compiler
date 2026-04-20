const boot = window.COMPILER_STUDIO_BOOT || { samples: {}, phaseSpecs: [] };

const state = {
    lastPayload: null,
    runtimeTargets: [],
};

const elements = {
    nlInput: document.getElementById("nlInput"),
    sourceInput: document.getElementById("sourceInput"),
    translateBtn: document.getElementById("translateBtn"),
    compileBtn: document.getElementById("compileBtn"),
    runBtn: document.getElementById("runBtn"),
    clearOutputsBtn: document.getElementById("clearOutputsBtn"),
    targetSelect: document.getElementById("targetSelect"),
    runtimeInputs: document.getElementById("runtimeInputs"),
    tokensBody: document.getElementById("tokensBody"),
    astTree: document.getElementById("astTree"),
    semanticOutput: document.getElementById("semanticOutput"),
    codegenOutput: document.getElementById("codegenOutput"),
    runtimeOutput: document.getElementById("runtimeOutput"),
    traceList: document.getElementById("traceList"),
    overviewOutput: document.getElementById("overviewOutput"),
    statusMessage: document.getElementById("statusMessage"),
    phaseStrip: document.getElementById("phaseStrip"),
};

const metrics = {
    source_lines: document.getElementById("metric-source-lines"),
    token_count: document.getElementById("metric-token-count"),
    policy_count: document.getElementById("metric-policy-count"),
    workflow_count: document.getElementById("metric-workflow-count"),
    semantic_state: document.getElementById("metric-semantic-state"),
    runtime_state: document.getElementById("metric-runtime-state"),
};

function setStatus(message) {
    elements.statusMessage.textContent = message;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function updateMetrics(payload) {
    const metricValues = payload?.metrics || {
        source_lines: elements.sourceInput.value.trim() ? elements.sourceInput.value.trim().split("\n").length : 0,
        token_count: "--",
        policy_count: "--",
        workflow_count: "--",
        semantic_state: "--",
        runtime_state: "--",
    };

    Object.entries(metrics).forEach(([key, node]) => {
        node.textContent = metricValues[key] ?? "--";
    });
}

function updatePhaseCards(payload) {
    const states = payload?.phase_states || {};
    boot.phaseSpecs.forEach((phase) => {
        const card = elements.phaseStrip.querySelector(`[data-phase="${phase.key}"]`);
        if (!card) return;
        const status = card.querySelector(".phase-status");
        const phaseState = states[phase.key] || { status: "Waiting", tone: "idle" };
        card.classList.remove("tone-idle", "tone-ok", "tone-warn", "tone-danger");
        card.classList.add(`tone-${phaseState.tone}`);
        status.textContent = phaseState.status;
    });
}

function renderTokens(tokens = []) {
    if (!tokens.length) {
        elements.tokensBody.innerHTML = `<tr><td colspan="4" class="empty-state">No tokens to display.</td></tr>`;
        return;
    }

    elements.tokensBody.innerHTML = tokens.map((token) => `
        <tr>
            <td>${escapeHtml(token.type ?? "")}</td>
            <td>${escapeHtml(JSON.stringify(token.value))}</td>
            <td>${escapeHtml(token.line ?? "")}</td>
            <td>${escapeHtml(token.col ?? "")}</td>
        </tr>
    `).join("");
}

function summarizeAstNode(label, value) {
    if (Array.isArray(value)) {
        return `${label} [${value.length}]`;
    }

    if (value && typeof value === "object") {
        const nodeName = value.node || label;
        if (value.name) return `${label}: ${nodeName} ${value.name}`;
        if (value.op) return `${label}: ${nodeName} ${value.op}`;
        if (Object.hasOwn(value, "value")) return `${label}: ${nodeName} ${value.value}`;
        return `${label}: ${nodeName}`;
    }

    return `${label}: ${String(value)}`;
}

function astLeafMarkup(label, value) {
    return `
        <li class="ast-tree-item ast-tree-leaf">
            <div class="ast-row">
                <span class="ast-key">${escapeHtml(label)}</span>
                <span class="ast-value">${escapeHtml(String(value))}</span>
            </div>
        </li>
    `;
}

function astNodeMarkup(value, label = "node", expanded = false) {
    if (Array.isArray(value)) {
        if (!value.length) {
            return astLeafMarkup(label, "[]");
        }

        return `
            <li class="ast-tree-item">
                <details class="ast-branch" ${expanded ? "open" : ""}>
                    <summary class="ast-row ast-row-branch">
                        <span class="ast-toggle"></span>
                        <span class="ast-key">${escapeHtml(label)}</span>
                        <span class="ast-meta">${value.length} item(s)</span>
                    </summary>
                    <ul class="ast-tree-children">
                        ${value.map((child, index) => astNodeMarkup(child, `[${index}]`)).join("")}
                    </ul>
                </details>
            </li>
        `;
    }

    if (value && typeof value === "object") {
        const nodeName = value.node || label;
        const descriptor = value.name
            ? value.name
            : value.op
                ? value.op
                : Object.hasOwn(value, "value")
                    ? String(value.value)
                    : "";

        const children = Object.entries(value)
            .filter(([key]) => key !== "node")
            .map(([key, child]) => astNodeMarkup(child, key))
            .join("");

        return `
            <li class="ast-tree-item">
                <details class="ast-branch" ${expanded ? "open" : ""}>
                    <summary class="ast-row ast-row-branch">
                        <span class="ast-toggle"></span>
                        <span class="ast-node-type">${escapeHtml(nodeName)}</span>
                        <span class="ast-key">${escapeHtml(label)}</span>
                        ${descriptor ? `<span class="ast-value">${escapeHtml(descriptor)}</span>` : ""}
                    </summary>
                    ${children ? `<ul class="ast-tree-children">${children}</ul>` : ""}
                </details>
            </li>
        `;
    }

    return astLeafMarkup(label, value);
}

function renderAst(ast) {
    if (!ast) {
        elements.astTree.innerHTML = "Compile a valid program to inspect the AST.";
        elements.astTree.classList.add("empty-state");
        return;
    }

    elements.astTree.classList.remove("empty-state");
    elements.astTree.innerHTML = `
        <div class="ast-tree-root">
            <div class="ast-tree-caption">Expandable syntax tree</div>
            <ul class="ast-tree-list">
                ${astNodeMarkup(ast, summarizeAstNode("root", ast), true)}
            </ul>
        </div>
    `;
}

function renderTrace(trace = []) {
    if (!trace.length) {
        elements.traceList.innerHTML = "Run a policy or workflow to inspect trace events.";
        elements.traceList.classList.add("empty-state");
        return;
    }

    elements.traceList.classList.remove("empty-state");
    elements.traceList.innerHTML = trace.map((event) => `
        <article class="trace-event">
            <div class="trace-type">${escapeHtml(event.type || "info")}</div>
            <div class="trace-message">${escapeHtml(event.message || "")}</div>
        </article>
    `).join("");
}

function renderRuntimeTargets(targets = []) {
    state.runtimeTargets = targets;
    if (!targets.length) {
        elements.targetSelect.innerHTML = `<option value="">Compile a valid program first</option>`;
        renderRuntimeInputs(null);
        return;
    }

    elements.targetSelect.innerHTML = targets.map((target, index) => `
        <option value="${index}">${escapeHtml(target.label)}</option>
    `).join("");
    renderRuntimeInputs(targets[0]);
}

function renderRuntimeInputs(target) {
    if (!target || !target.inputs?.length) {
        elements.runtimeInputs.className = "runtime-inputs empty-state";
        elements.runtimeInputs.textContent = "This target does not require runtime inputs.";
        return;
    }

    elements.runtimeInputs.className = "runtime-inputs";
    elements.runtimeInputs.innerHTML = target.inputs.map((input) => `
        <div class="runtime-field">
            <label for="input-${escapeHtml(input.name)}">${escapeHtml(input.name)}</label>
            <input
                id="input-${escapeHtml(input.name)}"
                class="runtime-input"
                data-name="${escapeHtml(input.name)}"
                data-type="${escapeHtml(input.type)}"
                type="text"
                placeholder="Enter ${escapeHtml(input.type)} value"
            />
            <span class="runtime-type">${escapeHtml(input.type)}</span>
        </div>
    `).join("");
}

function applyPayload(payload) {
    state.lastPayload = payload;
    updateMetrics(payload);
    updatePhaseCards(payload);
    renderTokens(payload?.result?.tokens || []);
    renderAst(payload?.result?.ast || null);
    renderTrace(payload?.result?.execution?.trace || []);
    renderRuntimeTargets(payload?.runtime_targets || []);
    elements.semanticOutput.textContent = payload?.semantic_report || "No semantic analysis yet.";
    elements.codegenOutput.textContent = payload?.result?.generated_code || "No generated code yet.";
    elements.runtimeOutput.textContent = payload?.runtime_report || "Runtime not executed yet.";
    elements.overviewOutput.textContent = (payload?.overview_lines || []).join("\n");
    setStatus(payload?.message || "Ready.");
}

function clearOutputs() {
    state.lastPayload = null;
    state.runtimeTargets = [];
    renderTokens([]);
    renderAst(null);
    renderTrace([]);
    renderRuntimeTargets([]);
    elements.semanticOutput.textContent = "";
    elements.codegenOutput.textContent = "";
    elements.runtimeOutput.textContent = "";
    elements.overviewOutput.textContent = "Outputs cleared. Compile again to inspect the pipeline.";
    updateMetrics(null);
    updatePhaseCards(null);
    setStatus("All output panels were cleared.");
}

async function postJson(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });

    const data = await response.json();
    if (!response.ok) {
        throw data;
    }
    return data;
}

async function translateBrief() {
    const text = elements.nlInput.value.trim();
    if (!text) {
        setStatus("Add a plain English description before translating.");
        return;
    }

    elements.translateBtn.disabled = true;
    setStatus("Translating natural language into DSL...");
    try {
        const data = await postJson("/api/translate", { text });
        elements.sourceInput.value = data.dsl || "";
        setStatus(data.message || "Plain English brief translated into DSL.");
        updateMetrics(null);
    } catch (error) {
        setStatus(error.message || "Translation failed.");
    } finally {
        elements.translateBtn.disabled = false;
    }
}

async function compileSource() {
    const source = elements.sourceInput.value.trim();
    if (!source) {
        setStatus("The DSL editor is empty.");
        return;
    }

    elements.compileBtn.disabled = true;
    setStatus("Compiling through all visible phases...");
    try {
        const data = await postJson("/api/compile", { source });
        applyPayload(data);
    } catch (error) {
        if (error.result) {
            applyPayload(error);
        } else {
            setStatus(error.message || "Compilation failed.");
        }
    } finally {
        elements.compileBtn.disabled = false;
    }
}

function gatherRuntimeInputValues() {
    const values = {};
    elements.runtimeInputs.querySelectorAll(".runtime-input").forEach((input) => {
        const type = input.dataset.type;
        const raw = input.value.trim();
        if (type === "number") {
            values[input.dataset.name] = Number(raw);
        } else if (type === "boolean") {
            values[input.dataset.name] = ["true", "1", "yes"].includes(raw.toLowerCase());
        } else {
            values[input.dataset.name] = raw;
        }
    });
    return values;
}

async function runTarget() {
    const source = elements.sourceInput.value.trim();
    if (!source) {
        setStatus("The DSL editor is empty.");
        return;
    }

    const targetIndex = elements.targetSelect.value;
    const target = state.runtimeTargets[Number(targetIndex)];
    if (!target) {
        setStatus("Choose a policy or workflow target before running.");
        return;
    }

    elements.runBtn.disabled = true;
    setStatus(`Executing ${target.label}...`);
    try {
        const data = await postJson("/api/run", {
            source,
            target,
            inputs: gatherRuntimeInputValues(),
        });
        applyPayload(data);
    } catch (error) {
        if (error.result) {
            applyPayload(error);
        } else {
            setStatus(error.message || "Execution failed.");
        }
    } finally {
        elements.runBtn.disabled = false;
    }
}

function loadSample(key) {
    const sample = boot.samples[key];
    if (!sample) return;
    if (sample.type === "dsl") {
        elements.sourceInput.value = sample.content;
        setStatus(`${sample.label} loaded into the source workshop.`);
        updateMetrics(null);
        return;
    }
    elements.nlInput.value = sample.content;
    setStatus(`${sample.label} loaded into the natural language brief.`);
}

function setupTabs() {
    document.querySelectorAll(".tab-button").forEach((button) => {
        button.addEventListener("click", () => {
            const tab = button.dataset.tab;
            document.querySelectorAll(".tab-button").forEach((node) => node.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach((node) => node.classList.remove("active"));
            button.classList.add("active");
            document.querySelector(`[data-tab-panel="${tab}"]`)?.classList.add("active");
        });
    });
}

function attachEvents() {
    elements.translateBtn.addEventListener("click", translateBrief);
    elements.compileBtn.addEventListener("click", compileSource);
    elements.runBtn.addEventListener("click", runTarget);
    elements.clearOutputsBtn.addEventListener("click", clearOutputs);

    document.querySelectorAll("[data-sample]").forEach((button) => {
        button.addEventListener("click", () => loadSample(button.dataset.sample));
    });

    elements.targetSelect.addEventListener("change", () => {
        const target = state.runtimeTargets[Number(elements.targetSelect.value)];
        renderRuntimeInputs(target || null);
    });

    elements.sourceInput.addEventListener("input", () => updateMetrics(null));
}

function init() {
    attachEvents();
    setupTabs();
    updateMetrics(null);
    updatePhaseCards(null);
}

init();

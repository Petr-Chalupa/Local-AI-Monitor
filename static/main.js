const REFRESH_INTERVAL = 3000;
const LOG_TAIL = 200;

const el = (id) => document.getElementById(id);
const statusElement = el("status");
const updatedElement = el("updated");
const cpuElement = el("cpu");
const memoryElement = el("memory");
const diskElement = el("disk");
const resourcesChartElement = el("resources-chart");
const requestsProcessingElement = el("requests-processing");
const requestsQueuedElement = el("requests-queued");
const requestsSlotsElement = el("requests-slots");
const requestsSpeedElement = el("requests-speed");
const requestsPromptElement = el("requests-prompt");
const requestsChartElement = el("requests-chart");
const speedChartElement = el("speed-chart");
const containersElement = el("containers");
const gpusElement = el("gpus");
const logSourceElement = el("log-source");
const logsElement = el("logs");

let resourcesChart = null;
let requestsChart = null;
let speedChart = null;

// ----- Helpers -----

async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
}

function formatBytes(bytes) {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let unit = 0;
    while (bytes >= 1024 && unit < units.length - 1) {
        bytes /= 1024;
        unit++;
    }
    return `${bytes.toFixed(1)} ${units[unit]}`;
}

function formatUptime(startedAt) {
    const minutes = Math.max(0, Math.floor((Date.now() - new Date(startedAt)) / 60000));
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    if (days) return `${days}d ${hours}h`;
    return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

function percent(value) {
    return value != null ? `${value} %` : "—";
}

function calculateSpeedBetween(curr, prev) {
    if (!curr?.data?.stats || !prev?.data?.stats) return { gen: 0, prompt: 0 };

    const dt = (new Date(curr.timestamp) - new Date(prev.timestamp)) / 1000;
    const c = curr.data.stats;
    const p = prev.data.stats;

    const dGen = c.gen_tokens - p.gen_tokens;
    const genSpeed = dt > 0 && dGen > 0 ? dGen / dt : 0;

    const pDt = c.prompt_seconds - p.prompt_seconds;
    const dPrompt = c.prompt_tokens - p.prompt_tokens;
    const promptSpeed = pDt > 0 && dPrompt > 0 ? dPrompt / pDt : 0;

    return { gen: genSpeed, prompt: promptSpeed };
}

// ----- Chart -----

function makeChart(canvas, datasets, yScale) {
    if (typeof Chart === "undefined") {
        console.warn("Chart.js unavailable");
        return null;
    }

    return new Chart(canvas, {
        type: "line",
        data: { labels: [], datasets },
        options: {
            responsive: true,
            animation: false,
            interaction: { intersect: false, mode: "index" },
            elements: {
                point: { radius: 1, hoverRadius: 5 },
            },
            scales: {
                y: yScale,
                x: { ticks: { maxTicksLimit: 8 } },
            },
        },
    });
}

function createCharts() {
    resourcesChart = makeChart(
        resourcesChartElement,
        [
            { label: "CPU %", data: [] },
            { label: "RAM %", data: [] },
            { label: "Disk %", data: [], hidden: true },
        ],
        { min: 0, max: 100 },
    );

    requestsChart = makeChart(
        requestsChartElement,
        [
            { label: "Processing", data: [], stepped: true },
            { label: "Queued", data: [], stepped: true },
            { label: "Slots", data: [], borderDash: [4, 4], pointRadius: 0 },
        ],
        { min: 0, ticks: { precision: 0 } },
    );

    speedChart = makeChart(
        speedChartElement,
        [
            { label: "Generation (tok/s)", data: [] },
            { label: "Prompt Processing (tok/s)", data: [], hidden: true },
        ],
        { min: 0 },
    );
}

function setResourcesChart(items) {
    if (!resourcesChart) return;

    resourcesChart.data.labels = items.map((i) => new Date(i.timestamp).toLocaleTimeString());
    resourcesChart.data.datasets[0].data = items.map((i) => i.data.cpu?.usage_percent ?? null);
    resourcesChart.data.datasets[1].data = items.map((i) => i.data.memory?.usage_percent ?? null);
    resourcesChart.data.datasets[2].data = items.map((i) => i.data.disk?.usage_percent ?? null);
    resourcesChart.update("none");
}

function setRequestsChart(items) {
    if (!requestsChart) return;

    requestsChart.data.labels = items.map((i) => new Date(i.timestamp).toLocaleTimeString());
    requestsChart.data.datasets[0].data = items.map((i) => i.data?.processing ?? null);
    requestsChart.data.datasets[1].data = items.map((i) => i.data?.queued ?? null);
    requestsChart.data.datasets[2].data = items.map((i) => i.data?.slots_total || null);
    requestsChart.update("none");
}

function setSpeedChart(history) {
    if (!speedChart) return;

    const labels = [];
    const genData = [];
    const promptData = [];

    for (let i = 1; i < history.length; i++) {
        const curr = history[i];
        const { gen, prompt } = calculateSpeedBetween(curr, history[i - 1]);
        labels.push(new Date(curr.timestamp).toLocaleTimeString());
        genData.push(gen);
        promptData.push(prompt);
    }

    speedChart.data.labels = labels;
    speedChart.data.datasets[0].data = genData;
    speedChart.data.datasets[1].data = promptData;
    speedChart.update("none");
}

// ----- Rendering -----

function renderList(list, rows, emptyText) {
    list.replaceChildren();

    if (rows.length === 0) rows = [[emptyText]];

    for (const [left, right] of rows) {
        const item = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = left;
        item.appendChild(name);

        if (right != null) {
            const value = document.createElement("span");
            value.textContent = right;
            item.appendChild(value);
        }
        list.appendChild(item);
    }
}

function renderContainers(containers) {
    renderList(
        containersElement,
        containers.map((c) => {
            const details = [
                c.health ? `${c.status} (${c.health})` : c.status,
                c.started_at && formatUptime(c.started_at),
                c.memory_bytes != null && formatBytes(c.memory_bytes),
                c.restarts > 0 && `${c.restarts}x restart`,
            ];
            return [c.name, details.filter(Boolean).join(" · ")];
        }),
        "No containers",
    );
}

function renderGpus(gpus) {
    renderList(
        gpusElement,
        gpus.map((g) => [
            `${g.index}: ${g.name}`,
            `${g.usage_percent} % · ${g.memory_used_mb} / ${g.memory_total_mb} MB · ${g.temperature_c} °C`,
        ]),
        "No GPUs",
    );
}

function renderLogSources(containers) {
    const names = containers.map((c) => c.name);
    if (names.join() === Array.from(logSourceElement.options, (o) => o.value).join()) return;

    const selected = logSourceElement.value;
    logSourceElement.replaceChildren(...names.map((name) => new Option(name, name)));
    if (names.includes(selected)) logSourceElement.value = selected;
}

// ----- Updates -----

async function updateResources() {
    const { timestamp, data } = await fetchJson("/api/resources");

    updatedElement.textContent = new Date(timestamp).toLocaleTimeString();
    cpuElement.textContent = percent(data.cpu?.usage_percent);
    memoryElement.textContent = percent(data.memory?.usage_percent);
    diskElement.textContent = percent(data.disk?.usage_percent);

    setResourcesChart(await fetchJson("/api/history/resources"));
}

async function updateRequests() {
    const { data } = await fetchJson("/api/requests");
    const history = await fetchJson("/api/history/requests");

    const busy = data?.slots_busy ?? 0;
    const total = data?.slots_total ?? 0;

    requestsProcessingElement.textContent = data ? data.processing : "unavailable";
    requestsQueuedElement.textContent = !data ? "unavailable" : data.queued;
    requestsSlotsElement.textContent = !data ? "unavailable" : total ? `${busy} / ${total} busy` : "n/a";

    const speeds = calculateSpeedBetween(history.at(-1), history.at(-2));
    const formatSpeed = (val) => (!data ? "unavailable" : val > 0 ? `${val.toFixed(1)} tok/s` : "idle");
    requestsSpeedElement.textContent = formatSpeed(speeds.gen);
    requestsPromptElement.textContent = formatSpeed(speeds.prompt);

    setRequestsChart(history);
    setSpeedChart(history);
}

async function updateContainers() {
    const { data } = await fetchJson("/api/containers");
    renderContainers(data);
    renderLogSources(data);
}

async function updateGpus() {
    const { data } = await fetchJson("/api/gpus");
    renderGpus(data);
}

async function updateLogs() {
    if (!logSourceElement.value) return;

    const url = `/api/logs?container=${encodeURIComponent(logSourceElement.value)}&tail=${LOG_TAIL}`;
    const { data } = await fetchJson(url);

    const atBottom = logsElement.scrollHeight - logsElement.scrollTop - logsElement.clientHeight < 20;
    logsElement.textContent = data.lines.join("\n") || "No logs";
    if (atBottom) logsElement.scrollTop = logsElement.scrollHeight;
}

async function refresh() {
    const results = await Promise.allSettled([
        updateResources(),
        updateRequests(),
        updateContainers().then(updateLogs),
        updateGpus(),
    ]);

    const online = results[0].status === "fulfilled";
    statusElement.textContent = online ? "Online" : "Offline";

    results.forEach((r) => r.status === "rejected" && console.error(r.reason));
}

createCharts();
refresh();
setInterval(refresh, REFRESH_INTERVAL);
logSourceElement.addEventListener("change", () => updateLogs().catch(console.error));

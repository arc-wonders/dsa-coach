/* Charts for DSA Coach. Requires Chart.js 4 (loaded in base.html). */
const LEVELS = ["Off", "Light", "Steady", "Focused", "Deep"];
const MODE_NAMES = { normal: "Normal", exam: "Exam", free: "Free", off: "Off" };

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function fmtDay(iso, opts) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, opts || { weekday: "short", day: "numeric" });
}
function baseOptions() {
  Chart.defaults.font.family = 'Inter, -apple-system, "Segoe UI", Roboto, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = cssVar("--text-3");
  return {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: cssVar("--surface"),
        titleColor: cssVar("--text"),
        bodyColor: cssVar("--text-2"),
        borderColor: cssVar("--border-strong"),
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        boxPadding: 4,
        usePointStyle: true,
      },
    },
  };
}

/**
 * Effort-level editor: one point per day, drag up/down (or across several days) to set the level.
 * Double-click a point to return that day to automatic.
 */
function loadEditor(canvas, days, { onSaved, horizon } = {}) {
  let data = days.slice();
  const modeColor = (m) => cssVar("--mode-" + m);
  const opts = baseOptions();
  const chart = new Chart(canvas, {
    type: "line",
    data: {
      labels: data.map((d) => d.day),
      datasets: [
        {
          data: data.map((d) => d.level),
          borderColor: cssVar("--border-strong"),
          borderWidth: 2,
          tension: 0.25,
          fill: { target: "origin", above: cssVar("--accent-soft") },
          pointRadius: 6,
          pointHoverRadius: 8,
          pointHitRadius: 14,
          pointBackgroundColor: data.map((d) => modeColor(d.mode)),
          pointBorderColor: data.map((d) => (d.override ? cssVar("--text") : cssVar("--surface"))),
          pointBorderWidth: data.map((d) => (d.override ? 2.5 : 2)),
        },
      ],
    },
    options: {
      ...opts,
      interaction: { mode: "nearest", axis: "x", intersect: false },
      layout: { padding: { top: 10, right: 8 } },
      scales: {
        y: {
          min: 0, max: 4,
          ticks: { stepSize: 1, callback: (v) => LEVELS[v] },
          grid: { color: cssVar("--border") },
          border: { display: false },
        },
        x: {
          grid: { display: false },
          border: { color: cssVar("--border-strong") },
          ticks: {
            maxRotation: 0, autoSkip: true, autoSkipPadding: 10,
            callback: function (v) { return fmtDay(this.getLabelForValue(v), { day: "numeric", month: "short" }); },
          },
        },
      },
      plugins: {
        ...opts.plugins,
        tooltip: {
          ...opts.plugins.tooltip,
          displayColors: false,
          callbacks: {
            title: (items) => fmtDay(data[items[0].dataIndex].day, { weekday: "long", day: "numeric", month: "short" }),
            label: (item) => {
              const d = data[item.dataIndex];
              const lines = [`${LEVELS[d.level]} · ~${d.minutes} min`, `${MODE_NAMES[d.mode]} day${d.note ? " · " + d.note : ""}`];
              lines.push(d.override ? "Set by you (double-click to reset)" : "Automatic");
              return lines;
            },
          },
        },
      },
    },
  });

  // ---- drag to edit ----
  let dragging = false;
  const changed = new Map();
  const todayIso = data[0] && data[0].day;
  function pointAt(evt) {
    const rect = canvas.getBoundingClientRect();
    const x = evt.clientX - rect.left, y = evt.clientY - rect.top;
    const idx = Math.round(chart.scales.x.getValueForPixel(x));
    const lvl = Math.max(0, Math.min(4, Math.round(chart.scales.y.getValueForPixel(y))));
    if (idx < 0 || idx >= data.length) return null;
    return { idx, lvl };
  }
  function apply(p) {
    if (!p) return;
    const d = data[p.idx];
    if (d.level === p.lvl) return;
    d.level = p.lvl; d.override = true;
    changed.set(d.day, p.lvl);
    const ds = chart.data.datasets[0];
    ds.data[p.idx] = p.lvl;
    ds.pointBorderColor[p.idx] = cssVar("--text");
    ds.pointBorderWidth[p.idx] = 2.5;
    chart.update("none");
  }
  canvas.addEventListener("pointerdown", (e) => {
    dragging = true; canvas.setPointerCapture(e.pointerId); apply(pointAt(e));
  });
  canvas.addEventListener("pointermove", (e) => { if (dragging) apply(pointAt(e)); });
  async function finish() {
    if (!dragging) return;
    dragging = false;
    if (!changed.size) return;
    const payload = [...changed].map(([day, level]) => ({ day, level }));
    changed.clear();
    await save(payload);
  }
  canvas.addEventListener("pointerup", finish);
  canvas.addEventListener("pointercancel", finish);
  canvas.addEventListener("dblclick", async (e) => {
    const p = pointAt(e);
    if (p) await save([{ day: data[p.idx].day, level: null }]);
  });

  async function save(payload) {
    const r = await fetch("/api/load", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days: payload, horizon: horizon || data.length }),
    });
    const res = await r.json();
    data = res.schedule.slice(0, data.length);
    const ds = chart.data.datasets[0];
    ds.data = data.map((d) => d.level);
    ds.pointBackgroundColor = data.map((d) => modeColor(d.mode));
    ds.pointBorderColor = data.map((d) => (d.override ? cssVar("--text") : cssVar("--surface")));
    ds.pointBorderWidth = data.map((d) => (d.override ? 2.5 : 2));
    chart.update("none");
    if (onSaved) onSaved(res, payload.some((p) => p.day === todayIso));
  }
  return chart;
}

function weeklyChart(canvas, weeks) {
  const opts = baseOptions();
  const surface = cssVar("--surface");
  return new Chart(canvas, {
    type: "bar",
    data: {
      labels: weeks.map((w) => w.label),
      datasets: [
        { label: "New", data: weeks.map((w) => w.new), backgroundColor: cssVar("--mode-normal"),
          borderColor: surface, borderWidth: { top: 2 }, borderRadius: 4, borderSkipped: "bottom", stack: "s", maxBarThickness: 28 },
        { label: "Review", data: weeks.map((w) => w.review), backgroundColor: cssVar("--mode-exam"),
          borderColor: surface, borderWidth: { top: 2 }, borderRadius: 4, borderSkipped: "bottom", stack: "s", maxBarThickness: 28 },
      ],
    },
    options: {
      ...opts,
      scales: {
        y: { beginAtZero: true, stacked: true, ticks: { precision: 0 }, grid: { color: cssVar("--border") }, border: { display: false } },
        x: { stacked: true, grid: { display: false }, border: { color: cssVar("--border-strong") }, ticks: { maxRotation: 0, autoSkipPadding: 8 } },
      },
      plugins: {
        ...opts.plugins,
        tooltip: {
          ...opts.plugins.tooltip,
          callbacks: {
            title: (items) => "Week of " + weeks[items[0].dataIndex].label,
            footer: (items) => {
              const w = weeks[items[0].dataIndex];
              return w.planned ? `Plan followed: ${w.done}/${w.planned}` : "";
            },
          },
        },
      },
    },
  });
}

function progressChart(canvas, p, goal) {
  const opts = baseOptions();
  const blue = cssVar("--mode-normal");
  return new Chart(canvas, {
    type: "line",
    data: {
      labels: p.labels,
      datasets: [
        { label: "Solved", data: p.actual, borderColor: blue, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, spanGaps: false },
        { label: "Forecast", data: p.forecast, borderColor: blue, borderDash: [5, 4], borderWidth: 2, pointRadius: 0, pointHoverRadius: 5 },
        { label: "Target pace", data: p.target, borderColor: cssVar("--text-3"), borderDash: [2, 3], borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 4 },
      ],
    },
    options: {
      ...opts,
      scales: {
        y: { beginAtZero: true, suggestedMax: goal, grid: { color: cssVar("--border") }, border: { display: false }, ticks: { precision: 0 } },
        x: {
          grid: { display: false }, border: { color: cssVar("--border-strong") },
          ticks: { maxRotation: 0, autoSkipPadding: 24, callback: function (v) { return fmtDay(this.getLabelForValue(v), { day: "numeric", month: "short" }); } },
        },
      },
      plugins: {
        ...opts.plugins,
        tooltip: {
          ...opts.plugins.tooltip,
          filter: (i) => i.raw !== null,
          callbacks: {
            title: (items) => fmtDay(items[0].label, { weekday: "short", day: "numeric", month: "short" }),
            label: (i) => ` ${i.dataset.label}: ${Math.round(i.raw)}`,
          },
        },
      },
    },
  });
}

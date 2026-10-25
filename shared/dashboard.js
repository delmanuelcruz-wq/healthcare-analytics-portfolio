/* Shared dashboard helpers - inlined into every project dashboard at build time.
   Charts read colors from CSS variables, so light/dark themes stay in one place. */
(function () {
  // ?theme=light|dark forces a theme (used for README screenshots); otherwise follow the OS.
  const forced = new URLSearchParams(location.search).get("theme");
  if (forced === "light" || forced === "dark") document.documentElement.setAttribute("data-theme", forced);
  const charts = [];
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const fmt = new Intl.NumberFormat("en-US");

  function colors() {
    return {
      ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"), grid: css("--grid"), axis: css("--axis"),
      surface: css("--surface"), s1: css("--series-1"), s2: css("--series-2"), s3: css("--series-3"),
      gray: css("--series-gray"), good: css("--good"), warning: css("--warning"), critical: css("--critical"),
      seq: [1, 2, 3, 4, 5, 6, 7].map((i) => css(`--seq-${i}`)),
      ord: [1, 2, 3, 4, 5].map((i) => css(`--ord-${i}`)),
    };
  }

  function layout(extra) {
    const c = colors();
    const axis = { gridcolor: c.grid, linecolor: c.axis, zeroline: false, tickfont: { color: c.muted, size: 11 },
                   title: { font: { color: c.ink2, size: 12 } }, automargin: true };
    const base = {
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: c.ink, size: 12 },
      margin: { l: 48, r: 18, t: 10, b: 40 }, hovermode: "x unified",
      hoverlabel: { bgcolor: c.surface, bordercolor: c.axis, font: { color: c.ink } },
      legend: { orientation: "h", x: 0, y: 1.12, font: { color: c.ink2, size: 12 } },
      xaxis: Object.assign({}, axis, { showgrid: false, showline: true }),
      yaxis: Object.assign({}, axis, { showline: false, rangemode: "tozero" }),
      bargap: 0.35,
    };
    return deepMerge(base, extra || {});
  }

  function deepMerge(a, b) {
    const out = Array.isArray(a) ? a.slice() : Object.assign({}, a);
    for (const k of Object.keys(b)) {
      if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k] && typeof a[k] === "object") out[k] = deepMerge(a[k], b[k]);
      else out[k] = b[k];
    }
    return out;
  }

  const config = { displayModeBar: false, responsive: true };

  function register(fn) { charts.push(fn); }
  function renderAll() { const c = colors(); charts.forEach((fn) => fn(c)); }

  function table(el, columns, rows) {
    const head = columns.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("");
    const body = rows.map((r) => "<tr>" + columns.map((c) => {
      let v = r[c.key];
      if (c.num && typeof v === "number") v = c.pct ? (v * 100).toFixed(1) + "%" : (Number.isInteger(v) ? fmt.format(v) : v.toFixed(c.dp ?? 1));
      return `<td class="${c.num ? "num" : ""}">${v ?? ""}</td>`;
    }).join("") + "</tr>").join("");
    el.innerHTML = `<div class="table-scroll"><table class="data"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function tiles(el, items) {
    el.innerHTML = items.map((t) => {
      let delta = "";
      if (t.delta !== undefined && t.delta !== null) {
        const up = t.delta >= 0;
        const good = t.upIsGood === undefined ? null : (up === t.upIsGood);
        const cls = good === null ? "" : (good ? "up" : "down");
        const sign = up ? "+" : "−";
        delta = `<p class="delta"><span class="${cls}">${sign}${Math.abs(t.delta).toFixed(1)}%</span> ${t.deltaLabel || ""}</p>`;
      }
      return `<div class="tile"><p class="label">${t.label}</p><p class="value">${t.value}</p>${delta}${t.note ? `<p class="note">${t.note}</p>` : ""}</div>`;
    }).join("");
  }

  window.Dash = { register, renderAll, layout, config, table, tiles, colors, fmt };
  document.addEventListener("DOMContentLoaded", renderAll);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderAll);
  new MutationObserver(renderAll).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();

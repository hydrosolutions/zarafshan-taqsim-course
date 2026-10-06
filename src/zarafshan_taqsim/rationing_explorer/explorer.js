(function () {
  "use strict";
  const root = document.getElementById("rationing-explorer");
  const dataNode = document.getElementById("rationing-data");
  if (!root || !dataNode) return;

  const data = JSON.parse(dataNode.textContent);
  // Compact mode (used on a slide): shorter charts, same data and behaviour.
  const compact = root.dataset.compact === "1";
  const chartHeight = compact ? 118 : 164;
  const NS = "http://www.w3.org/2000/svg";
  const plans = data.plans;
  const triggers = [...new Set(plans.map((p) => p.trigger))].sort((a, b) => a - b);
  const rations = [...new Set(plans.map((p) => p.ration))].sort((a, b) => a - b);
  const keyOf = (trigger, ration) => trigger + "|" + ration;
  const byKey = new Map(plans.map((p) => [keyOf(p.trigger, p.ration), p]));
  const reference = byKey.get(keyOf(triggers[0], rations[rations.length - 1]));
  const front = plans
    .filter((p) => p.unbeaten)
    .filter((p, i, all) => all.findIndex((q) => q.mean_shortage === p.mean_shortage && q.worst_month === p.worst_month) === i)
    .sort((a, b) => a.mean_shortage - b.mean_shortage || b.worst_month - a.worst_month);

  const $ = (id) => document.getElementById(id);
  const tooltip = $("rx-tooltip");
  let current = reference;

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }
  function text(parent, x, y, content, attrs) {
    const node = el("text", Object.assign({ x, y }, attrs || {}), parent);
    node.textContent = content;
    return node;
  }
  const scale = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
  const cssVar = (name) => getComputedStyle(root).getPropertyValue(name).trim();
  const C = {
    water: cssVar("--water"),
    shortage: cssVar("--shortage"),
    reference: cssVar("--reference"),
    ink: cssVar("--ink"),
    muted: cssVar("--muted"),
    grid: cssVar("--grid"),
    axis: cssVar("--axis"),
    surface: cssVar("--surface"),
  };
  const fmt = (v, digits) => v.toFixed(digits === undefined ? 0 : digits);
  const percent = (ration) => fmt(ration * 100) + " %";

  // A chart frame: axes, gridlines, and a pointer helper that reports data-space coordinates.
  function frame(svg, opts) {
    // Draw at the element's real pixel width so that text keeps its size on any screen.
    const W = Math.max(280, Math.round(svg.getBoundingClientRect().width) || 460);
    const H = opts.height;
    const m = Object.assign({ l: 44, r: 12, t: 8, b: 36 }, opts.margin || {});
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.replaceChildren();
    const x = scale(opts.x[0], opts.x[1], m.l, W - m.r);
    const y = scale(opts.y[0], opts.y[1], H - m.b, m.t);
    for (const tick of opts.yTicks) {
      el("line", { x1: m.l, x2: W - m.r, y1: y(tick), y2: y(tick), stroke: C.grid, "stroke-width": 1 }, svg);
      text(svg, m.l - 6, y(tick) + 3.5, String(tick), { "text-anchor": "end" });
    }
    for (const tick of opts.xTicks) {
      const label = opts.xTickLabel ? opts.xTickLabel(tick) : String(tick);
      text(svg, x(tick), H - m.b + 14, label, { "text-anchor": "middle" });
    }
    el("line", { x1: m.l, x2: W - m.r, y1: y(opts.y[0]), y2: y(opts.y[0]), stroke: C.axis, "stroke-width": 1 }, svg);
    if (opts.xTitle) text(svg, (m.l + W - m.r) / 2, H - 4, opts.xTitle, { "text-anchor": "middle", class: "rx-axis-title" });
    const toView = (event) => {
      const box = svg.getBoundingClientRect();
      return { vx: ((event.clientX - box.left) / box.width) * W, vy: ((event.clientY - box.top) / box.height) * H };
    };
    return { x, y, W, H, m, toView };
  }

  function showTooltip(event, rows) {
    tooltip.replaceChildren();
    for (const [strong, rest] of rows) {
      const row = document.createElement("div");
      const value = document.createElement("strong");
      value.textContent = strong;
      row.appendChild(value);
      row.appendChild(document.createTextNode(rest));
      tooltip.appendChild(row);
    }
    tooltip.hidden = false;
    const box = root.getBoundingClientRect();
    const left = Math.min(event.clientX - box.left + 14, box.width - tooltip.offsetWidth - 8);
    tooltip.style.left = Math.max(8, left) + "px";
    tooltip.style.top = event.clientY - box.top + 14 + "px";
  }
  const hideTooltip = () => (tooltip.hidden = true);

  // --- Trade-off chart ---------------------------------------------------------------------------------
  const tradeoffSvg = $("rx-tradeoff");
  const meanTop = data.mean_axis_max;
  const onChart = (p) => p.mean_shortage <= meanTop;
  let tradeoff;
  let marker;
  let hoverRing;

  function drawTradeoff() {
    tradeoff = frame(tradeoffSvg, {
      height: compact ? 250 : 340,
      x: [0, meanTop],
      y: [0, 100],
      xTicks: Array.from({ length: meanTop / 2 + 1 }, (_, i) => i * 2),
      yTicks: [0, 20, 40, 60, 80, 100],
      xTitle: "Average shortage (Mm³ per year)",
      margin: { t: 22 },
    });
    const { x, y, m, W } = tradeoff;
    text(tradeoffSvg, m.l - 30, 12, "Worst month (% of need not delivered)", { class: "rx-axis-title" });
    for (const p of plans) {
      if (!p.unbeaten && onChart(p)) el("circle", { cx: x(p.mean_shortage), cy: y(p.worst_month), r: 2.6, fill: C.reference }, tradeoffSvg);
    }
    const shown = front.filter(onChart);
    let path = "";
    shown.forEach((p, i) => {
      path += i === 0 ? `M${x(p.mean_shortage)},${y(p.worst_month)}` : `H${x(p.mean_shortage)}V${y(p.worst_month)}`;
    });
    el("path", { d: path, fill: "none", stroke: C.ink, "stroke-width": 1 }, tradeoffSvg);
    for (const p of shown) {
      el("circle", { cx: x(p.mean_shortage), cy: y(p.worst_month), r: 4, fill: C.ink, stroke: C.surface, "stroke-width": 1.5 }, tradeoffSvg);
    }
    const beyond = plans.filter((p) => !onChart(p)).length;
    if (beyond) text(tradeoffSvg, W - m.r, y(0) - 8, `${beyond} plans lie further right →`, { "text-anchor": "end" });
    const refLabel = text(tradeoffSvg, x(reference.mean_shortage) + 10, y(reference.worst_month) - 8, "no rationing", { class: "rx-label" });
    refLabel.setAttribute("pointer-events", "none");
    hoverRing = el("circle", { r: 8, fill: "none", stroke: C.muted, "stroke-width": 1.5, visibility: "hidden" }, tradeoffSvg);
    marker = el("circle", { r: 7, fill: C.water, stroke: C.surface, "stroke-width": 2 }, tradeoffSvg);
  }

  function nearestPlan(event) {
    const { vx, vy } = tradeoff.toView(event);
    let best = null;
    let bestDistance = 20;
    for (const p of plans) {
      if (!onChart(p)) continue;
      const d = Math.hypot(tradeoff.x(p.mean_shortage) - vx, tradeoff.y(p.worst_month) - vy) - (p.unbeaten ? 0.5 : 0);
      if (d < bestDistance) {
        best = p;
        bestDistance = d;
      }
    }
    return best;
  }
  tradeoffSvg.addEventListener("pointermove", (event) => {
    const p = nearestPlan(event);
    if (!p) {
      hoverRing.setAttribute("visibility", "hidden");
      tradeoffSvg.style.cursor = "default";
      return hideTooltip();
    }
    tradeoffSvg.style.cursor = "pointer";
    hoverRing.setAttribute("cx", tradeoff.x(p.mean_shortage));
    hoverRing.setAttribute("cy", tradeoff.y(p.worst_month));
    hoverRing.setAttribute("visibility", "visible");
    showTooltip(event, [
      [fmt(p.mean_shortage, 1) + " Mm³", " not delivered per year, on average"],
      [fmt(p.worst_month) + " %", " short in the worst month"],
      [p.years_short + " years", " of 100 with a shortage"],
      ["", `Trigger ${fmt(p.trigger)} Mm³, ration ${percent(p.ration)} · ${p.unbeaten ? "unbeaten" : "beaten"}`],
    ]);
  });
  tradeoffSvg.addEventListener("pointerleave", () => {
    hoverRing.setAttribute("visibility", "hidden");
    hideTooltip();
  });
  tradeoffSvg.addEventListener("click", (event) => {
    const p = nearestPlan(event);
    if (p) select(p);
  });

  // --- Shortage by year --------------------------------------------------------------------------------
  const shortageSvg = $("rx-shortage");
  let shortage;
  let shortageBars = [];
  let shortageCross;

  function drawShortage() {
    shortage = frame(shortageSvg, {
      height: chartHeight,
      x: [0.5, data.years + 0.5],
      y: [0, 100],
      xTicks: [1, 20, 40, 60, 80, 100],
      yTicks: [0, 50, 100],
      xTitle: "Year",
    });
    const { x, y } = shortage;
    const band = x(2) - x(1);
    reference.shortage.forEach((value, i) => {
      if (value > 0) el("rect", { x: x(i + 1) - band * 0.42, y: y(value), width: band * 0.84, height: y(0) - y(value), fill: C.reference, rx: 1 }, shortageSvg);
    });
    shortageBars = reference.shortage.map((_, i) => el("rect", { x: x(i + 1) - band * 0.24, width: band * 0.48, fill: C.shortage, rx: 1 }, shortageSvg));
    shortageCross = el("line", { y1: y(100), y2: y(0), stroke: C.muted, "stroke-width": 1, visibility: "hidden" }, shortageSvg);
  }
  shortageSvg.addEventListener("pointermove", (event) => {
    const { vx } = shortage.toView(event);
    const year = Math.round(1 + ((vx - shortage.x(1)) / (shortage.x(data.years) - shortage.x(1))) * (data.years - 1));
    if (year < 1 || year > data.years) return;
    shortageCross.setAttribute("x1", shortage.x(year));
    shortageCross.setAttribute("x2", shortage.x(year));
    shortageCross.setAttribute("visibility", "visible");
    showTooltip(event, [
      ["Year " + year, ""],
      [fmt(current.shortage[year - 1], 1) + " %", " short in its worst month, your plan"],
      [fmt(reference.shortage[year - 1], 1) + " %", " with no rationing"],
    ]);
  });
  shortageSvg.addEventListener("pointerleave", () => {
    shortageCross.setAttribute("visibility", "hidden");
    hideTooltip();
  });

  // --- Storage -----------------------------------------------------------------------------------------
  const storageSvg = $("rx-storage");
  const months = reference.storage.length;
  let storage;
  let storageLine;
  let triggerLine;
  let triggerLabel;
  let storageCross;

  const linePath = (values) => values.map((v, i) => (i ? "L" : "M") + storage.x(i) + "," + storage.y(v)).join("");

  function drawStorage() {
    const first = data.window.start_year;
    storage = frame(storageSvg, {
      height: chartHeight,
      x: [0, months - 1],
      y: [0, data.capacity],
      xTicks: Array.from({ length: data.window.years / 5 + 1 }, (_, i) => Math.min(i * 60, months - 1)),
      xTickLabel: (tick) => String(first + Math.round(tick / 12)),
      yTicks: [0, data.capacity / 2, data.capacity],
      xTitle: "Year",
    });
    el("path", { d: linePath(reference.storage), fill: "none", stroke: C.reference, "stroke-width": 1.5 }, storageSvg);
    triggerLine = el("line", { x1: storage.x(0), x2: storage.x(months - 1), stroke: C.muted, "stroke-width": 1 }, storageSvg);
    triggerLabel = text(storageSvg, storage.x(0) + 4, 0, "trigger");
    storageLine = el("path", { fill: "none", stroke: C.water, "stroke-width": 2, "stroke-linejoin": "round" }, storageSvg);
    storageCross = el("line", { y1: storage.y(data.capacity), y2: storage.y(0), stroke: C.muted, "stroke-width": 1, visibility: "hidden" }, storageSvg);
  }
  storageSvg.addEventListener("pointermove", (event) => {
    const { vx } = storage.toView(event);
    const i = Math.round(((vx - storage.x(0)) / (storage.x(months - 1) - storage.x(0))) * (months - 1));
    if (i < 0 || i >= months) return;
    storageCross.setAttribute("x1", storage.x(i));
    storageCross.setAttribute("x2", storage.x(i));
    storageCross.setAttribute("visibility", "visible");
    const month = i % 12;
    const season = month < 6 ? `winter month ${month + 1}` : `summer month ${month - 5}`;
    showTooltip(event, [
      [`Year ${data.window.start_year + Math.floor(i / 12)}`, `, ${season}`],
      [fmt(current.storage[i], 1) + " Mm³", " in store with your plan"],
      [fmt(reference.storage[i], 1) + " Mm³", " with no rationing"],
    ]);
  });
  storageSvg.addEventListener("pointerleave", () => {
    storageCross.setAttribute("visibility", "hidden");
    hideTooltip();
  });

  // --- Selecting a plan --------------------------------------------------------------------------------
  const triggerInput = $("rx-trigger");
  const rationInput = $("rx-ration");
  triggerInput.max = triggers.length - 1;
  rationInput.max = rations.length - 1;

  function betterPlan(plan) {
    const candidates = front.filter(
      (p) =>
        p.mean_shortage <= plan.mean_shortage &&
        p.worst_month <= plan.worst_month &&
        (p.mean_shortage < plan.mean_shortage || p.worst_month < plan.worst_month)
    );
    const gain = (p) => (plan.mean_shortage - p.mean_shortage) / meanTop + (plan.worst_month - p.worst_month) / 100;
    return candidates.sort((a, b) => gain(b) - gain(a))[0] || null;
  }
  const compare = (value, base, digits) => (Math.abs(value - base) < 1e-9 ? "same as no rationing" : `no rationing: ${fmt(base, digits)}`);

  let suggestion = null;
  function select(plan) {
    current = plan;
    triggerInput.value = triggers.indexOf(plan.trigger);
    rationInput.value = rations.indexOf(plan.ration);
    $("rx-trigger-out").textContent = fmt(plan.trigger) + " Mm³";
    $("rx-ration-out").textContent = percent(plan.ration);
    $("rx-mean").textContent = fmt(plan.mean_shortage, 1);
    $("rx-worst").textContent = fmt(plan.worst_month);
    $("rx-years").textContent = plan.years_short;
    $("rx-mean-note").textContent = compare(plan.mean_shortage, reference.mean_shortage, 1);
    $("rx-worst-note").textContent = compare(plan.worst_month, reference.worst_month, 0);
    $("rx-years-note").textContent = compare(plan.years_short, reference.years_short, 0);

    suggestion = plan.unbeaten ? null : betterPlan(plan);
    $("rx-verdict-text").textContent = suggestion
      ? `This plan is beaten. Trigger ${fmt(suggestion.trigger)} Mm³ with ration ${percent(suggestion.ration)} leaves ${fmt(suggestion.mean_shortage, 1)} Mm³ per year undelivered and is ${fmt(suggestion.worst_month)} % short in its worst month: no worse on either count, better on at least one.`
      : "No plan on the grid beats this one: every plan with a milder worst month leaves more water undelivered.";
    $("rx-verdict-load").hidden = !suggestion;

    marker.setAttribute("cx", tradeoff.x(Math.min(plan.mean_shortage, meanTop)));
    marker.setAttribute("cy", tradeoff.y(plan.worst_month));
    marker.setAttribute("opacity", onChart(plan) ? 1 : 0.45);
    plan.shortage.forEach((value, i) => {
      shortageBars[i].setAttribute("y", shortage.y(value));
      shortageBars[i].setAttribute("height", shortage.y(0) - shortage.y(value));
    });
    storageLine.setAttribute("d", linePath(plan.storage));
    const rationing = plan.trigger > 0 && plan.ration < 1;
    triggerLine.setAttribute("visibility", rationing ? "visible" : "hidden");
    triggerLabel.setAttribute("visibility", rationing ? "visible" : "hidden");
    triggerLine.setAttribute("y1", storage.y(plan.trigger));
    triggerLine.setAttribute("y2", storage.y(plan.trigger));
    triggerLabel.setAttribute("y", storage.y(plan.trigger) - 4);
  }

  const fromSliders = () => select(byKey.get(keyOf(triggers[+triggerInput.value], rations[+rationInput.value])));
  triggerInput.addEventListener("input", fromSliders);
  rationInput.addEventListener("input", fromSliders);
  root.querySelectorAll(".rx-presets button").forEach((button) => {
    button.addEventListener("click", () => {
      const plan = byKey.get(keyOf(+button.dataset.trigger, +button.dataset.ration));
      if (plan) select(plan);
    });
  });
  $("rx-verdict-load").addEventListener("click", () => suggestion && select(suggestion));

  const last = data.window.start_year + data.window.years - 1;
  $("rx-window").textContent = `years ${data.window.start_year}–${last}, around the worst year`;
  function drawAll() {
    drawTradeoff();
    drawShortage();
    drawStorage();
    select(current);
  }
  current = byKey.get(keyOf(16, 0.8)) || reference;
  drawAll();
  let lastWidth = root.getBoundingClientRect().width;
  let pending = 0;
  new ResizeObserver(() => {
    const width = root.getBoundingClientRect().width;
    if (Math.abs(width - lastWidth) < 1) return;
    lastWidth = width;
    clearTimeout(pending);
    pending = setTimeout(drawAll, 80);
  }).observe(root);
})();

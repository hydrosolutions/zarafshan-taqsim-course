// The canvas of the TaqSim block editor. Plain JavaScript and SVG, no libraries.
// It owns the drawing (blocks, connections, numbers) and sends it to Python, which runs TaqSim and
// sends back hints, scores and figures. See widget.py for the other side.

const SVG = "http://www.w3.org/2000/svg";
const MIN_W = 300, ROW_H = 240, SANDBOX_H = 430; // the canvas is as wide as the page gives it; one unit is one pixel // canvas size in its own units: one unit is one pixel unless the page is narrower than MIN_W
const BW = 132, BH = 56; // block size
const SLOT_X = 14, GAP = 26, ROW_Y = 60, ROW_STEP = 90;

const clone = (value) => JSON.parse(JSON.stringify(value));

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function shape(tag, attrs) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  return node;
}

function render({ model, el }) {
  let graph = clone(model.get("graph") || { nodes: [], edges: [] });
  let rev = model.get("rev") || 0;
  let selected = null; // {node: id} or {edge: index}
  let gesture = null; // what the pointer is doing on the canvas
  let sticky = null; // id of the block whose dot was tapped: the next tapped block gets the connection
  let waiting = false;
  let codeOpen = false;
  let timer = null;
  let wasDone = false;
  let W = MIN_W; // the width the page gives the canvas; a wider drawing scrolls sideways

  const lesson = () => model.get("lesson") || { steps: [], blocks: {}, kinds: {}, ui: {} };
  const ui = (key) => lesson().ui[key] || key;
  const stepIndex = () => model.get("step") || 0;
  const step = () => lesson().steps[stepIndex()] || { palette: [], fields: {} };
  // What the page knows about a block: a named block of the guided steps, or any block of its kind
  const infoOf = (node) => {
    const named = lesson().blocks[node.id];
    const kind = (lesson().kinds || {})[node.kind] || {};
    return { label: named && !step().sandbox ? named.label : node.id, colour: (named || kind).colour || "#888", about: step().sandbox ? kind.about : (named || kind).about, params: { ...(kind.params || {}), ...((named || {}).params || {}) } };
  };
  const sandbox = () => Boolean(step().sandbox);
  // tall enough for the lowest block, with room below it to move blocks further down
  const width = () => Math.max(W, ...graph.nodes.map((node) => node.x + BW + SLOT_X));
  const height = () => Math.max(sandbox() ? SANDBOX_H : ROW_H, ...graph.nodes.map((node) => node.y + BH + (sandbox() ? 100 : 40)));
  const nodeOf = (id) => graph.nodes.find((node) => node.id === id);
  const state = () => model.get("state") || {};

  // --- frame ------------------------------------------------------------------------------------------------
  const root = make("div", "tq");
  const head = make("header", "tq-head");
  const main = make("div", "tq-main");
  const inspector = make("aside", "tq-inspector");
  const messages = make("div", "tq-messages");
  const nav = make("div", "tq-nav");
  const result = make("section", "tq-result");
  const svg = shape("svg", { viewBox: `0 0 ${MIN_W} ${ROW_H}`, class: "tq-canvas", tabindex: "0", role: "application" });
  const palette = make("div", "tq-palette");
  const frame = make("div", "tq-canvas-frame");
  frame.append(svg);
  // One grid: the settings sit beside everything else and stay in view while the results scroll
  main.append(palette, frame, messages, inspector, nav, result);
  root.append(head, main);
  el.append(root);

  const fit = () => {
    const page = Math.max(MIN_W, Math.floor(frame.clientWidth));
    if (page === W) return;
    W = page;
    graph.nodes.forEach(clampNode);
    drawCanvas();
  };
  const watcher = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(fit);
  if (watcher) watcher.observe(frame);

  // --- sending the drawing to Python ------------------------------------------------------------------------
  function send(delay) {
    waiting = true;
    drawMessages();
    drawNav();
    clearTimeout(timer);
    timer = setTimeout(() => {
      rev += 1;
      model.set("graph", clone(graph));
      model.set("rev", rev);
      model.save_changes();
    }, delay || 0);
  }

  function goTo(index) {
    rev += 1;
    waiting = true;
    selected = null;
    wasDone = false;
    model.set("step", index);
    model.set("graph", clone(graph));
    model.set("rev", rev);
    model.save_changes();
    drawAll();
  }

  // --- the drawing's rules ----------------------------------------------------------------------------------
  const kindOf = (id) => (nodeOf(id) || {}).kind;

  function connect(from, to) {
    if (from === to || kindOf(from) === "Sink" || kindOf(to) === "Source") return false;
    if (graph.edges.some((edge) => edge.source === to && edge.target === from)) return false;
    if (graph.edges.some((edge) => edge.source === from && edge.target === to)) return false;
    // every block but a Splitter sends its water to one place: a new connection replaces the old one
    if (kindOf(from) !== "Splitter") graph.edges = graph.edges.filter((edge) => edge.source !== from);
    graph.edges.push({ source: from, target: to });
    return true;
  }

  function removeSelected() {
    if (!selected) return;
    if (selected.node) {
      graph.nodes = graph.nodes.filter((node) => node.id !== selected.node);
      graph.edges = graph.edges.filter((edge) => edge.source !== selected.node && edge.target !== selected.node);
    } else if (selected.edge !== undefined) {
      graph.edges.splice(selected.edge, 1);
    }
    selected = null;
    drawAll();
    send();
  }

  // --- geometry ---------------------------------------------------------------------------------------------
  // On a page too narrow for two blocks side by side (a phone), blocks stack and water runs top to bottom
  const stacked = () => W < 2 * SLOT_X + 2 * BW + GAP;
  const portOut = () => (stacked() ? { x: BW / 2, y: BH } : { x: BW, y: BH / 2 }); // where on a block the water leaves
  const portIn = () => (stacked() ? { x: BW / 2, y: 0 } : { x: 0, y: BH / 2 });
  const outPort = (node) => ({ x: node.x + portOut().x, y: node.y + portOut().y });
  const inPort = (node) => ({ x: node.x + portIn().x, y: node.y + portIn().y });

  function curve(a, b) {
    if (stacked()) {
      const bend = Math.max(20, Math.abs(b.y - a.y) / 2);
      return { a, c1: { x: a.x, y: a.y + bend }, c2: { x: b.x, y: b.y - bend }, b };
    }
    const bend = Math.max(30, Math.abs(b.x - a.x) / 2);
    return { a, c1: { x: a.x + bend, y: a.y }, c2: { x: b.x - bend, y: b.y }, b };
  }

  const pathOf = (c) => `M${c.a.x},${c.a.y} C${c.c1.x},${c.c1.y} ${c.c2.x},${c.c2.y} ${c.b.x},${c.b.y}`;

  function pointsOn(c) {
    const points = [];
    for (let i = 0; i <= 16; i += 1) {
      const t = i / 16, u = 1 - t;
      points.push({
        x: u * u * u * c.a.x + 3 * u * u * t * c.c1.x + 3 * u * t * t * c.c2.x + t * t * t * c.b.x,
        y: u * u * u * c.a.y + 3 * u * u * t * c.c1.y + 3 * u * t * t * c.c2.y + t * t * t * c.b.y,
      });
    }
    return points;
  }

  function edgeCurve(edge) {
    const a = nodeOf(edge.source), b = nodeOf(edge.target);
    return a && b ? curve(outPort(a), inPort(b)) : null;
  }

  function nodeAt(point, except) {
    return [...graph.nodes].reverse().find(
      (node) => node.id !== except && point.x >= node.x - 6 && point.x <= node.x + BW + 6 && point.y >= node.y - 6 && point.y <= node.y + BH + 6,
    );
  }

  // the connection a block lies on, if any (used to insert a block into a connection)
  function edgeUnder(node) {
    return graph.edges.findIndex((edge) => {
      if (edge.source === node.id || edge.target === node.id) return false;
      const c = edgeCurve(edge);
      return c && pointsOn(c).some((p) => p.x > node.x && p.x < node.x + BW && p.y > node.y - 8 && p.y < node.y + BH + 8);
    });
  }

  function insertIntoEdge(node) {
    if (node.kind === "Source" || node.kind === "Sink") return false;
    if (graph.edges.some((edge) => edge.source === node.id || edge.target === node.id)) return false;
    const index = edgeUnder(node);
    if (index < 0) return false;
    const [edge] = graph.edges.splice(index, 1);
    graph.edges.push({ source: edge.source, target: node.id }, { source: node.id, target: edge.target });
    return true;
  }

  function toCanvas(event) {
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(svg.getScreenCTM().inverse());
  }

  const clampNode = (node) => {
    node.x = Math.round(Math.max(8, stacked() ? Math.min(W - BW - 8, node.x) : node.x));
    node.y = Math.round(Math.max(8, node.y));
  };

  // How many blocks fit side by side, and how far apart a row of `columns` blocks is spread
  const perRow = (columns) => Math.max(1, Math.min(columns, Math.floor((W - 2 * SLOT_X + GAP) / (BW + GAP))));
  const slotStep = (columns) => Math.min(230, (W - 2 * SLOT_X - BW) / Math.max(1, perRow(columns) - 1));
  // A tidy row is never broken (the canvas scrolls sideways instead), except on a phone, where blocks stack
  const rowStep = (columns) => Math.max(BW + GAP, Math.min(230, (W - 2 * SLOT_X - BW) / Math.max(1, columns - 1)));

  // Line the blocks up from left to right in the order the water passes them
  function tidy() {
    const depth = {};
    const depthOf = (id, seen) => {
      if (depth[id] !== undefined) return depth[id];
      if (seen.has(id)) return 0;
      seen.add(id);
      const before = graph.edges.filter((edge) => edge.target === id).map((edge) => depthOf(edge.source, seen) + 1);
      depth[id] = before.length ? Math.max(...before) : 0;
      return depth[id];
    };
    graph.nodes.forEach((node) => depthOf(node.id, new Set()));
    const columns = Math.max(...graph.nodes.map((node) => depth[node.id]), 0) + 1;
    const used = {};
    graph.nodes.forEach((node) => (used[depth[node.id]] = (used[depth[node.id]] || 0) + 1));
    const band = ROW_STEP * Math.max(1, ...Object.values(used)); // a chain too long for the page continues one band lower
    const placed = {};
    for (const node of graph.nodes) {
      const column = depth[node.id];
      placed[column] = (placed[column] || 0) + 1;
      node.x = stacked() ? SLOT_X : SLOT_X + rowStep(columns) * column;
      node.y = ROW_Y + (stacked() ? band * column : 0) + ROW_STEP * (placed[column] - 1);
      clampNode(node);
    }
  }

  // --- adding blocks ----------------------------------------------------------------------------------------
  // In the guided steps a palette entry is one named block; in the sandbox it is a kind, and each new
  // block gets the kind's name with a number (farm, farm_2, ...)
  function addBlock(entry, at) {
    let id = entry, kind;
    if (sandbox()) {
      kind = entry;
      const base = lesson().kinds[kind].name;
      id = base;
      for (let n = 2; nodeOf(id); n += 1) id = `${base}_${n}`;
    } else {
      if (nodeOf(id)) return;
      kind = lesson().blocks[id].kind;
    }
    const node = { id, kind, x: 0, y: 0, params: {} };
    node.params = clone(infoOf(node).params);
    if (at) {
      node.x = at.x - BW / 2;
      node.y = at.y - BH / 2;
      clampNode(node);
      graph.nodes.push(node);
      insertIntoEdge(node);
    } else {
      // its place in the row of this step's blocks; one row lower if something is already there
      const slots = step().palette.length, slot = Math.max(0, step().palette.indexOf(entry));
      node.x = SLOT_X + slotStep(slots) * (slot % perRow(slots));
      node.y = ROW_Y + ROW_STEP * Math.floor(slot / perRow(slots));
      clampNode(node);
      const crowded = () => graph.nodes.some((other) => other !== node && Math.abs(other.x - node.x) < BW + 10 && Math.abs(other.y - node.y) < BH + 10);
      graph.nodes.push(node);
      // the next free row below, if something is already there
      for (let tries = 0; tries < 8 && (crowded() || edgeUnder(node) >= 0); tries += 1) node.y += ROW_STEP;
    }
    selected = { node: id };
    drawAll();
    send();
  }

  // --- drawing the page -------------------------------------------------------------------------------------
  function drawHead() {
    const steps = lesson().steps;
    head.replaceChildren();
    const dots = make("div", "tq-dots");
    steps.forEach((_, index) => {
      const dot = make("span", "tq-dot" + (index === stepIndex() ? " is-now" : index < stepIndex() ? " is-past" : ""));
      dots.append(dot);
    });
    const count = make("span", "tq-count", ui("step_of").replace("{n}", stepIndex() + 1).replace("{total}", steps.length));
    const top = make("div", "tq-progress");
    const languages = make("span", "tq-languages");
    for (const language of lesson().languages || []) {
      const pick = make("button", "tq-language" + (language.code === lesson().lang ? " is-on" : ""), language.name);
      pick.type = "button";
      pick.addEventListener("click", () => {
        model.set("lang", language.code);
        model.save_changes();
      });
      languages.append(pick);
    }
    top.append(dots, count, make("span", "tq-spacer"), languages);
    const title = make("h2", "tq-title", step().title || "");
    const body = make("p", "tq-body");
    body.innerHTML = step().body || "";
    const task = make("p", "tq-task", step().task || "");
    head.append(top, title, body, task);
  }

  function drawPalette() {
    palette.replaceChildren(make("h3", "tq-label", ui("blocks")));
    const list = make("div", "tq-palette-list");
    for (const id of step().palette) {
      const kind = sandbox() ? id : lesson().blocks[id].kind;
      const info = sandbox() ? { label: id, colour: lesson().kinds[id].colour, about: lesson().kinds[id].about } : infoOf({ id, kind });
      const item = make("button", "tq-chip");
      item.type = "button";
      item.style.setProperty("--kind", info.colour);
      item.disabled = !sandbox() && Boolean(nodeOf(id));
      item.append(make("b", null, info.label), make("span", null, sandbox() ? lesson().kinds[id].name : kind));
      item.title = info.about || "";
      item.addEventListener("pointerdown", (event) => startPaletteDrag(event, id, item));
      list.append(item);
    }
    palette.append(list, make("p", "tq-small", ui("connect_hint")));
    fit();
  }

  function startPaletteDrag(event, id, item) {
    if (item.disabled) return;
    event.preventDefault();
    const start = { x: event.clientX, y: event.clientY };
    const ghost = item.cloneNode(true);
    ghost.classList.add("tq-ghost");
    let moved = false;
    const move = (e) => {
      if (!moved && Math.hypot(e.clientX - start.x, e.clientY - start.y) > 6) {
        moved = true;
        root.append(ghost);
      }
      ghost.style.left = `${e.clientX}px`;
      ghost.style.top = `${e.clientY}px`;
    };
    const up = (e) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      ghost.remove();
      const box = svg.getBoundingClientRect();
      const inside = e.clientX >= box.left && e.clientX <= box.right && e.clientY >= box.top && e.clientY <= box.bottom;
      if (!moved) addBlock(id);
      else if (inside) addBlock(id, toCanvas(e));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function drawCanvas() {
    svg.replaceChildren();
    const tall = height();
    const wide = width();
    svg.setAttribute("viewBox", `0 0 ${wide} ${tall}`);
    svg.setAttribute("width", wide);
    svg.setAttribute("height", tall);
    const defs = shape("defs");
    const marker = shape("marker", { id: "tq-arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" });
    marker.append(shape("path", { d: "M0,0 L10,5 L0,10 z", class: "tq-arrow" }));
    defs.append(marker);
    svg.append(defs);
    if (!graph.nodes.length) {
      const hint = shape("text", { x: W / 2, y: tall / 2, class: "tq-empty", "text-anchor": "middle" });
      hint.textContent = ui("blocks_hint");
      svg.append(hint);
    }
    graph.edges.forEach((edge, index) => {
      const c = edgeCurve(edge);
      if (!c) return;
      const chosen = selected && selected.edge === index;
      svg.append(shape("path", { d: pathOf(c), class: "tq-edge" + (chosen ? " is-selected" : ""), "marker-end": "url(#tq-arrow)" }));
      svg.append(shape("path", { d: pathOf(c), class: "tq-edge-hit", "data-edge": index }));
    });
    if (gesture && gesture.type === "connect" && gesture.to) {
      svg.append(shape("path", { d: pathOf(curve(outPort(nodeOf(gesture.from)), gesture.to)), class: "tq-edge is-draft" }));
    }
    for (const node of graph.nodes) {
      const info = infoOf(node);
      const group = shape("g", { transform: `translate(${node.x},${node.y})`, class: "tq-block" + (selected && selected.node === node.id ? " is-selected" : "") + (sticky && sticky !== node.id && node.kind !== "Source" ? " is-target" : ""), "data-node": node.id });
      group.style.setProperty("--kind", info.colour);
      group.append(shape("rect", { width: BW, height: BH, rx: 8, class: "tq-block-box" }));
      group.append(shape("rect", { width: 7, height: BH, rx: 3, class: "tq-block-stripe" }));
      const name = shape("text", { x: 18, y: 24, class: "tq-block-name" });
      name.textContent = info.label;
      // a long name is written smaller, so that it stays inside its block
      name.style.fontSize = `${Math.max(10, Math.min(15, Math.floor((BW - 26) / (0.64 * info.label.length))))}px`;
      const kind = shape("text", { x: 18, y: 42, class: "tq-block-kind" });
      kind.textContent = node.kind;
      group.append(name, kind);
      if (node.kind !== "Source") group.append(shape("circle", { cx: portIn().x, cy: portIn().y, r: 5, class: "tq-port-in" }));
      if (node.kind !== "Sink") {
        group.append(shape("circle", { cx: portOut().x, cy: portOut().y, r: 7, class: "tq-port" + (sticky === node.id ? " is-active" : "") }));
        group.append(shape("circle", { cx: portOut().x, cy: portOut().y, r: 16, class: "tq-port-hit", "data-port": node.id }));
      }
      svg.append(group);
    }
  }

  svg.addEventListener("pointerdown", (event) => {
    const target = event.target;
    const point = toCanvas(event);
    const port = target.getAttribute && target.getAttribute("data-port");
    const group = target.closest && target.closest("[data-node]");
    svg.focus({ preventScroll: true });
    if (port) {
      gesture = { type: "connect", from: port, start: point, to: null };
      sticky = null;
    } else if (group) {
      const id = group.getAttribute("data-node");
      if (sticky && sticky !== id) {
        if (connect(sticky, id)) send();
        sticky = null;
        selected = { node: id };
        drawAll();
        return;
      }
      const node = nodeOf(id);
      selected = { node: id };
      gesture = { type: "move", id, dx: point.x - node.x, dy: point.y - node.y, start: point, moved: false };
      drawInspector();
    } else if (target.getAttribute && target.getAttribute("data-edge") !== null) {
      selected = { edge: Number(target.getAttribute("data-edge")) };
      sticky = null;
      drawInspector();
    } else {
      selected = null;
      sticky = null;
      drawInspector();
    }
    if (gesture) {
      try {
        svg.setPointerCapture(event.pointerId); // keeps the drag alive when the pointer leaves the canvas
      } catch (error) {
        // some pointers cannot be captured; the drag then simply ends at the canvas edge
      }
    }
    drawCanvas();
    event.preventDefault();
  });

  svg.addEventListener("pointermove", (event) => {
    if (!gesture) return;
    const point = toCanvas(event);
    if (gesture.type === "move") {
      if (Math.hypot(point.x - gesture.start.x, point.y - gesture.start.y) > 3) gesture.moved = true;
      const node = nodeOf(gesture.id);
      node.x = point.x - gesture.dx;
      node.y = point.y - gesture.dy;
      clampNode(node);
    } else if (Math.hypot(point.x - gesture.start.x, point.y - gesture.start.y) > 6) {
      gesture.to = { x: point.x, y: point.y };
    }
    drawCanvas();
  });

  svg.addEventListener("pointerup", (event) => {
    if (!gesture) return;
    const point = toCanvas(event);
    const done = gesture;
    gesture = null;
    if (done.type === "connect") {
      const target = done.to ? nodeAt(point, done.from) : null;
      if (target) {
        if (connect(done.from, target.id)) send();
      } else if (!done.to) {
        sticky = done.from; // a tap on the dot: the next tapped block is the target
      }
    } else if (done.moved && insertIntoEdge(nodeOf(done.id))) {
      send();
    }
    drawCanvas();
  });

  svg.addEventListener("pointercancel", () => {
    gesture = null; // the browser took the touch over, to scroll the page
    drawCanvas();
  });

  svg.addEventListener("keydown", (event) => {
    if (event.key === "Delete" || event.key === "Backspace") {
      removeSelected();
      event.preventDefault();
    } else if (event.key === "Escape") {
      sticky = null;
      selected = null;
      drawAll();
    }
  });

  function format(field, value) {
    if (field.percent) return `${Math.round(value * 100)} %`;
    return `${Number(value).toLocaleString("en", { maximumFractionDigits: 2 })} ${field.unit || ""}`.trim();
  }

  function drawInspector() {
    inspector.replaceChildren(make("h3", "tq-label", ui("settings")));
    if (!selected) {
      inspector.append(make("p", "tq-small", ui("nothing_selected")));
      return;
    }
    const remove = make("button", "tq-button is-quiet", ui("remove"));
    remove.type = "button";
    remove.addEventListener("click", removeSelected);
    if (selected.edge !== undefined) {
      inspector.append(make("p", "tq-small", ui("edge_selected")), remove);
      return;
    }
    const node = nodeOf(selected.node);
    if (!node) return;
    const info = infoOf(node);
    const title = make("div", "tq-block-title");
    title.style.setProperty("--kind", info.colour);
    title.append(make("b", null, info.label), make("span", "tq-kind", node.kind));
    inspector.append(title, make("p", "tq-small", info.about || ""));
    const fields = step().fields[node.id] || step().fields[node.kind] || [];
    if (!fields.length) inspector.append(make("p", "tq-small", ui("no_settings")));
    const locks = (step().locks || {})[node.id] || {};
    Object.assign(node.params, locks); // e.g. the capacity, which limits how far the trigger slider goes
    let group = null;
    const held = []; // numbers this step does not let the learner change: listed in one line, not as sliders
    for (const field of fields) {
      const fixed = false;
      if (locks[field.key] !== undefined) {
        const value = locks[field.key];
        const option = (field.options || []).find((choice) => choice.value === String(value));
        held.push(`${field.label} ${field.type === "toggle" ? ui(value ? "on" : "off") : option ? option.label : format(field, value)}`);
        continue;
      }
      if (field.group && field.group !== group) inspector.append(make("h4", "tq-rule", ui(`group.${field.group}`)));
      group = field.group || group;
      if (node.params[field.key] === undefined) node.params[field.key] = info.params[field.key] !== undefined ? info.params[field.key] : field.min;
      const row = make(field.type === "choice" ? "div" : "label", "tq-field" + (fixed ? " is-fixed" : ""));
      const top = make("span", "tq-field-top");
      const help = make("span", "tq-help", (field.help || "") + (fixed ? ` (${ui("fixed")})` : ""));
      if (field.type === "toggle") {
        const input = make("input");
        Object.assign(input, { type: "checkbox", checked: Boolean(node.params[field.key]), disabled: fixed });
        const value = make("output", null, ui(input.checked ? "on" : "off"));
        input.addEventListener("change", () => {
          node.params[field.key] = input.checked;
          value.textContent = ui(input.checked ? "on" : "off");
          send();
        });
        const text = make("span", "tq-toggle");
        text.append(input, make("span", null, field.label));
        top.append(text, value);
        row.append(top, help);
      } else if (field.type === "choice") {
        top.append(make("span", null, field.label));
        const choices = make("span", "tq-choices");
        for (const option of field.options) {
          const button = make("button", "tq-choice" + (String(node.params[field.key]) === option.value ? " is-on" : ""), option.label);
          button.type = "button";
          button.disabled = fixed;
          button.addEventListener("click", () => {
            node.params[field.key] = option.value;
            drawInspector();
            send();
          });
          choices.append(button);
        }
        row.append(top, choices, help);
      } else {
        const max = field.max_from ? Math.min(field.max, Number(node.params[field.max_from])) : field.max;
        if (node.params[field.key] > max) node.params[field.key] = max;
        const value = make("output", null, format(field, node.params[field.key]));
        top.append(make("span", null, field.label), value);
        const input = make("input");
        Object.assign(input, { type: "range", min: field.min, max, step: field.step, value: node.params[field.key], disabled: fixed });
        input.addEventListener("input", () => {
          node.params[field.key] = Number(input.value);
          value.textContent = format(field, node.params[field.key]);
          for (const other of fields) {
            if (other.max_from === field.key && node.params[other.key] > node.params[field.key]) node.params[other.key] = node.params[field.key];
          }
          send(350);
        });
        input.addEventListener("change", drawInspector); // refresh the sliders whose range depends on this one
        row.append(top, input, help);
      }
      inspector.append(row);
    }
    if (held.length) inspector.append(make("p", "tq-held", `${ui("fixed_list")} ${held.join(" · ")}`));
    inspector.append(remove);
  }

  function drawMessages() {
    messages.replaceChildren();
    if (waiting) {
      messages.append(make("p", "tq-message is-working", ui("working")));
      return;
    }
    for (const message of state().messages || []) messages.append(make("p", `tq-message is-${message.level}`, message.text));
  }

  function drawNav() {
    nav.replaceChildren();
    const last = stepIndex() >= lesson().steps.length - 1;
    const back = make("button", "tq-button", ui("back"));
    back.disabled = stepIndex() === 0;
    back.addEventListener("click", () => goTo(stepIndex() - 1));
    const solve = make("button", "tq-button is-quiet", ui(sandbox() ? "example" : "show_me"));
    solve.addEventListener("click", () => {
      waiting = true;
      selected = null;
      drawMessages();
      rev += 1;
      model.set("request", `solve:${Date.now()}`);
      model.set("rev", rev);
      model.save_changes();
    });
    const clear = make("button", "tq-button is-quiet", ui("start_over"));
    clear.addEventListener("click", () => {
      graph = { nodes: [], edges: [] };
      selected = null;
      sticky = null;
      drawAll();
      send();
    });
    const next = make("button", "tq-button is-primary", ui("next"));
    next.disabled = last || waiting || !state().done;
    next.addEventListener("click", () => goTo(stepIndex() + 1));
    for (const button of [back, solve, clear, next]) button.type = "button";
    nav.append(back, solve, clear);
    if (sandbox()) {
      const save = make("button", "tq-button is-quiet", ui("save"));
      save.type = "button";
      save.addEventListener("click", () => {
        const file = new Blob([JSON.stringify({ taqsim_blocks: 1, ...graph }, null, 1)], { type: "application/json" });
        const link = make("a");
        link.href = URL.createObjectURL(file);
        link.download = "my_taqsim_model.json";
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      });
      const picker = make("input");
      Object.assign(picker, { type: "file", accept: ".json,application/json", hidden: true });
      picker.addEventListener("change", async () => {
        try {
          const loaded = JSON.parse(await picker.files[0].text());
          const kinds = lesson().kinds;
          const fine = loaded.taqsim_blocks && Array.isArray(loaded.nodes) && Array.isArray(loaded.edges) && loaded.nodes.every((node) => typeof node.id === "string" && kinds[node.kind]);
          if (!fine) throw new Error("not a model");
          const ids = new Set(loaded.nodes.map((node) => node.id));
          graph = {
            nodes: loaded.nodes.map((node) => ({ id: node.id, kind: node.kind, x: Number(node.x) || 0, y: Number(node.y) || 0, params: node.params || {} })),
            edges: loaded.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)).map((edge) => ({ source: edge.source, target: edge.target })),
          };
          graph.nodes.forEach(clampNode);
          selected = null;
          drawAll();
          send();
        } catch (error) {
          messages.replaceChildren(make("p", "tq-message is-error", ui("load_failed")));
        }
        picker.value = "";
      });
      const load = make("button", "tq-button is-quiet", ui("load"));
      load.type = "button";
      load.addEventListener("click", () => picker.click());
      nav.append(save, load, picker);
    }
    nav.append(make("span", "tq-spacer"));
    if (last && !sandbox() && state().done) nav.append(make("span", "tq-small", ui("last_step")));
    if (!last) nav.append(next);
  }

  const tip = make("div", "tq-tip-box");
  tip.hidden = true;
  root.append(tip);

  function showTip(event) {
    const text = event.target.getAttribute && event.target.getAttribute("data-tip");
    if (!text) {
      tip.hidden = true;
      return;
    }
    tip.textContent = text;
    tip.hidden = false;
    // beside the pointer, so that it works for a small dot and for a tall bar alike
    const frame = root.getBoundingClientRect();
    const left = Math.min(Math.max(8, event.clientX - frame.left + 14), frame.width - tip.offsetWidth - 8);
    tip.style.left = `${left}px`;
    tip.style.top = `${event.clientY - frame.top - tip.offsetHeight - 12}px`;
  }

  function drawResult() {
    tip.hidden = true;
    const now = state();
    result.replaceChildren();
    if (!(now.figures || []).length) return;
    result.append(make("h3", "tq-label", ui("result")));
    const cards = make("div", "tq-cards");
    for (const card of now.cards || []) {
      const box = make("div", "tq-card");
      if (card.quiet) box.classList.add("is-quiet");
      if (card.tag) box.append(make("span", "tq-card-tag", card.tag));
      box.append(make("span", "tq-card-label", card.label), make("b", "tq-card-value", card.value), make("span", "tq-card-sub", card.sub || ""));
      cards.append(box);
    }
    const note = make("p", "tq-note");
    note.innerHTML = now.note || "";
    result.append(cards, note);
    for (const figure of now.figures) {
      // a figure may bring its own explanation, which is shown right above it
      if (figure.caption) {
        const caption = make("p", "tq-caption");
        caption.innerHTML = figure.caption;
        result.append(caption);
      }
      const holder = make("div", "tq-figure");
      holder.innerHTML = figure.svg || figure;
      result.append(holder);
      // points that carry a text show it when the pointer is on them (or, on a phone, when they are tapped)
      holder.addEventListener("pointerover", (event) => showTip(event));
      holder.addEventListener("pointermove", (event) => {
        if (!tip.hidden && event.pointerType === "mouse") showTip(event);
      });
      holder.addEventListener("pointerdown", (event) => showTip(event));
      holder.addEventListener("pointerout", (event) => {
        if (event.pointerType === "mouse") tip.hidden = true;
      });
    }
    if (now.table) {
      const grid = make("table", "tq-table");
      const headRow = make("tr");
      for (const column of now.table.columns) headRow.append(make("th", null, column));
      grid.append(headRow);
      for (const cells of now.table.rows) {
        const line = make("tr");
        for (const cell of cells) line.append(make("td", null, cell));
        grid.append(line);
      }
      result.append(grid);
    }
    if (now.code) {
      const toggle = make("button", "tq-button is-quiet", ui(codeOpen ? "hide_code" : "show_code"));
      toggle.type = "button";
      toggle.addEventListener("click", () => {
        codeOpen = !codeOpen;
        drawResult();
      });
      result.append(toggle);
      if (codeOpen) result.append(make("p", "tq-small", ui("code_about")), make("pre", "tq-code", now.code));
    }
  }

  // Open the settings of the block this step is about, unless the learner has chosen something else
  function focus() {
    const wanted = step().focus;
    if (!selected && wanted && nodeOf(wanted)) selected = { node: wanted };
  }

  function drawAll() {
    fit();
    focus();
    drawHead();
    drawPalette();
    drawCanvas();
    drawInspector();
    drawMessages();
    drawNav();
    drawResult();
  }

  // --- answers from Python ----------------------------------------------------------------------------------
  const onState = () => {
    if ((state().rev || 0) < rev) return; // an answer to an older drawing
    waiting = false;
    if (state().done && !wasDone && !gesture && !sandbox()) {
      tidy(); // the step's network is complete: show it in a clean row
      drawCanvas();
    }
    if (!selected && step().focus && nodeOf(step().focus)) {
      focus();
      drawCanvas();
      drawInspector();
    }
    wasDone = Boolean(state().done);
    drawMessages();
    drawNav();
    drawResult();
  };
  const onGraph = () => {
    const theirs = model.get("graph") || { nodes: [], edges: [] };
    if (JSON.stringify(theirs) === JSON.stringify(graph)) return;
    graph = clone(theirs); // Python built the step's network
    tidy();
    selected = null;
    drawAll();
  };
  model.on("change:state", onState);
  model.on("change:graph", onGraph);
  model.on("change:lesson", drawAll);
  model.on("change:step", drawAll);
  drawAll();

  return () => {
    clearTimeout(timer);
    if (watcher) watcher.disconnect();
    model.off("change:state", onState);
    model.off("change:graph", onGraph);
    model.off("change:lesson", drawAll);
    model.off("change:step", drawAll);
  };
}

export default { render };

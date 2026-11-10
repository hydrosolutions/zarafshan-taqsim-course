// The canvas of the TaqSim block editor. Plain JavaScript and SVG, no libraries.
// It owns the drawing (blocks, connections, numbers) and sends it to Python, which runs TaqSim and
// sends back hints, scores and figures. See widget.py for the other side.

const SVG = "http://www.w3.org/2000/svg";
const MIN_W = 640, H = 240; // canvas size in its own units: one unit is one pixel unless the page is narrower than MIN_W
const BW = 132, BH = 56; // block size
const SLOT_X = 20, ROW_Y = 60, ROW_STEP = 90;

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
  let W = MIN_W; // grows with the page, so that blocks keep their size

  const lesson = () => model.get("lesson") || { steps: [], blocks: {}, ui: {} };
  const ui = (key) => lesson().ui[key] || key;
  const stepIndex = () => model.get("step") || 0;
  const step = () => lesson().steps[stepIndex()] || { palette: [], fields: {} };
  const block = (id) => lesson().blocks[id] || { kind: "?", label: id, colour: "#888", params: {} };
  const nodeOf = (id) => graph.nodes.find((node) => node.id === id);
  const state = () => model.get("state") || {};

  // --- frame ------------------------------------------------------------------------------------------------
  const root = make("div", "tq");
  const head = make("header", "tq-head");
  const main = make("div", "tq-main");
  const stage = make("div", "tq-stage");
  const inspector = make("aside", "tq-inspector");
  const messages = make("div", "tq-messages");
  const nav = make("div", "tq-nav");
  const result = make("section", "tq-result");
  const svg = shape("svg", { viewBox: `0 0 ${W} ${H}`, class: "tq-canvas", tabindex: "0", role: "application" });
  const palette = make("div", "tq-palette");
  const frame = make("div", "tq-canvas-frame");
  frame.append(svg);
  stage.append(palette, frame, messages);
  main.append(stage, inspector);
  root.append(head, main, nav, result);
  el.append(root);

  const fit = () => {
    const width = Math.max(MIN_W, Math.floor(frame.clientWidth));
    if (width === W) return;
    W = width;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
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
    // these blocks send their water to one place: a new connection replaces the old one
    graph.edges = graph.edges.filter((edge) => edge.source !== from);
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
  const outPort = (node) => ({ x: node.x + BW, y: node.y + BH / 2 });
  const inPort = (node) => ({ x: node.x, y: node.y + BH / 2 });

  function curve(a, b) {
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
    node.x = Math.round(Math.min(W - BW - 8, Math.max(8, node.x)));
    node.y = Math.round(Math.min(H - BH - 8, Math.max(8, node.y)));
  };

  const slotStep = (columns) => Math.min(230, (W - 2 * SLOT_X - BW) / Math.max(1, columns - 1));

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
    for (const node of graph.nodes) {
      const column = depth[node.id];
      used[column] = (used[column] || 0) + 1;
      node.x = SLOT_X + slotStep(columns) * column;
      node.y = ROW_Y + ROW_STEP * (used[column] - 1);
      clampNode(node);
    }
  }

  // --- adding blocks ----------------------------------------------------------------------------------------
  function addBlock(id, at) {
    if (nodeOf(id)) return;
    const info = block(id);
    const node = { id, kind: info.kind, x: 0, y: 0, params: clone(info.params || {}) };
    if (at) {
      node.x = at.x - BW / 2;
      node.y = at.y - BH / 2;
      clampNode(node);
      graph.nodes.push(node);
      insertIntoEdge(node);
    } else {
      // its place in the row of this step's blocks; one row lower if something is already there
      node.x = SLOT_X + slotStep(step().palette.length) * Math.max(0, step().palette.indexOf(id));
      node.y = ROW_Y;
      clampNode(node);
      const crowded = graph.nodes.some((other) => Math.abs(other.x - node.x) < BW + 10 && Math.abs(other.y - node.y) < BH + 10);
      graph.nodes.push(node);
      if (crowded || edgeUnder(node) >= 0) node.y = ROW_Y + ROW_STEP;
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
    top.append(dots, count);
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
      const info = block(id);
      const item = make("button", "tq-chip");
      item.type = "button";
      item.style.setProperty("--kind", info.colour);
      item.disabled = Boolean(nodeOf(id));
      item.append(make("b", null, info.label), make("span", null, info.kind));
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
    const defs = shape("defs");
    const marker = shape("marker", { id: "tq-arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" });
    marker.append(shape("path", { d: "M0,0 L10,5 L0,10 z", class: "tq-arrow" }));
    defs.append(marker);
    svg.append(defs);
    if (!graph.nodes.length) {
      const hint = shape("text", { x: W / 2, y: H / 2, class: "tq-empty", "text-anchor": "middle" });
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
      const info = block(node.id);
      const group = shape("g", { transform: `translate(${node.x},${node.y})`, class: "tq-block" + (selected && selected.node === node.id ? " is-selected" : "") + (sticky && sticky !== node.id && node.kind !== "Source" ? " is-target" : ""), "data-node": node.id });
      group.style.setProperty("--kind", info.colour);
      group.append(shape("rect", { width: BW, height: BH, rx: 8, class: "tq-block-box" }));
      group.append(shape("rect", { width: 7, height: BH, rx: 3, class: "tq-block-stripe" }));
      const name = shape("text", { x: 18, y: 24, class: "tq-block-name" });
      name.textContent = info.label;
      const kind = shape("text", { x: 18, y: 42, class: "tq-block-kind" });
      kind.textContent = node.kind;
      group.append(name, kind);
      if (node.kind !== "Source") group.append(shape("circle", { cx: 0, cy: BH / 2, r: 5, class: "tq-port-in" }));
      if (node.kind !== "Sink") {
        group.append(shape("circle", { cx: BW, cy: BH / 2, r: 7, class: "tq-port" + (sticky === node.id ? " is-active" : "") }));
        group.append(shape("circle", { cx: BW, cy: BH / 2, r: 16, class: "tq-port-hit", "data-port": node.id }));
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
    const info = block(node.id);
    const title = make("div", "tq-block-title");
    title.style.setProperty("--kind", info.colour);
    title.append(make("b", null, info.label), make("span", "tq-kind", node.kind));
    inspector.append(title, make("p", "tq-small", info.about || ""));
    const fields = step().fields[node.id] || [];
    if (!fields.length) inspector.append(make("p", "tq-small", ui("no_settings")));
    let ruleStarted = false;
    for (const field of fields) {
      if (field.group === "rule" && !ruleStarted) {
        ruleStarted = true;
        inspector.append(make("h4", "tq-rule", ui("rule")));
      }
      const max = field.max_from ? Math.min(field.max, Number(node.params[field.max_from])) : field.max;
      if (node.params[field.key] === undefined) node.params[field.key] = field.min;
      if (node.params[field.key] > max) node.params[field.key] = max;
      const row = make("label", "tq-field");
      const top = make("span", "tq-field-top");
      const value = make("output", null, format(field, node.params[field.key]));
      top.append(make("span", null, field.label), value);
      const input = make("input");
      Object.assign(input, { type: "range", min: field.min, max, step: field.step, value: node.params[field.key] });
      input.addEventListener("input", () => {
        node.params[field.key] = Number(input.value);
        value.textContent = format(field, node.params[field.key]);
        for (const other of fields) {
          if (other.max_from === field.key && node.params[other.key] > node.params[field.key]) node.params[other.key] = node.params[field.key];
        }
        send(350);
      });
      input.addEventListener("change", drawInspector); // refresh the sliders whose range depends on this one
      row.append(top, input, make("span", "tq-help", field.help || ""));
      inspector.append(row);
    }
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
    const solve = make("button", "tq-button is-quiet", ui("show_me"));
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
    nav.append(back, solve, clear, make("span", "tq-spacer"));
    if (last && state().done) nav.append(make("span", "tq-small", ui("last_step")));
    nav.append(next);
  }

  function drawResult() {
    const now = state();
    result.replaceChildren();
    if (!(now.figures || []).length) return;
    result.append(make("h3", "tq-label", ui("result")));
    const cards = make("div", "tq-cards");
    for (const card of now.cards || []) {
      const box = make("div", "tq-card");
      box.append(make("span", "tq-card-label", card.label), make("b", "tq-card-value", card.value), make("span", "tq-card-sub", card.sub || ""));
      cards.append(box);
    }
    const note = make("p", "tq-note");
    note.innerHTML = now.note || "";
    result.append(cards, note);
    for (const figure of now.figures) {
      const holder = make("div", "tq-figure");
      holder.innerHTML = figure;
      result.append(holder);
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

  function drawAll() {
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
    if (state().done && !wasDone && !gesture) {
      tidy(); // the step's network is complete: show it in a clean row
      drawCanvas();
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

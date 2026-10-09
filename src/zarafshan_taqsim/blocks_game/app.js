(() => {
  "use strict";
  const D = JSON.parse(document.getElementById("blocks-data").textContent);
  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const KEY = { lang: "blocksGame.lang", theme: "blocksGame.theme" };
  const html = document.documentElement;
  let LANG = html.getAttribute("data-lang") === "ru" ? "ru" : "en";
  const L = (en, ru) => (LANG === "ru" ? ru : en);

  // ---------- texts ----------
  // English is the default; Russian covers the whole page. TaqSim's block kinds (Source, Reach, ...) and the code
  // of the rule cards stay in English, as in the other games of the course.
  const RU = {
    "Click a block for its card. Hover an edge or a block.": "Нажмите на блок, чтобы открыть его карточку. Наведите курсор на ребро или блок.",
    "Arrow width: the water carried along that edge this month. Dashed: nothing flows.": "Толщина стрелки — вода, которую несёт это ребро в этом месяце. Пунктир — ничего не течёт.",
    "Play": "Пуск", "Pause": "Пауза", "Reset": "Исходные значения",
    "The five knobs": "Пять рычагов",
    "Each knob is one number inside one block's rule. The sliders snap to the values TaqSim has run.": "Каждый рычаг — одно число внутри правила одного блока. Ползунки встают на значения, которые прогнал TaqSim.",
    "Scroll sideways to see the whole system →": "Прокрутите вбок, чтобы увидеть всю систему →",
  };
  const TITLE = { en: "TaqSim block by block", ru: "TaqSim блок за блоком" };
  const THEME = { en: { auto: "Theme: auto", light: "Theme: light", dark: "Theme: dark" }, ru: { auto: "Тема: авто", light: "Тема: светлая", dark: "Тема: тёмная" } };
  const MONTH_SHORT = { en: D.months, ru: ["Окт", "Ноя", "Дек", "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен"] };
  const MONTH_LONG = {
    en: ["October", "November", "December", "January", "February", "March", "April", "May", "June", "July", "August", "September"],
    ru: ["Октябрь", "Ноябрь", "Декабрь", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь"],
  };
  const NAME = {
    river: ["River", "Река"], canyon: ["Canyon", "Ущелье"], headworks: ["Headworks", "Гидроузел"], canal: ["Canal", "Канал"],
    reservoir: ["Reservoir", "Водохранилище"], farm: ["Farm", "Поле"], drain: ["Drain", "Коллектор"], turbine: ["Turbine", "Турбина"],
    river_end: ["River end", "Низовье"],
  };
  const ANALOGY_RU = {
    Source: "родник: вода появляется из списка чисел",
    Reach: "коридор: воде нужно время, чтобы пройти, и часть её утекает",
    Splitter: "развилка с регулировщиком: столько туда, остальное сюда",
    Storage: "ванна с задвижкой: наполняется, переливается, когда полна, теряет часть на испарение, выпускает столько, сколько велит задвижка",
    Demand: "потребитель: часть воды использует, остальное возвращает",
    PassThrough: "ворота заданной ширины: что помещается, проходит, остальное сбрасывается",
    Sink: "море: вода приходит, и рассказ кончается",
  };
  const QUESTION = {
    Source: ["How much comes in each month? (a list)", "Сколько приходит каждый месяц? (список)"],
    Reach: ["How long does it take, how much leaks? (routing, loss)", "Сколько времени уходит на проход, сколько утекает? (маршрутизация, потери)"],
    Splitter: ["How much goes which way? (split rule)", "Сколько идёт в какую сторону? (правило деления)"],
    Storage: ["How much to let out? What is lost? (release rule, loss rule)", "Сколько выпустить? Что теряется? (правило попуска, правило потерь)"],
    Demand: ["How much is needed, used up, delivered? (requirement, consumption, efficiency)", "Сколько нужно, сколько используется, сколько доставлено? (потребность, потребление, КПД)"],
    PassThrough: ["How much fits through? (capacity)", "Сколько проходит? (пропускная способность)"],
    Sink: ["Nothing to decide.", "Решать нечего."],
  };
  const KNOB = {
    canal_share: { title: ["Headworks rule: share into the canal", "Правило гидроузла: доля в канал"], show: (v) => `${Math.round(v * 100)} %` },
    canal_seepage: { title: ["Canal rule: seepage", "Правило канала: фильтрация"], show: (v) => `${Math.round(v * 100)} %` },
    release_cap: { title: ["Reservoir rule: valve maximum, Mm³ per month", "Правило водохранилища: максимум задвижки, млн м³ в месяц"], show: (v) => `${v}` },
    turbine_capacity: { title: ["Turbine: gate capacity, Mm³ per month", "Турбина: пропускная способность затвора, млн м³ в месяц"], show: (v) => `${v}` },
    consumption: { title: ["Farm: share used up by the crops", "Поле: доля, которую потребляют растения"], show: (v) => `${Math.round(v * 100)} %` },
  };
  const K = D.constants;
  const DOES = {
    river: [
      "Each month the river puts the next number of its inflow list into the network: the median monthly flow at Ravatkhoja, 2010–2023. It has nothing to decide; the list is the rule. All of it goes on into the canyon.",
      "Каждый месяц река подаёт в сеть очередное число из списка притока: медианный месячный сток у Раватходжи за 2010–2023 годы. Решать ей нечего; список и есть правило. Всё это идёт дальше, в ущелье.",
    ],
    canyon: [
      "The canyon is a corridor one month long: what enters this month comes out next month, unchanged. The water still inside at the end of the month is shown on the block. Its loss rule is set to zero, so nothing leaks here.",
      "Ущелье — коридор длиной в один месяц: что вошло в этом месяце, выходит в следующем, без изменений. Вода, которая ещё внутри в конце месяца, показана на блоке. Правило потерь здесь равно нулю, так что ничего не утекает.",
    ],
    headworks: [
      "The headworks receives the canyon's water and splits it by one number: a fixed share goes into the canal, the rest goes on down the river to the turbine. It stores nothing and loses nothing: in equals the two outs.",
      "Гидроузел получает воду из ущелья и делит её по одному числу: фиксированная доля идёт в канал, остальное — вниз по реке, к турбине. Он ничего не хранит и не теряет: приход равен сумме двух расходов.",
    ],
    canal: [
      "The canal is a corridor with no lag (water passes within the month) but with a leak: a share of the flow seeps into the ground. What is left arrives at the reservoir.",
      "Канал — коридор без задержки (вода проходит за месяц), но с утечкой: доля потока фильтруется в грунт. Остаток приходит в водохранилище.",
    ],
    reservoir: [
      `The reservoir keeps up to ${K.capacity} Mm³; below ${K.dead_storage} (dead storage) the valve cannot reach. Each month it first takes in the canal's water, overflowing what does not fit; ${Math.round(K.evaporation_share * 100)} % of its content evaporates; then the valve releases what the farm needs this month, at most the valve maximum, and never more than is above the dead storage. Released water and overflow both go on to the farm.`,
      `Водохранилище вмещает до ${K.capacity} млн м³; ниже ${K.dead_storage} (мёртвый объём) задвижка не достаёт. Каждый месяц оно сначала принимает воду канала, переливая то, что не помещается; ${Math.round(K.evaporation_share * 100)} % содержимого испаряется; затем задвижка выпускает столько, сколько нужно полю в этом месяце, но не больше максимума задвижки и не больше того, что выше мёртвого объёма. Попуск и перелив вместе идут на поле.`,
    ],
    farm: [
      `The farm asks for its monthly need at its gate. Of what arrives, ${Math.round(K.efficiency * 100)} % reaches the plants and ${Math.round(100 - K.efficiency * 100)} % is recorded as lost. The plants use up the consumption share of what they need and got; the rest drains back. The shortfall is the need minus what reached the plants.`,
      `Поле запрашивает месячную потребность у своего затвора. Из того, что приходит, ${Math.round(K.efficiency * 100)} % доходит до растений, а ${Math.round(100 - K.efficiency * 100)} % записывается как потери. Растения потребляют свою долю от того, что им нужно и что они получили; остальное стекает обратно. Дефицит — это потребность минус то, что дошло до растений.`,
    ],
    turbine: [
      "The turbine is a gate of fixed width: what fits goes through to the river's end; what is above the capacity spills. TaqSim records that spill and does not follow it: it leaves the books.",
      "Турбина — ворота заданной ширины: что помещается, проходит к низовью; что выше пропускной способности, сбрасывается. TaqSim записывает этот сброс и дальше не следит: вода выбывает из учёта.",
    ],
    drain: [
      "The drain takes the farm's return flow. Water arrives and the story ends: a Sink has no rule.",
      "Коллектор принимает возвратный сток поля. Вода приходит, и рассказ кончается: у Sink правила нет.",
    ],
    river_end: [
      "The river's end takes what came through the turbine. Water arrives and the story ends: a Sink has no rule.",
      "Низовье принимает то, что прошло через турбину. Вода приходит, и рассказ кончается: у Sink правила нет.",
    ],
  };
  const KNOB_OF = { headworks: "canal_share", canal: "canal_seepage", reservoir: "release_cap", turbine: "turbine_capacity", farm: "consumption" };

  // ---------- data ----------
  const COL = {};
  D.columns.forEach((c, i) => { COL[c] = i; });
  const RUNS = new Map(D.runs.map((r) => [r.knobs.join("|"), r]));
  const MAXFLOW = Math.max(...K.inflow);
  function cols(run) {
    if (!run.cols) {
      run.cols = {};
      for (const c of D.columns) run.cols[c] = run.data.slice(COL[c] * 12, COL[c] * 12 + 12).map((v) => v / D.scale);
    }
    return run.cols;
  }
  let knobs = D.default_knobs.slice();
  let month = 0;
  let selected = "reservoir";
  let timer = null;
  function current() { return cols(RUNS.get(knobs.join("|"))); }

  const nf0 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fmtEdge = (v) => (Math.abs(v) < 10 ? nf1.format(v) : nf0.format(v));
  const fmt1 = (v) => nf1.format(v);
  const fmt0 = (v) => nf0.format(v);
  const signed = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf0.format(Math.abs(v));
  const name = (b) => NAME[b][LANG === "ru" ? 1 : 0];

  // ---------- text measuring (labels fit their boxes) ----------
  const ctx = document.createElement("canvas").getContext("2d");
  const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  function textWidth(text, weight, size) { ctx.font = `${weight} ${size}px ${FONT}`; return ctx.measureText(text).width; }
  function fitSize(text, weight, maxWidth, start, min) {
    let s = start;
    while (s > min && textWidth(text, weight, s) > maxWidth) s -= 0.5;
    return s;
  }

  // ---------- the stage ----------
  // Geometry from the module's LAYOUT: boxes of fixed size, the unit chosen so that neighbouring boxes keep a gap
  // wide enough for an edge label; the viewBox follows the extent of the layout.
  const BW = 116, BH = 56, GAP = 54, UY = 118, MARGIN = 8, SUB = 26;
  const XS = Object.values(D.layout).map(([x]) => x), YS = Object.values(D.layout).map(([, y]) => y);
  const XMIN = Math.min(...XS), XMAX = Math.max(...XS), YMIN = Math.min(...YS), YMAX = Math.max(...YS);
  const steps = [...new Set(XS)].sort((a, b) => a - b).map((x, i, all) => (i ? x - all[i - 1] : Infinity));
  const UX = (BW + GAP) / Math.min(...steps);
  const X0 = MARGIN + BW / 2, Y0 = MARGIN + 22 + BH / 2;
  const WIDTH = Math.round(2 * MARGIN + BW + (XMAX - XMIN) * UX), HEIGHT = Math.round(Y0 + (YMAX - YMIN) * UY + BH / 2 + SUB);
  const px = (x) => X0 + (x - XMIN) * UX;
  const py = (y) => Y0 + (YMAX - y) * UY;
  const el = (tag, attrs, parent) => {
    const node = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  };
  const stage = $("stage");
  const EDGE_EL = {};
  const BLOCK_EL = {};

  function edgeGeometry(a, b) {
    const [xa, ya] = D.layout[a];
    const [xb, yb] = D.layout[b];
    const x0 = px(xa) + BW / 2, y0 = py(ya), x1 = px(xb) - BW / 2 - 1, y1 = py(yb);
    const mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
    const d = y0 === y1 ? `M${x0} ${y0} L${x1} ${y1}` : `M${x0} ${y0} C${mx} ${y0} ${mx} ${y1} ${x1} ${y1}`;
    return { d, lx: mx, ly: y0 === y1 ? y0 - 15 : my };
  }

  function buildStage() {
    stage.textContent = "";
    stage.setAttribute("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);
    const defs = el("defs", {}, stage);
    for (const [id, cls] of [["arrow", "head"], ["arrow-lit", "head lit"]]) {
      const m = el("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 11, markerHeight: 11, markerUnits: "userSpaceOnUse", orient: "auto" }, defs);
      el("path", { d: "M0 0 L10 5 L0 10 z", class: cls }, m);
    }
    for (const [a, b] of D.edges) {
      const id = `${a}_to_${b}`;
      const g = el("g", { class: "edge", "data-edge": id }, stage);
      const geo = edgeGeometry(a, b);
      const line = el("path", { class: "line", d: geo.d, "marker-end": "url(#arrow)" }, g);
      el("path", { class: "hit", d: geo.d }, g);
      const tag = el("rect", { class: "tag", height: 18 }, g);
      const text = el("text", { x: geo.lx, y: geo.ly + 4, "text-anchor": "middle", style: "font-size:12px" }, g);
      EDGE_EL[id] = { g, line, tag, text, geo, a, b };
      g.addEventListener("mouseenter", () => { BLOCK_EL[a].g.classList.add("lit"); BLOCK_EL[b].g.classList.add("lit"); });
      g.addEventListener("mouseleave", () => { BLOCK_EL[a].g.classList.remove("lit"); BLOCK_EL[b].g.classList.remove("lit"); });
    }
    for (const [block, kind] of Object.entries(D.block_kind)) {
      const [x, y] = D.layout[block];
      const cx = px(x), cy = py(y);
      const colour = D.kind_colour[kind];
      const g = el("g", { class: `blk ${kind.toLowerCase()}`, "data-block": block, tabindex: 0, role: "button" }, stage);
      el("rect", { class: "box", x: cx - BW / 2, y: cy - BH / 2, width: BW, height: BH, rx: 10, style: `fill: color-mix(in srgb, ${colour} var(--tint), var(--surface)); stroke: ${colour}` }, g);
      const label = el("text", { class: "name", x: cx, y: cy - 4, "text-anchor": "middle" }, g);
      el("text", { class: "kind", x: cx, y: cy + 11, "text-anchor": "middle", style: "font-size:11px" }, g).textContent = kind;
      let gaugeBg = null, gaugeFill = null;
      if (kind === "Storage") {
        gaugeBg = el("rect", { class: "gauge-bg", x: cx - BW / 2 + 10, y: cy + 16, width: BW - 20, height: 7, rx: 2 }, g);
        gaugeFill = el("rect", { class: "gauge-fill", x: cx - BW / 2 + 10, y: cy + 16, width: 0, height: 7, rx: 2 }, g);
      }
      const sub = el("text", { class: "sub", x: cx, y: cy + BH / 2 + 17, "text-anchor": "middle", style: "font-size:12.5px" }, g);
      BLOCK_EL[block] = { g, label, sub, gaugeFill, kind };
      const edgesOf = D.edges.filter(([a, b]) => a === block || b === block).map(([a, b]) => `${a}_to_${b}`);
      g.addEventListener("mouseenter", () => edgesOf.forEach((e) => EDGE_EL[e].g.classList.add("lit")));
      g.addEventListener("mouseleave", () => edgesOf.forEach((e) => EDGE_EL[e].g.classList.remove("lit")));
      const pick = () => { selected = block; render(); };
      g.addEventListener("click", pick);
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); } });
    }
    for (const block of Object.keys(BLOCK_EL)) {
      const size = fitSize(name(block), 650, BW - 12, 15, 10);
      BLOCK_EL[block].label.setAttribute("style", `font-size:${size}px`);
      BLOCK_EL[block].label.textContent = name(block);
    }
  }

  function subOf(block, c, m) {
    if (block === "reservoir") return { text: L(`holds ${fmt0(c.storage_level[m])} of ${fmt0(K.capacity)}`, `в запасе ${fmt0(c.storage_level[m])} из ${fmt0(K.capacity)}`), cls: "" };
    if (block === "farm") {
      const d = c["farm.deficit"][m];
      return d < 0.05 ? { text: L("all it needs", "всё, что нужно"), cls: "good" } : { text: L(`short by ${fmtEdge(d)}`, `не хватает ${fmtEdge(d)}`), cls: "bad" };
    }
    if (block === "turbine") {
      const s = c["turbine.spilled"][m];
      return s > 0.05 ? { text: L(`spills ${fmtEdge(s)}`, `сброс ${fmtEdge(s)}`), cls: "bad" } : { text: "", cls: "" };
    }
    if (block === "canyon") return { text: L(`inside ${fmtEdge(c.transit_level[m])}`, `внутри ${fmtEdge(c.transit_level[m])}`), cls: "" };
    return { text: "", cls: "" };
  }

  function renderStage() {
    const c = current();
    for (const [id, e] of Object.entries(EDGE_EL)) {
      const flow = c[id][month];
      e.line.setAttribute("stroke-width", (1.5 + 9 * flow / MAXFLOW).toFixed(2));
      e.line.classList.toggle("dry", flow < 0.05);
      const label = fmtEdge(flow);
      e.text.textContent = label;
      const w = textWidth(label, 500, 12) + 10;
      e.tag.setAttribute("x", e.geo.lx - w / 2);
      e.tag.setAttribute("y", e.geo.ly - 9);
      e.tag.setAttribute("width", w);
    }
    for (const [block, b] of Object.entries(BLOCK_EL)) {
      const s = subOf(block, c, month);
      b.sub.textContent = s.text;
      b.sub.setAttribute("class", `sub ${s.cls}`.trim());
      b.g.classList.toggle("selected", block === selected);
      if (b.gaugeFill) b.gaugeFill.setAttribute("width", ((BW - 20) * Math.min(1, c.storage_level[month] / K.capacity)).toFixed(1));
    }
    $("stage-title").textContent = L(`${MONTH_LONG.en[month]}: water on every edge, Mm³`, `${MONTH_LONG.ru[month]}: вода на каждом ребре, млн м³`);
  }

  // ---------- the block card ----------
  function h(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) { if (k === "class") node.className = v; else if (k === "text") node.textContent = v; else node.setAttribute(k, v); }
    for (const ch of children) if (ch !== null && ch !== undefined) node.append(ch);
    return node;
  }
  function cardNumbers(block, c, m) {
    const need = K.farm_need[m];
    const before = (level, change) => (m > 0 ? level[m - 1] : level[0] - change);
    switch (block) {
      case "river": {
        const v = K.inflow[m];
        return { rows: [[L("generated", "образовано"), v], [L("out, to the canyon", "уходит в ущелье"), c.river_to_canyon[m]]], lhs: [[L("generated", "образовано"), v]], rhs: [[L("out", "уходит"), c.river_to_canyon[m]]] };
      }
      case "canyon": {
        const inn = c.river_to_canyon[m], out = c.canyon_to_headworks[m], inside = c.transit_level[m], was = before(c.transit_level, inn - out);
        return {
          rows: [[L("in, from the river", "приходит из реки"), inn], [L("out, to the headworks (last month's water)", "уходит к гидроузлу (вода прошлого месяца)"), out], [L("inside at month end", "внутри в конце месяца"), inside]],
          lhs: [[L("in", "приход"), inn], [L("inside before", "внутри до"), was]], rhs: [[L("out", "расход"), out], [L("inside after", "внутри после"), inside]],
        };
      }
      case "headworks": {
        const inn = c.canyon_to_headworks[m], canal = c.headworks_to_canal[m], turb = c.headworks_to_turbine[m];
        return {
          rows: [[L("in, from the canyon", "приходит из ущелья"), inn], [L(`to the canal (share ${Math.round(knobs[0] * 100)} %)`, `в канал (доля ${Math.round(knobs[0] * 100)} %)`), canal], [L("to the turbine, the rest", "к турбине, остальное"), turb]],
          lhs: [[L("in", "приход"), inn]], rhs: [[L("to the canal", "в канал"), canal], [L("to the turbine", "к турбине"), turb]],
        };
      }
      case "canal": {
        const inn = c.headworks_to_canal[m], lost = c["canal.seepage"][m], out = c.canal_to_reservoir[m];
        return {
          rows: [[L("in, from the headworks", "приходит от гидроузла"), inn], [L(`lost to seepage (${Math.round(knobs[1] * 100)} %)`, `потеряно на фильтрацию (${Math.round(knobs[1] * 100)} %)`), lost], [L("out, to the reservoir", "уходит в водохранилище"), out]],
          lhs: [[L("in", "приход"), inn]], rhs: [[L("lost", "потеряно"), lost], [L("out", "расход"), out]],
        };
      }
      case "reservoir": {
        const inn = c.canal_to_reservoir[m], rel = c["reservoir.released"][m], over = c["reservoir.spilled"][m], evap = c["reservoir.evaporated"][m], level = c.storage_level[m];
        const was = before(c.storage_level, inn - evap - rel - over);
        return {
          rows: [
            [L("in, from the canal", "приходит из канала"), inn], [L("stored before", "в запасе до"), was],
            [L(`released by the valve (need ${fmt1(need)}, max ${knobs[2]})`, `попуск через задвижку (нужно ${fmt1(need)}, максимум ${knobs[2]})`), rel],
            [L("overflowed (full), goes on to the farm", "перелив (полно), идёт дальше на поле"), over], [L("evaporated", "испарилось"), evap],
            [L("stored after", "в запасе после"), level], [L("out, to the farm", "уходит на поле"), c.reservoir_to_farm[m]],
          ],
          lhs: [[L("in", "приход"), inn], [L("stored before", "в запасе до"), was]],
          rhs: [[L("released", "попуск"), rel], [L("overflow", "перелив"), over], [L("evaporated", "испарилось"), evap], [L("stored after", "в запасе после"), level]],
        };
      }
      case "farm": {
        const inn = c.reservoir_to_farm[m], lost = c["farm.inefficiency"][m], used = c["farm.consumed"][m], back = c.farm_to_drain[m], short = c["farm.deficit"][m];
        return {
          rows: [[L("need", "потребность"), need], [L("in, from the reservoir", "приходит из водохранилища"), inn], [L(`lost between gate and plants (${Math.round(100 - K.efficiency * 100)} %)`, `потеряно между затвором и растениями (${Math.round(100 - K.efficiency * 100)} %)`), lost], [L(`used up by the crops (${Math.round(knobs[4] * 100)} %)`, `потреблено растениями (${Math.round(knobs[4] * 100)} %)`), used], [L("drained back", "стекло обратно"), back], [L("short (need − what reached the plants)", "дефицит (потребность − дошло до растений)"), short]],
          lhs: [[L("in", "приход"), inn]], rhs: [[L("used up", "потреблено"), used], [L("lost", "потеряно"), lost], [L("drained back", "стекло обратно"), back]],
        };
      }
      case "turbine": {
        const inn = c.headworks_to_turbine[m], thr = c.turbine_to_river_end[m], left = c["turbine.spilled"][m];
        return {
          rows: [[L("in, from the headworks", "приходит от гидроузла"), inn], [L(`through the gate (capacity ${knobs[3]})`, `через затвор (пропускная способность ${knobs[3]})`), thr], [L("left the model (spilled past the gate)", "выбыло из модели (сброс мимо затвора)"), left]],
          lhs: [[L("in", "приход"), inn]], rhs: [[L("through", "прошло"), thr], [L("left the model", "выбыло"), left]],
        };
      }
      case "drain": {
        const inn = c.farm_to_drain[m];
        return { rows: [[L("in, from the farm", "приходит с поля"), inn]], lhs: [[L("in", "приход"), inn]], rhs: [[L("taken out of the system", "выведено из системы"), inn]] };
      }
      default: {
        const inn = c.turbine_to_river_end[m];
        return { rows: [[L("in, from the turbine", "приходит от турбины"), inn]], lhs: [[L("in", "приход"), inn]], rhs: [[L("taken out of the system", "выведено из системы"), inn]] };
      }
    }
  }
  function ruleCard(block) {
    const src = D.rule_source[block];
    const knob = KNOB_OF[block];
    if (!knob) return src;
    const i = D.knob_names.indexOf(knob);
    return `${src}\n# ${L("this run", "в этом прогоне")}: ${knob} = ${knobs[i]}`;
  }
  function renderCard() {
    const c = current();
    const kind = D.block_kind[selected];
    const colour = D.kind_colour[kind];
    const n = cardNumbers(selected, c, month);
    const sum = (pairs) => pairs.reduce((s, [, v]) => s + v, 0);
    const closes = Math.abs(sum(n.lhs) - sum(n.rhs)) <= 0.15 + 0.05 * n.rhs.length;
    const side = (pairs) => pairs.map(([label, v]) => `${label} ${fmt1(v)}`).join(" + ");
    const card = $("card");
    card.textContent = "";
    card.append(
      h("header", {}, h("h2", { text: name(selected) }), h("span", { class: `kind-tag ${kind}`, text: kind, style: `background:${colour}` })),
      h("p", { class: "analogy", text: LANG === "ru" ? ANALOGY_RU[kind] : D.analogy[kind] }),
      h("p", { class: "prose", text: DOES[selected][LANG === "ru" ? 1 : 0] }),
      h("h3", { text: L("Rule card", "Карточка правила") + ": " + D.rule_name[selected] }),
      h("pre", {}, h("code", { text: ruleCard(selected) })),
      h("h3", { text: L(`${MONTH_LONG.en[month]}'s numbers, Mm³`, `Числа за ${MONTH_LONG.ru[month].toLowerCase()}, млн м³`) }),
      h("table", { class: "nums" }, h("tbody", {}, ...n.rows.map(([label, v]) => h("tr", {}, h("td", { text: label }), h("td", { text: fmt1(v) }))))),
      h("div", { class: `balance ${closes ? "closes" : ""}`, text: `${side(n.lhs)} = ${side(n.rhs)}${closes ? L(" — adds up", " — сходится") : ""}` }),
    );
  }

  // ---------- the year strip ----------
  function renderYear() {
    const c = current();
    const total = (a) => a.reduce((s, v) => s + v, 0);
    const river = total(K.inflow);
    const sinks = total(c.farm_to_drain) + total(c.turbine_to_river_end);
    const consumed = total(c["farm.consumed"]);
    const lost = total(c["canal.seepage"]) + total(c["reservoir.evaporated"]) + total(c["farm.inefficiency"]);
    const left = total(c["turbine.spilled"]);
    const level0 = c.storage_level[0] - (c.canal_to_reservoir[0] - c["reservoir.evaporated"][0] - c["reservoir.released"][0] - c["reservoir.spilled"][0]);
    const transit0 = c.transit_level[0] - (c.river_to_canyon[0] - c.canyon_to_headworks[0]);
    const stored = (c.storage_level[11] - level0) + (c.transit_level[11] - transit0);
    const sum = sinks + consumed + lost + left + stored;
    const ok = Math.abs(sum - river) <= 1;
    const parts = [
      [L("to the two sinks", "в два стока"), fmt0(sinks)], [L("used by the crops", "потреблено растениями"), fmt0(consumed)],
      [L("lost (seepage, evaporation, farm)", "потеряно (фильтрация, испарение, поле)"), fmt0(lost)],
      [L("left the model at the turbine's gate", "выбыло из модели у затвора турбины"), fmt0(left)], [L("change in storage", "изменение запаса"), signed(stored)],
    ];
    const year = $("year");
    year.textContent = "";
    year.append(
      h("h2", { text: L(`This year the river brought ${fmt0(river)} Mm³. It went:`, `За год река принесла ${fmt0(river)} млн м³. Они ушли:`) }),
      h("div", { class: "parts" }, ...parts.map(([label, v]) => h("span", { class: "part" }, h("span", { text: label }), h("b", { class: "num", text: v })))),
      h("p", { class: `sum ${ok ? "" : "bad"}`, text: L(`Sum ${fmt0(sum)} of ${fmt0(river)}: ${ok ? "adds up." : "does not add up."}`, `Сумма ${fmt0(sum)} из ${fmt0(river)}: ${ok ? "сходится." : "не сходится."}`) }),
    );
  }

  // ---------- controls ----------
  function buildMonths() {
    const box = $("months");
    box.textContent = "";
    MONTH_SHORT[LANG].forEach((label, i) => {
      const b = h("button", { type: "button", text: label, "aria-pressed": String(i === month) });
      b.addEventListener("click", () => { stop(); month = i; render(); });
      box.append(b);
    });
  }
  function buildKnobs() {
    const box = $("knobs");
    box.textContent = "";
    D.knob_names.forEach((knobName, i) => {
      const values = D.knob_values[knobName];
      const spec = KNOB[knobName];
      const out = h("output", { class: "num", text: spec.show(knobs[i]) });
      const input = h("input", { type: "range", min: 0, max: values.length - 1, step: 1, value: values.indexOf(knobs[i]), "aria-label": spec.title[LANG === "ru" ? 1 : 0] });
      input.addEventListener("input", () => { knobs[i] = values[Number(input.value)]; out.textContent = spec.show(knobs[i]); render(); });
      box.append(h("div", { class: "knob" }, h("label", {}, h("b", { text: spec.title[LANG === "ru" ? 1 : 0] }), out), input, h("div", { class: "ticks" }, ...values.map((v) => h("span", { text: spec.show(v) })))));
    });
  }
  function buildKinds() {
    for (const lang of ["en", "ru"]) {
      const box = $(`kinds-${lang}`);
      const ru = lang === "ru";
      const head = h("tr", {}, ...(ru ? ["Вид", "Бытовая картинка", "Вопрос, на который отвечает правило"] : ["Kind", "The everyday picture", "The question its rule answers"]).map((x) => h("th", { text: x })));
      const rows = Object.keys(D.analogy).map((kind) => h("tr", {}, h("td", {}, h("span", { class: `kind-tag ${kind}`, text: kind, style: `background:${D.kind_colour[kind]}` })), h("td", { text: ru ? ANALOGY_RU[kind] : D.analogy[kind] }), h("td", { text: QUESTION[kind][ru ? 1 : 0] })));
      box.textContent = "";
      box.append(h("table", { class: "kinds" }, h("thead", {}, head), h("tbody", {}, ...rows)));
    }
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; } }
  $("play").addEventListener("click", () => {
    if (timer) { stop(); render(); return; }
    timer = setInterval(() => { month = (month + 1) % 12; render(); }, 900);
    render();
  });
  $("reset").addEventListener("click", () => { knobs = D.default_knobs.slice(); buildKnobs(); render(); });

  function render() {
    for (const [i, b] of Array.from($("months").children).entries()) b.setAttribute("aria-pressed", String(i === month));
    $("play").textContent = timer ? L("Pause", "Пауза") : L("Play", "Пуск");
    renderStage();
    renderCard();
    renderYear();
  }

  // ---------- language and theme ----------
  let mode = html.getAttribute("data-theme") || "auto";
  function applyLanguage() {
    html.setAttribute("lang", LANG);
    html.setAttribute("data-lang", LANG);
    document.title = TITLE[LANG];
    for (const node of document.querySelectorAll("[data-i18n]")) {
      if (!node.dataset.en) node.dataset.en = node.textContent.trim();
      node.textContent = LANG === "ru" ? RU[node.dataset.en] || node.dataset.en : node.dataset.en;
    }
    for (const node of document.querySelectorAll("[data-lang]")) if (!node.closest("#lang-buttons")) node.hidden = node.dataset.lang !== LANG;
    for (const b of $("lang-buttons").children) b.setAttribute("aria-pressed", String(b.dataset.lang === LANG));
    $("theme-toggle").textContent = THEME[LANG][mode];
  }
  for (const b of $("lang-buttons").children) {
    b.addEventListener("click", () => {
      if (b.dataset.lang === LANG) return;
      LANG = b.dataset.lang;
      try { localStorage.setItem(KEY.lang, LANG); } catch (e) { /* no storage */ }
      applyLanguage();
      buildStage();
      buildMonths();
      buildKnobs();
      render();
    });
  }
  $("theme-toggle").addEventListener("click", () => {
    mode = mode === "auto" ? "light" : mode === "light" ? "dark" : "auto";
    if (mode === "auto") html.removeAttribute("data-theme"); else html.setAttribute("data-theme", mode);
    try { localStorage.setItem(KEY.theme, mode); } catch (e) { /* no storage */ }
    $("theme-toggle").textContent = THEME[LANG][mode];
  });

  applyLanguage();
  buildKinds();
  buildStage();
  buildMonths();
  buildKnobs();
  render();
})();

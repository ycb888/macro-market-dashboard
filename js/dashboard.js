(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const stockKeys = ["sp500", "nasdaq", "shanghai", "hang_seng", "nikkei", "eurostoxx"];
  const riskKeys = ["vix", "ust2y", "real10y", "yield_curve", "hy_oas", "brent", "wti", "dollar", "breadth"];
  const macroKeys = ["cpi", "core_pce", "unemployment", "claims", "nfci", "us_cli", "china_cli", "japan_cli"];
  const directions = { bullish: "利好", bearish: "利空", mixed: "分化", watch: "待确认" };
  const dateTime = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const number = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });
  const signed = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2, signDisplay: "exceptZero" });
  const timeRange = byId("trend-window");
  const indicator = byId("trend-indicator");
  const canvas = byId("trend-chart");
  const statuses = byId("dashboard-status");
  const empty = byId("trend-empty");
  const marketData = window.marketData;
  let series = {};

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function marketLink(label, url) {
    const link = el("a", "", label);
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }

  function dateLabel(day, frequency) {
    return frequency === "monthly" ? day.slice(0, 7) : day;
  }

  function time(day, frequency) {
    const node = el("time", "", dateLabel(day, frequency));
    node.dateTime = dateLabel(day, frequency);
    return node;
  }

  function formatValue(value, kind) {
    const unit = { rate: "%", growth: "%", oil: " 美元/桶", people: " 人" }[kind] || "";
    return number.format(value) + unit;
  }

  function deltaNode(current, previous, kind) {
    if (previous === undefined || (["index", "oil"].includes(kind) && previous === 0)) return el("span");
    const change = current - previous;
    const percent = kind === "index" || kind === "oil";
    const value = percent ? change / Math.abs(previous) * 100 : kind === "rate" ? change * 100 : change;
    const suffix = percent ? "%" : { rate: " bp", growth: " 个百分点", points: " 点", people: " 人" }[kind] || "";
    const node = el("span", "delta", signed.format(value) + suffix);
    if (value) node.dataset.sign = value > 0 ? "up" : "down";
    return node;
  }

  function stockCard(key) {
    const item = series[key];
    const button = el("button", "stock-card");
    button.type = "button";
    button.dataset.key = key;
    button.setAttribute("aria-pressed", "false");
    const [day, value] = item.history.at(-1);
    const detail = el("span", "stock-footer");
    detail.append(deltaNode(value, item.history.at(-2)?.[1], item.kind), time(day, item.frequency));
    button.append(el("span", "stock-label", item.label), el("strong", "stock-value", formatValue(value, item.kind)), detail);
    button.addEventListener("click", () => {
      indicator.value = key;
      renderTrend();
      byId("trend-heading").scrollIntoView({ block: "nearest" });
    });
    return button;
  }

  function riskRow(key) {
    const item = series[key];
    const [day, value] = item.history.at(-1);
    const label = el("div");
    label.append(marketLink(item.label, item.url), time(day, item.frequency));
    const figure = el("div");
    figure.append(el("strong", "", formatValue(value, item.kind)), deltaNode(value, item.history.at(-2)?.[1], item.kind));
    const row = el("div", "risk-row");
    row.append(label, figure);
    return row;
  }

  function macroRow(key) {
    const item = series[key];
    const [day, value] = item.history.at(-1);
    const row = el("tr");
    const label = el("td");
    const date = el("td");
    label.append(marketLink(item.label, item.url));
    date.append(time(day, item.frequency));
    row.append(label, el("td", "", formatValue(value, item.kind)), date);
    return row;
  }

  function draw(points, item) {
    const ctx = canvas.getContext("2d");
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!ctx || !width || !height) return;

    const dpi = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpi);
    canvas.height = Math.round(height * dpi);
    ctx.setTransform(dpi, 0, 0, dpi, 0, 0);
    ctx.font = "12px system-ui";
    const values = points.map(([, value]) => value);
    const low = Math.min(...values);
    const high = Math.max(...values);
    const padding = (high - low) * .09 || Math.max(.01, Math.abs(low) * .02);
    const min = low - padding;
    const max = high + padding;
    const left = Math.max(ctx.measureText(number.format(high)).width, ctx.measureText(number.format(low)).width) + 14;
    const right = width - 14;
    const top = 21;
    const bottom = height - 30;
    const first = Date.parse(points[0][0]);
    const last = Date.parse(points.at(-1)[0]);
    const x = (day) => left + (Date.parse(day) - first) / (last - first || 1) * (right - left);
    const y = (value) => bottom - (value - min) / (max - min) * (bottom - top);

    ctx.textBaseline = "middle";
    for (let index = 0; index <= 4; index += 1) {
      const value = min + (max - min) * index / 4;
      const axis = y(value);
      ctx.beginPath();
      ctx.strokeStyle = "#30435d";
      ctx.lineWidth = 1;
      ctx.moveTo(left, axis);
      ctx.lineTo(right, axis);
      ctx.stroke();
      ctx.fillStyle = "#a8b7cb";
      ctx.fillText(number.format(value), 0, axis);
    }

    ctx.beginPath();
    for (const [index, [day, value]] of points.entries()) {
      if (index) ctx.lineTo(x(day), y(value)); else ctx.moveTo(x(day), y(value));
    }
    ctx.lineTo(right, bottom);
    ctx.lineTo(left, bottom);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
    gradient.addColorStop(0, "rgba(105, 173, 250, .3)");
    gradient.addColorStop(1, "rgba(105, 173, 250, .02)");
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    for (const [index, [day, value]] of points.entries()) {
      if (index) ctx.lineTo(x(day), y(value)); else ctx.moveTo(x(day), y(value));
    }
    ctx.strokeStyle = "#80bdfb";
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();

    const startLabel = dateLabel(points[0][0], item.frequency);
    const endLabel = dateLabel(points.at(-1)[0], item.frequency);
    ctx.fillStyle = "#a8b7cb";
    ctx.fillText(startLabel, left, bottom + 15);
    ctx.fillText(endLabel, right - ctx.measureText(endLabel).width, bottom + 15);
  }

  function renderTrend() {
    const key = indicator.value;
    const item = series[key];
    if (!item) return;
    const [lastDate, lastValue] = item.history.at(-1);
    const cutoff = Date.parse(lastDate) - Number(timeRange.value) * 86_400_000;
    const points = item.history.filter(([day]) => Date.parse(day) >= cutoff);
    byId("trend-overview").replaceChildren(
      el("strong", "", formatValue(lastValue, item.kind)),
      deltaNode(lastValue, item.history.at(-2)?.[1], item.kind),
    );

    const enough = points.length >= 2;
    canvas.hidden = !enough;
    empty.hidden = enough;
    byId("trend-caption").textContent = `${item.source} · 最新观测 ${dateLabel(lastDate, item.frequency)}`;
    canvas.setAttribute("aria-label", `${item.label}，最新观测 ${dateLabel(lastDate, item.frequency)}，${formatValue(lastValue, item.kind)}`);
    for (const card of document.querySelectorAll(".stock-card")) {
      card.setAttribute("aria-pressed", String(card.dataset.key === key));
    }
    if (enough) draw(points, item);
  }

  async function loadIndicators() {
    try {
      const { data, bundled } = await marketData.load("market_dashboard.json", 18 * 3_600_000, marketData.validDashboard);
      series = Object.fromEntries(Object.entries(data.series).filter(([, item]) => item.history?.length));
      const age = Date.now() - Date.parse(data.collected_at);
      statuses.textContent = `指标采集于 ${dateTime.format(new Date(data.collected_at))} 北京时间${age > 36 * 3_600_000 ? " · 采集延迟" : bundled ? " · 随站快照" : ""}`;
      indicator.replaceChildren(...[...stockKeys, ...riskKeys, ...macroKeys].filter((key) => series[key])
        .map((key) => {
          const option = el("option", "", series[key].label);
          option.value = key;
          return option;
        }));
      byId("stocks").replaceChildren(...stockKeys.filter((key) => series[key]).map(stockCard));
      byId("risk-list").replaceChildren(...riskKeys.filter((key) => series[key]).map(riskRow));
      byId("macro-rows").replaceChildren(...macroKeys.filter((key) => series[key]).map(macroRow));
      if (indicator.options.length > 0) {
        indicator.selectedIndex = 0;
        renderTrend();
      }
    } catch {
      statuses.textContent = "暂时无法读取指标";
    }
  }

  function headline(item) {
    const article = el("article");
    const meta = el("div", "event-meta");
    const tag = el("span", "tag", directions[item.impact.direction]);
    tag.dataset.direction = item.impact.direction;
    meta.append(tag, el("span", "event-source", item.source), el("time", "", dateTime.format(new Date(item.published_at))));
    const title = el("h3");
    title.append(marketLink(item.title, item.url));
    article.append(meta, title);
    return article;
  }

  async function loadHeadlines() {
    const headlines = byId("headline-list");
    try {
      const { data } = await marketData.load("market_news.json", 2 * 3_600_000, marketData.validNews);
      const cutoff = Date.now() - 7 * 86_400_000;
      const recent = data.items.filter((item) => item?.url?.startsWith("https://") && directions[item?.impact?.direction]
        && Date.parse(item.published_at) >= cutoff).slice(0, 4);
      headlines.replaceChildren(...(recent.length ? recent.map(headline) : [el("p", "empty", "最近 7 天暂无可显示资讯。")]));
    } catch {
      headlines.replaceChildren(el("p", "empty", "暂时无法读取新闻。"));
    }
  }

  indicator.addEventListener("change", renderTrend);
  timeRange.addEventListener("change", renderTrend);
  new ResizeObserver(renderTrend).observe(canvas);
  loadIndicators();
  loadHeadlines();
})();

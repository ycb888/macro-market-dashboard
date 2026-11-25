(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const hour = 3_600_000;
  const pageSize = 20;
  const categories = {
    markets: "股市与资金", macro: "宏观与央行", geopolitics: "政策与地缘", corporate: "公司与行业",
  };
  const directions = { bullish: "利好", bearish: "利空", mixed: "分化", watch: "待确认" };
  const dateTime = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hourCycle: "h23",
  });
  const number = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });
  const signed = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2, signDisplay: "exceptZero" });

  const controls = ["period", "category", "direction", "publisher"].map(byId);
  const refresh = byId("refresh-news");
  const feedStatus = byId("feed-status");
  const events = byId("events");
  const streamStatus = byId("stream-status");
  const itemCount = byId("item-count");
  const more = byId("more-events");
  const template = byId("event-template");

  let snapshot = null;
  let retainedFrom = "";
  let visibleLimit = pageSize;
  let loading = false;

  function safeArticle(item) {
    if (!item || typeof item.url !== "string" || typeof item.title !== "string" || !item.impact
        || !Object.hasOwn(directions, item.impact.direction) || !Object.hasOwn(categories, item.category)) return false;
    try {
      return new URL(item.url).protocol === "https:";
    } catch {
      return false;
    }
  }

  function createEvent(item) {
    const row = template.content.cloneNode(true);
    const set = (selector, value) => { row.querySelector(selector).textContent = value; };
    const time = row.querySelector("time");
    time.dateTime = item.published_at;
    time.textContent = dateTime.format(new Date(item.published_at));
    set(".event-source", item.source);
    set(".event-category", categories[item.category]);

    const link = row.querySelector(".event-link");
    link.href = item.url;
    link.textContent = item.title;

    const facts = row.querySelector(".event-facts-text");
    facts.textContent = item.facts_zh || item.facts || item.title;
    facts.lang = item.facts_zh ? "zh-CN" : "en";
    set(".event-facts-label", item.facts_basis && item.facts_basis !== "headline" ? "内容摘要" : "内容摘要 · 依据标题");

    const impact = item.impact;
    const tag = row.querySelector(".tag");
    tag.dataset.direction = impact.direction;
    tag.textContent = directions[impact.direction];
    set(".event-market", impact.market);
    set(".event-basis", impact.basis);
    set(".event-summary", impact.summary);
    set(".event-watch", `关注 ${impact.watch}`);
    return row;
  }

  function renderEvents() {
    if (!snapshot) return;
    const [hours, category, direction, publisher] = controls.map((control) => control.value);
    const now = Date.now();
    const cutoff = now - Number(hours) * hour;
    const items = snapshot.items.filter((item) => {
      if (!safeArticle(item)) return false;
      const published = Date.parse(item.published_at);
      const groupMatches = publisher === "official"
        ? !["bloomberg", "bbc"].includes(item.group)
        : !publisher || item.group === publisher;
      return published >= cutoff && published <= now
        && (!category || item.category === category)
        && (!direction || item.impact.direction === direction)
        && groupMatches;
    }).sort((a, b) => b.published_at.localeCompare(a.published_at));

    const limit = Math.min(visibleLimit, items.length);
    events.replaceChildren(...items.slice(0, limit).map(createEvent));
    itemCount.textContent = items.length ? `${limit} / ${items.length} 条 · 北京时间` : "";
    streamStatus.hidden = items.length > 0;
    streamStatus.textContent = now - Date.parse(snapshot.collected_at) > 168 * hour
      ? "快照已超过 7 天。可以从右侧链接查看来源的最新发布。"
      : "这个时间范围内没有匹配事件。可以延长时间范围或清除筛选。";
    more.hidden = items.length <= visibleLimit;
  }

  function renderFeedStatus() {
    const age = Date.now() - Date.parse(snapshot.collected_at);
    const stamp = dateTime.format(new Date(snapshot.collected_at));
    const qualifiers = [retainedFrom, age > 2 * hour ? "采集延迟" : ""].filter(Boolean);
    feedStatus.textContent = `采集于 ${stamp} 北京时间${qualifiers.length ? ` · ${qualifiers.join(" · ")}` : ""}`;

    const feeds = Object.values(snapshot.feeds);
    for (const label of document.querySelectorAll("[data-feed-state]")) {
      const group = feeds.filter((feed) => feed?.group === label.dataset.feedState);
      const working = group.filter((feed) => feed.status === "ok").length;
      const latest = group.map((feed) => feed.latest_published_at).filter(Boolean).sort().at(-1);
      const warning = age > 2 * hour || working < group.length || !group.length;
      label.dataset.state = warning ? "warning" : "ok";
      if (!working) label.textContent = "暂不可用";
      else if (working < group.length) label.textContent = "部分可用";
      else label.textContent = age > 2 * hour ? "采集延迟" : "已同步";
      label.title = latest ? `来源最新发布 ${dateTime.format(new Date(latest))} 北京时间` : "";
    }
  }

  async function loadNews() {
    if (loading) return;
    loading = true;
    refresh.disabled = true;
    try {
      const { data: candidate, bundled } = await window.marketData.load(
        "market_news.json", 2 * hour, window.marketData.validNews
      );
      if (!snapshot || Date.parse(candidate.collected_at) >= Date.parse(snapshot.collected_at)) {
        snapshot = candidate;
        retainedFrom = bundled ? "随站快照" : "";
      } else {
        retainedFrom = "保留上次结果";
      }
    } catch {
      if (snapshot) {
        retainedFrom = "保留上次结果";
      } else {
        feedStatus.textContent = "暂时无法读取快照";
        streamStatus.textContent = "当前无法加载新闻。可重试，或打开消息源查看最新发布。";
      }
    } finally {
      refresh.disabled = false;
      loading = false;
    }
    if (snapshot) {
      renderFeedStatus();
      renderEvents();
    }
  }

  const metrics = [
    { key: "sp500", label: "标普 500", unit: "", change: "%" },
    { key: "vix", label: "VIX 波动率", unit: "", change: "点" },
    { key: "ust2y", label: "美国 2 年期国债", unit: "%", change: "bp" },
    { key: "hy_oas", label: "美国高收益债 OAS", unit: "%", change: "bp" },
    { key: "wti", label: "WTI 现货", unit: "美元", change: "%" },
  ];

  function changeText(metric, current, previous) {
    if (!previous) return "";
    const difference = current.value - previous.value;
    if (metric.change === "%" && previous.value === 0) return "";
    const change = metric.change === "%" ? difference / Math.abs(previous.value) * 100
      : metric.change === "bp" ? difference * 100 : difference;
    return `${signed.format(change)} ${metric.change}`;
  }

  function metricCard(metric, series) {
    const points = (series?.history || [])
      .map(([date, value]) => ({ date, value }))
      .filter((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date) && Number.isFinite(point.value))
      .sort((a, b) => a.date.localeCompare(b.date));
    const current = points.at(-1);
    const previous = current && points.findLast((point) => point.date < current.date);

    const article = document.createElement("article");
    article.className = "metric";
    const title = document.createElement("h3");
    if (series) {
      const link = document.createElement("a");
      link.href = series.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = metric.label;
      title.append(link);
    } else {
      title.textContent = metric.label;
    }

    const row = document.createElement("div");
    row.className = "metric-data";
    const value = document.createElement("span");
    value.className = "metric-value";
    value.textContent = current ? `${number.format(current.value)}${metric.unit === "美元" ? " 美元" : metric.unit}` : "—";
    row.append(value);
    if (current && previous) {
      const delta = document.createElement("span");
      delta.className = "metric-change";
      delta.title = `较上一观测日 ${previous.date}`;
      delta.textContent = changeText(metric, current, previous);
      row.append(delta);
    }

    const date = document.createElement(current ? "time" : "span");
    date.className = "metric-date";
    if (current) date.dateTime = current.date;
    date.textContent = current ? current.date : "暂无数据";
    article.append(title, row, date);
    return article;
  }

  async function loadMetrics() {
    let series = {};
    try {
      const { data } = await window.marketData.load(
        "market_dashboard.json", 18 * hour, window.marketData.validDashboard
      );
      series = data.series;
    } catch {
      // The article list remains available when the market snapshot cannot be read.
    }
    byId("metrics").replaceChildren(...metrics.map((metric) => metricCard(metric, series[metric.key])));
  }

  const social = byId("social-news");
  social.addEventListener("toggle", function loadTimeline() {
    if (!social.open) return;
    social.removeEventListener("toggle", loadTimeline);
    const mount = byId("x-timeline");
    const timeline = document.createElement("a");
    timeline.className = "twitter-timeline";
    timeline.href = "https://x.com/Reuters";
    timeline.textContent = "在 X 查看 Reuters 时间线";
    timeline.target = "_blank";
    timeline.rel = "noopener noreferrer";
    timeline.dataset.theme = "dark";
    timeline.dataset.height = "380";
    timeline.dataset.dnt = "true";
    mount.append(timeline);

    const script = document.createElement("script");
    script.src = "https://platform.twitter.com/widgets.js";
    script.async = true;
    document.head.append(script);
  });

  for (const control of controls) {
    control.addEventListener("change", () => {
      visibleLimit = pageSize;
      renderEvents();
    });
  }
  more.addEventListener("click", () => {
    visibleLimit += pageSize;
    renderEvents();
  });
  refresh.addEventListener("click", () => {
    loadNews();
    loadMetrics();
  });
  loadNews();
  loadMetrics();
  window.setInterval(() => {
    if (!document.hidden) loadNews();
  }, 5 * 60_000);
})();

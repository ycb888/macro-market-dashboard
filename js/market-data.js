(() => {
  "use strict";

  function branchUrl(file) {
    const match = location.hostname.match(/^([\w-]+)\.github\.io$/);
    const repository = location.pathname.split("/")[1];
    if (!match || !repository || !/^[\w.-]+$/.test(repository) || repository.endsWith(".html")) return null;
    return `https://raw.githubusercontent.com/${match[1]}/${repository}/market-news-data/data/${file}`;
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(6000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function load(file, maxAge, validate) {
    const remote = branchUrl(file);
    let candidate = null;
    if (remote) {
      try {
        candidate = await fetchJson(remote);
        if (!validate(candidate)) throw new Error("Invalid data snapshot");
        if (Date.now() - Date.parse(candidate.collected_at) <= maxAge) {
          return { data: candidate, bundled: false };
        }
      } catch {
        candidate = null;
      }
    }
    try {
      const bundled = await fetchJson(`data/${file}`);
      if (!validate(bundled)) throw new Error("Invalid bundled snapshot");
      if (!candidate || Date.parse(bundled.collected_at) > Date.parse(candidate.collected_at)) {
        return { data: bundled, bundled: true };
      }
    } catch (error) {
      if (!candidate) throw error;
    }
    return { data: candidate, bundled: false };
  }

  const validNews = (data) => Number.isFinite(Date.parse(data?.collected_at))
    && Array.isArray(data.items) && data.feeds && typeof data.feeds === "object";
  const validDashboard = (data) => Number.isFinite(Date.parse(data?.collected_at))
    && data.series && typeof data.series === "object";

  window.marketData = { load, validNews, validDashboard };
})();

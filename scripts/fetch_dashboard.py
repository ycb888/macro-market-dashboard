#!/usr/bin/env python3
"""Refresh market and macro series from FRED and Yahoo Finance."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import UTC, datetime, timedelta
import gzip
import io
import json
import math
from pathlib import Path
import sys
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile
from zoneinfo import ZoneInfo


OUTPUT = Path(__file__).resolve().parents[1] / "data" / "market_dashboard.json"
FRED = {
    "sp500": ("SP500", "标普 500", "index", "daily"),
    "nasdaq": ("NASDAQCOM", "纳斯达克综合", "index", "daily"),
    "vix": ("VIXCLS", "VIX 波动率", "points", "daily"),
    "ust2y": ("DGS2", "美国 2 年期国债收益率", "rate", "daily"),
    "real10y": ("DFII10", "美国 10 年期实际收益率", "rate", "daily"),
    "yield_curve": ("T10Y2Y", "美债 10 年－2 年利差", "rate", "daily"),
    "hy_oas": ("BAMLH0A0HYM2", "美国高收益债 OAS", "rate", "daily"),
    "brent": ("DCOILBRENTEU", "布伦特现货", "oil", "daily"),
    "wti": ("DCOILWTICO", "WTI 现货", "oil", "daily"),
    "dollar": ("DTWEXBGS", "美联储广义美元指数", "index", "daily"),
    "nfci": ("NFCI", "芝加哥联储金融状况指数", "decimal", "weekly"),
    "cpi": ("CPIAUCSL", "美国 CPI 同比", "growth", "monthly"),
    "core_pce": ("PCEPILFE", "美国核心 PCE 同比", "growth", "monthly"),
    "unemployment": ("UNRATE", "美国失业率", "growth", "monthly"),
    "claims": ("ICSA", "美国初请失业金人数", "people", "weekly"),
    "us_cli": ("USALOLITOAASTSAM", "美国 OECD 领先指标", "points", "monthly"),
    "china_cli": ("CHNLOLITOAASTSAM", "中国 OECD 领先指标", "points", "monthly"),
    "japan_cli": ("JPNLOLITOAASTSAM", "日本 OECD 领先指标", "points", "monthly"),
}
QUOTES = {
    "shanghai": ("000001.SS", "上证综指"),
    "hang_seng": ("^HSI", "恒生指数"),
    "nikkei": ("^N225", "日经 225"),
    "eurostoxx": ("^STOXX50E", "欧洲斯托克 50"),
    "rsp": ("RSP", "标普 500 等权 ETF"),
    "spy": ("SPY", "标普 500 ETF"),
}


def download(url):
    request = Request(url, headers={"User-Agent": "MacroMarketDashboard/1.0"})
    with urlopen(request, timeout=16) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("response exceeds size limit")
    return gzip.decompress(data) if data.startswith(b"\x1f\x8b") else data


def read_fred(series, start):
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + urlencode({
        "id": ",".join(series), "cosd": start.isoformat(),
    })
    payload = download(url)
    if payload.startswith(b"PK"):
        with ZipFile(io.BytesIO(payload)) as archive:
            files = [archive.read(entry) for entry in archive.infolist()
                     if entry.filename.endswith(".csv") and entry.file_size <= 2_000_000]
    else:
        files = [payload]

    histories = {key: {} for key in series}
    for file in files:
        for row in csv.DictReader(io.StringIO(file.decode("utf-8-sig"))):
            day = row.get("observation_date") or row.get("DATE")
            if not day:
                continue
            for key in series:
                try:
                    value = float(row.get(key, ""))
                except (ValueError, TypeError):
                    continue
                if math.isfinite(value):
                    histories[key][day] = value
    return histories


def read_quote(code, adjusted, now):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(code, safe='')}?range=6mo&interval=1d"
    entry = json.loads(download(url))["chart"]["result"][0]
    meta = entry["meta"]
    zone = ZoneInfo(meta["exchangeTimezoneName"])
    periods = meta.get("currentTradingPeriod", {}).get("regular", {})
    # A bar for an open session is provisional. Drop it until the scheduled close.
    cutoff = periods.get("start", 0) if now.timestamp() < periods.get("end", 0) else float("inf")
    indicators = entry["indicators"]
    values = indicators["adjclose"][0]["adjclose"] if adjusted else indicators["quote"][0]["close"]
    return {
        datetime.fromtimestamp(stamp, zone).date().isoformat(): value
        for stamp, value in zip(entry["timestamp"], values)
        if stamp < cutoff and isinstance(value, (int, float)) and math.isfinite(value)
    }


def yoy(history):
    result = {}
    for day, value in history.items():
        prior = history.get(f"{int(day[:4]) - 1}{day[4:]}")
        if prior:
            result[day] = round((value / prior - 1) * 100, 4)
    return result


def breadth(rsp, spy):
    ratios = [(day, rsp[day] / spy[day]) for day in sorted(rsp.keys() & spy.keys()) if spy[day] > 0]
    return {day: round((value / ratios[index - 20][1] - 1) * 100, 4)
            for index, (day, value) in enumerate(ratios) if index >= 20}


def record(label, kind, frequency, source, url, history):
    observations = [[day, value] for day, value in sorted(history.items())]
    return {
        "label": label, "kind": kind, "frequency": frequency, "source": source,
        "url": url, "history": observations[-180:],
    }


def safe_get(future, label):
    try:
        data = future.result()
        print(f"{label}: {len(data)}")
        return data
    except Exception as exc:
        print(f"{label}: {exc}", file=sys.stderr)
        return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--min-hours", type=float, default=0)
    args = parser.parse_args()
    previous = json.loads(args.output.read_text(encoding="utf-8")) if args.output.is_file() else {}
    now = datetime.now(UTC)
    if previous.get("collected_at") and now - datetime.fromisoformat(previous["collected_at"]) < timedelta(hours=args.min_hours):
        print("Dashboard snapshot is recent.")
        return 0

    start = now.date() - timedelta(days=820)
    with ThreadPoolExecutor(max_workers=8) as pool:
        daily = [meta[0] for meta in FRED.values() if meta[3] == "daily"]
        slower = [meta[0] for meta in FRED.values() if meta[3] != "daily"]
        fred_daily = pool.submit(read_fred, daily, start)
        fred_slow = pool.submit(read_fred, slower, start)
        futures = {name: pool.submit(read_quote, code, name in ("rsp", "spy"), now)
                   for name, (code, _) in QUOTES.items()}
        fred = safe_get(fred_daily, "FRED daily") | safe_get(fred_slow, "FRED macro")
        quotes = {name: safe_get(future, name) for name, future in futures.items()}

    current = {}
    for name, (code, label, kind, freq) in FRED.items():
        history = fred.get(code, {})
        if name in ("cpi", "core_pce"):
            history = yoy(history)
        if history:
            current[name] = record(label, kind, freq, "FRED", f"https://fred.stlouisfed.org/series/{code}", history)
    for name, (code, label) in QUOTES.items():
        if name not in ("rsp", "spy") and quotes[name]:
            current[name] = record(label, "index", "daily", "Yahoo Finance",
                                   f"https://finance.yahoo.com/quote/{quote(code, safe='')}/", quotes[name])
    relative = breadth(quotes["rsp"], quotes["spy"])
    if relative:
        current["breadth"] = record("标普等权相对强弱 · 20 日", "growth", "daily", "Yahoo Finance · RSP 与 SPY 复权收盘",
                                    "https://finance.yahoo.com/quote/RSP/", relative)
    if not current:
        print("No series refreshed. Keeping previous snapshot.", file=sys.stderr)
        return 1

    snapshot = {
        "collected_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "series": previous.get("series", {}) | current,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(".tmp")
    temp.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(args.output)
    print(f"Refreshed {len(current)} series.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

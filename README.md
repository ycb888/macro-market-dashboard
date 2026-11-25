# 宏观市场看板

[打开看板](https://ycb888.github.io/macro-market-dashboard/) · [市场新闻](https://ycb888.github.io/macro-market-dashboard/market-news.html)

看板覆盖全球股指、美债、信用利差、原油、美国通胀和就业，以及美国、中国和日本的 OECD 领先指标。每项显示原始观测日期。标普等权相对强弱按 RSP 与 SPY 复权收盘价之比计算 20 个交易日的变化。

市场新闻保留出处和发布时间。内容摘要基于新闻源公开的简介或公告，市场影响另列并标注对象和依据。首批摘要已逐条复核。后续优先提供中文，自动翻译不可用或数字核对不通过时显示发布方提供的英文摘要。来源只提供标题时，卡片会注明摘要依据。

## 数据与部署

- 指标来自 [FRED](https://fred.stlouisfed.org/) 与 [Yahoo Finance](https://finance.yahoo.com/)。新闻源和机构链接见市场新闻页。
- GitHub Pages 使用 `main` 根目录。定时任务每半小时尝试采集新闻，每 12 小时尝试采集指标，并把快照更新到独立的 `market-news-data` 分支。来源短时故障时保留最近有效数据，页面继续显示相应观测日期。
- 中文翻译在工作流中运行 [NLLB](https://huggingface.co/facebook/nllb-200-distilled-600M) 模型。无需付费 API 密钥。

在项目目录运行 `python3 -m http.server 8000` 可本地查看。

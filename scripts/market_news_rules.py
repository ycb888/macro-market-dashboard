"""Explain market transmission using explicit events in public headlines."""

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Impact:
    direction: str
    market: str
    summary: str
    watch: str
    basis: str = "情景研判"


def has(text, pattern):
    return re.search(pattern, text, re.I) is not None


CHIPS = r"\b(nvidia|amd|tsmc|asml|semiconductors?|chips?|ai servers?)\b"
TRADE = r"\b(tariffs?|trade war|export (?:controls?|curbs?|restrictions?)|chip curbs|trade deal|trade talks|import (?:tax|duties))\b"
CONFLICT = r"\b(cease-?fire|peace deal|air\s?strikes?|missile strikes?|drone attacks?|houthi\w*|strait of hormuz|red sea shipping|sanctions?|military escalation|strikes? on [\w -]{0,20}(?:ships?|vessels?|tankers?))\b"
OIL = r"\b(oil|brent|wti|crude|tankers?|refiner\w*|gas suppl\w*|opec\+?|shipping)\b"
RATES = r"\b(fed(?:eral reserve)?|fomc|ecb|boj|bank of (?:japan|england)|interest rates?|rate[ -](?:cuts?|hikes?)|inflation|consumer prices?|(?:core )?cpi|pce|gdp|gross domestic product|personal income and outlays|nonfarm payrolls?|jobless claims|unemployment|treasur(?:y|ies)|bond yields?|central bank\w*|budget bill|tax cuts?)\b"
CORPORATE = r"\b(earnings|revenue|quarterly results|profit(?:s| forecast)?|guidance|ipo|buybacks?|dividends?|takeover|merger|antitrust|securities(?: fraud)?|stock exchanges?|investigation|probe|fraud)\b"
MARKETS = r"\b(stocks?|equities|shares|futures|s&p 500|nasdaq|dow jones|msci|nikkei|kospi|hang seng|stoxx|bond market|commodities|metals|gold|crude|brent|wti|stock market|financial markets|(?:fund|etf) flows)\b"
PROSPECTIVE = r"\b(could|may|might|weighs?|weighing|considers?|considering|plans?|prepares?|preparing|proposes?|proposed|proposal|threat\w*|is said to|rumou?rs?|speculation|bet[s]?\b|hopes?|awaits?|expected to|set to)\b"
UP = r"(?:rise[sn]?|rose|rising|gains?|gained|rall[yies]+|rallied|advances?|climb\w*|jumps?|surges?|rebound\w*)"
DOWN = r"(?:fall[s]?|fell|drop\w*|slide[sd]?|slid|sink[s]?|sank|slump\w*|retreat\w*|tumble[sd]?|plunge[sd]?|sell[ -]?off|decline[sd]?|losse?s?|dip(?:s|ped)?)"
EQUITIES = r"(?:stocks?|shares|equities|s&p 500|nasdaq|dow(?: jones)?|stoxx(?: 600)?|nikkei(?: 225)?|kospi|hang seng|ftse(?: 100)?)"
COMPANY_TOKEN = r"\b(nvidia|tesla|apple|microsoft|amazon|meta|alphabet|google|dell|asml|tsmc|samsung|huawei|broadcom|amd|easyjet|tencent|alibaba)\b"
COMPANY_EVENT = r"\b(earnings|guidance|profit|results|sales|revenue|ceo|guilty|probe|investigation|curbs|chips?|shares|stocks?|antitrust|lawsuit|bond|trade secrets)\b"

FALLBACK = {
    "macro": Impact("watch", "相关股市", "宏观数据或政策可能改变增长与利率预期，方向取决于结果相对预期的变化。", "实际值与预期、2 年期美债收益率", "需核对预期"),
    "geopolitics": Impact("watch", "相关地区及板块", "关注事件是否扩大，并传导至能源供给、贸易成本或风险溢价。", "官方后续、布伦特油价、VIX", "待确认"),
    "corporate": Impact("watch", "相关公司及同行", "消息首先影响公司的盈利或合规预期，指数层面的影响取决于权重和行业传导。", "公司公告、行业指数及相对表现", "待确认"),
    "markets": Impact("watch", "相关市场", "这条报道涉及市场走势或资金流向，方向还需结合对应资产的实际表现。", "主要指数、成交量、信用利差", "待确认"),
}

COMPANIES = {
    "nvidia": "英伟达 (NVDA)", "tesla": "特斯拉 (TSLA)", "apple": "苹果 (AAPL)",
    "microsoft": "微软 (MSFT)", "amazon": "亚马逊 (AMZN)", "meta": "Meta (META)",
    "alphabet": "Alphabet (GOOGL)", "google": "Alphabet (GOOGL)", "dell": "戴尔 (DELL)",
    "asml": "阿斯麦 (ASML)", "tsmc": "台积电 (TSM)", "samsung": "三星电子",
    "huawei": "相关通信供应链", "broadcom": "博通 (AVGO)", "amd": "AMD",
    "easyjet": "易捷航空 (EZJ)", "tencent": "腾讯 (0700.HK)", "alibaba": "阿里巴巴 (BABA)",
}


def equity_market(text):
    for pattern, market in (
        (r"\b(s&p 500|wall street|u\.?s\.? (?:stocks|shares|equities)|american stocks)\b", "美股"),
        (r"\bnasdaq\b", "纳斯达克"),
        (r"\b(dow jones|dow industrials)\b", "道琼斯指数"),
        (r"\b(indian (?:stocks|shares)|nifty|sensex)\b", "印度股市"),
        (r"\b(nikkei|japan(?:ese)? (?:stocks|shares))\b", "日本股市"),
        (r"\b(kospi|korean (?:stocks|shares))\b", "韩国股市"),
        (r"\b(asian (?:stocks|shares|equities)|asia(?:'s)? (?:stocks|shares|equities))\b", "亚太股市"),
        (r"\b(hang seng|hong kong (?:stocks|shares))\b", "港股"),
        (r"\b(csi 300|a-shares|chinese (?:stocks|shares|equities))\b", "中国股市"),
        (r"\b(ftse|british (?:stocks|shares)|uk (?:stocks|shares))\b", "英国股市"),
        (r"\b(stoxx|european (?:stocks|shares|equities))\b", "欧洲股市"),
        (r"\b(global (?:stocks|shares|equities)|world equities)\b", "全球股市"),
        (r"\btech(?:nology)? (?:stocks|shares|equities)\b", "科技股"),
    ):
        if has(text, pattern):
            return market
    return "报道所涉股市"


def market_move(title):
    negative = has(title, rf"\b{EQUITIES}\s+{DOWN}\b|\b{EQUITIES}\s+(?:extend|pare)\s+losses\b")
    positive = has(title, rf"\b{EQUITIES}\s+{UP}\b|\blifts?\s+(?:\w+\s+)?{EQUITIES}\b")
    if has(title, rf"\b{EQUITIES}\s+(?:pare\s+gains|cut\s+losses|reverse|(?:to|could|may|might)\s+{DOWN})\b"):
        return None
    if positive == negative:
        return None
    return Impact(
        "bullish" if positive else "bearish", equity_market(title),
        "报道所涉股市出现上涨。" if positive else "报道所涉股市出现下跌。",
        "对应指数、板块广度与收盘表现", "已报道走势",
    )


def classify(headline, description="", default=None):
    title = headline.casefold().replace("’", "'").replace("–", "-").replace("—", "-")
    context = f"{title} {description.casefold()[:300]}"
    tentative = has(title, PROSPECTIVE)
    company = re.search(COMPANY_TOKEN, title, re.I)
    if has(title, TRADE) and (has(title, r"\b(u\.?s\.?|china|eu|japan|global|chips?|across|trading partners)\b|\b(?:raises?|cuts?|imposes?|agrees?)\b") or has(context, r"\bworld trade\b")):
        market = "半导体及供应链" if has(title, CHIPS) else "受影响进出口板块"
        if not tentative and has(title, r"\b(agrees? to (?:cut|reduce|remove)|cuts?\b.{0,25}\btariffs?|removes?\b.{0,25}\btariffs?|reduces?\b.{0,25}\btariffs?|tariff truce)\b"):
            impact = Impact("bullish", market, "关税下调或休战有望缓和贸易摩擦，降低相关企业的成本预期。", "适用清单、税率与生效日期")
        elif not tentative and has(title, r"\b(imposes?|hikes?|raises?|tightens?|introduces?|expands?|announces increased)\b.{0,45}\b(tariffs?|curbs?|controls?|restrictions?|duties)\b"):
            impact = Impact("bearish", market, "新增贸易壁垒可能压缩受影响企业的利润或可销售市场。", "适用清单、豁免条款与企业收入敞口")
        else:
            impact = Impact("watch", market, "等待正式条款。若新增关税或限制落地，受影响进出口企业的利润和订单可能承压。", "税率、覆盖范围、生效时间及豁免条款", "待确认")
        return "geopolitics", asdict(impact)

    if has(title, CONFLICT):
        if not tentative and has(title, r"\b(agrees?|signs?|reaches?|takes effect|begins?|comes into effect)\b") and has(title, r"\b(cease-?fire|peace deal)\b"):
            impact = Impact("bullish", "受冲突影响的地区股市", "停火安排若得到执行，地区风险溢价和运输成本有望下降。", "执行进展、航线恢复、布伦特油价")
        elif not tentative and has(title, OIL) and has(title, r"\b(hits?|hit|attacks?|strikes?|damages?|shuts?|blocks?|halts?|disrupt\w*|suspends?)\b"):
            impact = Impact("mixed", "能源股 / 航空与运输股", "若供应或航运受扰推高油价，上游能源股可能受益，航空和运输企业则面临成本压力。", "布伦特油价、航运与产量公告")
        elif has(title, r"\b(houthi\w*|hormuz|red sea|saudi)\b"):
            impact = Impact("watch", "能源股 / 航空与运输股", "地区冲突升温。对股市的影响取决于事态是否波及能源设施、产量或航运。", "布伦特油价、船运通行与产量公告", "待确认")
        else:
            impact = FALLBACK["geopolitics"]
        return "geopolitics", asdict(impact)

    observed = market_move(title)
    if observed and not tentative:
        return "markets", asdict(observed)

    if company and has(title, COMPANY_EVENT):
        market = COMPANIES[company.group().lower()]
        if not tentative and has(title, r"\b(?:beats?|tops?|miss(?:es|ed)?|exceeds?)\b.{0,20}\b(?:estimates|expectations|forecasts)\b"):
            negative = has(title, r"\bmiss(?:es|ed)?\b")
            impact = Impact("bearish" if negative else "bullish", market, "公布结果低于预期，可能引发盈利预期下修。" if negative else "公布结果高于预期，可能支撑近期盈利预期。", "公司指引、利润率及同行走势")
        elif not tentative and has(title, r"\b(raises?|raises its|lifts?|boosts?|cuts?|lowers?|slashes?)\b.{0,24}\b(outlook|guidance|profit forecast|earnings forecast)\b"):
            negative = has(title, r"\b(cuts?|lowers?|slashes?)\b")
            impact = Impact("bearish" if negative else "bullish", market, "公司下调前瞻指引，可能带来估值或盈利预期下修。" if negative else "公司上调前瞻指引，可能带来盈利预期上修。", "调整幅度、利润率、正式财报")
        else:
            fallback = FALLBACK["corporate"]
            summary = "裁决带来合规及供应链不确定性，影响范围仍取决于判决和后续措施。" if has(title, r"\bfound guilty\b") else fallback.summary
            impact = Impact("watch", market, summary, fallback.watch, fallback.basis)
        return "corporate", asdict(impact)

    uk_energy_bills = has(context, r"\b(uk|britain|british|ofgem)\b") and has(title, r"\benergy bills?\b")
    if default == "macro" or has(title, RATES) or uk_energy_bills:
        if uk_energy_bills and not tentative and has(title, r"\b(rise|soar|jump|increase)\b"):
            impact = Impact("bearish", "英国可选消费股", "居民能源支出上升可能挤压非必需消费，影响幅度取决于账单补贴和实际能源支出。", "Ofgem 价格上限、英国零售数据")
        elif not tentative and has(title, r"\b(fed|u\.?s\.?|united states)\b") and has(title, r"\b(inflation|(?:core )?cpi|pce|consumer prices?)\b") and has(title, r"(hotter|cooler|higher|lower|faster|slower)[ -]than[ -](expected|forecast)"):
            negative = has(title, r"\b(hotter|higher|faster)\b")
            impact = Impact("bearish" if negative else "bullish", "美股利率敏感板块",
                            "通胀高于预期，若利率预期上移，成长股估值可能承压。" if negative else "通胀低于预期，若利率预期回落，成长股估值压力可能减轻。",
                            "2 年期美债、利率期货、纳斯达克")
        elif not tentative and has(title, r"\b(fed|federal reserve)\s+(?:raises?|hikes?|cuts?|lowers?)\s+(?:its\s+)?(?:key\s+|interest\s+|policy\s+)?rates?\b"):
            impact = Impact("mixed", "美股", "政策利率变动同时反映金融条件和央行对经济的判断，股市反应取决于变动幅度和前瞻指引相对预期的差异。", "2 年期美债、利率期货、政策声明")
        elif has(title, r"\bdiscount rate meetings?\b"):
            impact = Impact("watch", "美股利率敏感板块", "贴现率会议纪要反映各地区联储的利率建议。可用于观察政策分歧，接下来关注联邦基金利率指引。", "会议纪要、利率期货、2 年期美债", "需核对预期")
        elif has(title, r"\bminutes\b") and has(title, r"\b(fomc|federal open market committee)\b"):
            impact = Impact("watch", "美股利率敏感板块", "FOMC 会议纪要披露此前讨论和分歧。若市场重新定价利率路径，成长股与利率敏感板块更容易波动。", "政策措辞、利率期货、2 年期美债", "需核对预期")
        else:
            impact = FALLBACK["macro"]
        return "macro", asdict(impact)

    if default == "corporate" or has(title, CORPORATE) and (has(title, MARKETS) or has(context, r"\b(quarter|analysts|company)\b")):
        return "corporate", asdict(FALLBACK["corporate"])
    if has(title, MARKETS) or has(title, OIL):
        return "markets", asdict(FALLBACK["markets"])
    return None

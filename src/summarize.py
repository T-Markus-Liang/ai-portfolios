"""LLM summarizer.

Uses an OpenAI-compatible client (default: Volcengine Ark coding endpoint)
to turn normalized monitor items into a Chinese investment-research brief.

Env vars:
  ARK_API_KEY     required
  ARK_BASE_URL    default https://ark.cn-beijing.volces.com/api/coding/v3
  ARK_PLANNER_MODEL default kimi-k2.7-code
  ARK_WRITER_MODEL  default minimax-m3
  ARK_PLANNER_FALLBACK_MODELS default minimax-m3
  ARK_WRITER_FALLBACK_MODELS  default doubao-seed-2.0-lite,deepseek-v4-flash
  ARK_TIMEOUT_SECONDS default 45
  ARK_PLANNER_TIMEOUT_SECONDS default 20
  ARK_WRITER_TIMEOUT_SECONDS default 45
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

INVESTMENT_KEYWORDS = (
    "AI", "算力", "DRAM", "HBM", "CXL", "MLCC", "半导体", "存储", "光模块",
    "CPO", "CoPoS", "ASIC", "GPU", "TPU", "加仓", "加cang", "买入", "卖出",
    "03121", "03119", "台积电", "美光", "海力士", "苹果", "Siri",
)
NOISE_KEYWORDS = ("会员服务使用指南", "关于抄作业", "关于提问", "关于知识库", "SVIP服务", "需求调研")

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
DEFAULT_PLANNER_MODEL = "kimi-k2.7-code"
DEFAULT_WRITER_MODEL = "minimax-m3"
DEFAULT_PLANNER_FALLBACK_MODELS = ("minimax-m3",)
DEFAULT_WRITER_FALLBACK_MODELS = ("doubao-seed-2.0-lite", "deepseek-v4-flash")
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_PLANNER_TIMEOUT_SECONDS = 20.0
DEFAULT_WRITER_TIMEOUT_SECONDS = 45.0

MAX_ITEMS = 18
MAX_RETRY_ITEMS = 10
MAX_TEXT_LEN = 220
MAX_ARCHIVE_TEXT_LEN = 1600
MAX_RETRY_TEXT_LEN = 140
MAX_PAYLOAD_CHARS = 6200
MAX_RETRY_PAYLOAD_CHARS = 3600
MAX_OUTPUT_TOKENS = 4096
REQUIRED_SECTIONS = (
    "## 一页决策总览",
    "## 今日核心判断",
    "## 主线深度拆解",
    "## 机会与仓位建议",
    "## 市场动量与分歧",
    "## 风险与证伪",
    "## 证据链",
    "## 明日行动清单",
)

SYSTEM_PROMPT = "你是中文买方投研助手。严格遵守用户要求的输出格式，不输出思考过程。"

PLANNER_TEMPLATE = """基于 JSON 输出投资报告提纲。latest 是本次新增，recent 是近几天上下文。你只负责判断结构、核心点、论点论据链和行动框架，不负责成文。监控源少于20个，要尽量覆盖不同博主/来源，不能只抓一两个热点词。短句，禁止 Markdown，禁止解释。

输出 schema，key 必须使用英文短 key：
{"one":{"temp":"偏热/中性/偏冷/风险升温","risk":"低/中/高","pos":"总体仓位态度","conclusion":"一句话总判断","note":"普通投资者提示","avoid":"今天不要做什么"},
"calls":[{"t":"主题","rank":"1/2/3","d":"强化/降温/反转/待确认","e":"A/B/C/D","why":"一句话理由","map":"国内映射","act":"进攻/观察/等待/回避"}],
"deep":[{"t":"主题","thesis":"核心论点","bull":"支持论据，至少2点","bear":"反向证据/缺口","map":"国内映射","strat":"操作含义","watch":"验证信号"}],
"plan":[{"t":"主题","bucket":"进攻/观察/等待/回避","pos":"定性仓位","entry":"介入条件","add":"加仓条件","trim":"减仓/回避条件","bad":"证伪信号"}],
"mom":[{"t":"主题","chg":"动量变化","drv":"核心驱动","watch":"观察项"}],
"src":[{"name":"来源/博主","stance":"支持/谨慎/反对/信息源","theme":"对应主题","point":"贡献的关键证据"}],
"risk":[{"r":"风险","trig":"触发","imp":"影响","resp":"应对"}],
"ev":[{"s":"A/B/C/D","theme":"主题","src":"来源","sum":"推文/文章/群消息摘要","url":"URL或本地归档","use":"支撑哪个结论"}],
"next":[{"it":"验证事项","why":"重要性","src":"观察指标/来源","act":"若验证通过/失败怎么做"}]}

数量：calls 2-4；deep 2-3；plan 2-4；mom 2-4；src 3-6；risk 2-3；ev 5-8；next 3-5。

JSON:
{{items}}
"""

WRITER_TEMPLATE = """把下面的报告提纲 JSON 改写成完整、清晰、专业但普通投资者也能读懂的中文投资报告 JSON。你只负责把逻辑讲清楚，不新增未经提纲支持的主题。每条主线必须体现：结论 -> 论据 -> 反证 -> 国内映射 -> 行动建议。禁止 Markdown，禁止解释。

输出同一 schema，字段必须完整，短句但信息密度高：
{"one":{"temp":"","risk":"","pos":"","conclusion":"","note":"","avoid":""},"calls":[{"t":"","rank":"","d":"","e":"","why":"","map":"","act":""}],"deep":[{"t":"","thesis":"","bull":"","bear":"","map":"","strat":"","watch":""}],"plan":[{"t":"","bucket":"","pos":"","entry":"","add":"","trim":"","bad":""}],"mom":[{"t":"","chg":"","drv":"","watch":""}],"src":[{"name":"","stance":"","theme":"","point":""}],"risk":[{"r":"","trig":"","imp":"","resp":""}],"ev":[{"s":"","theme":"","src":"","sum":"","url":"","use":""}],"next":[{"it":"","why":"","src":"","act":""}]}

JSON:
{{outline}}
"""


class LLMError(RuntimeError):
    pass


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _importance_score(item: dict[str, Any]) -> tuple[int, int]:
    content_type = item.get("contentType") or "tweet"
    text = item.get("text") or ""
    source = item.get("source") or ""
    engagement = _to_int(item.get("likeCount")) + _to_int(item.get("retweetCount")) * 3
    priority = 0
    if item.get("contextRole") == "latest":
        priority += 40_000
    if content_type == "wechat_group_archive":
        priority += 30_000
    elif content_type == "article":
        priority += 12_000
    if "wechat_group" in source:
        priority += 20_000
    if any(keyword in text for keyword in INVESTMENT_KEYWORDS):
        priority += 2_000
    return (priority + engagement, len(text))


def _keyword_score(text: str) -> int:
    score = sum(1 for keyword in INVESTMENT_KEYWORDS if keyword in text)
    score += sum(ch.isdigit() for ch in text) // 3
    if any(keyword in text for keyword in ("DRAM", "HBM", "CXL", "MLCC", "03121", "03119", "加仓", "加cang")):
        score += 6
    if any(keyword in text for keyword in NOISE_KEYWORDS):
        score -= 8
    return score


def _wechat_archive_excerpt(text: str, max_text_len: int) -> str:
    chunks = []
    text = text.replace("六便士：", "六便士:")
    for raw in text.split("六便士:")[1:]:
        chunk = raw.strip()
        if not chunk:
            continue
        if not any(keyword in chunk for keyword in INVESTMENT_KEYWORDS):
            continue
        score = _keyword_score(chunk)
        if score <= 0:
            continue
        chunks.append((score, "六便士: " + chunk))
    if not chunks:
        return text[:max_text_len]
    chunks.sort(key=lambda item: item[0], reverse=True)
    out: list[str] = []
    total = 0
    for _, chunk in chunks[:4]:
        clipped = chunk[:520]
        if total + len(clipped) > max_text_len and out:
            break
        out.append(clipped)
        total += len(clipped)
    return " …… ".join(out)[:max_text_len]


def _clip_text(item: dict[str, Any], max_text_len: int) -> str:
    text = " ".join((item.get("text") or "").strip().split())
    if item.get("contentType") == "wechat_group_archive":
        max_text_len = max(max_text_len, min(MAX_ARCHIVE_TEXT_LEN, max_text_len * 4))
        text = _wechat_archive_excerpt(text, max_text_len)
    if len(text) > max_text_len:
        return text[:max_text_len] + "…"
    return text


def _compact_record(item: dict[str, Any], max_text_len: int) -> dict[str, Any]:
    return {
        "source": item.get("kol") or item.get("handle") or "",
        "type": item.get("contentType") or "tweet",
        "contextRole": item.get("contextRole") or "latest",
        "contextDate": item.get("contextDate") or "",
        "title": item.get("title") or "",
        "text": _clip_text(item, max_text_len),
        "url": item.get("url") or "",
        "time": item.get("createdAt") or "",
        "heat": _to_int(item.get("likeCount")) + _to_int(item.get("retweetCount")) * 3,
    }


def _pack(items: list[dict[str, Any]], *, max_items: int, max_text_len: int, max_payload_chars: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    for source in sorted({str(item.get("kol") or item.get("handle") or "") for item in items}):
        source_items = [item for item in items if str(item.get("kol") or item.get("handle") or "") == source]
        if not source_items:
            continue
        best = max(source_items, key=_importance_score)
        selected.append(best)
        seen_ids.add(id(best))

    for item in sorted(items, key=_importance_score, reverse=True):
        if len(selected) >= max_items:
            break
        if id(item) in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(id(item))

    packed: list[dict[str, Any]] = []
    total_chars = 0
    for item in selected:
        record = _compact_record(item, max_text_len)
        record_chars = len(json.dumps(record, ensure_ascii=False))
        if packed and total_chars + record_chars > max_payload_chars:
            break
        packed.append(record)
        total_chars += record_chars
    return packed


def _finish_reason(resp: Any) -> str:
    try:
        return str(resp.choices[0].finish_reason or "")
    except Exception:
        return ""


def _response_id(resp: Any) -> str:
    return str(getattr(resp, "id", "") or "")


def _csv_models(value: str) -> list[str]:
    models: list[str] = []
    for model in value.split(","):
        model = model.strip()
        if model and model not in models:
            models.append(model)
    return models


def _model_candidates(role: str) -> list[str]:
    if role == "planner":
        primary = (os.environ.get("ARK_PLANNER_MODEL") or os.environ.get("ARK_MODEL") or DEFAULT_PLANNER_MODEL).strip()
        fallback = os.environ.get("ARK_PLANNER_FALLBACK_MODELS") or ",".join(DEFAULT_PLANNER_FALLBACK_MODELS)
    else:
        primary = (os.environ.get("ARK_WRITER_MODEL") or DEFAULT_WRITER_MODEL).strip()
        fallback = os.environ.get("ARK_WRITER_FALLBACK_MODELS") or ",".join(DEFAULT_WRITER_FALLBACK_MODELS)
    models: list[str] = []
    for model in [primary, *_csv_models(fallback)]:
        if model and model not in models:
            models.append(model)
    return models


def _client(api_key: str, base_url: str, role: str) -> Any:
    return OpenAI(api_key=api_key, base_url=base_url, timeout=_timeout_seconds(role), max_retries=0)


def _create_completion(client: Any, request: dict[str, Any]) -> Any:
    try:
        return client.chat.completions.create(**request)
    except Exception as exc:
        message = str(exc).lower()
        if "response_format" not in request or "response_format" not in message:
            raise
        fallback = dict(request)
        fallback.pop("response_format", None)
        return client.chat.completions.create(**fallback)


def _supports_json_mode(model: str) -> bool:
    disabled = _csv_models(os.environ.get("LLM_JSON_MODE_DISABLED_MODELS") or "deepseek-v4-flash,minimax-m3")
    if model in disabled:
        return False
    return (os.environ.get("LLM_JSON_MODE") or "1").strip().lower() not in {"0", "false", "no", "off"}


def _call_model(client: Any, model: str, user_prompt: str, *, max_tokens: int = MAX_OUTPUT_TOKENS) -> tuple[str, Any]:
    request = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if _supports_json_mode(model):
        request["response_format"] = {"type": "json_object"}
    resp = _create_completion(client, request)
    return (resp.choices[0].message.content or "").strip(), resp


def _call_json_candidates(api_key: str, base_url: str, role: str, prompt: str, *, max_tokens: int) -> tuple[dict[str, Any], str]:
    errors: list[str] = []
    for model in _model_candidates(role):
        try:
            content, resp = _call_model(_client(api_key, base_url, role), model, prompt, max_tokens=max_tokens)
        except Exception as exc:
            errors.append(f"{role}:{model}: {type(exc).__name__}: {exc}")
            continue
        data = _json_from_model(content)
        if data and _valid_report_data(_coerce_report_data(data)):
            return data, model
        finish = _finish_reason(resp)
        errors.append(
            f"{role}:{model}: invalid_json finish={finish}; response_id={_response_id(resp)}; "
            f"chars={len(content)}"
        )
    raise LLMError("all " + role + " candidates failed: " + " | ".join(errors))


def _safe_text(value: Any, default: str = "待确认") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_rows(value: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = [row for row in value if isinstance(row, dict)]
    return rows[:limit]


def _json_from_model(content: str) -> dict[str, Any]:
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _valid_report_data(data: dict[str, Any]) -> bool:
    required = (
        "one_page",
        "key_calls",
        "deep_dives",
        "action_plan",
        "source_view",
        "risk_radar",
        "evidence",
        "tomorrow",
    )
    if not all(key in data for key in required):
        return False
    return bool(_safe_rows(data.get("key_calls"), 3) and _safe_rows(data.get("evidence"), 6))


def _coerce_report_data(data: dict[str, Any]) -> dict[str, Any]:
    key_calls_raw = data.get("key_calls") or data.get("calls")
    deep_raw = data.get("deep_dives") or data.get("deep") or data.get("logic_chains") or data.get("logic")
    action_raw = data.get("action_plan") or data.get("plan") or data.get("opportunity_matrix") or data.get("opp")
    momentum_raw = data.get("momentum_table") or data.get("mom")
    source_raw = data.get("source_view") or data.get("src")
    risks_raw = data.get("risk_radar") or data.get("risk")
    evidence_raw = data.get("evidence") or data.get("ev")
    tomorrow_raw = data.get("tomorrow") or data.get("next")
    key_calls_raw = key_calls_raw if isinstance(key_calls_raw, list) else []
    deep_raw = deep_raw if isinstance(deep_raw, list) else []
    action_raw = action_raw if isinstance(action_raw, list) else []
    momentum_raw = momentum_raw if isinstance(momentum_raw, list) else []
    source_raw = source_raw if isinstance(source_raw, list) else []
    risks_raw = risks_raw if isinstance(risks_raw, list) else []
    evidence_raw = evidence_raw if isinstance(evidence_raw, list) else []
    tomorrow_raw = tomorrow_raw if isinstance(tomorrow_raw, list) else []

    def first_text(value: Any) -> str:
        if isinstance(value, dict):
            return _safe_text(value.get("theme") or value.get("t") or value.get("target") or value.get("name") or value.get("risk") or value.get("r"))
        return _safe_text(value)

    key_calls: list[dict[str, Any]] = []
    for row in key_calls_raw[:3]:
        if isinstance(row, dict):
            key_calls.append(
                {
                    "theme": row.get("theme") or row.get("t"),
                    "rank": row.get("rank") or row.get("priority") or "",
                    "direction": row.get("direction") or row.get("d") or "待确认",
                    "evidence": row.get("evidence") or row.get("e") or "C",
                    "why": row.get("why") or row.get("reason") or "信号仍需交叉验证",
                    "china_map": row.get("china_map") or row.get("map") or "A股/港股相关产业链",
                    "action": row.get("action") or row.get("act") or "观察",
                }
            )
        else:
            key_calls.append(
                {
                    "theme": first_text(row),
                    "rank": "",
                    "direction": "待确认",
                    "evidence": "C",
                    "why": "信号仍需交叉验证",
                    "china_map": "A股/港股相关产业链",
                    "action": "观察",
                }
            )

    deep_dives: list[dict[str, Any]] = []
    for row in deep_raw[:4]:
        if isinstance(row, dict):
            deep_dives.append(
                {
                    "theme": row.get("theme") or row.get("t") or row.get("signal") or row.get("sig"),
                    "thesis": row.get("thesis") or row.get("conclusion") or row.get("con") or row.get("mechanism") or row.get("mech"),
                    "bull": row.get("bull") or row.get("evidence") or row.get("support") or row.get("mechanism") or row.get("mech"),
                    "bear": row.get("bear") or row.get("gap") or row.get("invalid") or row.get("bad") or "缺少价格/订单/业绩验证时不能上升为强交易结论",
                    "china_map": row.get("china_map") or row.get("map") or "A股/港股相关产业链",
                    "strategy": row.get("strategy") or row.get("strat") or row.get("conclusion") or row.get("con") or "纳入观察池，等待验证",
                    "watch": row.get("watch") or row.get("next") or "资金响应、产业数据、公司公告",
                }
            )

    action_plan: list[dict[str, Any]] = []
    for row in action_raw[:5]:
        if isinstance(row, dict):
            action_plan.append(
                {
                    "theme": row.get("theme") or row.get("t") or row.get("target"),
                    "bucket": row.get("bucket") or row.get("action") or row.get("act") or "观察",
                    "position": row.get("position") or row.get("pos") or row.get("strategy") or row.get("strat") or "轻仓/观察",
                    "entry": row.get("entry") or row.get("trigger") or "主题继续跨来源强化且国内映射放量",
                    "add": row.get("add") or row.get("increase") or "订单/价格/业绩验证出现",
                    "trim": row.get("trim") or row.get("reduce") or row.get("exit") or "高位放量回落或证据降温",
                    "invalid": row.get("invalid") or row.get("bad") or "主题热度下降且缺少基本面跟进",
                }
            )

    momentum: list[dict[str, Any]] = []
    for row in momentum_raw[:5]:
        if isinstance(row, dict):
            momentum.append(
                {
                    "theme": row.get("theme") or row.get("t") or row.get("target") or row.get("name"),
                    "change": row.get("change") or row.get("chg") or row.get("trend") or "待确认",
                    "drivers": row.get("drivers") or row.get("drv") or row.get("logic") or row.get("reason"),
                    "watch": row.get("watch") or row.get("next") or "资金响应与基本面验证",
                }
            )

    source_view: list[dict[str, Any]] = []
    for row in source_raw[:8]:
        if isinstance(row, dict):
            source_view.append(
                {
                    "name": row.get("name") or row.get("source") or row.get("src") or "未知来源",
                    "stance": row.get("stance") or "信息源",
                    "theme": row.get("theme") or row.get("t") or "综合",
                    "point": row.get("point") or row.get("summary") or row.get("sum") or "提供主题线索",
                }
            )

    risks: list[dict[str, Any]] = []
    for row in risks_raw[:3]:
        if isinstance(row, dict):
            risks.append(
                {
                    "risk": row.get("risk") or row.get("r"),
                    "trigger": row.get("trigger") or row.get("trig") or row.get("severity") or "待确认",
                    "impact": row.get("impact") or row.get("imp") or "可能造成波动放大",
                    "response": row.get("response") or row.get("resp") or "降低仓位，等待验证",
                }
            )

    evidence: list[dict[str, Any]] = []
    for row in evidence_raw[:6]:
        if isinstance(row, dict):
            evidence.append(
                {
                    "strength": row.get("strength") or row.get("s") or "C",
                    "theme": row.get("theme") or row.get("t") or "综合",
                    "source": row.get("source") or row.get("src") or "模型提炼",
                    "summary": row.get("summary") or row.get("sum"),
                    "url": row.get("url") or "本地归档",
                    "use": row.get("use") or "支撑核心判断",
                }
            )
        else:
            evidence.append({"strength": "C", "theme": "综合", "source": "模型提炼", "summary": first_text(row), "url": "本地归档", "use": "支撑核心判断"})

    tomorrow: list[dict[str, Any]] = []
    for row in tomorrow_raw[:3]:
        if isinstance(row, dict):
            tomorrow.append(
                {
                    "item": row.get("item") or row.get("it"),
                    "why": row.get("why") or "验证动量是否延续",
                    "source": row.get("source") or row.get("src") or "市场数据/信息源",
                    "action": row.get("action") or row.get("act") or "通过则提高权重，失败则降级观察",
                }
            )
        else:
            tomorrow.append({"item": first_text(row), "why": "验证动量是否延续", "source": "市场数据/信息源", "action": "通过则提高权重，失败则降级观察"})

    one_page = data.get("one_page") or data.get("one")
    one_page = one_page if isinstance(one_page, dict) else {}
    if one_page:
        one_page = {
            "market_temperature": one_page.get("market_temperature") or one_page.get("temp"),
            "risk_level": one_page.get("risk_level") or one_page.get("risk"),
            "position": one_page.get("position") or one_page.get("pos") or "观察为主，小仓试探",
            "core_conclusion": one_page.get("core_conclusion") or one_page.get("conclusion"),
            "investor_note": one_page.get("investor_note") or one_page.get("note"),
            "avoid": one_page.get("avoid") or "不要把单条热帖当成买入理由",
        }
    if not one_page:
        one_page = {
            "market_temperature": "中性偏热",
            "risk_level": "中",
            "position": "观察为主，小仓试探",
            "core_conclusion": first_text(key_calls[0] if key_calls else "暂无强共识主线"),
            "investor_note": "先看证据是否连续强化，不因单条消息追高。",
            "avoid": "不要把单条热帖当成买入理由。",
        }

    themes = [_safe_text(row.get("theme")) for row in key_calls] or ["暂无高一致性主题"]
    if not deep_dives:
        deep_dives = [
            {
                "theme": theme,
                "thesis": f"{theme} 是当前需要优先拆解的观察主线。",
                "bull": "已有信号进入监控范围，但需要更多跨来源证据确认。",
                "bear": "若缺少订单、价格、业绩或资金响应，仍可能只是短期叙事。",
                "china_map": "A股/港股相关产业链",
                "strategy": "先纳入观察池，验证后再决定是否提高权重。",
                "watch": "成交额、板块强弱、公司公告和产业数据。",
            }
            for theme in themes[:3]
        ]
    if not action_plan:
        action_plan = [
            {
                "theme": theme,
                "bucket": "观察",
                "position": "观察仓",
                "entry": "连续跨来源强化且国内映射标的放量",
                "add": "出现订单、价格、业绩或产业新闻确认",
                "trim": "高位放量回落或证据降温",
                "invalid": "连续多日无新增证据或国内映射失败",
            }
            for theme in themes[:3]
        ]
    if not momentum:
        momentum = [
            {
                "theme": theme,
                "change": "待确认",
                "drivers": "进入监控范围但仍需更多证据",
                "watch": "是否继续跨来源出现并获得资金响应",
            }
            for theme in themes[:3]
        ]
    if not source_view and evidence:
        source_view = [
            {
                "name": _safe_text(row.get("source"), "未知来源"),
                "stance": "信息源",
                "theme": _safe_text(row.get("theme"), themes[0]),
                "point": _safe_text(row.get("summary"), "提供主题线索"),
            }
            for row in evidence[:6]
        ]
    if not risks:
        risks = [
            {"risk": "主题拥挤", "trigger": "热点只停留在观点层且涨幅过大", "impact": "情绪交易后回撤", "response": "等订单、价格和业绩验证"},
            {"risk": "映射错配", "trigger": "海外叙事强但国内兑现弱", "impact": "A股/港股跟涨失败", "response": "跟踪成交额、强弱排序和公司公告"},
        ]
    if not tomorrow:
        tomorrow = [
            {"item": "主题是否继续跨来源出现", "why": "判断动量是否延续", "source": "X/Nitter、微信公众号、微信群归档", "action": "继续强化则保留观察权重，否则降级"},
            {"item": "国内映射是否有资金响应", "why": "判断能否转化为交易机会", "source": "A股/港股成交额、强弱排序、板块涨跌", "action": "放量跑赢则提高关注，否则只做资料跟踪"},
            {"item": "是否出现反向证据", "why": "防止单边叙事误导", "source": "价格回撤、公司澄清、宏观或监管冲击", "action": "出现反证则降低仓位或移出观察池"},
        ]

    coerced = dict(data)
    coerced.update(
        {
            "one_page": one_page,
            "key_calls": key_calls,
            "deep_dives": deep_dives,
            "action_plan": action_plan,
            "momentum_table": momentum,
            "source_view": source_view,
            "risk_radar": risks,
            "evidence": evidence,
            "tomorrow": tomorrow,
        }
    )
    return coerced


def _as_markdown_link(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return "本地归档"
    if text.startswith(("http://", "https://")):
        return f"[打开]({text})"
    return text


def _render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [cell.replace("\n", " ").replace("|", "/").strip() or "待确认" for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _render_report_data(data: dict[str, Any]) -> str:
    one_page = data.get("one_page") if isinstance(data.get("one_page"), dict) else {}
    key_calls = _safe_rows(data.get("key_calls"), 3)
    deep_dives = _safe_rows(data.get("deep_dives"), 4)
    action_plan = _safe_rows(data.get("action_plan"), 5)
    momentum = _safe_rows(data.get("momentum_table"), 5)
    source_view = _safe_rows(data.get("source_view"), 8)
    risks = _safe_rows(data.get("risk_radar"), 3)
    evidence = _safe_rows(data.get("evidence"), 8)
    tomorrow = _safe_rows(data.get("tomorrow"), 5)

    lines: list[str] = [
        "## 一页决策总览",
        "",
        "| 指标 | 判断 |",
        "|---|---|",
        f"| 市场温度 | {_safe_text(one_page.get('market_temperature'))} |",
        f"| 风险等级 | {_safe_text(one_page.get('risk_level'))} |",
        f"| 总体仓位 | {_safe_text(one_page.get('position'), '观察为主，小仓试探')} |",
        f"| 今日结论 | {_safe_text(one_page.get('core_conclusion'))} |",
        f"| 普通投资者提示 | {_safe_text(one_page.get('investor_note'))} |",
        f"| 今日不要做 | {_safe_text(one_page.get('avoid'), '不要把单条热帖当成买入理由')} |",
        "",
        "## 今日核心判断",
        "",
    ]
    for row in key_calls:
        rank = _safe_text(row.get("rank"), "").strip()
        prefix = f"#{rank} " if rank else ""
        lines.append(
            f"- **{prefix}{_safe_text(row.get('theme'))}** [{_safe_text(row.get('evidence'), 'C')}级证据]"
            f"：{_safe_text(row.get('direction'))}。理由：{_safe_text(row.get('why'))}"
            f"；国内映射：{_safe_text(row.get('china_map'))}"
            f"；行动：{_safe_text(row.get('action'))}。"
        )

    lines += [
        "",
        "## 主线深度拆解",
        "",
        *_render_table(
            ["主线", "核心论点", "支持论据", "反向证据/缺口", "国内映射", "操作含义", "验证信号"],
            [
                [
                    _safe_text(row.get("theme")),
                    _safe_text(row.get("thesis")),
                    _safe_text(row.get("bull")),
                    _safe_text(row.get("bear")),
                    _safe_text(row.get("china_map")),
                    _safe_text(row.get("strategy")),
                    _safe_text(row.get("watch")),
                ]
                for row in deep_dives
            ],
        ),
        "",
        "## 机会与仓位建议",
        "",
        *_render_table(
            ["主题", "分层", "建议仓位", "介入条件", "加仓条件", "减仓/回避条件", "证伪信号"],
            [
                [
                    _safe_text(row.get("theme")),
                    _safe_text(row.get("bucket")),
                    _safe_text(row.get("position")),
                    _safe_text(row.get("entry")),
                    _safe_text(row.get("add")),
                    _safe_text(row.get("trim")),
                    _safe_text(row.get("invalid")),
                ]
                for row in action_plan
            ],
        ),
        "",
        "## 市场动量与分歧",
        "",
        *_render_table(
            ["主题", "动量变化", "核心驱动", "下一步观察"],
            [
                [
                    _safe_text(row.get("theme")),
                    _safe_text(row.get("change")),
                    _safe_text(row.get("drivers")),
                    _safe_text(row.get("watch")),
                ]
                for row in momentum
            ],
        ),
        "",
        "### 来源分布",
        "",
        *_render_table(
            ["来源/博主", "立场", "对应主题", "贡献的关键证据"],
            [
                [
                    _safe_text(row.get("name")),
                    _safe_text(row.get("stance")),
                    _safe_text(row.get("theme")),
                    _safe_text(row.get("point")),
                ]
                for row in source_view
            ],
        ),
        "",
        "## 风险与证伪",
        "",
        *_render_table(
            ["风险", "触发条件", "影响", "应对"],
            [
                [
                    _safe_text(row.get("risk")),
                    _safe_text(row.get("trigger")),
                    _safe_text(row.get("impact")),
                    _safe_text(row.get("response")),
                ]
                for row in risks
            ],
        ),
        "",
        "## 证据链",
        "",
    ]
    for row in evidence:
        lines.append(
            f"- [{_safe_text(row.get('strength'), 'C')}] **{_safe_text(row.get('theme'), '综合')}** / "
            f"{_safe_text(row.get('source'), '未知来源')}：{_safe_text(row.get('summary'))}"
            f"；用途：{_safe_text(row.get('use'), '支撑核心判断')}"
            f"；链接：{_as_markdown_link(row.get('url'))}"
        )

    lines += [
        "",
        "## 明日行动清单",
        "",
        *_render_table(
            ["验证事项", "为什么重要", "观察指标/来源", "行动规则"],
            [
                [
                    _safe_text(row.get("item")),
                    _safe_text(row.get("why")),
                    _safe_text(row.get("source")),
                    _safe_text(row.get("action")),
                ]
                for row in tomorrow
            ],
        ),
        "",
        "---",
        "仅供研究，不构成投资建议。",
    ]
    return "\n".join(lines)


def _normalize_model_report(content: str) -> str:
    data = _json_from_model(content)
    if data:
        data = _coerce_report_data(data)
    if _valid_report_data(data):
        return _render_report_data(data)
    return _normalize_report(content)


def _parse_timeout(raw: str, default: float) -> float:
    if not raw.strip():
        return default
    try:
        return max(5.0, min(float(raw), 180.0))
    except ValueError:
        return default


def _timeout_seconds(role: str | None = None) -> float:
    if role == "planner":
        raw = os.environ.get("ARK_PLANNER_TIMEOUT_SECONDS") or os.environ.get("ARK_TIMEOUT_SECONDS") or ""
        return _parse_timeout(raw, DEFAULT_PLANNER_TIMEOUT_SECONDS)
    if role == "writer":
        raw = os.environ.get("ARK_WRITER_TIMEOUT_SECONDS") or os.environ.get("ARK_TIMEOUT_SECONDS") or ""
        return _parse_timeout(raw, DEFAULT_WRITER_TIMEOUT_SECONDS)
    return _parse_timeout(os.environ.get("ARK_TIMEOUT_SECONDS") or "", DEFAULT_TIMEOUT_SECONDS)


def _has_required_sections(content: str) -> bool:
    return all(section in content for section in REQUIRED_SECTIONS)


def _normalize_report(content: str) -> str:
    content = content.strip()
    if len(content) < 350:
        return ""
    if not _has_required_sections(content):
        return ""
    if "仅供研究，不构成投资建议" not in content:
        content = content.rstrip() + "\n\n---\n仅供研究，不构成投资建议。"
    return content


def _ensure_evidence_links(content: str, records: list[dict[str, Any]]) -> str:
    evidence_header = "## 证据链"
    next_header = "## 明日行动清单"
    if evidence_header not in content or "链接：" in content:
        return content
    start = content.find(evidence_header)
    end = content.find(next_header, start)
    if end == -1:
        return content
    lines = _evidence_lines(records, limit=4)
    enriched_lines = []
    for line in lines:
        match = re.match(r"- \[([ABCD])\] ([^：]+)：(.+?)；链接：(.+)$", line)
        if match:
            enriched_lines.append(
                f"- [{match.group(1)}] **综合** / {match.group(2)}：{match.group(3)}"
                f"；用途：支撑核心判断；链接：{_as_markdown_link(match.group(4))}"
            )
        else:
            enriched_lines.append(line)
    insert = evidence_header + "\n" + "\n".join(enriched_lines) + "\n"
    return content[:start] + insert + content[end:]


def _is_complete_report(content: str) -> bool:
    if len(content) < 350:
        return False
    if "仅供研究，不构成投资建议" not in content:
        return False
    return _has_required_sections(content)


def summarize(items: list[dict[str, Any]]) -> str:
    if OpenAI is None:
        raise LLMError("openai package not installed")
    api_key = os.environ.get("ARK_API_KEY", "").strip()
    if not api_key:
        raise LLMError("ARK_API_KEY is not set")

    base_url = (os.environ.get("ARK_BASE_URL") or DEFAULT_BASE_URL).strip()

    packed = _pack(
        items,
        max_items=MAX_ITEMS,
        max_text_len=MAX_TEXT_LEN,
        max_payload_chars=MAX_PAYLOAD_CHARS,
    )
    payload = json.dumps(packed, ensure_ascii=False, separators=(",", ":"))
    planner_prompt = PLANNER_TEMPLATE.replace("{{items}}", payload)
    planner_model = "rule-engine"
    planner_error = ""
    try:
        outline_data, planner_model = _call_json_candidates(
            api_key,
            base_url,
            "planner",
            planner_prompt,
            max_tokens=900,
        )
    except LLMError as exc:
        planner_error = str(exc)
        outline_data = _outline_from_records(packed, planner_error)
    outline = _coerce_report_data(outline_data)
    outline_md = _render_report_data(outline)

    writer_prompt = WRITER_TEMPLATE.replace(
        "{{outline}}",
        json.dumps(outline, ensure_ascii=False, separators=(",", ":")),
    )
    try:
        report_data, writer_model = _call_json_candidates(
            api_key,
            base_url,
            "writer",
            writer_prompt,
            max_tokens=1800,
        )
        report = _render_report_data(_coerce_report_data(report_data))
        return _ensure_evidence_links(report, packed)
    except LLMError as exc:
        note = (
            f"> ⚠️ Writer 模型调用失败，已使用 Planner 提纲直接生成报告；"
            f"planner={planner_model}；失败原因：{str(exc)[:180]}"
        )
        if planner_error:
            note = (
                f"> ⚠️ Planner 与 Writer 均未成功，已使用规则提纲生成报告；"
                f"planner_error={planner_error[:120]}；writer_error={str(exc)[:120]}"
            )
        return note + "\n\n" + _ensure_evidence_links(outline_md, packed)


THEME_KEYWORDS = {
    "AI算力链": ("AI", "算力", "GPU", "ASIC", "TPU", "CPO", "光模块", "数据中心"),
    "存储/HBM": ("DRAM", "HBM", "CXL", "存储", "美光", "海力士", "Siri", "苹果"),
    "半导体设备材料": ("半导体", "先进封装", "CoPoS", "台积电", "MLCC", "封装"),
    "港股/中概成长": ("港股", "恒生", "中概", "03121", "03119", "加仓", "加cang"),
    "机器人/端侧AI": ("机器人", "具身", "端侧", "手机", "Siri", "苹果AI"),
    "宏观风险": ("降息", "通胀", "美元", "利率", "关税", "地缘", "风险"),
}


def _theme_counts(records: list[dict[str, Any]], role: str | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        if role and record.get("contextRole") != role:
            continue
        text = f"{record.get('title') or ''} {record.get('text') or ''}"
        for theme, keywords in THEME_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                counts[theme] = counts.get(theme, 0) + 1
    return counts


def _top_themes(records: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counts = _theme_counts(records)
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)[:4] or [("暂无高一致性主题", 0)]


def _outline_from_records(records: list[dict[str, Any]], error: str | None = None) -> dict[str, Any]:
    top = _top_themes(records)
    primary = top[0][0]
    secondary = top[1][0] if len(top) > 1 else "相关产业链"
    evidence_rows = []
    for line in _evidence_lines(records, limit=4):
        match = re.match(r"- \[([ABCD])\] ([^：]+)：(.+?)；链接：(.+)$", line)
        if match:
            evidence_rows.append(
                {
                    "s": match.group(1),
                    "src": match.group(2),
                    "sum": match.group(3),
                    "url": match.group(4),
                }
            )
    return {
        "one": {
            "temp": "中性偏热",
            "risk": "中",
            "pos": "观察为主，小仓试探",
            "conclusion": f"{primary} 是当前最集中的跨来源线索，{secondary} 是第二观察方向。",
            "note": "先看证据是否连续强化，不因单条消息追高。",
            "avoid": "不要把单条热帖当成买入理由。",
        },
        "calls": [
            {"t": primary, "rank": "1", "d": "强化/待确认", "e": "B", "why": "多来源相关信息集中出现", "map": "A股/港股产业链龙头、ETF、核心供应商", "act": "观察"},
            {"t": secondary, "rank": "2", "d": "待确认", "e": "C", "why": "已有主题热度但基本面证据不足", "map": "相关设备、材料、应用链", "act": "等待"},
        ],
        "deep": [
            {"t": primary, "thesis": f"{primary} 是当前最值得优先跟踪的主线。", "bull": "最新信息与滚动上下文共同出现，说明不是单条孤立消息。", "bear": "仍缺少价格、订单或业绩层面的硬验证。", "map": "A股/港股产业链龙头、ETF、核心供应商", "strat": "纳入重点观察池，验证通过后再提高仓位。", "watch": "国内映射标的是否放量、板块是否跑赢。"},
            {"t": secondary, "thesis": f"{secondary} 是第二观察方向。", "bull": "主题已被多条信息提及，具备扩散可能。", "bear": "证据强度弱于第一主线，容易停留在叙事层。", "map": "相关设备、材料、应用链", "strat": "等待确认，不急于追高。", "watch": "订单、价格、财报或政策催化是否出现。"},
        ],
        "plan": [
            {"t": primary, "bucket": "观察/小仓试探", "pos": "轻仓", "entry": "连续两天跨来源强化且国内映射放量", "add": "出现订单、价格、业绩或产业新闻确认", "trim": "高位放量回落或证据降温", "bad": "主题热度下降且无基本面跟进"},
            {"t": secondary, "bucket": "等待", "pos": "观察仓", "entry": "证据从观点层升级到数据/公告层", "add": "国内相关板块开始独立走强", "trim": "只有海外叙事、国内无响应", "bad": "连续多日无新增证据"},
        ],
        "mom": [
            {"t": primary, "chg": "强化/待确认", "drv": "最新信息与滚动上下文共同出现", "watch": "是否继续跨来源出现并获得资金响应"},
            {"t": secondary, "chg": "待确认", "drv": "主题热度进入观察区", "watch": "是否出现订单、价格或财报催化"},
        ],
        "src": [
            {"name": row.get("source") or "未知来源", "stance": "信息源", "theme": primary, "point": (row.get("text") or row.get("title") or "")[:70]}
            for row in records[:6]
        ],
        "risk": [
            {"r": "主题拥挤", "trig": "热点只停留在观点层且涨幅过大", "imp": "情绪交易后回撤", "resp": "等订单/价格/业绩验证"},
            {"r": "映射错配", "trig": "海外叙事强但国内兑现弱", "imp": "A股/港股跟涨失败", "resp": "盯成交额、强弱排序和公司公告"},
        ],
        "ev": evidence_rows,
        "next": [
            {"it": "主题是否继续跨来源出现", "why": "判断动量是否延续", "src": "X/Nitter、微信公众号、微信群归档", "act": "继续强化则保留观察权重，否则降级"},
            {"it": "国内映射是否有资金响应", "why": "判断能否转化为交易机会", "src": "A股/港股成交额、强弱排序、板块涨跌", "act": "放量跑赢则提高关注，否则只做资料跟踪"},
            {"it": "是否出现反向证据", "why": "防止单边叙事误导", "src": "价格回撤、公司澄清、宏观或监管冲击", "act": "出现反证则降低仓位或移出观察池"},
        ],
    }


def _evidence_lines(records: list[dict[str, Any]], limit: int = 6) -> list[str]:
    selected = sorted(
        records,
        key=lambda record: (
            1 if record.get("contextRole") == "latest" else 0,
            _to_int(record.get("heat")),
            len(record.get("text") or ""),
        ),
        reverse=True,
    )[:limit]
    lines: list[str] = []
    for record in selected:
        source = record.get("source") or "未知来源"
        text = (record.get("text") or record.get("title") or "").strip()
        if len(text) > 90:
            text = text[:90] + "…"
        url = record.get("url") or "本地归档"
        strength = "B" if record.get("contextRole") == "latest" else "C"
        lines.append(f"- [{strength}] {source}：{text}；链接：{url}")
    return lines or ["- [D] 暂无可用证据；链接：本地归档"]


def fallback_summary(items: list[dict[str, Any]], error: str) -> str:
    records = _pack(
        items,
        max_items=MAX_ITEMS,
        max_text_len=MAX_TEXT_LEN,
        max_payload_chars=MAX_PAYLOAD_CHARS,
    )
    escaped_error = error.replace("\n", " ")[:220]
    outline = _coerce_report_data(_outline_from_records(records, escaped_error))
    return f"> ⚠️ LLM 调用失败，以下为规则引擎生成的产品化简报；失败原因：{escaped_error}\n\n{_render_report_data(outline)}"

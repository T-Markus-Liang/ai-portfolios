# ai-portfolios / 全球投资动能监控

每天 1 次自动读取 X/Twitter 重点 KOL 的**新增推文**和已配置 RSS/Atom 的文章源，生成面向中国国内资本市场的全球投资动能监控日报，并推送到 Discord 频道。

详细方案见 [`x_mcp_github_actions_investment_brief_plan.md`](./x_mcp_github_actions_investment_brief_plan.md)。

## 数据源（多源 + 自动降级）

1. **Nitter RSS（首选，免费）**：从 `config/sources.yaml` 中的实例列表逐个尝试，第一个返回真 RSS 的实例就用。
2. **twitterapi.io（兜底，付费 / 试用 credit）**：Nitter 全失败时自动降级；需要在环境变量里配 `TWITTERAPI_IO_KEY`。
3. **RSS/Atom 文章源（可选）**：从 `config/article_sources.yaml` 读取文章源；微信公众号需先通过 WeWe RSS / RSSHub 等服务转成 RSS。
4. **Volcengine Ark LLM（总结层）**：若配置了 `ARK_API_KEY`，会把当天新增内容总结成中文简报；失败时自动退回原文模式。

> 公共 Nitter 实例可用性变化频繁（多数实例已加 Anubis / Cloudflare 反爬），多源 + 兜底是必要设计。

## 抓取策略

- **新关注的账号**（`data/last_seen.json` 里无记录）：回溯过去 7 天的推文。
- **已追踪的账号**：只抓 id 大于 `last_tweet_id` 的增量推文（≈ 过去 24 小时）。
- 每次运行结束写回 `data/last_seen.json` 并 commit 回仓库，作为下次运行的基线。

## 触发时间

- 默认每天**北京时间 08:00**自动跑（GitHub Actions cron `0 0 * * *` UTC）。
- 也可在 Actions 页面手动 `Run workflow`。
- 手动触发时可设置 `force_lookback_days`，用于强制回溯 N 天测试 LLM；此模式不会写回 `last_seen.json`。

## 链路

```
Nitter RSS (主) ─┐
twitterapi.io ───┼─► Python (normalize → 增量过滤 → Kimi 合成分析) ─► Markdown/HTML/PDF ─► Discord
文章 RSS/Atom ───┘                                                                    ↓
                                                                          data/last_seen.json (commit 回仓)
```

Kimi 的任务不是逐条复述推文，而是把多个 KOL 的碎片信息合成为“全球领先信号、国内市场映射、研究命题、最大公约数、分歧与反证、证据强度、明日验证清单”。

## 本地运行

1. 装依赖：
   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. 复制 `.env.example` 为 `.env`，至少填 `DISCORD_WEBHOOK_URL`；填了 `TWITTERAPI_IO_KEY` 会自动启用兜底。
3. 如需中文总结，再填：
   - `ARK_API_KEY`
   - `ARK_BASE_URL`（默认 `https://ark.cn-beijing.volces.com/api/coding/v3`）
   - `ARK_MODEL`（当前验证通过 `kimi-k2.6`）
4. 验证 twitterapi.io key（可选）：
   ```bash
   python scripts/ping_twitterapi.py elonmusk
   ```
5. 生成日报：
   ```bash
   python -m src.main
   ```
6. 渲染 HTML + PDF（可选）：
   ```bash
   python scripts/render_report_pdf.py reports/全球投资动能监控二零二六年六月二十一日.md
   ```
7. 推送到 Discord（可选）：
   ```bash
   python scripts/send_discord.py reports/全球投资动能监控二零二六年六月二十一日.pdf --title "Local Test"
   ```

> macOS 本地若开了 Clash 等代理（默认 `127.0.0.1:7893`），可能需要 `export HTTPS_PROXY=http://127.0.0.1:7893` 才能直连。GitHub Actions 不需要代理。

## GitHub Actions Secrets
- `ARK_API_KEY`（必需）：火山方舟 API Key
- `ARK_BASE_URL`（可选）：方舟接口地址，默认 `https://ark.cn-beijing.volces.com/api/coding/v3`
- `ARK_MODEL`（可选）：模型名或推理接入点 ID，默认 `kimi-k2.6`


仓库 Settings → Secrets and variables → Actions：

- `TWITTERAPI_IO_KEY`（可选，仅 Nitter 失败时兜底用）
- `DISCORD_WEBHOOK_URL`（必需）
- `ARK_API_KEY`（可选，启用 LLM 总结）
- `ARK_BASE_URL`（可选，默认值见 `.env.example`）
- `ARK_MODEL`（可选，默认 `kimi-k2.6`）

## KOL 配置

编辑 `config/kol_accounts.yaml`，`handle` 字段写真实 X 用户名（不带 `@`）。

## 文章源配置

编辑 `config/article_sources.yaml`。目前已登记 `投资人六便士`、`击球区小能手1`：

- 如果拿到 WeWe RSS / RSSHub 链接，填入 `rss_url` 并把 `enabled` 改为 `true`，系统会自动增量抓取。
- 如果暂时只有单篇文章链接，放到 `manual_articles`，可补 `title`、`summary`、`published_at`；系统不会请求微信网页，只把你提供的信息送入日报。
- 本地自建 WeWe RSS：先启动 Docker Desktop，再运行 `scripts/start_wewe_rss.sh`，详细步骤见 `docs/integrations/wechat-rss.md`。

## 微信投资群摘要

已配置本地群：`🈲言-2六便士AI吟诗`。本方案只通过 Mac 微信界面复制当前可见消息，不读取/解密微信数据库。

- 自动抓取入口：`scripts/run_wechat_group_sync.sh`
- 原始消息：写入 `data/wechat_groups/inbox/`，默认被 `.gitignore` 忽略。
- 日报素材：写入 `data/wechat_groups/archives/`，以原文归档形式提交到 GitHub；`python -m src.main` 会把它作为 `微信投资群原文` 数据源，统一交给日报 LLM 做交叉验证和 PDF 输出。
- 本地不对微信群消息做 LLM 摘要，避免提前丢失细节。
- 本地索引：写入 `data/wechat_groups/processed/`，默认不提交，避免把逐条消息预览推到 GitHub。
- 首次运行需在 macOS 授权：系统设置 → 隐私与安全性 → 辅助功能，添加并允许 `tools/WeChatGroupCapture.app`（若仍失败，再允许 Terminal/Codex）。

## Nitter 实例配置

编辑 `config/sources.yaml` 的 `nitter_instances`。实例自上而下尝试，第一个返回真 RSS 的就用。当某个实例长期挂掉，把它移到底部或删掉即可。

## twitterapi.io 注意

- 计费：1 USD = 100,000 credits；推文 15 credits/条；最低 15 credits/次（无论是否有数据）。
- QPS：余额 < 1000 credits 时锁定为 1 req/5s；本项目当前以 Nitter 为主，兜底调用极少。
- 当前免费试用 credit ~8746 在本项目稳态用量下可作为长期兜底储备。

## 目录结构

```
config/   监控配置（KOL / Nitter 实例 / 关键词 / 股票池）
src/      主流程
  sources/  数据源适配（nitter.py / twitterapi_io.py / rss_articles.py / types.py）
  fetch_x_data.py  twitterapi.io 底层 HTTP 封装（含 QPS 节流）
  state.py        last_seen 持久化
  main.py         调度入口
scripts/  小工具（ping、Discord 推送）
prompts/  LLM prompt（system.md / daily_brief.md）
data/     last_seen.json + 原始抓取 raw_*.json（raw 被 .gitignore 忽略）
reports/  生成的 markdown 报告（被 .gitignore 忽略）
reports/summaries/  LLM 总结归档（提交到仓库，便于追踪历史观点）
.github/workflows/  定时任务
```

## 后续路线

- 调整 LLM prompt，优化个股信号和预警质量。
- 加入关键词搜索 + 个股代码关联。
- 预警规则（高/中/低优先级）。

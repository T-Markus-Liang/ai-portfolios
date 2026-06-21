# ai-portfolios / x-market-brief

每天两次自动读取 X/Twitter 重点 KOL，生成中文投资情报简报，并推送到 Discord 频道。

详细方案见 [`x_mcp_github_actions_investment_brief_plan.md`](./x_mcp_github_actions_investment_brief_plan.md)。

## 当前阶段

链路打通版（不含 LLM）：

```
twitterapi.io (read-only) → Python → reports/*.md → Discord Webhook
```

GitHub Actions 默认每天**上海时间 08:00 / 20:00**触发，也支持手动触发。

## 本地运行

1. 安装依赖：
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. 复制 `.env.example` 为 `.env`，填入：
   - `TWITTERAPI_IO_KEY`：twitterapi.io 后台的 API Key。
   - `DISCORD_WEBHOOK_URL`：Discord 频道 Webhook URL。
3. 验证 twitterapi.io key：
   ```bash
   python scripts/ping_twitterapi.py elonmusk
   ```
4. 生成一次报告：
   ```bash
   python -m src.main
   ```
   报告写入 `reports/`，原始抓取写入 `data/`。
5. 推送到 Discord：
   ```bash
   python scripts/send_discord.py reports/report_YYYYMMDD_morning.md --title "Local Test"
   ```

## GitHub Actions 配置

在仓库 Settings → Secrets and variables → Actions 中添加：

- `TWITTERAPI_IO_KEY`
- `DISCORD_WEBHOOK_URL`

然后到 Actions 页面手动 `Run workflow` 一次，验证 Discord 是否收到消息。

## KOL 配置

编辑 `config/kol_accounts.yaml`，把 `handle` 字段填成真实 X 用户名（不带 `@`）。
没填 handle 的条目会被跳过。

## 目录结构

```
config/   监控配置（KOL / 关键词 / 股票池）
src/      主流程（抓取、报告生成）
scripts/  小工具（ping、Discord 推送）
prompts/  LLM prompt（后续阶段）
data/     原始抓取（被 .gitignore 忽略）
reports/  生成的 markdown 报告（被 .gitignore 忽略）
.github/workflows/  定时任务
```

## 后续路线

- 接入 LLM（OpenAI）做中文总结、情绪打分、分类。
- 加入关键词搜索、个股关联、预警规则。
- 历史 `last_seen` 通过 commit 回仓或 artifact roundtrip 实现去重。

# Session Log

- Date: 2026-06-21
- Session id: current-thread
- Project: ai-portfolios
- Workspace: /Users/markus/投资组合
- Task: Build global investment momentum monitor for China-market leading signals
- Status: in_progress
- Branch: main

## User request summary

Continue the existing investment brief project, correcting the product positioning from a US growth-stock brief to a global investment momentum monitor that provides leading signals for China domestic capital markets.

## Work done

- Inspected the current multi-source Nitter/twitterapi.io pipeline.
- Validated Ark coding endpoint connectivity with model `kimi-k2.6`.
- Added prompt files and `src/summarize.py`.
- Wired `src/main.py`, workflow env vars, and Discord title output.
- Added KOL handles: Rocky (`Rocky_Bitcoin`), Serenity (`aleabitoreddit`), 潘驴邓晓闲缺一 (`JohnsonZ91127`).
- Added force lookback workflow input, LLM summary archive under `reports/summaries/`, and upgraded Discord-friendly report prompt.
- Added PDF rendering for Discord delivery while keeping Markdown summaries archived.
- Upgraded rendering plan to Markdown -> HTML/CSS -> Chromium PDF, with ReportLab fallback.
- Redesigned prompt around investment synthesis: consensus, disagreement, evidence strength, opportunity matrix, validation checklist.


- Updated `src/main.py` so KOL display names are loaded with handles and passed into flattened LLM items, e.g. `上头资本（@sixpanny159920）`.
- Corrected report positioning from `美股成长股日报` to `全球投资动能监控`.
- Changed generated report/archive Markdown filenames to pure Chinese date names using `全球投资动能监控`.
- Removed the automatically appended `附：原始推文链接` details appendix from final reports.
- Updated `prompts/daily_brief.md` so links only appear in the curated `证据链摘录` section and every KOL with new tweets must be considered or explicitly downgraded.
- Ran `python3 -m py_compile src/main.py src/summarize.py scripts/render_report_pdf.py scripts/send_discord.py`.
- Ran an offline structural validation using sample `上头资本` data; confirmed Chinese filenames, no raw-link appendix, and KOL display name packing.
- Attempted local PDF rendering, but local Python lacks `playwright` and `reportlab`; GitHub Actions installs both, so rendering remains expected to work in CI.
- Updated README, GitHub Actions display name, report title, Discord title, generated filenames, and LLM prompt to emphasize global leading signals mapped back to China domestic capital markets.

- Added `config/article_sources.yaml` with disabled WeChat targets `投资人六便士` and `击球区小能手1`, ready for RSS URLs.
- Added `src/sources/rss_articles.py` to parse generic RSS/Atom article feeds without new dependencies.
- Integrated enabled article feeds into `src/main.py` using the existing state file and LLM content pipeline.
- Updated `src/summarize.py` and `prompts/daily_brief.md` so the LLM can distinguish tweets from articles.
- Updated README with article source setup instructions and the WeChat RSS requirement.
- Verified with `python3 -m py_compile ...` and a mocked RSS feed parsing/flattening check.

- Added manual WeChat article ingestion via `manual_articles` for concrete article URLs when no RSS feed exists.
- Added the two provided article links under `投资人六便士` and `击球区小能手1` in `config/article_sources.yaml`.
- Updated `src/sources/rss_articles.py` to build normalized article items from manual links without fetching WeChat pages.
- Updated `src/main.py` so enabled article sources can combine manual links and RSS feeds, dedupe via state, and avoid repeating the same manual link on later normal runs.
- Verified manual article import with a local check: first run yields two article items; second run with updated state yields zero repeats.

- Researched WeChat article automation options; public Wechat2RSS did not list `投资人六便士` or `击球区小能手1`, so no ready public RSS URL was found.
- Added local WeWe RSS deployment files under `docker/wewe-rss/` using `cooderl/wewe-rss-sqlite:latest`.
- Added `scripts/start_wewe_rss.sh` to start the local WeWe RSS service after Docker Desktop is running.
- Added `docs/integrations/wechat-rss.md` with setup steps: scan WeChat Reading account, add公众号 share links, copy generated RSS URLs into `config/article_sources.yaml`.
- Verified YAML and shell syntax; startup is blocked locally because Docker daemon is not running.

- Started local WeWe RSS successfully after Docker Desktop was opened; service is available at `http://127.0.0.1:4010`.
- Port `4000` was occupied locally, so the compose mapping was changed to host port `4010` while keeping container port `4000`.
- Confirmed `curl -I http://127.0.0.1:4010` returns HTTP 200 and container `ai-portfolios-wewe-rss` is running.

- WeWe RSS feed discovery succeeded: `投资人六便士` -> `MP_WXS_3203395390`, `击球区小能手1` -> `MP_WXS_3198212796`.
- Wrote local RSS URLs into `config/article_sources.yaml` and marked them `local_only: true` so GitHub Actions skips localhost feeds.
- Verified local RSS parsing: `投资人六便士` returned 10 articles; `击球区小能手1` feed currently returned 0 articles.
- Updated `src/main.py` to skip `local_only` article sources when `GITHUB_ACTIONS` is set.

- Updated GitHub Actions schedule to run daily at Beijing 08:00 (`0 0 * * *` UTC).

- Switched the planned local WeChat sync scheduling from launchd to Codex local automations per user preference.
- Kept `scripts/sync_wechat_articles.py` and `scripts/run_wechat_sync.sh` as the reusable sync entrypoint for the Codex automation.
- Updated sync behavior to prefer RSS articles over manual placeholders for the same URL and avoid duplicate records.
- Verified `scripts/run_wechat_sync.sh --no-git` succeeds with 11 unique WeChat article records and no duplicate URLs.


- Added safe Mac WeChat group ingestion for `🈲言-2六便士AI吟诗`: UI/clipboard capture only, no database decryption or Hook path.
- Added `config/wechat_groups.yaml`, `scripts/capture_wechat_group_visible.py`, `scripts/import_wechat_group_clipboard.py`, `scripts/process_wechat_group_inbox.py`, and `scripts/run_wechat_group_sync.sh`.
- Added `src/sources/wechat_groups.py` and wired `src/main.py` so committed daily group archives under `data/wechat_groups/archives/` become a report source named `微信投资群原文`.
- Updated `.gitignore` so raw inbox and local processed previews stay local, while daily raw archives can be committed to GitHub.
- Created Codex local automation `微信群投资情报本地同步` (`automation-2`) at Beijing 08:20, 12:20, 18:20, 22:20 to run the group sync script and push raw archive updates.
- Verified Python compilation and simulated summary ingestion; removed simulated raw and summary data before committing.
- Direct UI capture test is blocked until macOS grants Accessibility permission to Terminal/Codex/osascript.


- After the user granted Terminal Accessibility, live `osascript` capture still reported macOS assistive access denial, likely because Codex/osascript needs separate Accessibility permission.
- Used the visible WeChat window as a one-time safe source to seed a concise group intelligence summary, then regenerated it through `.venv` with Ark/Kimi.
- Updated `scripts/process_wechat_group_inbox.py` to load `.env`, strip accidental Markdown code fences, and constrain group-summary output length.
- Updated `scripts/run_wechat_group_sync.sh` to prefer `.venv/bin/python` so scheduled runs can access installed dependencies and `.env` loading.
- Prepared `data/wechat_groups/summaries/2026-06-21_微信投资群情报摘要.md` for GitHub as the report-consumable group-summary source; raw inbox and processed preview remain local/ignored.


- Investigated macOS Accessibility issue: Terminal, Codex, and Codex Computer Use are enabled, but `/usr/bin/osascript` remains hidden in System Settings and cannot directly control WeChat via System Events.
- Added a visible helper app `tools/WeChatGroupCapture.app` plus source `tools/WeChatGroupCapture.applescript` so the user can grant Accessibility permission to a named local app instead of invisible `osascript`.
- Updated `scripts/capture_wechat_group_visible.py` to prefer the helper app and use a sentinel clipboard value to avoid false failures when the clipboard already contains WeChat content.


- User clarified WeChat group sync should copy raw group messages to GitHub and should not run local LLM summarization; the daily report LLM will handle all cross-source synthesis later.
- Reworked WeChat group pipeline from `summaries/` to `archives/`: `scripts/process_wechat_group_inbox.py` now writes raw daily Markdown archives with front matter, keywords, and original message text.
- Updated `src/sources/wechat_groups.py` and `src/main.py` to read `data/wechat_groups/archives/` as `微信投资群原文` with content type `wechat_group_archive`.
- Updated `scripts/run_wechat_group_sync.sh`, `.gitignore`, `README.md`, `config/wechat_groups.yaml`, and Codex automation `automation-2` to commit raw archives and avoid local LLM summaries.
- Imported the user-provided recent group messages into `data/wechat_groups/archives/2026-06-22_微信群原文归档.md`; removed the old generated summary file from Git tracking.
- Verified `FORCE_LOOKBACK_DAYS=1 .venv/bin/python -m src.main` sees one `wechat_group_archive` item from `微信投资群原文` with 2542 characters.

## Decisions

- Use the Ark coding endpoint `https://ark.cn-beijing.volces.com/api/coding/v3`.
- Use a two-stage LLM pipeline: `kimi-k2.7-code`/compatible deeper models for planning, faster models such as `minimax-m3` for final writing.
- Keep graceful degradation: if LLM fails, still send the raw tweet report.
- Include source hit counts in the Discord title for quick diagnostics.

## Current state

- Prompt and summarizer modules exist.
- Main orchestration calls the summarizer and emits a Chinese source-aware Discord title under `全球投资动能监控`.
- Current KOL config has seven real X accounts.
- Article source config has `投资人六便士` and `击球区小能手1` enabled with one manual WeChat article link each; RSS URLs can be added later for automation.
- KOL display names are included in LLM inputs, so `上头资本（@sixpanny159920）` is visible when that account has new tweets.
- Reports no longer append the raw tweet link appendix; curated links remain only in `证据链摘录`.
- Latest Actions run showed `nitter:7`, then `0 新` after `last_seen` was persisted. Use `force_lookback_days` for manual LLM testing.

## Resume instructions

- Read `src/main.py`, `src/sources/wechat_groups.py`, `scripts/run_wechat_group_sync.sh`, `src/summarize.py`, `.github/workflows/market-brief.yml`, and `README.md`.
- Ensure GitHub Secrets include `ARK_API_KEY`, `ARK_BASE_URL`, `ARK_PLANNER_MODEL`, `ARK_WRITER_MODEL`, and `DISCORD_WEBHOOK_URL`.
- Manually trigger `全球投资动能监控` in GitHub Actions and inspect Discord output.

## Open questions

- Local WeWe RSS URLs are configured and Codex automation syncs articles multiple times per day.
- Mac WeChat group UI capture automation is configured, but first live run requires macOS Accessibility permission for Terminal/Codex/osascript if not already granted.

- Investigated the 2026-06-23 afternoon Discord PDF: PDF delivery worked, but the report fell back to raw mode because Ark/Kimi returned empty or incomplete LLM content.
- Reworked `src/summarize.py` for stable production summaries: short embedded investment prompt, compact per-source packing, priority scoring for WeChat archives/articles/AI hardware keywords, and retry with a smaller payload.
- Added WeChat group archive excerpting so noisy service-guide text is dropped and investment messages such as Apple AI -> DRAM/HBM demand and `03121加cang至7%` reach the main LLM synthesis.
- Added report completeness validation requiring all expected Markdown sections and the investment-disclaimer footer; incomplete or empty model output now retries instead of silently becoming a broken investment brief.
- Verified locally with `.venv` and Ark/Kimi using historical raw data and `FORCE_LOOKBACK_DAYS=1 .venv/bin/python -m src.main`; generated an analysis-mode report containing `一页结论`, `今日最大公约数`, `机会线索矩阵`, `分歧与风险`, `证据链摘录`, and `明日行动清单`.
- Verified PDF rendering path locally with `.venv/bin/python scripts/render_report_pdf.py`; local Playwright browser is not installed so fallback PDF rendered, while GitHub Actions installs Chromium and should use the HTML/Chromium path.

- User reported Codex cron automations were creating many visible sidebar threads.
- Confirmed current Codex cron automations run as standalone local job threads; there were repeated visible threads for `微信公众号文章本地同步` and `微信群原文归档本地同步`.
- Added `scripts/run_automation_job.sh`, a minimal wrapper for `wechat_articles` and `wechat_group` jobs. It captures stdout/stderr, appends a compact row to `docs/automation-runs.md`, commits/pushes the run ledger, and preserves the underlying script exit code.
- Created `docs/automation-runs.md` as the unified automation run ledger so future results can be reviewed in one document instead of opening per-run threads.
- Updated both Codex automations to call the wrapper and instruct each run to report only the ledger path and archive the run thread afterward.
- Archived prior visible automation run threads for the two WeChat sync jobs to reduce sidebar clutter.

- Audited `docs/automation-runs.md` on 2026-06-24 after the overnight automation window. The ledger was still empty, so the local cron automations did not successfully reach `scripts/run_automation_job.sh`.
- Inspected Codex automation session JSONL logs for `019ef4d2-3fdc-7f01-a9b4-382c867587b9` and `019ef4db-67d0-7563-bbae-9678ca021dc2`: both sessions contain only startup/user prompt/task_complete records and no assistant/tool execution records, ending with `last_agent_message: null`.
- Manually verified `NO_GIT=1 scripts/run_automation_job.sh wechat_articles` succeeds and writes a row to `docs/automation-runs.md`; reverted the manual test row afterward so the ledger remains reserved for real scheduled runs.
- Updated both Codex automations from model `gpt-5.4-mini` to the configured local default `gpt-5.4`, because the machine's active provider config is `local-qwen-rapid` with default model `gpt-5.4` and the automation sessions appeared to stall before execution.
- Archived the two failed automation threads to keep the sidebar clean.

- Investigated the LLM analysis chain on 2026-06-24: a direct Ark/Kimi call using the latest raw data could hang without a client timeout, and the main report only called LLM when the current run had new items.
- Updated `src/main.py` so reports pass both latest items and a deduplicated rolling recent context window into the LLM. If the day has `0 新` but recent raw files exist, the report can still produce market momentum, risk, and strategy analysis.
- Updated `src/summarize.py` to use the new report structure: `市场动量总览`, `动量变化`, `风险雷达`, `交易策略`, `证据链摘录`, and `明日验证`.
- Added Ark client timeout via `ARK_TIMEOUT_SECONDS` defaulting to 75 seconds, smaller first/retry payloads, retry-on-network-timeout behavior, and report normalization for model outputs that are structurally complete but missing the disclaimer.
- Added deterministic `fallback_summary()` so a failed LLM call still produces a usable rule-based market momentum/risk/strategy brief instead of falling back to raw-only text.
- Added evidence-link post-processing so model outputs that summarize evidence without URLs are replaced with selected source excerpts containing links/local archive references.
- Verified with `python3 -m py_compile src/main.py src/summarize.py`, rule-based fallback checks, PDF rendering from generated Markdown, and a real Ark/Kimi call that returned an 868-character analysis report after the prompt/payload changes.

- Productized the final PDF report format on 2026-06-24 after user requested a report suitable for both professional and ordinary investors.
- Added `docs/report-product-spec.md` to freeze the product positioning, fixed report directory, analysis chain, LLM context-control rules, structured intermediate layer, and future chart/scoring upgrades.
- Reworked `src/summarize.py` so the LLM now outputs compact structured JSON instead of free-form Markdown. The code renders that JSON into a fixed report template: one-page decision dashboard, key calls, momentum map, logic chains, opportunity matrix, risk radar, evidence excerpts, and tomorrow checklist.
- Added compatibility for shortened model JSON keys and imperfect model schemas, because Ark/Kimi sometimes returns simplified keys even when prompted with a full schema.
- Reduced LLM input payload and disabled SDK retries with `max_retries=0`; default `ARK_TIMEOUT_SECONDS` is now 45 seconds so GitHub Actions does not stall on slow model responses.
- Kept a same-template rule-based fallback so even when LLM times out or returns truncated JSON, the PDF still has the productized directory and a usable market momentum/risk/strategy skeleton.
- Updated `scripts/render_report_pdf.py` so new report metadata fields (`新增内容`, `滚动上下文`) render as cover pills in HTML/PDF.
- Updated `.github/workflows/market-brief.yml` to pass `ARK_TIMEOUT_SECONDS`, and updated `README.md` with the productized PDF flow and context-length strategy.
- Verified with Python compilation, short-schema rendering checks, full local `python -m src.main`, and PDF rendering to `/tmp/product_report_final.pdf`. Local Playwright browser is still missing, so local render used ReportLab fallback; GitHub Actions installs Chromium and should use the HTML/CSS path.

- Split the Ark LLM chain into two layers on 2026-06-26: Planner model builds the report outline/core points, Writer model turns the outline into final report JSON.
- Set defaults to `ARK_PLANNER_MODEL=kimi-k2.7-code` and `ARK_WRITER_MODEL=minimax-m3`, with Planner fallback `minimax-m3` and Writer fallbacks `doubao-seed-2.0-lite,deepseek-v4-flash`.
- Added role-specific timeouts: `ARK_PLANNER_TIMEOUT_SECONDS=20` and `ARK_WRITER_TIMEOUT_SECONDS=45`.
- Disabled JSON mode by default for `minimax-m3` and `deepseek-v4-flash`, because Ark tests showed these models either perform better without JSON mode or do not support `response_format`.
- Added schema validation for candidate model output: valid JSON without the required report fields no longer counts as success.
- Updated `.github/workflows/market-brief.yml`, `.env.example`, `README.md`, and `docs/report-product-spec.md` to document the two-stage Planner/Writer pipeline.

- Reviewed the generated 2026-06-26 PDF and confirmed the pipeline worked but the report still looked like a thin skeleton: fixed sections were present, yet decision advice, argument/evidence chains, source coverage, and action rules were not strong enough for a professional investment report.
- Upgraded `src/summarize.py` report schema from summary-oriented fields to productized decision fields: `one_page`, `key_calls`, `deep_dives`, `action_plan`, `momentum_table`, `source_view`, `risk_radar`, `evidence`, and `tomorrow`.
- Changed the fixed PDF directory to `一页决策总览`, `今日核心判断`, `主线深度拆解`, `机会与仓位建议`, `市场动量与分歧`, `风险与证伪`, `证据链`, and `明日行动清单`.
- Expanded Planner input packing from a very small sample to up to 18 high-weight records so the system can cover fewer-than-20 monitored X/blogger sources instead of over-compressing.
- Added automatic schema backfill so partial model JSON still renders complete decision sections rather than empty tables.
- Updated `scripts/render_report_pdf.py` to render third-level headings such as `来源分布`.
- Updated `README.md` and `docs/report-product-spec.md` to freeze the report v2 structure and analysis logic.
- Verified with Python compilation, structured rendering checks, and a local report/PDF generation smoke test. Local Ark call hit connection fallback, but the fallback report now uses the upgraded productized structure.

- Reviewed the latest 2026-06-26 `-3` PDF and found the v2 structure rendered, but it still exposed model timeout/response diagnostics in the cover and used overly wide tables for main-line analysis.
- Hid detailed LLM/API diagnostics from the formal PDF; failures now print to GitHub Actions stderr while the report only shows a concise downgrade note.
- Reduced Planner input from 18 to 14 records and shortened per-item text to reduce Ark timeout risk while still preserving one high-value item per source.
- Increased default Ark role timeouts to Planner 35 seconds and Writer 60 seconds in code, `.env.example`, workflow, and README.
- Converted `主线深度拆解` and `机会与仓位建议` from wide tables into card-style Markdown sections for better PDF readability.
- Added source-balanced evidence selection and per-record theme detection so `来源分布` and `证据链` are less dominated by one account/theme.

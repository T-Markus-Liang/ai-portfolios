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

- Use `kimi-k2.6` on `https://ark.cn-beijing.volces.com/api/coding/v3`.
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
- Ensure GitHub Secrets include `ARK_API_KEY`, `ARK_BASE_URL`, `ARK_MODEL`, and `DISCORD_WEBHOOK_URL`.
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

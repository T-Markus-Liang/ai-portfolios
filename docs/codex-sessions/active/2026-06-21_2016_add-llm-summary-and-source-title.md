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

- Read `src/main.py`, `src/summarize.py`, `.github/workflows/market-brief.yml`, and `README.md`.
- Ensure GitHub Secrets include `ARK_API_KEY`, `ARK_BASE_URL`, `ARK_MODEL`, and `DISCORD_WEBHOOK_URL`.
- Manually trigger `全球投资动能监控` in GitHub Actions and inspect Discord output.

## Open questions

- Local WeWe RSS URLs are configured. For GitHub Actions automation, deploy WeWe RSS to a public HTTPS endpoint or keep using manual articles for cloud runs.

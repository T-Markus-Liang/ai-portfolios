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

## Decisions

- Use `kimi-k2.6` on `https://ark.cn-beijing.volces.com/api/coding/v3`.
- Keep graceful degradation: if LLM fails, still send the raw tweet report.
- Include source hit counts in the Discord title for quick diagnostics.

## Current state

- Prompt and summarizer modules exist.
- Main orchestration calls the summarizer and emits a Chinese source-aware Discord title under `全球投资动能监控`.
- Current KOL config has seven real accounts.
- KOL display names are included in LLM inputs, so `上头资本（@sixpanny159920）` is visible when that account has new tweets.
- Reports no longer append the raw tweet link appendix; curated links remain only in `证据链摘录`.
- Latest Actions run showed `nitter:7`, then `0 新` after `last_seen` was persisted. Use `force_lookback_days` for manual LLM testing.

## Resume instructions

- Read `src/main.py`, `src/summarize.py`, `.github/workflows/market-brief.yml`, and `README.md`.
- Ensure GitHub Secrets include `ARK_API_KEY`, `ARK_BASE_URL`, `ARK_MODEL`, and `DISCORD_WEBHOOK_URL`.
- Manually trigger `全球投资动能监控` in GitHub Actions and inspect Discord output.

## Open questions

- Need one GitHub Actions manual run with `force_lookback_days=1` to verify Discord attachment uses the `全球投资动能监控` filename and China-market-oriented synthesis prompt.

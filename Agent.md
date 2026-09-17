# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the project root (module paths depend on it).

```powershell
pip install -r requirements.txt

# Full app: FastAPI + Gradio chat mounted at /chat (http://127.0.0.1:8000/chat)
python -m src.main

# Gradio UI only (no FastAPI endpoints)
python -m src.ui.chatbotui

# Run a specialist agent directly from the CLI (fastest way to debug tools/prompts)
python -m src.agents.anamoly_agent 1001
python -m src.agents.anamoly_agent 1001 --model llama-3.3-70b-versatile
python -m src.agents.financerecon_agent 1001
```

Rebuilding the mock database. The loader uses plain `INSERT` with no truncate or `OR REPLACE`, and `main()` only creates the schema when `vendor_agreement.db` is absent — so running it against the committed DB fails with `sqlite3.IntegrityError` on the `Vendor` primary keys. Deleting the file first is mandatory, and gives a fresh set of random data. These scripts import each other by bare module name, so they must be run from inside `mockup_db/`:

```powershell
cd mockup_db
Remove-Item vendor_agreement.db   # required, otherwise the load fails
python mockup_data_load.py        # schema (if needed) + all mock data
python DB_schema.py               # schema only
python export_to_csv.py           # dump every table to csv_exports/ for inspection
```

There is no test runner, linter, or CI configured. [test/demo_test.py](test/demo_test.py) and [src/node/sample.py](src/node/sample.py) are empty placeholders, and pytest is not in `requirements.txt`.

## Configuration

`.env` at the project root is loaded by [src/settings/config.py](src/settings/config.py) into a pydantic-settings `Config` singleton imported as `from src.settings.config import config`. `OPENAI_API_KEY` is **required** — importing anything that transitively imports `config` raises a validation error without it. See [.env.example](.env.example) for the full set.

That module also calls `truststore.inject_into_ssl()` at import time so SSL verification uses the Windows certificate store rather than certifi. This is needed behind a TLS-inspecting corporate proxy; do not remove it, and keep `src.settings.config` imported early (ahead of HTTP clients) in any new entrypoint.

## Architecture

Three layers, each a plain function boundary — no shared state or session store.

**Tools** ([src/tools/](src/tools/)) — LangChain `@tool` functions, each with an explicit pydantic `args_schema`. Every one opens its own short-lived `sqlite3.connect(DB_FILE)` against `mockup_db/vendor_agreement.db` (resolved via `Path(__file__).resolve().parents[2]`, so it works regardless of cwd), runs one parameterized aggregate query, and returns plain `float` / `list[dict]`. Tool docstrings and `Field` descriptions are load-bearing: they are the only thing the LLM sees when deciding how to call them.

**Specialist agents** ([src/agents/anamoly_agent.py](src/agents/anamoly_agent.py), [src/agents/financerecon_agent.py](src/agents/financerecon_agent.py)) — each is a LangGraph `create_react_agent` over a fixed tool list, driven by a long `SYSTEM_PROMPT` that spells out a numbered, strictly ordered procedure. The comparison logic itself lives in the prompt, not in Python: the tools only fetch numbers, and the LLM does the reconciliation and writes the report. Changing detection behavior usually means editing `SYSTEM_PROMPT`, not the tools. Both are always built with openai at `temperature=0` and are rebuilt per call (`run_anomaly_check` / `run_financerecon_check`).

**Orchestrator** ([src/agents/chatbot_agent.py](src/agents/chatbot_agent.py)) — a second react agent whose two tools (`check_allowance_anomaly`, `check_finance_reconciliation`) simply wrap the specialist `run_*` functions, so an agent-in-agent call happens on every routed request. Unlike the specialists, this one supports both providers (`openai`|groq` | `claude`, chosen per-request via the UI dropdown, defaulting to `config.DEFAULT_LLM_PROVIDER`) and caches one built agent per provider in the module-level `_agents` dict.

**Guardrails** ([src/agents/guardrails.py](src/agents/guardrails.py)) — regex-only PII and prompt-injection screening. `check_input` runs in `handle_user_message` *before* the agent is invoked; a block returns a canned refusal and no LLM call is made. This is the single choke point for user input, and it only covers the chat path — the FastAPI `/anomaly-check` and `/finance-recon` endpoints bypass it (they take an int, not free text).

**Entrypoints** — [src/main.py](src/main.py) builds the FastAPI app and mounts the Gradio `demo` object imported from [src/ui/chatbotui.py](src/ui/chatbotui.py) at `/chat`; the two POST endpoints call the specialist agents directly, skipping the orchestrator. Both `main.py` and `chatbotui.py` prepend the project root to `sys.path` at import so `src.*` resolves under `python file.py`, `python -m`, and uvicorn's `--reload` subprocess. There are no `__init__.py` files — everything relies on implicit namespace packages.

`handle_user_message(message, history, provider)` converts Gradio history to `(role, content)` tuples and replays the whole list into the agent on every turn — conversation state is carried entirely by the client.

## Mock data

`mockup_db/vendor_agreement.db` is committed and is the only data source. `mockup_db/csv_exports/` holds a committed dump of every table, so current data can be inspected without opening SQLite — but it is only as fresh as the last `export_to_csv.py` run. Schema in [mockup_db/vendor_agreement_schema.sql](mockup_db/vendor_agreement_schema.sql); column names contain typos that are part of the schema and must be matched exactly in queries (`canculated_amt`, `transacion_id`, `Jorunal_date`, `last_changed_iser_id`).

How [mockup_db/mockup_data_load.py](mockup_db/mockup_data_load.py) generates data determines what the agents can actually find, so it matters when interpreting results:

- Agreement ids are `1001`–`1010`; `Vendor.Agreement_type` is randomly `SALE` or `RECV`.
- `Agreement_allowance_history` is the seed table. `Sales_item_store_history` rows are derived from it **only for `SALE` agreements**, copying `item_nbr`/`store_nbr`/`sales_date`/`quantity`/`item_cost` across. A `RECV` agreement therefore has no sales rows at all, so the anomaly agent computes a sales-derived allowance of 0 against a non-zero recorded amount and always reports a large "anomaly" — that is a data artifact, not a bug.
- `SAP_Invoice_history` is copied 1:1 from `Agreement_bill_history` with identical amounts and dates, so finance reconciliation reports a clean match for every agreement unless rows are edited by hand.
- `ALLOWANCE_HISTORY_START_DATE` is hardcoded to `2026-08-11` while `Vendor` agreement start/end dates are randomized relative to `date.today()`. If today's date falls outside that window the agreement date range won't overlap the allowance/sales rows and sales-based totals come back 0.

## Known inconsistencies

Docstrings in [src/agents/chatbot_agent.py](src/agents/chatbot_agent.py) reference `src.agent.guardrails`; the actual package is `src.agents`. The filename `anamoly_agent.py` and [src/tools/allownce_history.py](src/tools/allownce_history.py) are both misspelled — keep imports matching the files on disk.

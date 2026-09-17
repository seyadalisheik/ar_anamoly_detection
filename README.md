# AR Allowance Anomaly Detection

Prototype application for detecting accounts receivable allowance anomalies in
vendor agreements and reconciling agreement bill history against SAP invoice
history.

The solution combines a FastAPI service, a Gradio chat UI, LangGraph/LangChain
agents, and read-only tools over a mock SQLite database. The current code is a
working prototype, not a production posting system. The LLM is used to route,
explain, and summarize findings; authoritative financial calculations and any
future correction workflow should be implemented in deterministic services with
explicit controls.

## Business Problem

Vendor allowance agreements can create revenue leakage or close delays when
recorded allowance activity does not match the underlying sales, receiving,
billing, or SAP records. This prototype demonstrates two core workflows:

- **Allowance anomaly detection**: compare calculated allowance amounts from
  sales activity against recorded allowance history for a vendor agreement.
- **Finance reconciliation**: compare agreement bill amounts against SAP invoice
  amounts by date and report missing or mismatched entries.

## Architecture

```text
User
  |-- Gradio chat UI (/chat)
  |     |-- chatbot orchestrator agent
  |           |-- allowance anomaly specialist agent
  |           |-- finance reconciliation specialist agent
  |
  |-- FastAPI endpoints
        |-- /anomaly-check
        |-- /finance-recon

Agents -> LangChain tools -> mockup_db/vendor_agreement.db
```

Key modules:

- `src/main.py`: FastAPI entrypoint and Gradio mount at `/chat`.
- `src/ui/chatbotui.py`: Gradio chat interface with provider/model selection.
- `src/agents/chatbot_agent.py`: orchestrator that routes user requests to the
  specialist agents.
- `src/agents/anamoly_agent.py`: allowance anomaly specialist agent.
- `src/agents/financerecon_agent.py`: finance reconciliation specialist agent.
- `src/agents/guardrails.py`: regex-based PII and prompt-injection screening
  for the chat path.
- `src/tools/`: LangChain tools that query SQLite and return structured
  results to the agents.
- `mockup_db/`: mock schema, committed SQLite database, data loader, and CSV
  exports.

## Runtime Requirements

- Python 3.10+
- A valid `.env` file at the repository root
- `GROQ_API_KEY` is required by configuration import, even when experimenting
  with Claude or OpenAI as the selected provider
- Optional API keys for Anthropic Claude and OpenAI

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create local configuration:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with the required provider keys:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_LLM_MODEL=llama-3.3-70b-versatile

CLAUDE_API_KEY=
CLAUDE_LLM_MODEL=claude-opus-5

OPENAI_API_KEY=
OPENAI_LLM_MODEL=gpt-4o-mini

DEFAULT_LLM_PROVIDER=groq
```

`src/settings/config.py` injects the Windows certificate store through
`truststore`. Keep that import path in place for environments behind corporate
TLS inspection.

## Running the Application

Run the full FastAPI application and mounted chat UI:

```powershell
python -m src.main
```

Open:

```text
http://127.0.0.1:8000/chat
```

Run only the Gradio UI:

```powershell
python -m src.ui.chatbotui
```

Run specialist agents directly:

```powershell
python -m src.agents.anamoly_agent 1001
python -m src.agents.financerecon_agent 1001
```

## API Usage

Allowance anomaly check:

```curl
curl -X POST http://127.0.0.1:8000/anomaly-check \
  -H "Content-Type: application/json" \
  -d '{"agreement_id":1001}'
```

Finance reconciliation:

```curl
curl -X POST http://127.0.0.1:8000/finance-recon \
  -H "Content-Type: application/json" \
  -d '{"agreement_id":1001}'
```

## Mock Data

The committed SQLite database is:

```text
mockup_db/vendor_agreement.db
```

CSV exports are available under:

```text
mockup_db/csv_exports/
```

The mock loader creates agreement ids `1001` through `1010`. It randomizes
several values, so regenerated data will not exactly match the committed
database.

Important data caveats:

- `Agreement_allowance_history` is the seed table for allowance activity.
- Sales rows are generated only for `SALE` agreements.
- Receiving rows are generated only for `RECV` agreements.
- The current anomaly agent compares allowance records to sales history. For
  `RECV` agreements, sales-derived totals can be zero by design, which may look
  like an anomaly even though it is a mock-data artifact.
- `SAP_Invoice_history` is generated from `Agreement_bill_history` with matching
  dates and amounts, so finance reconciliation is expected to be clean unless
  data is edited.
- Some schema column names contain typos and must be referenced exactly, such as
  `canculated_amt`, `transacion_id`, `Jorunal_date`, and
  `last_changed_iser_id`.

To rebuild the mock database from scratch:

```powershell
cd mockup_db
Remove-Item vendor_agreement.db
python mockup_data_load.py
python export_to_csv.py
```

The loader does not truncate existing rows. Delete the database first, or the
load will fail on primary key collisions.

## Current Guardrails

The chat UI runs `check_input()` before invoking an agent. It blocks common PII
patterns and direct prompt-injection phrases.

The typed FastAPI endpoints accept only an integer `agreement_id` and call the
specialist agents directly. They do not use the chat guardrail path.

## Current Limitations

- Reconciliation logic is largely prompt-driven. Tools fetch data, while the LLM
  performs comparison and narrative reporting.
- There is no persistence layer for user sessions or prior agent runs.
- There is no test runner, lint configuration, CI pipeline, or production
  packaging.
- Specialist agents are rebuilt per direct run. The chatbot orchestrator caches
  agents by provider/model.
- No automatic correction or posting is implemented.
- `test/demo_test.py` and `src/node/sample.py` are placeholders.

## Production Hardening Direction

For a production AR anomaly solution, keep the current modular agent pattern but
move control-critical work out of prompts:

- Implement deterministic reconciliation services for allowance, receiving,
  billing, journal, and SAP matching.
- Add tolerance rules, materiality thresholds, exception categories, and
  agreement-type-specific logic.
- Persist findings, evidence, approvals, and correction proposals.
- Introduce role-based approval workflows before any financial correction.
- Add idempotent execution for safe technical retries only.
- Add audit logs, observability, automated tests, and data quality checks.
- Use the LLM only for orchestration, explanation, evidence summarization, and
  user-facing investigation support.

## Repository Notes

The project intentionally keeps file names as they exist on disk. Some names are
misspelled, including `anamoly_agent.py` and `allownce_history.py`; imports must
continue to match those file names unless the codebase is refactored together.

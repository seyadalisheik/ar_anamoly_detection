# Test Results and Coverage Report

Generated on: 2026-09-17  
Repository: `ar_anamoly_detection`  
Command executed:

```powershell
python -m pytest
```

## Executive Summary

| Metric | Result |
| --- | ---: |
| Test status | Passed |
| Total tests collected | 37 |
| Total tests passed | 37 |
| Total tests failed | 0 |
| Total tests skipped | 0 |
| Runtime | 72.00 seconds |
| Coverage threshold | 90.00% |
| Actual coverage | 98.50% |
| Coverage gate | Passed |

## Test Results by File

| Test file | Tests | Result |
| --- | ---: | --- |
| `test/test_chatbot_agent.py` | 10 | Passed |
| `test/test_db_schema.py` | 2 | Passed |
| `test/test_guardrails.py` | 12 | Passed |
| `test/test_specialist_agents.py` | 9 | Passed |
| `test/test_tools.py` | 4 | Passed |

## Coverage Details

| Source file | Statements | Missed | Coverage | Missing lines |
| --- | ---: | ---: | ---: | --- |
| `mockup_db/DB_schema.py` | 24 | 0 | 100% | |
| `src/agents/anamoly_agent.py` | 45 | 0 | 100% | |
| `src/agents/chatbot_agent.py` | 113 | 5 | 96% | 122-130 |
| `src/agents/financerecon_agent.py` | 44 | 1 | 98% | 87 |
| `src/agents/guardrails.py` | 30 | 0 | 100% | |
| `src/settings/config.py` | 17 | 0 | 100% | |
| `src/tools/allownce_history.py` | 51 | 0 | 100% | |
| `src/tools/bill_history.py` | 29 | 0 | 100% | |
| `src/tools/sales_history.py` | 46 | 0 | 100% | |
| **TOTAL** | **399** | **6** | **98%** | |

Coverage plugin reported:

```text
Required test coverage of 90.0% reached. Total coverage: 98.50%
```

## Coverage Configuration

Coverage is configured in `.coveragerc`.

Included source roots:

```ini
source =
    src
    mockup_db
```

Ignored files and paths:

| Omitted path | Reason |
| --- | --- |
| `*/__pycache__/*` | Generated Python bytecode cache |
| `src/ui/chatbotui.py` | UI construction around Gradio components; best covered through integration/smoke tests |
| `src/main.py` | App server bootstrap and route mounting; best covered by API integration tests |
| `src/node/sample.py` | Empty placeholder |
| `mockup_db/mockup_data_load.py` | Randomized data generation script; deterministic unit coverage would be low-value |
| `mockup_db/export_to_csv.py` | File export utility; better covered by focused integration/file-system tests if needed |

Coverage gate:

```ini
[report]
fail_under = 90
show_missing = True
skip_empty = True
```

## Test Scope

The current test suite covers:

- SQLite query tools for allowance history, sales history, and bill/SAP history.
- Guardrail PII and prompt-injection detection.
- Chatbot orchestration behavior, including message history handling, guardrail blocking, provider fallback, and agent cache behavior.
- Specialist agent construction and execution wiring without making real LLM or network calls.
- Database schema creation and table-list logging.

## Notable Implementation Finding

The tests identified and fixed a guardrail bug where phone numbers in the common format `(312) 555-1212` were not detected. The phone regex in `src/agents/guardrails.py` now supports that format.

## Reproduction

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run tests with coverage:

```powershell
python -m pytest
```

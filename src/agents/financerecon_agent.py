"""
LangChain/LangGraph agent (Groq LLM) that reconciles vendor agreement bill
amounts against SAP invoice bill amounts for a given agreement.

The agent compares, per bill date, the Bill_amount recorded in
Agreement_bill_history against the SAP_Bill_amount recorded in
SAP_Invoice_history, and reports any deviations as anomalies for the
business team.
"""
import argparse
import logging

from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.settings.config import config
from src.tools.bill_history import get_bill_amount_by_date, get_sap_bill_amount_by_date

logger = logging.getLogger(__name__)

DEFAULT_MODEL = config.GROQ_LLM_MODEL

SYSTEM_PROMPT = """\
You are a finance reconciliation agent for vendor agreement billing. Given an
agreement id, follow these steps exactly, using the available tools, and do
not skip or reorder any step:

Step 1: Call get_bill_amount_by_date with the agreement id to get the
Bill_amount for the agreement for each Bill_date, from Agreement_bill_history.

Step 2: Call get_sap_bill_amount_by_date with the agreement id to get the
SAP_Bill_amount for the agreement for each SAP_Bill_date, from
SAP_Invoice_history.

Step 3: Compare the two datasets by matching Bill_date to SAP_Bill_date, and
check for any deviations (missing dates on either side, or amounts that do
not match) between Bill_amount and SAP_Bill_amount.

Step 4: If there are any deviations, generate a summary report for the
business team that clearly lists, for each mismatched date: the date,
Bill_amount, SAP_Bill_amount, and the difference. If there are no
deviations, report that the agreement's bills reconcile cleanly and include
the total Bill_amount and total SAP_Bill_amount as supporting data points.

Always present your final answer as a clear, structured summary.
"""

TOOLS = [
    get_bill_amount_by_date,
    get_sap_bill_amount_by_date,
]


def build_financerecon_agent(provider: str = None, model: str = None):
    """
    Build and return the finance reconciliation agent.
    
    Args:
        provider: "groq", "claude", or "openai" (defaults to config.DEFAULT_LLM_PROVIDER)
        model: specific model to use (uses provider defaults if not specified)
    """
    if provider is None:
        provider = config.DEFAULT_LLM_PROVIDER
    
    if provider.lower() == "claude":
        if model is None:
            model = config.CLAUDE_LLM_MODEL
        try:
            llm = ChatAnthropic(
                model=model,
                api_key=config.CLAUDE_API_KEY,
                timeout=30.0,
            )
            logger.info(f"Initialized Claude LLM with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize Claude: {e}")
            logger.info("Falling back to Groq LLM")
            llm = ChatGroq(
                model=config.GROQ_LLM_MODEL,
                api_key=config.GROQ_API_KEY,
                temperature=0
            )
    elif provider.lower() == "openai":
        if model is None:
            model = config.OPENAI_LLM_MODEL
        try:
            llm = ChatOpenAI(
                model=model,
                api_key=config.OPENAI_API_KEY,
                temperature=0,
            )
            logger.info(f"Initialized OpenAI LLM with model: {model}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            logger.info("Falling back to Groq LLM")
            llm = ChatGroq(
                model=config.GROQ_LLM_MODEL,
                api_key=config.GROQ_API_KEY,
                temperature=0
            )
    else:  # default to groq
        if model is None:
            model = config.GROQ_LLM_MODEL
        llm = ChatGroq(
            model=model,
            api_key=config.GROQ_API_KEY,
            temperature=0
        )
        logger.info(f"Initialized Groq LLM with model: {model}")
    
    return create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)


def run_financerecon_check(agreement_id: int, provider: str = None, model: str = None) -> str:
    """
    Run the finance reconciliation agent for the given agreement id and return its final answer.
    
    Args:
        agreement_id: The agreement id to reconcile
        provider: "groq", "claude", or "openai" (defaults to config.DEFAULT_LLM_PROVIDER)
        model: specific model to use (uses provider defaults if not specified)
    """
    agent = build_financerecon_agent(provider=provider, model=model)
    result = agent.invoke(
        {
            "messages": [
                ("user", f"Reconcile bill amounts for agreement id {agreement_id}.")
            ]
        }
    )
    return result["messages"][-1].content


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Run the finance reconciliation agent.")
    parser.add_argument("agreement_id", type=int, help="Agreement id to reconcile.")
    args = parser.parse_args()

    print(run_financerecon_check(args.agreement_id))

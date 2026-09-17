"""
Chatbot orchestrator agent (multi-provider LLM) that acts as the backend for the
Gradio chat UI.

It routes user requests to the specialized agents (allowance anomaly
detection, finance reconciliation) when the user references an agreement id
and a relevant task, and answers generic questions directly using the LLM.
All user input is first screened for PII and prompt-injection attempts via
src.agent.guardrails.
"""
import logging
from typing import List, Optional, Tuple

from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from src.agents.guardrails import check_input
from src.agents.anamoly_agent import run_anomaly_check
from src.agents.financerecon_agent import run_financerecon_check
from src.settings.config import config

logger = logging.getLogger(__name__)

DEFAULT_LLM_PROVIDER = config.DEFAULT_LLM_PROVIDER
DEFAULT_GROQ_MODEL = config.GROQ_LLM_MODEL
DEFAULT_CLAUDE_MODEL = config.CLAUDE_LLM_MODEL
DEFAULT_OPENAI_MODEL = config.OPENAI_LLM_MODEL


class AgreementIdInput(BaseModel):
    agreement_id: int = Field(..., description="The vendor agreement id to check.")


def build_tools(provider: str, model: str):
    """
    Build the orchestrator's tools bound to the given provider/model, so the
    specialist agents they invoke run on the same LLM as the orchestrator.

    The tools are closures rather than module-level objects on purpose: each
    cached agent then carries its own provider/model. A shared mutable global
    would only be rewritten on a cache miss, so a cache hit would leave the
    specialist agents pointing at whichever provider was built last (and it
    would be wrong outright under concurrent users).
    """

    @tool("check_allowance_anomaly", args_schema=AgreementIdInput)
    def check_allowance_anomaly(agreement_id: int) -> str:
        """
        Run the allowance anomaly detection agent for the given agreement id.
        Use this when the user asks about allowance discrepancies or anomalies,
        or whether the recorded allowance amount matches what sales data
        implies, for a specific vendor agreement.
        """
        return run_anomaly_check(agreement_id, provider=provider, model=model)

    @tool("check_finance_reconciliation", args_schema=AgreementIdInput)
    def check_finance_reconciliation(agreement_id: int) -> str:
        """
        Run the finance reconciliation agent for the given agreement id. Use
        this when the user asks about bill/invoice reconciliation, or whether
        billed amounts match SAP invoice amounts, for a specific vendor
        agreement.
        """
        return run_financerecon_check(agreement_id, provider=provider, model=model)

    return [check_allowance_anomaly, check_finance_reconciliation]

SYSTEM_PROMPT = """\
You are the front-line assistant for a vendor agreement management chatbot.

You have two specialized tools available:
- check_allowance_anomaly(agreement_id): checks whether the allowance
  amount recorded for a vendor agreement matches what sales data implies,
  and reports any anomalies.
- check_finance_reconciliation(agreement_id): checks whether billed amounts
  for a vendor agreement reconcile against SAP invoice amounts, and reports
  any deviations.

Routing rules:
1. If the user asks about allowance anomalies/discrepancies for a specific
   agreement and gives an agreement id, call check_allowance_anomaly with
   that agreement id.
2. If the user asks about bill/invoice reconciliation or SAP invoice
   mismatches for a specific agreement and gives an agreement id, call
   check_finance_reconciliation with that agreement id.
3. If the user's request matches one of the above but no agreement id was
   given, ask the user to provide the agreement id. Do not guess an id.
4. If the user asks a generic question unrelated to the above two tasks,
   answer it directly yourself using your own knowledge, without calling
   any tool.

Always present tool results as a clear, structured summary for the user.
"""


def build_chatbot_agent(provider: str = None, model: str = None):
    """
    Build and return the chatbot orchestrator agent.
    
    Args:
        provider: "groq", "claude", or "openai" (defaults to config.DEFAULT_LLM_PROVIDER)
        model: specific model to use (uses provider defaults if not specified)
    """
    if provider is None:
        provider = DEFAULT_LLM_PROVIDER
    provider = provider.lower()

    if provider == "claude":
        if model is None:
            model = DEFAULT_CLAUDE_MODEL
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
                model=DEFAULT_GROQ_MODEL,
                api_key=config.GROQ_API_KEY,
                temperature=0
            )
            provider, model = "groq", DEFAULT_GROQ_MODEL
    elif provider == "openai":
        if model is None:
            model = DEFAULT_OPENAI_MODEL
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
                model=DEFAULT_GROQ_MODEL,
                api_key=config.GROQ_API_KEY,
                temperature=0
            )
            provider, model = "groq", DEFAULT_GROQ_MODEL
    else:  # default to groq
        provider = "groq"
        if model is None:
            model = DEFAULT_GROQ_MODEL
        llm = ChatGroq(
            model=model,
            api_key=config.GROQ_API_KEY,
            temperature=0
        )
        logger.info(f"Initialized Groq LLM with model: {model}")

    # Bind the tools to the provider/model actually built, so a Claude/OpenAI
    # fallback to Groq also moves the specialist agents to Groq.
    return create_react_agent(llm, build_tools(provider, model), prompt=SYSTEM_PROMPT)


_agents = {}


def _get_agent(provider: str = None, model: str = None):
    """
    Get or build and cache the orchestrator agent for a specific provider and model.
    
    Args:
        provider: "groq", "claude", or "openai" (defaults to config.DEFAULT_LLM_PROVIDER)
        model: specific model to use (uses provider defaults if not specified)
    """
    global _agents
    if provider is None:
        provider = DEFAULT_LLM_PROVIDER
    
    cache_key = f"{provider}:{model}"
    
    if cache_key not in _agents:
        _agents[cache_key] = build_chatbot_agent(provider=provider, model=model)
    return _agents[cache_key]


def _history_to_messages(history: Optional[list]) -> List[Tuple[str, str]]:
    """
    Convert Gradio chat history into LangChain-style (role, content) tuples.

    Supports both the modern Gradio "messages" format (list of
    {"role": ..., "content": ...} dicts) and the legacy format (list of
    (user, assistant) tuples).
    """
    messages: List[Tuple[str, str]] = []
    if not history:
        return messages

    for entry in history:
        if isinstance(entry, dict):
            role = entry.get("role")
            content = entry.get("content")
            if role and content:
                messages.append((role, content))
        else:
            user_msg, assistant_msg = entry
            if user_msg:
                messages.append(("user", user_msg))
            if assistant_msg:
                messages.append(("assistant", assistant_msg))
    return messages


def handle_user_message(message: str, history: Optional[list] = None, provider: str = None, model: str = None) -> str:
    """
    Handle a single user chat message: run guardrail checks (PII, prompt
    injection) first, then route to the orchestrator agent, which will
    either call a specialized tool (using the agreement id) or answer the
    generic question directly.
    
    Args:
        message: The user's message
        history: Gradio chat history
        provider: "groq", "claude", or "openai" (defaults to config.DEFAULT_LLM_PROVIDER)
        model: specific model to use (uses provider defaults if not specified)
    """
    guardrail_result = check_input(message)
    if guardrail_result.is_blocked:
        reasons = "; ".join(guardrail_result.reasons)
        logger.warning("Blocked user message due to guardrail violation(s): %s", reasons)
        return (
            "I can't process that message because it appears to contain "
            f"sensitive or unsafe content ({reasons}). "
            "Please rephrase your question without sharing personal data, "
            "and avoid trying to change my instructions."
        )

    try:
        agent = _get_agent(provider=provider, model=model)
        messages = _history_to_messages(history)
        messages.append(("user", message))

        result = agent.invoke({"messages": messages})
        return result["messages"][-1].content
    
    except Exception as e:
        error_msg = str(e).lower()
        error_type = type(e).__name__
        
        # If Claude or OpenAI fail, fallback to Groq
        if provider and provider.lower() in ["claude", "openai"]:
            provider_name = provider.lower()
            logger.warning(
                "%s error (%s: %s), falling back to Groq.",
                provider_name.capitalize(),
                error_type,
                str(e)[:200]  # First 200 chars of error
            )
            try:
                # Retry with Groq
                agent = _get_agent(provider="groq")
                messages = _history_to_messages(history)
                messages.append(("user", message))
                result = agent.invoke({"messages": messages})
                return (
                    f"Note: {provider_name.capitalize()} is currently unavailable, so I'm using Groq instead.\n\n" 
                    + result["messages"][-1].content
                )
            except Exception as fallback_error:
                logger.exception("Fallback to Groq also failed")
                return (
                    f"I'm sorry, I'm having trouble with the {provider_name} provider right now. "
                    "Groq fallback also failed. Please try again in a moment or switch providers."
                )
        
        # For Groq or other provider errors, log and return user-friendly message
        logger.exception("Error handling chat message with provider=%s, model=%s", provider, model)
        return (
            "I'm sorry, something went wrong while processing your request. "
            "Please try again, or switch to a different LLM provider if the issue persists."
        )


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
#     print(handle_user_message("Check agreement id 1001 for allowance anomalies."))

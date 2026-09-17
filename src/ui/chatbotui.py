"""
Gradio chat UI for the vendor agreement chatbot.

Run with:
    python -m src.ui.chatbotui
"""
import logging
import sys
from pathlib import Path

# Ensure the project root is importable as "src...", regardless of how this
# file is invoked (e.g. `python src/ui/chatbotui.py` or `python -m src.ui.chatbotui`).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import gradio as gr

from src.agents.chatbot_agent import handle_user_message
from src.settings.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Model mapping for each provider
MODELS_BY_PROVIDER = {
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"],
    "claude": ["claude-opus-5", "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
}

DEFAULT_MODELS = {
    "groq": config.GROQ_LLM_MODEL,
    "claude": config.CLAUDE_LLM_MODEL,
    "openai": config.OPENAI_LLM_MODEL,
}

# Every model across all providers. The Model dropdown is always populated
# with the full list: a gr.Dropdown silently refuses any value outside its
# own `choices`, so scoping the choices to the selected provider would make
# the model column of a claude/openai example unrenderable and unselectable.
ALL_MODELS = [model for models in MODELS_BY_PROVIDER.values() for model in models]

MODEL_TO_PROVIDER = {
    model: provider
    for provider, models in MODELS_BY_PROVIDER.items()
    for model in models
}


def get_models_for_provider(provider: str) -> list:
    """Get available models for the selected provider."""
    return MODELS_BY_PROVIDER.get(provider, [DEFAULT_MODELS.get(provider, "")])


def get_default_model(provider: str) -> str:
    """Get the default model for the selected provider."""
    return DEFAULT_MODELS.get(provider, "")


def respond(message: str, history: list, llm_provider: str, llm_model: str) -> str:
    """Gradio ChatInterface callback: handle a single user message."""
    # The two dropdowns are set independently (by the user or by an example),
    # so they can disagree. Sending e.g. a llama model name to Anthropic just
    # fails upstream, so prefer the provider and reset the model.
    if llm_model and MODEL_TO_PROVIDER.get(llm_model) != llm_provider:
        corrected = get_default_model(llm_provider)
        logger.warning(
            "Model %r does not belong to provider %r; using %r instead.",
            llm_model, llm_provider, corrected,
        )
        llm_model = corrected

    try:
        return handle_user_message(message, history, provider=llm_provider, model=llm_model)
    except Exception:
        logger.exception("Error handling chat message.")
        return "Sorry, something went wrong while processing your request. Please try again."


# Create the interface with provider and model selection
with gr.Blocks(title="Vendor Agreement Assistant") as demo:
    gr.Markdown("# Vendor Agreement Assistant")
    gr.Markdown(
        "Ask about allowance anomalies or bill/invoice reconciliation for a "
        "vendor agreement (include the agreement id), or ask a general question."
    )
    
    with gr.Row():
        llm_provider = gr.Dropdown(
            choices=["groq", "claude", "openai"],
            value=config.DEFAULT_LLM_PROVIDER,
            label="LLM Provider",
            info="Select which LLM provider to use"
        )
        llm_model = gr.Dropdown(
            choices=ALL_MODELS,
            value=get_default_model(config.DEFAULT_LLM_PROVIDER),
            label="Model",
            info="Select which model to use"
        )

    # Move to the provider's default model when the provider changes, keeping
    # the full choice list so example-supplied models stay valid.
    def update_models(provider: str):
        return gr.update(choices=ALL_MODELS, value=get_default_model(provider))

    # .input() rather than .change(): .change() also fires on programmatic
    # updates, so clicking an example would trigger this handler and overwrite
    # the example's own model with the provider default.
    llm_provider.input(
        fn=update_models,
        inputs=[llm_provider],
        outputs=[llm_model]
    )
    
    chatbot = gr.ChatInterface(
        fn=respond,
        additional_inputs=[llm_provider, llm_model],
        examples=[
            ["Check agreement id 1001 for allowance anomalies.", "openai", "gpt-4o-mini"],
            ["Reconcile bill amounts for agreement id 1001.", "openai", "gpt-4o-mini"],
            ["Check agreement id 1002 for allowance anomalies.", "openai", "gpt-4o-mini"],
            ["Reconcile bill amounts for agreement id 1002.", "openai", "gpt-4o-mini"],
            ["What is a vendor allowance agreement?", "openai", "gpt-4o-mini"],
        ],
    )


if __name__ == "__main__":
    demo.launch()

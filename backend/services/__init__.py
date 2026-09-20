"""Service layer package with optional production stacks loaded on demand."""

from importlib import import_module

_EXPORTS = {
    "AgentService": "agent_service",
    "Commander": "commander",
    "LLMService": "llm_service",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value

from core.llm.base import LLMProvider, create_llm_provider


def test_create_openai_provider():
    provider = create_llm_provider("openai", api_key="test-key")
    assert isinstance(provider, LLMProvider)


def test_create_claude_provider():
    provider = create_llm_provider("claude", api_key="test-key")
    assert isinstance(provider, LLMProvider)


def test_create_unknown_provider_raises():
    import pytest

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_provider("unknown", api_key="test")

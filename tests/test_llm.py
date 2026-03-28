import pytest
from app.llm import get_available_providers, get_llm_client
from app.prompts import build_prompt

def test_build_brief_prompt():
    prompt = build_prompt(
        style="brief", language="English",
        transcript="[00:00] Hello world",
        video_url="https://youtube.com/watch?v=abc123",
    )
    assert "comprehensive summary" in prompt
    assert "[00:00] Hello world" in prompt
    assert "English" in prompt
    assert "Tags: " in prompt

def test_build_structured_prompt():
    prompt = build_prompt(
        style="structured", language="Korean",
        transcript="[00:00] 안녕하세요",
        video_url="https://youtube.com/watch?v=abc123",
    )
    assert "## Overview" in prompt
    assert "## Key Moments" in prompt
    assert "abc123" in prompt
    assert "Korean" in prompt

def test_get_available_providers_no_keys():
    providers = get_available_providers(gemini_key=None, anthropic_key=None, openai_key=None)
    assert len(providers) == 0

def test_get_available_providers_all_keys():
    providers = get_available_providers(gemini_key="key1", anthropic_key="key2", openai_key="key3")
    assert "gemini" in providers
    assert "claude" in providers
    assert "openai" in providers

def test_get_llm_client_gemini():
    client = get_llm_client("gemini", gemini_key="test-key")
    assert client is not None
    assert type(client).__name__ == "GeminiClient"

def test_get_llm_client_claude():
    client = get_llm_client("claude", anthropic_key="test-key")
    assert client is not None
    assert type(client).__name__ == "ClaudeClient"

def test_get_llm_client_openai():
    client = get_llm_client("openai", openai_key="test-key")
    assert client is not None
    assert type(client).__name__ == "OpenAIClient"

def test_get_llm_client_unknown():
    with pytest.raises(ValueError):
        get_llm_client("unknown")

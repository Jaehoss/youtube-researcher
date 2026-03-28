from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from google import genai
import anthropic
import openai

class LLMClient(ABC):
    @abstractmethod
    async def summarize_stream(
        self, transcript: str, style: str, language: str, video_url: str
    ) -> AsyncGenerator[str, None]:
        ...

class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gemini-3.1-pro-preview"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def summarize_stream(self, transcript, style, language, video_url):
        from app.prompts import build_prompt
        # Gemini can natively understand YouTube URLs — include it in the prompt
        # so it can watch the video directly (visual + audio) alongside any transcript
        prompt = build_prompt(style, language, transcript, video_url)
        if video_url:
            prompt = f"YouTube video: {video_url}\n\n{prompt}"
        response = self.client.models.generate_content_stream(
            model=self.model, contents=prompt
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text

class ClaudeClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def summarize_stream(self, transcript, style, language, video_url):
        from app.prompts import build_prompt
        prompt = build_prompt(style, language, transcript, video_url)
        async with self.client.messages.stream(
            model=self.model, max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-5.4"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def summarize_stream(self, transcript, style, language, video_url):
        from app.prompts import build_prompt
        prompt = build_prompt(style, language, transcript, video_url)
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

def get_available_providers(gemini_key=None, anthropic_key=None, openai_key=None):
    providers = {}
    if gemini_key:
        providers["gemini"] = "Gemini 3.1 Pro"
    if anthropic_key:
        providers["claude"] = "Claude Sonnet 4.6"
    if openai_key:
        providers["openai"] = "GPT-5.4"
    return providers

def get_llm_client(provider, gemini_key=None, anthropic_key=None, openai_key=None):
    if provider == "gemini":
        return GeminiClient(api_key=gemini_key)
    elif provider == "claude":
        return ClaudeClient(api_key=anthropic_key)
    elif provider == "openai":
        return OpenAIClient(api_key=openai_key)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

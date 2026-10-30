import os

from openai import OpenAI


class AIProviderError(RuntimeError):
    pass


class OpenAIProvider:
    def __init__(self, api_key=None, model=None, client=None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if client is None and not api_key:
            raise AIProviderError("OPENAI_API_KEY is not configured.")

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self._client = client or OpenAI(api_key=api_key, timeout=30.0, max_retries=1)
        self._history = []

    def respond(self, message):
        message = message.strip()
        if not message:
            raise AIProviderError("The message is empty.")
        if len(message) > 4000:
            raise AIProviderError("The message is too long; please keep it under 4000 characters.")

        request_input = [*self._history, {"role": "user", "content": message}]
        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=(
                    "You are Jarvis, a concise and practical voice assistant. "
                    "Answer naturally and keep replies suitable for speech. "
                    "You cannot browse the web or control the computer; never claim that you did. "
                    "Do not ask for passwords, API keys, or patient-identifying information. "
                    "For healthcare billing or compliance questions, distinguish general guidance "
                    "from verified payer rules and recommend checking current authoritative sources. "
                    "Do not claim professional credentials."
                ),
                input=request_input,
                max_output_tokens=400,
                store=False,
            )
        except Exception as error:
            raise AIProviderError(f"OpenAI request failed ({type(error).__name__}).") from error

        answer = response.output_text.strip()
        if not answer:
            raise AIProviderError("OpenAI returned an empty response.")

        self._history = [
            *request_input,
            {"role": "assistant", "content": answer},
        ][-12:]
        return answer
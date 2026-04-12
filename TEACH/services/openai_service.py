from openai import OpenAI
from core.config import get_settings
from typing import List, Optional

settings = get_settings()

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are AI-Tut, a friendly and expert academic mentor for engineering students.
You help with doubts, explain concepts clearly, give step-by-step solutions, and encourage students.
Keep responses clear and well-structured. Use emojis sparingly to keep it friendly."""

def get_chatgpt_response(
    question: str,
    university: str = "general",
    branch: str = "cse",
    year: int = 1,
    subject: str = "general",
    history: Optional[List[dict]] = None
) -> str:
    try:
        messages = []

        # Add system prompt
        messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT
        })

        # Add history
        if history:
            for msg in history:
                messages.append({
                    "role": msg["role"],  # "user" or "assistant"
                    "content": msg["content"]
                })

        # Add contextualized question
        contextualized_question = (
            f"Student Context: {university.upper()} | {branch.upper()} "
            f"| Year {year} | Subject: {subject.upper()}\n\n"
            f"Student Question: {question}"
        )

        messages.append({
            "role": "user",
            "content": contextualized_question
        })

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # fast + cheap
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"OpenAI Error: {e}")
        return f"I'm having trouble connecting right now. Please try again. (Error: {str(e)})"
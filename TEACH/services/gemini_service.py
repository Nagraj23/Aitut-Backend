from google import genai
from google.genai import types
from core.config import get_settings
from typing import List, Optional

settings = get_settings()

# New SDK client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

SYSTEM_PROMPT = """You are AI-Tut, a friendly and expert academic mentor for engineering students.
You help with doubts, explain concepts clearly, give step-by-step solutions, and encourage students.
Keep responses clear and well-structured. Use emojis sparingly to keep it friendly."""

def get_gemini_response(
    question: str,
    university: str = "general",
    branch: str = "cse",
    year: int = 1,
    subject: str = "general",
    history: Optional[List[dict]] = None
) -> str:
    try:
        # Build conversation history in new SDK format
        contents = []

        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=msg["content"])]
                    )
                )

        # Add the current question with context
        contextualized_question = (
            f"Student Context: {university.upper()} | {branch.upper()} "
            f"| Year {year} | Subject: {subject.upper()}\n\n"
            f"Student Question: {question}"
        )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=contextualized_question)]
            )
        )

        response = client.models.generate_content(
            model="models/gemini-2.0-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
                max_output_tokens=1024,
            ),
            contents=contents
        )

        return response.text

    except Exception as e:
        print(f"Gemini Error: {e}")
        return f"I'm having trouble connecting right now. Please try again. (Error: {str(e)})"
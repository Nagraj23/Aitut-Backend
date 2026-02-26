import json
import os
import google.generativeai as genai
from django.conf import settings

def generate_diagnostic(domain, university, day_number):
    """Call Gemini LLM and return parsed JSON test."""
    print(f"DEBUG: AI logic received Domain='{domain}', Day={day_number}")
    # 1. Initialize inside the function to ensure settings are loaded
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')

    if day_number <= 2:
        level = "Introductory (Fundamentals & Syntax)"
    elif day_number <= 5:
        level = "Intermediate (Architecture & Logic)"
    else:
        level = "Advanced (Optimization & Troubleshooting)"

    prompt = f"""
    You are a world-class educational psychologist and technical interviewer. 
    Generate Day {day_number} of a 7-day diagnostic series for a {domain} student at {university}.
    
    Current Phase: Day {day_number} - {level}
    
    Rules:
    1. Generate exactly 6 MCQs: Focus on logical application and edge cases.
    2. Generate exactly 4 Descriptive questions: Focus on "Explain Like I'm 5" (ELI5) scenarios.
    3. Ensure questions are different from typical textbook questions.
    4. Output ONLY valid JSON. No conversational filler.

    Structure:
    {{
      "day": {day_number},
      "level": "{level}",
      "questions": [
        {{ 
          "id": 1, 
          "type": "mcq", 
          "question": "...", 
          "options": ["A) ...", "B) ...", "C) ...", "D) ..."], 
          "answer": "A" 
        }},
        {{ 
          "id": 7, 
          "type": "descriptive", 
          "question": "..." 
        }}
      ]
    }}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json"
            }
        )
        
        content = response.text
        if not content:
            raise ValueError("Gemini returned an empty response.")
            
        return json.loads(content)
    except Exception as e:
        raise ValueError(f"Gemini generation failed: {str(e)}")

def evaluate_answer(question, student_answer):
    """Grade a descriptive answer for knowledge gaps using Gemini."""
    
    # 2. Re-initialize here as well to avoid scope errors
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""
    Question: {question}
    Student Answer: {student_answer}

    Evaluate this answer for clarity, logic, and creative thinking.
    Return ONLY valid JSON:
    {{
      "level": "Strong" or "Intermediate" or "Weak",
      "knowledge_gap": "one specific concept the student is missing",
      "feedback": "one sentence of actionable advice"
    }}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json"
            }
        )
        
        content = response.text
        if not content:
            raise ValueError("Gemini returned an empty evaluation.")
            
        return json.loads(content)
    except Exception as e:
        raise ValueError(f"Evaluation failed: {str(e)}")
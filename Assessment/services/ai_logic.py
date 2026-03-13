import json
import os
from groq import Groq  # 👈 Changed
from django.conf import settings

def generate_diagnostic(domain, university, day_number):
    """Call Groq LLM and return parsed JSON test."""
    print(f"DEBUG: AI logic received Domain='{domain}', Day={day_number}")
    
    # 1. Initialize Groq client
    client = Groq(api_key=settings.GROQ_API_KEY) # 👈 Ensure this is in settings
    
    # Using Llama 3.1 8B for high speed and generous daily limits
    model_name = "llama-3.1-8b-instant" 

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
        # 👈 Groq completion logic
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} # 👈 Forces valid JSON
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned an empty response.")
            
        return json.loads(content)
    except Exception as e:
        raise ValueError(f"Groq generation failed: {str(e)}")

def evaluate_answer(question, student_answer):
    """Grade a descriptive answer for knowledge gaps using Groq."""
    
    client = Groq(api_key=settings.GROQ_API_KEY)
    model_name = "llama-3.1-8b-instant"

    prompt = f"""
    As an expert technical tutor, analyze this student's answer.
    
    Question: {question}
    Student Answer: {student_answer}

    Task:
    1. If the answer is correct and explains the concept well, set level to "Strong" and knowledge_gap to null.
    2. If the answer is partially correct or vague, set level to "Intermediate" and identify the missing technical detail.
    3. If the answer is wrong, set level to "Weak" and identify the core concept they don't understand.

    Return ONLY JSON:
    {{
      "level": "Strong" | "Intermediate" | "Weak",
      "concept_mastered": "The specific technical topic they explained well (max 5 words)",
      "knowledge_gap": "The specific technical concept they missed (max 5 words) or null if Strong",
      "feedback": "One helpful sentence."
    }}"""
    
    try:
        # 👈 Groq evaluation logic
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned an empty evaluation.")
            
        return json.loads(content)
    except Exception as e:
        raise ValueError(f"Evaluation failed: {str(e)}")
import json
from groq import Groq
from django.conf import settings
from db.models import UserKnowledgeGraph

# Initialize Groq Client
client = Groq(api_key=settings.GROQ_API_KEY)
MODEL_NAME = "llama-3.1-8b-instant"

def generate_diagnostic(domain, university, day_number, previous_loopholes=None):
    """
    Generates a 10-question test. 
    If previous_loopholes (list) is provided, it crafts specific questions to re-test those gaps.
    """
    print(f"DEBUG: Generating Day {day_number} for {domain}")

    # Logic-based difficulty scaling
    if day_number <= 2:
        level = "Introductory (Fundamentals & Syntax)"
    elif day_number <= 5:
        level = "Intermediate (Architecture & Logic)"
    else:
        level = "Advanced (Optimization & Troubleshooting)"

    # Adaptive Instruction: If they failed something yesterday, hit it again today.
    adaptive_retest = ""
    if previous_loopholes and len(previous_loopholes) > 0:
        adaptive_retest = f"\nCRITICAL: The student struggled with these specific concepts previously: {', '.join(previous_loopholes)}. Dedicate 2 MCQs and 1 Descriptive question to re-evaluating these loopholes specifically."

    prompt = f"""
    You are a world-class educational psychologist and technical interviewer. 
    Generate Day {day_number} of a 7-day diagnostic series for a {domain} student at {university}.
    
    Current Phase: Day {day_number} - {level} {adaptive_retest}
    
    Rules:
    1. Generate exactly 6 MCQs: Focus on logical application and real-world edge cases.
    2. Generate exactly 4 Descriptive questions: Use ELI5 (Explain Like I'm 5) or "Scenario-based troubleshooting" prompts.
    3. Ensure questions are practical, not just theoretical definitions.
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
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The AI returned an empty response.")
        
        return json.loads(content)
    except Exception as e:
        raise ValueError(f"Groq generation failed: {str(e)}")


def evaluate_answer(question, student_answer):
    """
    Deep evaluation of a descriptive answer. 
    Categorizes the error type to determine roadmap priorities on Day 8.
    """
    
    prompt = f"""
    As an expert technical tutor, analyze this student's answer.
    
    Question: {question}
    Student Answer: {student_answer}

    Task:
    1. Categorize the error: Is it "Conceptual" (doesn't get the 'why'), "Logic" (process is wrong), or "Syntax" (coding/grammar error)?
    2. Identify the specific knowledge gap.

    Return ONLY JSON:
    {{
      "level": "Strong" | "Intermediate" | "Weak",
      "error_type": "Conceptual" | "Logic" | "Syntax" | "None",
      "concept_mastered": "Specific technical topic explained well (max 5 words)",
      "knowledge_gap": "The core technical concept they missed (max 5 words) or null if Strong",
      "root_cause": "A brief explanation of why the answer is incorrect/incomplete",
      "feedback": "One helpful, encouraging sentence."
    }}"""
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The AI returned an empty response.")
        
        return json.loads(content)
    except Exception as e:
        raise ValueError(f"Evaluation failed: {str(e)}")
    
def generate_deep_roadmap(user_id, user_preferences):
    """
    Generates a personalized learning path based on 7-day diagnostic results.
    user_preferences: dict containing 'daily_hours', 'total_days', 'goal'
    """
    # from .models import UserKnowledgeGraph # Import your master profile model
    
    # 1. Fetch the user's diagnostic summary
    graph = UserKnowledgeGraph.objects.get(spring_user_id=user_id)
    
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    # 2. Craft the "Deep" Roadmap Prompt
    prompt = f"""
    You are a Senior Technical Architect and Mentor. 
    Create a highly personalized, deep learning roadmap for a student based on a 7-day diagnostic.

    STUDENT DATA:
    - Domain: {graph.domain}
    - Critical Loopholes (Repeated Failures): {graph.critical_loopholes}
    - Mastered Concepts (Skip these): {graph.mastery_scores}
    - Primary Error Type: {graph.top_error_type} (Tailor content to fix this)
    
    LOGISTICS:
    - Target Goal: {user_preferences.get('goal')}
    - Daily Commitment: {user_preferences.get('daily_hours')} hours/day
    - Roadmap Duration: {user_preferences.get('total_days')} days

    ROADMAP STRUCTURE RULES:
    1. Phase 1 (Remediation): Spend the first 20% of time strictly fixing the "Critical Loopholes".
    2. Phase 2 (Progression): Move into advanced topics the student hasn't mastered yet.
    3. Phase 3 (Application): Design a final project syllabus aligned with their 'Goal'.
    4. Provide specific technical tasks, not just titles.
    5. No conversational filler. Output ONLY valid JSON.

    OUTPUT FORMAT:
    {{
        "title": "...",
        "overview": "...",
        "phases": [
            {{
                "name": "Phase Name",
                "days": "Day 1-X",
                "focus": "...",
                "daily_plan": [
                    {{ "day": 1, "topic": "...", "task": "...", "depth": "Beginner|DeepDive" }}
                ]
            }}
        ],
        "final_project_idea": "..."
    }}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Roadmap generation returned empty content")
            
        return json.loads(content)
        
    except Exception as e:
        raise ValueError(f"Roadmap Generation Failed: {str(e)}")
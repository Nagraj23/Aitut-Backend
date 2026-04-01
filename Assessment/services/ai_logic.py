import json
from groq import Groq
from django.conf import settings
from db.models import UserKnowledgeGraph,Roadmap
# from .config import get_settings
from django.conf import settings
# from core.settings import get_setting
import chromadb
from django.conf import settings
from chromadb.api.types import Where
import os 
from .chroma_service import get_collection

# Initialize Groq Client
teach_db_path = "../TEACH/db/chroma_storage" 

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# This goes one level up, then into the TEACH folder
SHARED_CHROMA_PATH = os.path.join(BASE_DIR, '..', 'TEACH', 'chroma_data')

chroma_client = chromadb.PersistentClient(path=SHARED_CHROMA_PATH)

client = Groq(api_key=settings.GROQ_API_KEY)
MODEL_NAME = "llama-3.1-8b-instant"

def get_syllabus_from_chroma(subject_id, user_goal="Complete syllabus mastery", units=None):
    if not subject_id: return None
    try:
        collection_name = str(subject_id).lower().strip()
        collection = get_collection(collection_name)
        
        # Increase n_results to 20 or 25 to get the WHOLE syllabus 
        # since we can't filter by unit metadata.
        results = collection.query(
            query_texts=[user_goal], 
            n_results=25, 
            where={"doc_type": "syllabus"}
        )
        
        if not results['documents']: return "No syllabus found."
        return " ".join(results['documents'][0]) 
    except Exception as e:
        print(f"Error: {e}")
        return None
    
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
    
def generate_deep_roadmap(user_id, user_preferences, role="student", subject_id=None, phase_number=1):
    """
    Generates a structured learning roadmap using Groq LLM.
    Phase 1: Units 1-3 | Phase 2: Units 4-6
    Ensures 7-8 days of pure learning per chapter for 95%+ coverage.
    """
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    if role == "student":
        goal = user_preferences.get('goal', 'Complete syllabus mastery')
        
        # We still keep this variable to help the prompt, 
        # even if we don't filter Chroma by it.
        target_unit_names = "Units 1, 2, and 3" if phase_number == 1 else "Units 4, 5, and 6"
        
        # Fetch the full syllabus (top 25 chunks)
        syllabus_context = get_syllabus_from_chroma(subject_id, user_goal=goal)
        
        if not syllabus_context:
            raise ValueError(f"Could not retrieve context for {subject_id}")

        # THE REFACTORED "SMART-SPLIT" PROMPT
        prompt = f"""
        You are a Senior Academic Mentor. I am providing the FULL SYLLABUS below.
        Your goal is to generate ONLY PHASE {phase_number} of a 60-day roadmap.

        SYLLABUS DATA:
        \"\"\"{syllabus_context}\"\"\"

        --- PHASE INSTRUCTIONS ---
        - You are currently generating: PHASE {phase_number}.
        - TARGET TOPICS: If phase=1, focus ONLY on the topics in {target_unit_names}. 
        - If phase=2, focus ONLY on the remaining units (Unit 4, 5, and 6), specifically including Nanotechnology and Carbon Nanotubes (CNT).

        --- DYNAMIC ALLOCATION RULES ---
        1. CHAPTER DEPTH: Allocate 7 to 8 days of PURE LEARNING for each unit in THIS phase.
        2. EXCLUSION: Mon-Fri for learning. Saturdays (Test) and Sundays (Revision) are ADDITIONAL.
        3. 95% COVERAGE: Break down every sub-topic, derivation, and application mentioned for these specific units.

        --- MANDATORY WEEKLY STRUCTURE ---
        - Mon-Fri: Daily learning tasks based on syllabus.
        - SATURDAY: Topic: "Weekly Assessment Test" | Type: "Test"
        - SUNDAY: Topic: "Revision & Backlog Clear" | Type: "Free"

        --- OUTPUT FORMAT (JSON ONLY) ---
        {{
            "phase": {phase_number},
            "title": "Phase {phase_number}: {'Foundations' if phase_number == 1 else 'Advanced Applications'}",
            "daily_plan": [
                {{ 
                "day": {'1' if phase_number == 1 else '31'}, 
                "topic": "Unit/Sub-topic Name", 
                "task": "Learning objective", 
                "type": "Learning|Problem Solving|Test|Free" 
                }}
            ]
        }}
        """

        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-70b-8192",
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"Error generating phase {phase_number}: {e}")
            return None
    
    # 2. PATH B: INDIVIDUAL (DIAGNOSTIC-BASED)
    else:
        from db.models import UserKnowledgeGraph # Import here to avoid circular imports
        graph = UserKnowledgeGraph.objects.get(spring_user_id=user_id)
        
        prompt = f"""
        You are a Senior Technical Architect. Create a deep learning roadmap based on a 7-day diagnostic.

        STUDENT DATA:
        - Domain: {graph.domain}
        - Critical Loopholes: {graph.critical_loopholes}
        - Mastered Concepts: {graph.mastery_scores}
        - Primary Error Type: {graph.top_error_type}
        
        LOGISTICS:
        - Goal: {user_preferences.get('goal')}
        - Daily Commitment: {user_preferences.get('daily_hours')} hours
        - Duration: {user_preferences.get('total_days')} days

        RULES:
        1. Phase 1 (Remediation): First 20% of time fixing "Critical Loopholes".
        2. Phase 2 (Progression): Advance into unmastered topics.
        3. Phase 3 (Application): Final project aligned with goal.
        4. No conversational filler. OUTPUT ONLY VALID JSON.

        OUTPUT FORMAT:
        {{
            "title": "Personalized {graph.domain} Path",
            "overview": "...",
            "phases": [
                {{
                    "name": "Phase Name",
                    "days": "Day 1-10",
                    "focus": "...",
                    "daily_plan": [
                        {{ "day": 1, "topic": "...", "task": "...", "depth": "Beginner|DeepDive" }}
                    ]
                }}
            ],
            "final_project_idea": "..."
        }}
        """

    # 3. EXECUTION & ERROR HANDLING
    try:
        response = client.chat.completions.create(
            model=settings.CHAT_MODEL, # Uses "llama-3.1-8b-instant" from your config
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        # Capture content for Type-Safety (Fixes the VS Code Red Squiggle)
        content = response.choices[0].message.content
        
        if content is None:
            raise ValueError("Groq returned empty content. Verify API status.")

        # Return the parsed JSON
        return json.loads(content)
        
    except Exception as e:
        # Catching everything from JSON errors to API timeouts
        raise ValueError(f"Roadmap Generation Failed: {str(e)}")
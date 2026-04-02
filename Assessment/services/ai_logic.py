import json
from groq import Groq
from django.conf import settings
from db.models import UserKnowledgeGraph,Roadmap,RoadmapTask
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
    # Using Llama 3.3 70B for better reasoning and larger output limit
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    if role == "student":
        goal = user_preferences.get('goal', 'Complete syllabus mastery')
        target_unit_names = "Units 1, 2, and 3" if phase_number == 1 else "Units 4, 5, and 6"
        
        # Fetching context (Ensure n_results is high enough)
        syllabus_context = get_syllabus_from_chroma(subject_id, user_goal=goal)
        
        if not syllabus_context:
            raise ValueError(f"Could not retrieve context for {subject_id}")

        # --- THE UPDATED STRICT PROMPT ---
        prompt = f"""
        You are a Senior Academic Mentor. Generate a PURE JSON roadmap for PHASE {phase_number}.
        
        SYLLABUS DATA:
        \"\"\"{syllabus_context}\"\"\"

        --- PHASE CONFIGURATION ---
        - CURRENT PHASE: Phase {phase_number}
        - TARGET UNITS: {target_unit_names}
        - TOTAL DURATION: Exactly 25 Days.

        --- STRICT ALLOCATION RULES (DO NOT DEVIATE) ---
        1. PURE LEARNING: For EACH of the 3 Units, allocate STRICTLY 6 days of "Learning" or "Problem Solving" (Mon-Fri + the following Mon).
        2. NO COMPRESSION: Every sub-topic, derivation, and numerical mentioned in the SYLLABUS DATA must have its own dedicated day.
        3. WEEKLY STRUCTURE:
           - Days 1-5: Learning (Unit 1)
           - Day 6: Weekly Assessment Test (Type: "Test")
           - Day 7: Revision & Backlog Clear (Type: "Free")
           - Days 8: Learning (Finish Unit 1)
           - Days 9-12: Learning (Unit 2)... continue this pattern.
        4. NANOTECHNOLOGY: {'If Phase 2, Unit 6 (Carbon Nanotubes/CNT) must span at least 6 detailed days.' if phase_number == 2 else ''}

        --- OUTPUT FORMAT (JSON ONLY) ---
        Return ONLY a JSON object. No conversational filler.
        {{
            "phase": {phase_number},
            "title": "Phase {phase_number}: {'Foundations' if phase_number == 1 else 'Advanced Applications'}",
            "daily_plan": [
                {{ 
                  "day": {'1' if phase_number == 1 else '31'}, 
                  "topic": "Unit X: Specific Sub-topic", 
                  "task": "Step-by-step learning objective including derivations", 
                  "type": "Learning|Problem Solving|Test|Free" ,
                  "is_completed": false  
                }}
            ]
        }}
        """

        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile", # Switched to 3.3 for larger context/output
                temperature=0.3, # Slightly higher for better task breakdown
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content) if content else None

        except Exception as e:
            print(f"❌ Error: {e}")
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
                        {{ "day": 1, "topic": "...", "task": "...", "depth": "Beginner|DeepDive","is_completed": false }}
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
    
def get_existing_roadmap_data(user_id):
    """
    Fetches the latest roadmap and its tasks from the DB 
    and reconstructs the JSON format for the mobile frontend.
    """
    try:
        # 1. Get the most recent roadmap object
        roadmap_obj = Roadmap.objects.filter(
            spring_user_id=user_id
        ).order_by('-id').first()

        if not roadmap_obj:
            return None

        # 2. Fetch all tasks associated with this roadmap
        tasks = RoadmapTask.objects.filter(roadmap=roadmap_obj).order_by('day_number')

        # 3. Reconstruct the daily_plan list
        daily_plan = []
        for task in tasks:
            daily_plan.append({
                "day": task.day_number,
                "topic": task.topic,
                "task": task.task_description,
                "type": task.phase_name,  # Le,arning, Test, etc.
                "is_completed": getattr(task, 'is_completed', False)
            })

        # 4. Return formatted response (matches what GenerateDeepRoadmap creates)
        return {
            "roadmap_id": roadmap_obj.id,
            "title": roadmap_obj.title,
            "overview": roadmap_obj.overview,
            "progress": getattr(roadmap_obj, 'progress', 0), # Uses progress if field exists
            "daily_plan": daily_plan
        }

    except Exception as e:
        print(f"Error fetching roadmap: {e}")
        return None
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
    
import json

def generate_assessment(domain, tier, role="STUDENT", assessment_type="ONBOARDING", previous_loopholes=None, chat_context=None):
    # 0. NORMALIZE INPUT (Crucial for DB consistency)
    domain = domain.strip().title() # Transforms "react native" -> "React Native"
    
    personas = {
        "STUDENT": "Academic Examiner. Focus on formal theory, fundamental laws, and conceptual accuracy.",
        "INDIVIDUAL": "Industry Consultant. Focus on real-world application, efficiency, and practical troubleshooting."
    }

    tier_depth = {
        "EASY": "Core terminology, fundamental principles, and basic 'How-to' concepts.",
        "MEDIUM": "Process flow, relationship between variables, and standard problem-solving.",
        "HARD": "Complex system troubleshooting, edge cases, and high-level evaluation/optimization."
    }

    # 3. Protocol Logic
    if assessment_type == "WEEKLY":
        context_prompt = f"""
        WEEKLY PROTOCOL:
        - Mastery Check: 7 questions must challenge concepts recently discussed: {chat_context if chat_context else 'General curriculum'}.
        - Gap Closure: 3 questions must revisit previous weaknesses/loopholes: {', '.join(previous_loopholes) if previous_loopholes else 'None'}.
        """
    else:
        context_prompt = f"""
        DIAGNOSTIC PROTOCOL:
        - Goal: Establish a baseline for {domain}.
        - Level: {tier} - {tier_depth.get(tier)}
        """

    # 4. Final Prompt Construction
    prompt = f"""
    {personas.get(role, personas['STUDENT'])}
    Generate a 10-question {assessment_type} for a {role} learning {domain}.

    {context_prompt}

    RULES:
    1. 6 MCQs: No 'all of the above' answers. Use scenario-based options.
    2. 4 Descriptive: Use 'Problem-Solving' or 'Conceptual Explanation' (ELI5) prompts.
    3. Ensure questions test logical reasoning, not just memorization.
    4. Output ONLY valid JSON. No conversational filler.

    FORMAT:
    {{
      "tier": "{tier}",
      "type": "{assessment_type}",
      "role": "{role}",
      "questions": [
        {{ "id": 1, "type": "mcq", "question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A", "explanation": "..." }},
        {{ "id": 7, "type": "descriptive", "question": "...", "key_points": ["point 1", "point 2"] }}
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
            return None
            
        data = json.loads(content)
        # Return both the questions AND the normalized domain to the view
        return data.get("questions") 
        
    except Exception as e:
        print(f"Generation Error: {e}")
        return None
    # ... (Client execution logic same as before)

def normalize_list(items):
    """
    Converts AI + MCQ mixed outputs into clean string list.
    Prevents dict/unhashable crashes.
    """
    clean = []

    for i in items:
        if not i:
            continue

        if isinstance(i, dict):
            clean.append(
                i.get("topic") or i.get("name") or i.get("value")
            )
        else:
            clean.append(i)

    return [str(x).strip() for x in clean if x]

def evaluate_answer(question, student_answer, domain):
    """
    Dynamically evaluates answers based on the specific assessment domain.
    """
    
    prompt = f"""
    As a Senior {domain} Specialist and Architect, perform a high-standard forensic analysis 
    of this student's answer for a 50-day elite roadmap.

    Current Domain: {domain}
    Question: {question}
    Student Answer: {student_answer}

    EVALUATION CRITERIA:
    1. DEPTH: Does the user mention internal mechanics, advanced patterns, or performance trade-offs relevant to {domain}?
    2. PRECISION: Are they using exact industry terminology?
    3. CRITICAL GAPS: What key technical nuances did they NOT mention that a lead developer in {domain} should know?

    Return ONLY JSON:
    {{
      "level": "Strong" | "Intermediate" | "Weak",
      "depth_rating": 1-10,
      "error_type": "Conceptual" | "Logic" | "Syntax" | "None",
      "mastered_topics": [], 
      "critical_gaps": [],    
      "root_cause": "Technical explanation of the rating level",
      "roadmap_directives": {{
          "immediate_fixes": ["Concept for Day 1-10"],
          "advanced_mastery": ["Concept for Day 20-40"],
          "project_challenge": "A mini-project idea to prove mastery"
      }},
      "feedback": "Direct, professional feedback on what is missing for 'Senior' level mastery."
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
    

def generate_deep_roadmap(user_id, role="student", subject_id=None, phase_number=1, domain=None):
    """
    Unified Roadmap Engine:
    1. Students -> Try Syllabus (RAG) -> Fallback to SWOT if missing.
    2. Individuals -> Performance-based (SWOT) only.
    """
    role = role.lower()
    
    # --- 1. CONTEXT GATHERING ---
    syllabus_context = None
    if role == "student" and subject_id:
        syllabus_context = get_syllabus_from_chroma(subject_id)

    # If we need performance data (Individual OR Student Fallback)
    if not syllabus_context or role == "individual":
        from db.models import UserKnowledgeGraph, AssessmentSWOT
        
        lookup_domain = domain if domain else subject_id
        try:
            graph = UserKnowledgeGraph.objects.get(
                spring_user_id=user_id, 
                domain__iexact=lookup_domain
            )
            swots = AssessmentSWOT.objects.filter(
                spring_user_id=user_id, 
                assessment__domain__iexact=lookup_domain
            )
            
            all_loopholes = []
            for s in swots:
                if s.weaknesses:
                    all_loopholes.extend(s.weaknesses)
            
            loopholes = list(set(all_loopholes))
            mastery_data = graph.mastery_scores
            error_type = graph.top_error_type
        except Exception:
            # Emergency fallback if no assessment data exists either
            loopholes = ["Core fundamentals", "Industry standards"]
            mastery_data = {}
            error_type = "Conceptual"

    # --- 2. PROMPT CONSTRUCTION ---
    if syllabus_context:
        # PATH A: ACADEMIC (SYLLABUS-DRIVEN)
        target_unit_names = "Units 1, 2, and 3" if phase_number == 1 else "Units 4, 5, and 6"
        prompt = f"""
        You are a Senior Academic Mentor. Generate a PURE JSON roadmap for PHASE {phase_number}.
        SOURCE: Official University Syllabus Data.

        SYLLABUS CONTENT:
        \"\"\"{syllabus_context}\"\"\"

        --- CONFIGURATION ---
        - TARGET: {target_unit_names}
        - TOTAL DURATION: 25 Days.

        --- RULES ---
        1. STRUCTURE: Days 1-5: Learning | Day 6: Weekly Test | Day 7: Revision/Free.
        2. ALLOCATION: Strictly 6 days per Unit. 
        3. DETAIL: Every topic and derivation in the syllabus must be a specific task.
        {'4. SPECIAL: Unit 6 (Carbon Nanotubes) must span at least 6 days.' if phase_number == 2 else ''}
        """
    else:
        prompt = f"""
        You are a Senior Technical Architect. Generate a STRICT 25-day roadmap based on performance gaps.
        ROLE: {role.upper()}
        DOMAIN: {domain or subject_id}

        STUDENT DATA:
        - Critical Loopholes: {loopholes}
        - Current Mastery Scores: {mastery_data}
        - Error Pattern: {error_type}

        --- MANDATORY RULES ---
        1. DURATION: Your 'daily_plan' array MUST contain exactly 25 objects (Day 1 to Day 25).
        2. PHASE 1 (Remediation): Days 1-7 (Fixing Critical Loopholes).
        3. PHASE 2 (Progression): Days 8-20 (Advanced concepts and unmastered concepts).
        4. PHASE 3 (Application): Days 21-25 (Professional Capstone Project).
        5. Every single day must have a unique 'task' and 'topic'.
        """

    # Add shared Formatting Rules
    prompt += f"""
    --- OUTPUT FORMAT ---
    Return ONLY valid JSON.
    {{
        "phase": {phase_number},
        "title": "Roadmap Title",
        "daily_plan": [
            {{ 
              "day": 1, 
              "topic": "Specific Topic", 
              "task": "Actionable task description", 
              "type": "Learning|Test|Free",
              "is_completed": false 
            }}
        ]
    }}
    """

    # --- 3. EXECUTION ---
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned empty content.")

        return json.loads(content)
        
    except Exception as e:
        print(f"Roadmap Generation Failed: {str(e)}")
        return None
    
def get_existing_roadmap_data(user_id):
    try:
        roadmap_obj = Roadmap.objects.filter(
            spring_user_id=user_id
        ).order_by('-id').first()

        if not roadmap_obj:
            return None

        tasks = RoadmapTask.objects.filter(
            roadmap=roadmap_obj
        ).order_by('day_number')

        daily_plan = []

        for task in tasks:
            daily_plan.append({
                "day": task.day_number,
                "topic": task.topic,
                "task": task.task_description,
                "type": task.phase_name,
                "is_completed": getattr(task, 'is_completed', False)
            })

        # 🔥 TAKE SUBJECT FROM FIRST TASK (or roadmap if available)
        subject = roadmap_obj.subject

        return {
            "roadmap_id": roadmap_obj.id,
            "subject": subject,   # ✅ TOP LEVEL NOW
            "title": roadmap_obj.title,
            "overview": roadmap_obj.overview,
            "progress": getattr(roadmap_obj, 'progress', 0),
            "daily_plan": daily_plan
        }

    except Exception as e:
        print(f"Error fetching roadmap: {e}")
        return None
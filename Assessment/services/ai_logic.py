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
    
def generate_assessment(domain, tier, assessment_type="ONBOARDING", previous_loopholes=None, chat_context=None):
    """
    Tier-based Blitz (Easy/Med/Hard) for Onboarding 
    OR Chat-context driven Weekly Reinforcement.
    """
    
    tier_depth = {
        "EASY": "Focus on core syntax, fundamental principles, and 'The Why' behind basic operations.",
        "MEDIUM": "Focus on logic flow, data handling, error management, and architecture.",
        "HARD": "Focus on performance optimization, security, edge cases, and complex system troubleshooting."
    }

    # Weekly Reinforcement Logic
    if assessment_type == "WEEKLY":
        context_prompt = f"""
        WEEKLY PROTOCOL:
        1. CONCEPTS MASTERED IN RECENT SESSIONS: {chat_context if chat_context else 'General curriculum'}
        2. RESIDUAL LOOPHOLES FROM PREVIOUS TESTS: {', '.join(previous_loopholes) if previous_loopholes else 'None'}
        
        INSTRUCTION: 
        You are verifying the student's actual retention of this week's topics. 
        - 7 questions must challenge the concepts they claimed to 'master' in chat sessions.
        - 3 questions must revisit their previous loopholes to ensure they haven't relapsed.
        """
    else:
        # Initial Blitz Logic
        context_prompt = f"""
        DIAGNOSTIC PROTOCOL:
        - Goal: Establish a technical baseline for {domain}.
        - Level: {tier} - {tier_depth.get(tier)}
        - Ensure questions require logical reasoning rather than just memory recall.
        """

    prompt = f"""
    You are a Senior Technical Lead and Educational Psychologist. 
    Generate a 10-question {assessment_type} for an individual learning {domain}.

    {context_prompt}

    RULES:
    1. 6 MCQs: No 'all of the above' answers. Use scenario-based options.
    2. 4 Descriptive: Use 'Scenario Troubleshooting' (e.g., 'Your app is doing X, how do you fix Y?') or 'ELI5' prompts.
    3. Ensure a mix of coding logic and high-level conceptual understanding.
    4. Output ONLY valid JSON. No conversational filler.

    FORMAT:
    {{
      "tier": "{tier}",
      "type": "{assessment_type}",
      "questions": [
        {{ "id": 1, "type": "mcq", "question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A" }},
        {{ "id": 7, "type": "descriptive", "question": "..." }}
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
        # Ensure we return the 'questions' list specifically
        return data.get("questions") 
        
    except Exception as e:
        print(f"Groq Generation Error: {e}")
        return None
    # ... (Client execution logic same as before)

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
    
def generate_deep_roadmap(user_id, role="student", subject_id=None, phase_number=1):
    # Using Llama 3.3 70B for better reasoning and larger output limit
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    if role == "student":
        # goal is now a direct variable, not from user_preferences
        target_unit_names = "Units 1, 2, and 3" if phase_number == 1 else "Units 4, 5, and 6"
        
        # Fetching context
        syllabus_context = get_syllabus_from_chroma(subject_id, )
        
        if not syllabus_context:
            raise ValueError(f"Could not retrieve context for {subject_id}")

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
           - Day 8: Learning (Finish Unit 1)
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
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content) if content else None

        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    else:
        # PATH B: INDIVIDUAL (DIAGNOSTIC-BASED)
        from db.models import UserKnowledgeGraph, AssessmentSWOT
    
        graph = UserKnowledgeGraph.objects.get(spring_user_id=user_id)
        swots = AssessmentSWOT.objects.filter(spring_user_id=user_id)
        all_loopholes = []
        
        for s in swots:
            loopholes = getattr(s, 'critical_loopholes', [])
            if loopholes:
                all_loopholes.extend(loopholes)
        
        prompt = f"""
        You are a Senior Technical Architect. Create a deep learning roadmap based on a 7-day diagnostic.

        STUDENT DATA:
        - Domain: {graph.domain}
        - Critical Loopholes: {all_loopholes}
        - Mastered Concepts: {graph.mastery_scores}
        - Primary Error Type: {graph.top_error_type}
        
       
        - Duration: 25 days

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

    try:
        response = client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        
        if content is None:
            raise ValueError("Groq returned empty content.")

        return json.loads(content)
        
    except Exception as e:
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
                 "subject": getattr(task, 'subject', None), 
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
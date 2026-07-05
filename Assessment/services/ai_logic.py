import json
from groq import Groq
from django.conf import settings
from db.models import UserKnowledgeGraph,Roadmap,RoadmapTask
# from .config import get_settings
from django.conf import settings
# from core.settings import get_setting
from django.db import transaction
import chromadb
from django.conf import settings
from db.models import (
    UserKnowledgeGraph, 
    Assessment, 
    AssessmentSWOT, 
    Roadmap, 
    RoadmapTask
)
from chromadb.api.types import Where
import os 
from .drant_service import search_points
from sentence_transformers import SentenceTransformer


client = Groq(api_key=settings.GROQ_API_KEY)
MODEL_NAME = "llama-3.1-8b-instant"

def get_syllabus_from_qdrant(subject_id, user_goal="Complete syllabus mastery"):
    if not subject_id:
        return None

    try:
        collection_name = str(subject_id).replace(" ", "").lower().strip()

        embedding = embedding_model.encode(user_goal).tolist()

        results = search_points(
            collection_name=collection_name,
            query_vector=embedding,
            subject=collection_name,
            doc_type="syllabus",
            limit=25,
        )

        if not results:
            return None

        syllabus = []

        for hit in results:
            syllabus.append(hit.payload["text"])

        return "\n".join(syllabus)

    except Exception as e:
        print(e)
        return None
    
import json

# 🔥 FIX 1: Added user_id to the function arguments
def generate_assessment(user_id, domain, tier, role="STUDENT", assessment_type="ONBOARDING", previous_loopholes=None, chat_context=None):
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
        # 🔥 FIX 2: Define the variable clearly
        questions_data = data.get("questions") 
    
        with transaction.atomic():
            # 1. Store the assessment session
            # Note: Using 'questions_data' to match what we got from the AI
            Assessment.objects.create(
                spring_user_id=user_id,
                domain=domain,
                tier=tier,
                assessment_type=assessment_type,
                questions=questions_data 
            )

            # 2. Update/Create the Knowledge Graph
            UserKnowledgeGraph.objects.get_or_create(
                spring_user_id=user_id,
                domain=domain,
                defaults={
                    'university': 'BMIT', 
                    'mastery_scores': {},
                    'critical_loopholes': []
                }
            )
            
        return questions_data
        
    except Exception as e:
        print(f"Generation Error: {e}")
        return None

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

# 🔥 FIX: Added user_id and assessment_id to the arguments
def evaluate_answer(user_id, assessment_id, question, student_answer, domain):
    """
    Dynamically evaluates answers and STORES the SWOT and Knowledge Graph data.
    """
    
    prompt = f"""
    As a Senior {domain} Specialist and Architect, perform a high-standard forensic analysis 
    of this student's answer for a 50-day elite roadmap.

    Current Domain: {domain}
    Question: {question}
    Student Answer: {student_answer}

    EVALUATION CRITERIA:
    1. DEPTH: Does the user mention internal mechanics, advanced patterns, or performance trade-offs?
    2. PRECISION: Are they using exact industry terminology?
    3. CRITICAL GAPS: What key technical nuances did they NOT mention?

    Return ONLY JSON:
    {{
      "level": "Strong" | "Intermediate" | "Weak",
      "depth_rating": 1-10,
      "score": 0-100,
      "error_type": "Conceptual" | "Logic" | "Syntax" | "None",
      "mastered_topics": [], 
      "critical_gaps": [],    
      "root_cause": "Technical explanation",
      "roadmap_directives": {{
          "immediate_fixes": [],
          "advanced_mastery": [],
          "project_challenge": "..."
      }},
      "feedback": "Direct, professional feedback."
    }}"""
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        content_str = response.choices[0].message.content
        if not content_str:
            raise ValueError("The AI returned an empty response.")
        
        evaluation_data = json.loads(content_str)

        # 🔥 DATABASE PERSISTENCE
        with transaction.atomic():
            # 1. Fetch the actual Assessment record
            assessment_obj = Assessment.objects.get(id=assessment_id)

            # 2. Create the SWOT record (Matches your models.py fields)
            AssessmentSWOT.objects.create(
                assessment=assessment_obj,
                spring_user_id=user_id,
                score=evaluation_data.get('score', 0),
                strengths=evaluation_data.get('mastered_topics', []),
                weaknesses=evaluation_data.get('critical_gaps', []),
                depth_score=evaluation_data.get('depth_rating', 5),
                roadmap_directives=evaluation_data.get('roadmap_directives', {}),
                suggested_focus=evaluation_data.get('feedback', '')
            )

            # 3. Update the Knowledge Graph with the latest results
            UserKnowledgeGraph.objects.filter(
                spring_user_id=user_id, 
                domain__iexact=domain
            ).update(
                mastery_scores=evaluation_data.get('mastered_topics', {}),
                critical_loopholes=evaluation_data.get('critical_gaps', [])
            )

        return evaluation_data
        
    except Exception as e:
        print(f"Evaluation Save Error: {e}")
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
        syllabus_context = get_syllabus_from_qdrant(subject_id)
        # Handle cases where Chroma returns a string saying no syllabus found
        if syllabus_context == "No syllabus found.":
            syllabus_context = None

    # NEW: Create a clean domain name for SQL lookups to avoid naming mismatches
    # e.g., "bmit_cse_4_reactnative" -> "Reactnative"
    clean_domain = domain if domain else str(subject_id).split('_')[-1].title()

    # If we need performance data (Individual OR Student Fallback)
    if not syllabus_context or role == "individual":
        from db.models import UserKnowledgeGraph, AssessmentSWOT
        
        # Use clean_domain for DB queries to ensure we find the SWOT/KnowledgeGraph records
        lookup_domain = clean_domain
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
                    # Handle both list and string types for weaknesses
                    if isinstance(s.weaknesses, list):
                        all_loopholes.extend(s.weaknesses)
                    else:
                        all_loopholes.append(str(s.weaknesses))
            
            loopholes = list(set(all_loopholes)) if all_loopholes else ["Core fundamentals"]
            mastery_data = graph.mastery_scores
            error_type = getattr(graph, 'top_error_type', 'Conceptual')
        except Exception as e:
            print(f"Fallback context lookup failed: {e}")
            # Emergency fallback if no assessment data exists either
            loopholes = ["Core fundamentals", "Industry standards"]
            mastery_data = {}
            error_type = "Conceptual"
            lookup_domain = clean_domain # Ensure lookup_domain is defined
    else:
        # If syllabus exists, we use the original subject_id for the database record
        lookup_domain = subject_id

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
        # PATH B: PERFORMANCE-BASED (The updated Fallback)
        prompt = f"""
        You are a Senior Technical Architect. Generate a STRICT 25-day roadmap based on performance gaps.
        ROLE: {role.upper()}
        DOMAIN: {clean_domain}

        STUDENT DATA:
        - Critical Loopholes: {loopholes}
        - Current Mastery Scores: {mastery_data}
        - Error Pattern: {error_type}

        --- MANDATORY RULES ---
        1. DURATION: Your 'daily_plan' array MUST contain exactly 25 objects (Day 1 to Day 25).
        2. PHASE 1 (Remediation): Days 1-7 (Fixing Critical Loopholes).
        3. PHASE 2 (Progression): Days 8-20 (Advanced concepts and industry-standard patterns).
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

        roadmap_json = json.loads(content)

        with transaction.atomic():
            new_roadmap = Roadmap.objects.create(
                spring_user_id=user_id,
                subject=lookup_domain,
                title=roadmap_json.get('title', f"Mastery: {lookup_domain}"),
                overview="Personalized learning path based on assessment gaps.",
                full_data=roadmap_json
            )

            tasks = [
                RoadmapTask(
                    roadmap=new_roadmap,
                    day_number=d['day'],
                    topic=d['topic'],
                    task_description=d['task'],
                    phase_name=d.get('type', 'Learning'),
                    depth=d.get('depth', 'Intermediate')
                ) for d in roadmap_json.get('daily_plan', [])
            ]
            RoadmapTask.objects.bulk_create(tasks)
            
            UserKnowledgeGraph.objects.filter(spring_user_id=user_id, domain=lookup_domain).update(has_roadmap=True)
            
        return roadmap_json # Return the JSON so the view can send it to the mobile app
        
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
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from django.db import connection
from rest_framework.permissions import IsAuthenticated

from db.models import (
    Assessment, AssessmentSWOT, UserKnowledgeGraph, 
    RoadmapTask, Roadmap, AssessmentTier, AssessmentType
)
from django.db import transaction
from services.ai_logic import (
    generate_assessment, # Updated from generate_diagnostic
    evaluate_answer, 
    generate_deep_roadmap,
    get_existing_roadmap_data
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny 
from django.db import transaction

from db.models import Roadmap, RoadmapTask, UserKnowledgeGraph
from services.ai_logic import generate_deep_roadmap
from rest_framework import status

# Ensure these imports match your project structure


class GenerateTestView(APIView):
    """
    Acts as an AI-Microservice. Receives spring_user_id from the Mobile app 
    (after Spring Boot Auth) and manages the assessment progression.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. DATA EXTRACTION
        # We take the ID from the request body as Spring is the source of truth
        spring_user_id = request.data.get("spring_user_id")
        raw_domain = request.data.get("domain")

        if not spring_user_id or not raw_domain:
            return Response(
                {"error": "Both spring_user_id and domain are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. NORMALIZATION
        domain = raw_domain.strip().title() # "react native" -> "React Native"
        # Optional: Get role from request or default to STUDENT
        user_role = request.data.get("role", "STUDENT").upper()

        # 3. PROGRESSION CHECK (EASY -> MEDIUM -> HARD)
        # Check which tiers this specific Spring User has already finished
        completed_tiers = Assessment.objects.filter(
            spring_user_id=spring_user_id,
            domain__iexact=domain,
            is_completed=True
        ).values_list('tier', flat=True)

        if "EASY" not in completed_tiers:
            next_tier = "EASY"
        elif "MEDIUM" not in completed_tiers:
            next_tier = "MEDIUM"
        elif "HARD" not in completed_tiers:
            next_tier = "HARD"
        else:
            return Response({
                "status": "completed",
                "message": f"Assessment for {domain} is already fully complete!",
                "onboarding_finished": True
            }, status=status.HTTP_200_OK)

        # 4. IDEMPOTENCY (Don't generate a new one if an unfinished one exists)
        existing_assessment = Assessment.objects.filter(
            spring_user_id=spring_user_id,
            domain__iexact=domain,
            tier=next_tier,
            is_completed=False
        ).first()

        if existing_assessment:
            return Response({
                "status": "exists",
                "test_id": existing_assessment.id,
                "domain": existing_assessment.domain,
                "tier": existing_assessment.tier,
                "questions": existing_assessment.questions 
            }, status=status.HTTP_200_OK)

        # 5. AI GENERATION LOGIC
        try:
            # Fetch previous loopholes from SWOT to make the next test harder/targeted
            previous_swot = AssessmentSWOT.objects.filter(
                spring_user_id=spring_user_id,
                assessment__domain__iexact=domain
            ).order_by("-created_at").first()
            
            loopholes = previous_swot.weaknesses if previous_swot else []

            # Call our AI Service (from ai_logic.py)
            generated_questions = generate_assessment(
                user_id=spring_user_id, # Passing Spring ID to AI Logic
                domain=domain, 
                tier=next_tier, 
                role=user_role,
                assessment_type="ONBOARDING", 
                previous_loopholes=loopholes
            )

            if not generated_questions:
                return Response({"error": "AI failed to generate questions"}, status=500)

            # 6. DATABASE PERSISTENCE
            with transaction.atomic():
                # Create the Assessment
                new_assessment = Assessment.objects.create(
                    spring_user_id=spring_user_id,
                    domain=domain,
                    tier=next_tier,
                    assessment_type="ONBOARDING",
                    is_completed=False,
                    questions=generated_questions
                )

                # Ensure Knowledge Graph entry exists for this Spring User
                UserKnowledgeGraph.objects.get_or_create(
                    spring_user_id=spring_user_id,
                    domain=domain,
                    defaults={'university': 'BMIT'} # You can pass this from Spring too
                )

            return Response({
                "status": "generated",
                "test_id": new_assessment.id,
                "domain": new_assessment.domain,
                "tier": new_assessment.tier,
                "questions": new_assessment.questions 
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"Internal Server Error: {str(e)}"}, status=500)

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

class SubmitAnswersView(APIView):
    """
    Receives answers from the mobile app, evaluates them via AI, 
    and updates the user's technical profile (SWOT & Knowledge Graph).
    """
   

    def post(self, request):
        # 1. DATA EXTRACTION
        test_id = request.data.get("test_id")
        answers = request.data.get("answers", [])
        spring_user_id = request.data.get("spring_user_id") # Explicitly sent from App

        if not test_id or not spring_user_id:
            return Response(
                {"error": "test_id and spring_user_id are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Fetch the assessment ensuring it belongs to the correct Spring User
            assessment = Assessment.objects.get(
                id=test_id, 
                spring_user_id=spring_user_id
            )

            if assessment.is_completed:
                return Response({"error": "This test has already been submitted."}, status=400)

        except Assessment.DoesNotExist:
            return Response({"error": "Assessment record not found."}, status=404)

        # 2. EVALUATION INITIALIZATION
        questions_list = assessment.questions
        answers_map = {str(a["id"]): a["answer"] for a in answers if isinstance(a, dict)}

        strength_tags = []
        weakness_tags = []
        depth_scores = []
        master_directives = []
        error_counts = {"Syntax": 0, "Logic": 0, "Conceptual": 0}

        total_mcq_correct = 0
        mcq_count = 0

        # 3. CORE PROCESSING LOOP
        for q in questions_list:
            q_id = str(q.get("id"))
            u_ans = answers_map.get(q_id, "").strip()

            # --- MCQ LOGIC ---
            if q.get("type") == "mcq":
                mcq_count += 1
                if u_ans.upper() == str(q.get("answer", "")).upper():
                    total_mcq_correct += 1
                    strength_tags.append(q.get("topic", "General"))
                else:
                    weakness_tags.append(q.get("topic", "General"))

            # --- DESCRIPTIVE AI LOGIC ---
            elif q.get("type") == "descriptive":
                try:
                    # Call AI Service with the explicit Spring ID
                    result = evaluate_answer(
                        user_id=spring_user_id,
                        assessment_id=assessment.id,
                        question=q["question"],
                        student_answer=u_ans,
                        domain=assessment.domain
                    )

                    depth_scores.append(result.get("depth_rating", 5))
                    
                    if result.get("roadmap_directives"):
                        master_directives.append(result.get("roadmap_directives"))

                    e_type = result.get("error_type")
                    if e_type in error_counts:
                        error_counts[e_type] += 1

                    strength_tags.extend(normalize_list(result.get("mastered_topics", [])))
                    weakness_tags.extend(normalize_list(result.get("critical_gaps", [])))

                except Exception as e:
                    print(f"AI Eval failed for Q{q_id}: {e}")

        # 4. FINAL SCORING
        final_score = (total_mcq_correct / mcq_count * 100) if mcq_count > 0 else 0
        avg_depth = sum(depth_scores) / len(depth_scores) if depth_scores else 5

        # 5. DATABASE PERSISTENCE (Atomic)
        with transaction.atomic():
            # Save SWOT Analysis
            AssessmentSWOT.objects.update_or_create(
                assessment=assessment, # ✅ This is the UNIQUE lookup field
                defaults={             # ✅ Everything else goes here
                    "spring_user_id": spring_user_id,
                    "score": final_score,
                    "depth_score": int(avg_depth),
                    "strengths": list(set(strength_tags)),
                    "weaknesses": list(set(weakness_tags)),
                    "error_analysis": error_counts,
                    "roadmap_directives": {"collection": master_directives}
                }
            )

            # Mark Assessment as done
            assessment.is_completed = True
            assessment.answers = answers 
            assessment.save()

            # Update Knowledge Graph Progression
            completed_tiers = Assessment.objects.filter(
                spring_user_id=spring_user_id,
                domain=assessment.domain,
                is_completed=True
            ).values_list('tier', flat=True).distinct()

            # If they finished EASY, MEDIUM, and HARD, they are ready for the Roadmap
            has_full_progression = all(t in completed_tiers for t in ["EASY", "MEDIUM", "HARD"])

            UserKnowledgeGraph.objects.filter(
                spring_user_id=spring_user_id, 
                domain=assessment.domain
            ).update(
                is_onboarding_complete=has_full_progression,
                is_ready_for_roadmap=has_full_progression
            )

        return Response({
            "status": "Success",
            "score": final_score,
            "tier_completed": assessment.tier,
            "onboarding_finished": has_full_progression,
            "ready_for_roadmap": has_full_progression
        }, status=status.HTTP_201_CREATED)

class GenerateRoadmapView(APIView):
    """
    Generates a personalized learning roadmap based on the Spring User ID.
    Uses transaction.atomic to ensure the Roadmap and all RoadmapTasks 
    are saved together or not at all.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # 1. DATA EXTRACTION
            # Get the Spring User ID and context from request body
            user_id = request.data.get('user_id') 
            role = request.data.get('role', 'student').lower()
            phase = int(request.data.get('phase', 1))
            is_complete = request.data.get('is_complete', False)
            domain = request.data.get('domain')
            
            # Academic details (primarily for students)
            university = request.data.get('university', '').lower()
            branch = request.data.get('branch', '').lower()
            year = request.data.get('year', '')
            subject = request.data.get('subject_id', '').lower()

            # 2. VALIDATION GATES
            if not user_id:
                return Response({"error": "user_id (Spring ID) is required."}, status=status.HTTP_400_BAD_REQUEST)

            if not is_complete:
                return Response({
                    "error": "Profile Incomplete",
                    "message": "Please finish your academic setup in the app first."
                }, status=status.HTTP_400_BAD_REQUEST)

            # 3. IDEMPOTENCY CHECK
            # Check if a roadmap for this specific subject/phase already exists for this Spring user
            existing_roadmap = Roadmap.objects.filter(
                spring_user_id=user_id,
                subject=subject,
                title__icontains=f"Phase {phase}"
            ).first()

            if existing_roadmap:
                return Response({
                    "message": "Roadmap already exists.",
                    "roadmap_id": existing_roadmap.id,
                    "data": existing_roadmap.full_data
                }, status=status.HTTP_200_OK)

            # 4. FORMATTING FOR AI
            # This helps the AI context (ChromaDB collection mapping)
            formatted_subject_id = f"{university}_{branch}_{year}_{subject}" if role == 'student' else subject

            # 5. AI GENERATION
            roadmap_data = generate_deep_roadmap(
                user_id=user_id,
                role=role,
                subject_id=formatted_subject_id,
                phase_number=phase,
                domain=domain
            )

            # Safety check for AI failure
            if not roadmap_data or "error" in roadmap_data:
                return Response({
                    "error": "AI Generation Failed",
                    "message": roadmap_data.get("message", "AI service timeout or syllabus missing.") if roadmap_data else "Empty AI response."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 6. ATOMIC SAVE (DATABASE)
            with transaction.atomic():
                # Get or link the Knowledge Graph for this Spring user
                graph = None
                if domain:
                    graph, _ = UserKnowledgeGraph.objects.get_or_create(
                        spring_user_id=user_id,
                        domain__iexact=domain
                    )

                # Create main Roadmap entry
                roadmap_obj = Roadmap.objects.create(
                    knowledge_graph=graph,
                    spring_user_id=user_id,
                    title=roadmap_data.get("title", f"Phase {phase}: {subject.upper()}"),
                    full_data=roadmap_data,
                    subject=subject 
                )

                # Bulk create the daily plan tasks
                daily_plans = roadmap_data.get("daily_plan") or []
                tasks = [
                    RoadmapTask(
                        roadmap=roadmap_obj,
                        day_number=t.get("day"),
                        topic=t.get("topic"),
                        task_description=t.get("task"),
                        phase_name=t.get("type", "Learning")
                    ) for t in daily_plans if isinstance(t, dict)
                ]
                RoadmapTask.objects.bulk_create(tasks)

                # Optional: Update the graph to reflect that a roadmap is now active
                if graph:
                    graph.has_roadmap = True
                    graph.save()

            return Response({
                "status": "success",
                "message": "Roadmap created!",
                "roadmap_id": roadmap_obj.id,
                "data": roadmap_data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserProgressStatusView(APIView):
    def get(self, request, spring_user_id):
        try:
            # 1. Get or create the Knowledge Graph record
            # If it doesn't exist, the user hasn't started Phase 1.
            kg = UserKnowledgeGraph.objects.filter(spring_user_id=spring_user_id).first()

            if not kg:
                return Response({
                    "profile_complete": False,
                    "test_count": 0,
                    "is_ready_for_roadmap": False,
                    "has_roadmap": False,
                    "domain": None
                }, status=status.HTTP_200_OK)

            # 2. Safety Sync: Recalculate test count to ensure DB integrity
            actual_test_count = Assessment.objects.filter(
                spring_user_id=spring_user_id, 
                is_completed=True
            ).count()
            
            # Update KG if count changed
            if kg.test_count != actual_test_count:
                kg.test_count = actual_test_count
                kg.save()

            # 3. Check Roadmap existence
            roadmap_exists = Roadmap.objects.filter(spring_user_id=spring_user_id).exists()
            if kg.has_roadmap != roadmap_exists:
                kg.has_roadmap = roadmap_exists
                kg.save()

            # 4. Final Logic Check for "Phase Readiness"
            # Ensure onboarding is marked complete if uni and domain exist
            if not kg.is_onboarding_complete and kg.university and kg.domain:
                kg.is_onboarding_complete = True
                kg.save()

            # Ensure ready flag is set if tests hit 3
            if kg.test_count >= 3 and not kg.is_ready_for_roadmap:
                kg.is_ready_for_roadmap = True
                kg.save()

            return Response({
                "spring_user_id": spring_user_id,
                "profile_complete": kg.is_onboarding_complete,
                "test_count": kg.test_count,
                "is_ready_for_roadmap": kg.is_ready_for_roadmap,
                "has_roadmap": kg.has_roadmap,
                "domain": kg.domain,
                "university": kg.university
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class GetLatestRoadmapView(APIView):
    """
    Retrieves the most recent roadmap for a specific Spring User.
    Usage: GET /api/roadmap/latest/<spring_user_id>/
    """
    permission_classes = [AllowAny] 

    def get(self, request, user_id):
        # 1. Call your helper function
        roadmap_data = get_existing_roadmap_data(user_id)

        # 2. Handle Case: No Roadmap Found
        if not roadmap_data:
            return Response({
                "exists": False,
                "message": "No roadmap found for this user. Please generate one first."
            }, status=status.HTTP_404_NOT_FOUND)

        # 3. Return data in the structure the App expects
        return Response({
            "exists": True,
            **roadmap_data
        }, status=status.HTTP_200_OK)
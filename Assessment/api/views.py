from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from rest_framework.permissions import IsAuthenticated

from db.models import (
    Assessment, AssessmentSWOT, UserKnowledgeGraph, 
    RoadmapTask, Roadmap, AssessmentTier, AssessmentType
)
from services.ai_logic import (
    generate_assessment, # Updated from generate_diagnostic
    evaluate_answer, 
    generate_deep_roadmap,
    get_existing_roadmap_data
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

# Ensure these imports match your project structure


class GenerateTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.id
        domain = request.data.get("domain")

        if not domain:
            return Response({"error": "Domain is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Determine which tier is next based on completed SWOTs
        completed_tiers = AssessmentSWOT.objects.filter(
            spring_user_id=user_id,
            assessment__domain=domain
        ).values_list('assessment__tier', flat=True)

        if "EASY" not in completed_tiers:
            next_tier = AssessmentTier.EASY
        elif "MEDIUM" not in completed_tiers:
            next_tier = AssessmentTier.MEDIUM
        elif "HARD" not in completed_tiers:
            next_tier = AssessmentTier.HARD
        else:
            return Response({
                "message": "Onboarding tiers complete!", 
                "onboarding_finished": True
            }, status=status.HTTP_200_OK)

        # 2. Try to fetch an existing, incomplete assessment for this tier
        # This prevents re-generating questions if the user refreshes the page
        assessment = Assessment.objects.filter(
            spring_user_id=user_id,
            domain=domain,
            tier=next_tier,
            assessment_type=AssessmentType.ONBOARDING,
            is_completed=False
        ).first()

        # 3. If no incomplete assessment exists, generate a new one
        if not assessment:
            # Fetch loopholes from the absolute latest SWOT for adaptive questions
            previous_swot = AssessmentSWOT.objects.filter(
                spring_user_id=user_id,
                assessment__domain=domain
            ).order_by("-assessment__created_at").first()
            
            loopholes = previous_swot.weaknesses if previous_swot else None

            # Generate the questions
            generated_questions = generate_assessment(
                domain=domain, 
                tier=next_tier, 
                assessment_type=AssessmentType.ONBOARDING, 
                previous_loopholes=loopholes
            )

            # Check if generation actually returned data to avoid IntegrityError
            if not generated_questions:
                return Response({
                    "error": "Failed to generate questions. Please check your AI service or domain constraints."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Create the record in the database
            assessment = Assessment.objects.create(
                spring_user_id=user_id,
                domain=domain,
                tier=next_tier,
                assessment_type=AssessmentType.ONBOARDING,
                is_completed=False,
                questions=generated_questions
            )

        # 4. Return the assessment (either the existing one or the newly created one)
        return Response({
            "tier": assessment.tier,
            "test_id": assessment.id,
            "questions": assessment.questions
        }, status=status.HTTP_200_OK)

class SubmitAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        test_id = request.data.get("test_id")
        answers = request.data.get("answers", []) 

        try:
            assessment = Assessment.objects.get(id=test_id, spring_user_id=request.user.id)
            if assessment.is_completed:
                return Response({"error": "Test already submitted."}, status=status.HTTP_400_BAD_REQUEST)
        except Assessment.DoesNotExist:
            return Response({"error": "Test not found."}, status=status.HTTP_404_NOT_FOUND)

        # ── 1. Scoring & Deep Analysis ──
        questions_list = assessment.questions
        answers_map = {str(a["id"]): a["answer"] for a in answers}
        
        strength_tags, weakness_tags = [], []
        depth_scores = []
        master_directives = []
        error_counts = {"Syntax": 0, "Logic": 0, "Conceptual": 0}
        total_mcq_correct = 0
        mcq_count = 0

        for q in questions_list:
            u_ans = answers_map.get(str(q.get("id")), "").strip()
            
            if q.get("type") == "mcq":
                mcq_count += 1
                if u_ans.upper() == str(q.get("answer", "")).upper():
                    total_mcq_correct += 1
                    strength_tags.append(q.get("topic", "General"))
                else:
                    weakness_tags.append(q.get("topic", "General"))

            elif q.get("type") == "descriptive":
                try:
                    # DYNAMIC CALL: Uses assessment.domain for targeted evaluation
                    result = evaluate_answer(q["question"], u_ans, assessment.domain) 
                    
                    # Track depth and directives for the Roadmap
                    depth_scores.append(result.get("depth_rating", 5))
                    if result.get("roadmap_directives"):
                        master_directives.append(result.get("roadmap_directives"))

                    # Aggregate Error Types
                    e_type = result.get("error_type")
                    if e_type in error_counts:
                        error_counts[e_type] += 1
                    
                    # Handle new LIST-based tags
                    mastered = result.get("mastered_topics", [])
                    gaps = result.get("critical_gaps", [])
                    
                    strength_tags.extend(mastered)
                    weakness_tags.extend(gaps)

                except Exception as e:
                    print(f"AI Evaluation failed for Q{q.get('id')}: {e}")

        # Final Scoring logic
        final_score = (total_mcq_correct / mcq_count * 100) if mcq_count > 0 else 0
        avg_depth = sum(depth_scores) / len(depth_scores) if depth_scores else 5

        # ── 2. Create High-Standard SWOT ──
        AssessmentSWOT.objects.create(
            assessment=assessment,
            spring_user_id=str(request.user.id),
            score=final_score,
            depth_score=int(avg_depth),
            strengths=list(set(filter(None, strength_tags))),
            weaknesses=list(set(filter(None, weakness_tags))),
            error_analysis=error_counts,
            roadmap_directives={"collection": master_directives}
        )

        assessment.is_completed = True
        assessment.answers = answers 
        assessment.save()

        # ── 3. Knowledge Graph Update ──
        completed_tiers = Assessment.objects.filter(
            spring_user_id=request.user.id,
            domain=assessment.domain,
            is_completed=True
        ).values_list('tier', flat=True).distinct()

        # The core logic: Must have EASY, MEDIUM, and HARD in the history
        has_full_progression = all(tier in completed_tiers for tier in ["EASY", "MEDIUM", "HARD"])

        if has_full_progression:
            # Aggregate all weaknesses from the entire journey for a better roadmap
            all_swots = AssessmentSWOT.objects.filter(
                spring_user_id=request.user.id,
                assessment__domain=assessment.domain
            )
            
            master_gaps = []
            for s in all_swots: 
                master_gaps.extend(s.weaknesses)

            # Unlock the Roadmap
            UserKnowledgeGraph.objects.update_or_create(
                spring_user_id=request.user.id,
                domain=assessment.domain,
                defaults={
                    "critical_loopholes": list(set(master_gaps)),
                    "is_onboarding_complete": True,
                    "is_ready_for_roadmap": True
                }
            )

        return Response({
            "status": "Success", 
            "tier_completed": assessment.tier,
            "onboarding_finished": has_full_progression, # Use the logic check here
            "depth_rating": avg_depth,
            "ready_for_roadmap": has_full_progression
        }, status=status.HTTP_201_CREATED)

class GenerateRoadmapView(APIView):
    def post(self, request):
        try:
            # 1. DATA EXTRACTION
            user_id = request.data.get('user_id')
            role = request.data.get('role', 'student').lower()
            phase = int(request.data.get('phase', 1))
            is_complete = request.data.get('is_complete', False)
            domain = request.data.get('domain')
            
            university = request.data.get('university', '').lower()
            branch = request.data.get('branch', '').lower()
            year = request.data.get('year', '')
            subject = request.data.get('subject_id', '').lower()
            
            # Format the Chroma Collection Name
            formatted_subject_id = f"{university}_{branch}_{year}_{subject}" if role == 'student' else subject

            # 2. VALIDATION GATES
            if not user_id:
                return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

            if not is_complete:
                return Response({
                    "error": "Profile Incomplete",
                    "message": "Please finish your academic setup first."
                }, status=status.HTTP_400_BAD_REQUEST)

            # 3. DUPLICATE CHECK (Fixes the Error in Image 2)
            # You cannot use 'if role == student' inside the filter like that. 
            # We use Q objects or a conditional dictionary.
            filter_kwargs = {
                "spring_user_id": user_id,
                "title__icontains": f"Phase {phase}"
            }
            if role == 'student':
                filter_kwargs["title__icontains"] = subject

            existing_roadmap = Roadmap.objects.filter(**filter_kwargs).first()

            if existing_roadmap:
                return Response({
                    "message": "Roadmap already exists.",
                    "roadmap_id": existing_roadmap.id,
                    "data": existing_roadmap.full_data
                }, status=status.HTTP_200_OK)

            # 4. GENERATE VIA AI (Only call this ONCE)
            roadmap_data = generate_deep_roadmap(
                user_id=user_id,
                role=role,
                subject_id=formatted_subject_id,
                phase_number=phase,
                
               
            )

            # 5. SAFETY CHECK (Fixes the Error in Image 1)
            if not roadmap_data or "error" in roadmap_data:
                return Response({
                    "error": "AI Generation Failed",
                    "message": roadmap_data.get("message", "Syllabus missing or AI timeout.") if roadmap_data else "Empty AI response."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 6. SAVE TO DATABASE
            graph = None
            if domain:
                graph, _ = UserKnowledgeGraph.objects.get_or_create(
                    spring_user_id=user_id,
                    domain__iexact=domain
                )

            roadmap_obj = Roadmap.objects.create(
                knowledge_graph=graph,
                spring_user_id=user_id,
                title=roadmap_data.get("title", f"Phase {phase}: {subject.upper()}"),
                full_data=roadmap_data
            )

            # 7. BULK CREATE TASKS
            daily_plans = roadmap_data.get("daily_plan", [])
            tasks = [
                RoadmapTask(
                    roadmap=roadmap_obj,
                    day_number=t.get("day"),
                    topic=t.get("topic"),
                    task_description=t.get("task"),
                    phase_name=t.get("type", "Learning")
                ) for t in daily_plans
            ]
            RoadmapTask.objects.bulk_create(tasks)

            return Response({
                "message": "Roadmap created!",
                "roadmap_id": roadmap_obj.id,
                "data": roadmap_data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class GetLatestRoadmapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        # Call the method we just created in ai_logic
        roadmap_data = get_existing_roadmap_data(user_id)

        if not roadmap_data:
            return Response({
                "exists": False, 
                "message": "No roadmap found for this user."
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "exists": True,
            **roadmap_data
        }, status=status.HTTP_200_OK)
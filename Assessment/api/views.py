from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from rest_framework.permissions import IsAuthenticated

from db.models import Assessment, DailySWOT, UserKnowledgeGraph ,RoadmapTask ,Roadmap
from services.ai_logic import generate_diagnostic, evaluate_answer, generate_deep_roadmap,get_existing_roadmap_data

class GenerateTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.id
        domain = request.data.get("domain")
        university = request.data.get("university")

        completed_days = Assessment.objects.filter(
            spring_user_id=user_id, 
            domain=domain,
            is_completed=True
        ).count()

        if completed_days >= 3:
            return Response({"message": "3-day onboarding complete!", "onboarding_finished": True}, status=200)

        current_day = completed_days + 1

        # Fetch loopholes for adaptive testing
        previous_swot = DailySWOT.objects.filter(
            spring_user_id=user_id,
            assessment__domain=domain
        ).order_by("-assessment__day_number").first()
        
        loopholes = previous_swot.weaknesses if previous_swot else None

        assessment, created = Assessment.objects.get_or_create(
            spring_user_id=user_id,
            day_number=current_day,
            domain=domain,
            defaults={
                "questions": generate_diagnostic(domain, university, current_day, previous_loopholes=loopholes)
            }
        )

        return Response({
            "day": assessment.day_number,
            "test_id": assessment.id,
            "questions": assessment.questions
        })

class SubmitAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        test_id = request.data.get("test_id")
        answers = request.data.get("answers") 

        try:
            assessment = Assessment.objects.get(id=test_id, spring_user_id=request.user.id)
            if assessment.is_completed:
                return Response({"error": "Test already submitted."}, status=status.HTTP_400_BAD_REQUEST)
        except Assessment.DoesNotExist:
            return Response({"error": "Test not found."}, status=status.HTTP_404_NOT_FOUND)

        questions_data = assessment.questions
        if isinstance(questions_data, str):
            questions_data = json.loads(questions_data)
        
        actual_questions_list = questions_data.get("questions", questions_data)
        answers_map = {str(a["id"]): a["answer"] for a in answers}

        # ── 1. MCQ Scoring ──
        mcqs = [q for q in actual_questions_list if q.get("type") == "mcq"]
        correct = sum(1 for q in mcqs if answers_map.get(str(q["id"]), "").strip().upper() == str(q.get("answer", "")).upper())
        mcq_score = (correct / len(mcqs) * 100) if mcqs else 0

        # ── 2. Descriptive Evaluation ──
        descriptive_qs = [q for q in actual_questions_list if q.get("type") == "descriptive"]
        strength_tags, weakness_tags, error_counts = [], [], {"Syntax": 0, "Logic": 0, "Conceptual": 0}

        for q in descriptive_qs:
            ans = answers_map.get(str(q["id"]), "")
            if ans:
                result = evaluate_answer(q["question"], ans) 
                e_type = result.get("error_type", "None")
                if e_type in error_counts:
                    error_counts[e_type] += 1
                
                if result.get("level") == "Strong":
                    strength_tags.append(result.get("concept_mastered"))
                elif result.get("knowledge_gap"):
                    weakness_tags.append(result.get("knowledge_gap"))

        # ── 3. Save Daily Result ──
        DailySWOT.objects.create(
            spring_user_id=str(request.user.id),
            assessment=assessment,
            day_score=mcq_score,
            strengths=strength_tags,
            weaknesses=weakness_tags,
            error_analysis=error_counts
        )

        assessment.is_completed = True
        assessment.answers = answers 
        assessment.save()

        # ── 4. FINALIZATION: Create Master Profile on Day 7 ──
        completed_count = Assessment.objects.filter(
            spring_user_id=request.user.id, 
            domain=assessment.domain, 
            is_completed=True
        ).count()
        
        if completed_count >= 3:
            all_swots = DailySWOT.objects.filter(
                spring_user_id=request.user.id, 
                assessment__domain=assessment.domain
            )
            
            master_weaknesses = []
            total_errors = {"Syntax": 0, "Logic": 0, "Conceptual": 0}
            for s in all_swots:
                master_weaknesses.extend(s.weaknesses)
                for k, v in s.error_analysis.items():
                    total_errors[k] = total_errors.get(k, 0) + v

            # FIX for the "max" warning
            top_error = "Conceptual" # Default
            if any(total_errors.values()):
                top_error = max(total_errors, key=lambda k: total_errors[k])

            UserKnowledgeGraph.objects.update_or_create(
                spring_user_id=request.user.id,
                domain=assessment.domain,
                defaults={
                    "critical_loopholes": list(set([w for w in master_weaknesses if master_weaknesses.count(w) > 1])),
                    "top_error_type": top_error,
                    "is_ready_for_roadmap": True
                }
            )

        return Response({"status": "Success", "onboarding_finished": completed_count >= 3}, status=201)

class GenerateRoadmapView(APIView):
    def post(self, request):
        # 1. EXTRACT DATA FROM YOUR JSON PAYLOAD
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'student').lower()
        subject_id = request.data.get('subject_id')
        domain = request.data.get('domain')
        phase = int(request.data.get('phase', 1))
        
        # Gatekeeper variables from Spring
        is_complete = request.data.get('is_complete', False)
        daily_hours = request.data.get('daily_hours')
        goal = request.data.get('goal')

        # 2. VALIDATION GATES
        if not user_id:
            return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not is_complete:
            return Response({
                "error": "Profile Incomplete",
                "message": "Please finish setting up your profile in the main app."
            }, status=status.HTTP_400_BAD_REQUEST)

        if role == 'student' and not subject_id:
            return Response({"error": "subject_id is required for students."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. DUPLICATE CHECK (Using the UUID string)
        # We check if Phase X for this subject/domain already exists for this UUID
        existing_roadmap = Roadmap.objects.filter(
            spring_user_id=user_id,
            title__icontains=f"Phase {phase}",
            # If you store subject_id in Roadmap model, add filter here
        ).first()

        if existing_roadmap:
            return Response({
                "message": f"Phase {phase} roadmap already exists.",
                "roadmap_id": existing_roadmap.id,
                "data": existing_roadmap.full_data
            }, status=status.HTTP_200_OK)

        # 4. PREPARE AI PREFERENCES
        user_preferences = {
            "daily_hours": daily_hours or 2,
            "total_days": 25, # Fixed as per your prompt rules
            "goal": goal or "General Mastery",
        }

        try:
            # 5. GENERATE VIA AI
            # This calls the function using Llama 3.3 70B
            roadmap_data = generate_deep_roadmap(
                user_id, 
                user_preferences, 
                role=role, 
                subject_id=subject_id,
                phase_number=phase
            )

            if not roadmap_data:
                return Response({"error": "AI failed to generate roadmap."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 6. DATABASE SYNC (SQL)
            # Find or create a graph reference if domain is provided
            graph = None
            if domain:
                graph, _ = UserKnowledgeGraph.objects.get_or_create(
                    spring_user_id=user_id,
                    domain__iexact=domain,
                    defaults={'title': f"{domain} Path"}
                )

            # Create the Roadmap entry
            roadmap_obj = Roadmap.objects.create(
                knowledge_graph=graph,
                spring_user_id=user_id, # Storing the UUID string
                title=roadmap_data.get("title", f"Phase {phase}: {subject_id}"),
                overview=roadmap_data.get("overview", f"Mastery plan for {subject_id}"),
                full_data=roadmap_data
            )

            # 7. BULK INSERT TASKS
            daily_plans = roadmap_data.get("daily_plan", [])
            tasks_to_create = [
                RoadmapTask(
                    roadmap=roadmap_obj,
                    day_number=t.get("day"),
                    phase_name=t.get("type", "Learning"),
                    topic=t.get("topic", "General Topic"),
                    task_description=t.get("task", "")
                ) for t in daily_plans
            ]
            RoadmapTask.objects.bulk_create(tasks_to_create)

            return Response({
                "message": f"Phase {phase} roadmap generated successfully!",
                "roadmap_id": roadmap_obj.id,
                "data": roadmap_data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Roadmap Error: {str(e)}")
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
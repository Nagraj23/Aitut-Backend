from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from rest_framework.permissions import IsAuthenticated

from db.models import Assessment, DailySWOT, UserKnowledgeGraph ,RoadmapTask ,Roadmap
from services.ai_logic import generate_diagnostic, evaluate_answer, generate_deep_roadmap

# ─────────────────────────────────────────────
# 1️⃣ Generate Diagnostic Test
# ─────────────────────────────────────────────
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

        if completed_days >= 7:
            return Response({"message": "7-day onboarding complete!", "onboarding_finished": True}, status=200)

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

# ─────────────────────────────────────────────
# 2️⃣ Submit Answers & Generate SWOT
# ─────────────────────────────────────────────
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
        
        if completed_count >= 7:
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

        return Response({"status": "Success", "onboarding_finished": completed_count >= 7}, status=201)

# ─────────────────────────────────────────────
# 3️⃣ Generate Roadmap (Day 8)
# ─────────────────────────────────────────────
class GenerateRoadmapView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. Force ID to string to match the CharField in Postgres
        user_id = str(request.user.id) 
        domain = request.data.get('domain')
        
        user_preferences = {
            "daily_hours": request.data.get('daily_hours'),
            "total_days": request.data.get('total_days'),
            "goal": request.data.get('goal')
        }

        try:
            # 2. Use __iexact for the domain to prevent case-sensitivity issues
            graph = UserKnowledgeGraph.objects.get(
                spring_user_id=user_id, 
                domain__iexact=domain
            )
            
            if not graph.is_ready_for_roadmap:
                return Response({"error": "Onboarding not complete. Please finish 7 days."}, status=403)

            # 3. Generate the Roadmap via AI
            roadmap_data = generate_deep_roadmap(user_id, user_preferences)

            # 4. SAVE the Roadmap so it persists in the database
            roadmap_obj = Roadmap.objects.create(
                knowledge_graph=graph,
                spring_user_id=user_id,
                title=roadmap_data.get("title", f"{domain} Mastery Path"),
                overview=roadmap_data.get("overview", ""),
                full_data=roadmap_data # Saving the whole JSON
            )
            
            # 5. Optional: Save individual tasks if you want to track them
            days = roadmap_data.get("daily_plan", [])
            for day in days:
                RoadmapTask.objects.create(
                    roadmap=roadmap_obj,
                    day_number=day.get("day"),
                    phase_name=day.get("phase", "Learning"),
                    topic=day.get("topic", ""),
                    task_description=day.get("task", ""),
                    depth=day.get("depth", "DeepDive")
                )

            return Response({
                "message": "Roadmap generated and saved successfully!",
                "roadmap_id": roadmap_obj.id,
                "data": roadmap_data
            }, status=status.HTTP_201_CREATED)

        except UserKnowledgeGraph.DoesNotExist:
            return Response({
                "error": f"Knowledge graph not found for User {user_id} and Domain {domain}."
            }, status=status.HTTP_404_NOT_FOUND)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from rest_framework.permissions import IsAuthenticated

from db.models import Assessment, DailySWOT
from services.ai_logic import generate_diagnostic, evaluate_answer

# ─────────────────────────────────────────────
# 1️⃣ Generate Diagnostic Test
# ─────────────────────────────────────────────
class GenerateTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.user.id
        domain = request.data.get("domain")
        university = request.data.get("university")

        # 1. Check how many days are completed
        completed_days = Assessment.objects.filter(
            spring_user_id=user_id, 
            is_completed=True
        ).count()

        if completed_days >= 7:
            return Response({"message": "7-day onboarding complete!"}, status=200)

        current_day = completed_days + 1

        # 2. Prevent generating the same day's test twice
        assessment, created = Assessment.objects.get_or_create(
            spring_user_id=user_id,
            day_number=current_day,
            defaults={
                "domain": domain,
                "questions": generate_diagnostic(domain, university, current_day)
            }
        )

        return Response({
            "day": assessment.day_number,
            "test_id": assessment.id,
            "questions": assessment.questions
        })
        # except Exception as e:
        #     return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────
# 2️⃣ Submit Answers & Generate SWOT
# ─────────────────────────────────────────────


class SubmitAnswersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        test_id = request.data.get("test_id")
        answers = request.data.get("answers") 

        try:
            # Ensure the test belongs to the user and isn't already submitted
            assessment = Assessment.objects.get(id=test_id, spring_user_id=request.user.id)
            if assessment.is_completed:
                return Response({"error": "This test has already been submitted."}, status=status.HTTP_400_BAD_REQUEST)
        except Assessment.DoesNotExist:
            return Response({"error": "Test not found."}, status=status.HTTP_404_NOT_FOUND)

        questions_data = assessment.questions
        
        # 1. Handle String to JSON conversion
        if isinstance(questions_data, str):
            questions_data = json.loads(questions_data)
        
        # 2. Extract the actual LIST of questions from the nested key
        # If your AI output has a 'questions' key inside, we must access it
        if isinstance(questions_data, dict) and "questions" in questions_data:
            actual_questions_list = questions_data["questions"]
        else:
            actual_questions_list = questions_data # Fallback if not nested

        # Normalize keys to string for JSON mapping
        answers_map = {str(a["id"]): a["answer"] for a in answers}

        # ── 1. MCQ Scoring ──
        # Use the list we extracted above!
        mcqs = [q for q in actual_questions_list if q.get("type") == "mcq"]
        
        correct = 0
        for q in mcqs:
            user_ans = answers_map.get(str(q["id"]), "").strip().upper()
            if user_ans == str(q.get("answer", "")).upper():
                correct += 1
        
        mcq_score = (correct / len(mcqs) * 100) if mcqs else 0

        # ── 2. Descriptive Evaluation ──
        descriptive_qs = [q for q in actual_questions_list if q.get("type") == "descriptive"]
        strength_tags, weakness_tags, levels = [], [], []

        for q in descriptive_qs:
            ans = answers_map.get(str(q["id"]), "")
            if ans:
                result = evaluate_answer(q["question"], ans) 
                levels.append(result.get("level", "Intermediate"))
                
                # REAL Strengths: If they are strong, take the 'concept_mastered'
                if result.get("level") == "Strong":
                    strength_tags.append(result.get("concept_mastered", "Java Fundamentals"))
                
                # REAL Weaknesses: Only add if there is an actual gap
                if result.get("level") != "Strong" and result.get("knowledge_gap"):
                    weakness_tags.append(result.get("knowledge_gap"))

        # ── 3. Determine Day Level ──
        # Simple logic: majority wins
        if levels.count("Strong") > levels.count("Weak"):
            domain_level = "strong" 
        elif levels.count("Weak") > levels.count("Strong"):
            domain_level = "weak" 
        else:
            domain_level = "intermediate"

        # ── 4. Save Daily Result & Mark Assessment Complete ──
        swot = DailySWOT.objects.create(
            spring_user_id=str(request.user.id), # Cast to string to match CharField
            assessment=assessment,
            day_score=mcq_score,       # Fixed from 'score'
            strengths=strength_tags,   # Fixed from 'strength_tags'
            weaknesses=weakness_tags   # Fixed from 'weakness_tags'
            # Note: domain_level removed because it's not in your model
        )

        # Mark as completed
        assessment.is_completed = True
        assessment.answers = answers 
        assessment.save()

        # Check if onboarding is finished
        completed_count = Assessment.objects.filter(spring_user_id=request.user.id, is_completed=True).count()

        return Response({
            "status": "Success", 
            "day_completed": assessment.day_number,
            "total_completed": completed_count,
            # "swot_id": swot.id,
            "onboarding_finished": completed_count >= 7
        }, status=status.HTTP_201_CREATED)

# ─────────────────────────────────────────────
# 3️⃣ Get Latest SWOT Result
# ─────────────────────────────────────────────
class SWOTResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch the latest result for this specific user [cite: 38]
        result = DailySWOT.objects.filter(spring_user_id=request.user.id).order_by("-created_at").first()

        if not result:
            return Response({"error": "No results found."}, status=status.HTTP_404_NOT_FOUND) 

        return Response({
            "score": result.day_score,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            # "level": result.domain_level
        })
from django.db import models
import uuid

class Assessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spring_user_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=100)
    # Track progress (1 to 7)
    day_number = models.IntegerField(default=1) 
    questions = models.JSONField()  # The 5 questions
    answers = models.JSONField(null=True, blank=True) # User's responses
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['day_number']

class DailySWOT(models.Model):
    """Stores the analysis of a specific day's test"""
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE)
    spring_user_id = models.CharField(max_length=255)
    day_score = models.FloatField()
    strengths = models.JSONField(default=list)
    weaknesses = models.JSONField(default=list) # Knowledge Gaps
    created_at = models.DateTimeField(auto_now_add=True)
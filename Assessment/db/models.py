from django.db import models
import uuid

class Assessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    spring_user_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=100)
    day_number = models.IntegerField(default=1) 
    questions = models.JSONField()  # Generated MCQs and Descriptive
    answers = models.JSONField(null=True, blank=True) # User's responses
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class DailySWOT(models.Model):
    assessment = models.OneToOneField(Assessment, on_delete=models.CASCADE)
    spring_user_id = models.CharField(max_length=255)
    day_score = models.FloatField()
    strengths = models.JSONField(default=list)
    weaknesses = models.JSONField(default=list) 
    error_analysis = models.JSONField(default=dict) 

class UserKnowledgeGraph(models.Model):
    """The Master Profile generated after Day 7"""
    spring_user_id = models.CharField(max_length=255) # Removed unique=True here
    domain = models.CharField(max_length=100)
    university = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    mastery_scores = models.JSONField(default=dict) 
    critical_loopholes = models.JSONField(default=list) 
    top_error_type = models.CharField(max_length=50) 
    
    is_ready_for_roadmap = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('spring_user_id', 'domain'),)

class Roadmap(models.Model):
    """Stores the actual learning plan generated on Day 8"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    knowledge_graph = models.ForeignKey(UserKnowledgeGraph, on_delete=models.CASCADE,null=True, 
        blank=True)
    spring_user_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    overview = models.TextField()
    full_data = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)

class RoadmapTask(models.Model):
    """Individual tasks within a roadmap"""
    roadmap = models.ForeignKey(Roadmap, related_name="tasks", on_delete=models.CASCADE)
    day_number = models.IntegerField()
    phase_name = models.CharField(max_length=100)
    topic = models.CharField(max_length=255)
    task_description = models.TextField()
    depth = models.CharField(max_length=50) 
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Fixed: Removed the nonexistent fields from unique_together
        ordering = ['day_number']
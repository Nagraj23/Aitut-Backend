from django.urls import path
from api.views import (
    GenerateTestView, 
    SubmitAnswersView, 
    GetLatestRoadmapView,
    GenerateRoadmapView # 👈 New View
)

urlpatterns = [
    path('api/assessment/generate/', GenerateTestView.as_view(), name='gen_test'),
    path('api/assessment/submit/', SubmitAnswersView.as_view(), name='sub_test'),
    # path('api/assessment/results/', SWOTResultView.as_view(), name='get_results'),
    
    # Day 8: Generate the deep roadmap
    path('api/roadmaps/latest/<str:user_id>/', GetLatestRoadmapView.as_view(), name='get_latest_roadmap'),
    path('api/roadmap/create/', GenerateRoadmapView.as_view(), name='create_roadmap'),
]
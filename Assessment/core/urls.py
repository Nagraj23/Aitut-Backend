from django.urls import path
from api.views import GenerateTestView, SubmitAnswersView, SWOTResultView


urlpatterns = [
    path('api/assessment/generate/', GenerateTestView.as_view(), name='gen_test'), # [cite: 23, 24]
    path('api/assessment/submit/', SubmitAnswersView.as_view(), name='sub_test'), # [cite: 23, 28]
    path('api/assessment/results/', SWOTResultView.as_view(), name='get_results'), # [cite: 23, 38]
]
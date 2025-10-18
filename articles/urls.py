from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ArticleViewSet, TagViewSet, QuestionViewSet, ActionItemViewSet, StatisticsView  # ★インポート追加

router = DefaultRouter()
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'tags', TagViewSet, basename='tag') # ★この行を追加
router.register(r'questions', QuestionViewSet, basename='question') # ★追加
router.register(r'actions', ActionItemViewSet, basename='action') # ★追加

urlpatterns = [
    path('', include(router.urls)),
    # ★この行を追加
    path('statistics/', StatisticsView.as_view(), name='statistics'),
]
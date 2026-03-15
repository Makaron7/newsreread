from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ArticleViewSet, TagViewSet, RSSSubscriptionViewSet, QuestionViewSet, ActionItemViewSet, StatisticsView  # ★インポート追加
from . import views

router = DefaultRouter()
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'tags', TagViewSet, basename='tag') # ★この行を追加
router.register(r'rss-subscriptions', RSSSubscriptionViewSet, basename='rss-subscription')
router.register(r'questions', QuestionViewSet, basename='question') # ★追加
router.register(r'actions', ActionItemViewSet, basename='action') # ★追加

urlpatterns = [
    path('', include(router.urls)),
    path('statistics/', StatisticsView.as_view(), name='statistics'),

    # HTML画面（Django テンプレート用）
    path('share/', views.article_share, name='article_share'),
]
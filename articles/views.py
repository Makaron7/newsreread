from django.shortcuts import render

# Create your views here.

from rest_framework import viewsets, permissions # permissions をインポート
from .models import Article ,Tag, Question, ActionItem
from .serializers import ArticleSerializer, TagSerializer, QuestionSerializer, ActionItemSerializer
from django_filters.rest_framework import DjangoFilterBackend
from .filters import ArticleFilter


class TagViewSet(viewsets.ModelViewSet):
    """
    タグの取得、作成、更新、削除を行うAPIビュー
    """
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        ログイン中のユーザーが作成したタグのみを返す
        """
        return self.request.user.tags.all().order_by('name')

    def perform_create(self, serializer):
        """
        タグ作成時に、自動でログインユーザーを紐づける
        """
        serializer.save(user=self.request.user)
# ★ここまで追加

class QuestionViewSet(viewsets.ModelViewSet):
    """
    「問い」のAPIビュー
    """
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        ログインユーザーの記事に紐づく「問い」のみを返す
        """
        return Question.objects.filter(article__user=self.request.user)

class ActionItemViewSet(viewsets.ModelViewSet):
    """
    「アクション」のAPIビュー
    """
    serializer_class = ActionItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        ログインユーザーの記事に紐づく「アクション」のみを返す
        """
        return ActionItem.objects.filter(article__user=self.request.user)

class ArticleViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]
    # ★フィルター機能を設定
    filter_backends = [DjangoFilterBackend] # フィルターバックエンドを指定
    filterset_class = ArticleFilter         # どのフィルター定義を使うか指定

    def get_queryset(self):
        """
        このAPIが返すデータセットを定義します。
        ログインしているユーザーの記事のみを返します。
        """
        # 以前: return Article.objects.all() (全員の記事)
        # 変更後:
        return self.request.user.articles.all().order_by('-saved_at') # 自分の記事を新しい順に

    def perform_create(self, serializer):
        """
        新しい記事が作成(POST)されるときに呼ばれます。
        記事の 'user' フィールドに、ログイン中のユーザーを自動で割り当てます。
        """
        serializer.save(user=self.request.user)
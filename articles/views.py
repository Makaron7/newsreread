
# Standard Library
from datetime import timedelta

# Django Core
from django.db.models import F, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

# Third-Party Libraries (DRF, Django-Filter)
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

# Local Application Imports
from .models import Article, Tag, Question, ActionItem
from .serializers import (
    ArticleSerializer, 
    ArticleSimpleSerializer,
    TagSerializer, 
    QuestionSerializer, 
    ActionItemSerializer
)
from .filters import ArticleFilter
from .tasks import fetch_article_metadata

# ↓ ここから ViewSet の定義が始まります

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

class StatisticsView(APIView):
    """
    ユーザーの統計情報を返すAPIビュー
    (GET /api/statistics/)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        
        # ログインユーザーの記事クエリセット
        user_articles = Article.objects.filter(user=user)

        # 1. ステータスごとの記事数 (機能4)
        status_counts = user_articles.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # 2. タグごとの記事数 (機能7)
        # (タグがついていない記事は除外)
        tag_counts = Tag.objects.filter(
            user=user, 
            articles__isnull=False
        ).annotate(
            count=Count('articles')
        ).values('name', 'count').order_by('-count')[:10] # Top 10

        # 3. 月別の保存記事数 (機能7)
        monthly_counts = user_articles.annotate(
            month=TruncMonth('saved_at')
        ).values('month').annotate(
            count=Count('id')
        ).values('month', 'count').order_by('month')

        # 4. 総合統計
        total_articles = user_articles.count()
        total_read = user_articles.filter(status='read').count()

        # データをまとめて返す
        data = {
            'total_articles': total_articles,
            'total_read_articles': total_read,
            'counts_by_status': list(status_counts),
            'top_10_tags': list(tag_counts),
            'saved_articles_by_month': list(monthly_counts),
        }
        
        return Response(data)
    
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


REPETITION_INTERVALS = [1, 3, 7, 14, 30, 60, 90]  # 0->1日後, 1->3日後, 2->7日後, ...
class ArticleViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]
    # ★フィルター機能を設定
    filter_backends = [DjangoFilterBackend] # フィルターバックエンドを指定
    filterset_class = ArticleFilter         # どのフィルター定義を使うか指定

    def get_queryset(self):
        return self.request.user.articles.all().order_by('-saved_at')

    # perform_create はもう使わないので削除

    # ★ここから追加 (perform_create の代わり)
    def create(self, request, *args, **kwargs):
        """
        新しい記事を作成(POST)する処理をオーバーライド
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 1. 記事を保存 (ログインユーザーを紐付け)
        article_instance = serializer.save(user=request.user)

        # 2. Celery タスクを呼び出し (非同期スクレイピング)
        fetch_article_metadata.delay(article_instance.id)

        # 3. レスポンスデータを準備 (保存した記事本体)
        #    (context={'request': request} を渡して tag_ids が機能するようにする)
        response_serializer = ArticleSerializer(
            article_instance,
            context={'request': request}
        )
        response_data = response_serializer.data

        # --- 機能3-3: 関連する記事の提案 ---
        related_articles = []
        # 保存した記事に紐づくタグIDリストを取得
        tag_ids = [tag.id for tag in article_instance.tags.all()]

        if tag_ids:
            # 同じタグを持ち、自分自身(article_instance)を除外し、
            # ログインユーザーの記事で、最大5件まで
            related_articles_query = Article.objects.filter(
                user=request.user,
                tags__id__in=tag_ids
            ).exclude(
                id=article_instance.id
            ).distinct().order_by('-saved_at')[:5]
            # 軽量なSerializerでシリアライズ
            related_articles = ArticleSimpleSerializer(related_articles_query, many=True).data

        # 4. レスポンスに「関連する記事」を追加して返す
        response_data['related_articles_suggestion'] = related_articles

        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
    # ★ここまで追加
        
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """
        記事を「読んだ」ことにして、read_count を+1し、
        次のリマインド日を計算・更新する
        """
        try:
            article = self.get_object()
            # --- リマインド日の計算 (★追加) ---
            current_level = article.repetition_level
            # 間隔リストの範囲内なら次のレベルへ
            if current_level < len(REPETITION_INTERVALS):
                days_to_add = REPETITION_INTERVALS[current_level]
                article.next_reminder_date = timezone.now().date() + timedelta(days=days_to_add)
                article.repetition_level = F('repetition_level') + 1
            else:
                # 最大レベルに達したら、リマインド日をクリア (殿堂入り)
                article.next_reminder_date = None
                # (もしくは status を 'hof' に変更するのも良い)

            # --- 既存の処理 ---
            article.read_count = F('read_count') + 1
            article.last_read_at = timezone.now()
            # DBに保存 (update_fields に追加)
            article.save(update_fields=[
                'read_count', 
                'last_read_at', 
                'next_reminder_date', 
                'repetition_level'
            ])
            article.refresh_from_db() # F() の結果をDBから再取得
            serializer = self.get_serializer(article)
            return Response(serializer.data)
        except Article.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
# ★ここから追加
    @action(detail=False, methods=['get'])
    def reminders(self, request):
        """
        リマインド対象の記事一覧を返す
        (GET /api/articles/reminders/)
        """
        today = timezone.now().date()
        
        # ログインユーザーの記事で、
        # 次回リマインド日が今日以前 (かつ None でない) のものを取得
        reminder_articles = self.get_queryset().filter(
            next_reminder_date__isnull=False,
            next_reminder_date__lte=today
        ).order_by('next_reminder_date') # 古いリマインドから表示
        
        # ページネーションを適用してシリアライズ
        page = self.paginate_queryset(reminder_articles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(reminder_articles, many=True)
        return Response(serializer.data)
    # ★ここまで追加

    @action(detail=False, methods=['get'])

    def random_pickup(self, request):
        """
        ランダムで1件の記事を取得 (「今日のおすすめ」機能)
        (GET /api/articles/random_pickup/)
        """
        # ログインユーザーの記事からランダムで1件
        random_article = self.get_queryset().order_by('?').first()
        
        if random_article:
            serializer = self.get_serializer(random_article)
            return Response(serializer.data)
        else:
            # 記事が1件も保存されていない場合
            return Response(status=status.HTTP_404_NOT_FOUND)
import django_filters
from .models import Article

class ArticleFilter(django_filters.FilterSet):
    """
    記事を検索・絞り込みするためのフィルター
    """
    
    # ★機能6：キーワード検索
    # title, description, user_memo, user_summary のいずれかに
    # キーワードが含まれていたらヒットさせる (icontains = 大文字小文字を区別しない)
    q = django_filters.CharFilter(method='search_q', label='総合検索(q=)')

    # ★機能2, 4：タグやステータスでの絞り込み
    # ?tag_id=3 のようなリクエストに対応
    tag_id = django_filters.NumberFilter(field_name='tags__id', label='タグID(tag_id=)')
    
    # ?status=unread のようなリクエストに対応
    status = django_filters.ChoiceFilter(choices=Article.STATUS_CHOICES, label='ステータス(status=)')
    
    # ?priority=high のようなリクエストに対応
    priority = django_filters.ChoiceFilter(choices=Article.PRIORITY_CHOICES, label='重要度(priority=)')

    class Meta:
        model = Article
        # URLで ?is_favorite=true のような絞り込みも許可する
        fields = ['status', 'priority', 'is_favorite', 'tag_id']

    def search_q(self, queryset, name, value):
        """
        総合検索(q=) のロジック
        """
        if not value:
            return queryset
        
        # Qオブジェクトを使って OR 検索を実現
        from django.db.models import Q
        return queryset.filter(
            Q(cached_url__title__icontains=value) |
            Q(cached_url__description__icontains=value) |
            Q(user_memo__icontains=value) |
            Q(user_summary__icontains=value) |
            Q(cached_url__site_name__icontains=value)
        ).distinct() # 重複を除外
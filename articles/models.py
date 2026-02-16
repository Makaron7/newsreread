from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

# ★ここから追加
class CachedURL(models.Model):
    """
    スクレイピング結果をURL単位でキャッシュするモデル
    """
    url = models.URLField(max_length=2000, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(max_length=2000, blank=True, null=True)
    last_scraped_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url

    def needs_rescrape(self, days=7):
        """
        最後にスクレイピングしてから指定日数経過したか
        """
        return timezone.now() - self.last_scraped_at > timedelta(days=days)
# ★ここまで追加

class Tag(models.Model):
    """
    記事に紐づけるタグ
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=50)

    class Meta:
        # ユーザーとタグ名の組み合わせが一意（重複しない）ようにする
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name

class Article(models.Model):
    """
    保存する記事のモデル (ユーザー固有の情報のみ)
    """
    # ステータスの選択肢 (機能4)
    STATUS_CHOICES = [
        ('unread', '未読'),
        ('read_later', '後で読む'), 
        ('read', '読了'),
        ('reread', '要再読'),
        ('hof', '殿堂入り'), # Hall of Fame
        ('archived', 'アーカイブ'),
        ('trash', 'ゴミ箱'),
    ]
    # 重要度の選択肢 (機能4-3)
    PRIORITY_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
    ]

    # --- データベースのカラム定義 ---

    # 記事の所有者 (機能1)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    
    # ★追加：タグとの関連付け（これがないとエラーになります）
    tags = models.ManyToManyField(Tag, blank=True)

    # スクレイピング結果キャッシュとの関連
    cached_url = models.ForeignKey(CachedURL, on_delete=models.CASCADE, related_name='articles')

    # 読了ステータス (機能4)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unread')
    
    # お気に入り (機能4-3)
    is_favorite = models.BooleanField(default=False)
    
    # 重要度 (機能4-3)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    # 読んだ回数 (機能4-2)
    read_count = models.IntegerField(default=0)
    # メモ・要約 (機能5)
    user_memo = models.TextField(blank=True, null=True)
    user_summary = models.TextField(blank=True, null=True)
    
    # 日時
    saved_at = models.DateTimeField(auto_now_add=True) # 保存日時
    last_read_at = models.DateField(blank=True, null=True) # 最終閲覧日時

    # リマインド用 (機能3-2)
    repetition_level = models.IntegerField(default=0) # 間隔反復のレベル
    next_reminder_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        unique_together = ('user', 'cached_url')

    def __str__(self):
        return self.cached_url.title or self.cached_url.url
    
# ★ここから追加
class Question(models.Model):
    """
    記事から生まれた「問い」 (機能5-3)
    """
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:50] # テキストの先頭50文字を表示

class ActionItem(models.Model):
    """
    記事から生まれた「アクション」 (機能5-4)
    """
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='actions')
    text = models.TextField()
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:50]
# ★ここまで追加
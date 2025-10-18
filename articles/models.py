from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User # Django標準のUserモデルを使います

# ★ここから追加
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
# ★ここまで追加

class Article(models.Model):
    """
    保存する記事のモデル
    """
    # ステータスの選択肢 (機能4)
    STATUS_CHOICES = [
        ('unread', '未読'),
        ('read', '読了'),
        ('reread', '要再読'),
        ('hof', '殿堂入り'), # Hall of Fame
        ('archived', 'アーカイブ'),
    ]
    tags = models.ManyToManyField(Tag, blank=True, related_name='articles')
    
    # リマインド用 (機能3-2)
    repetition_level = models.IntegerField(default=0) # 間隔反復のレベル
    next_reminder_date = models.DateField(blank=True, null=True)

    # 読んだ回数 (機能4-2)
    read_count = models.IntegerField(default=0)
    # メモ・要約 (機能5)
    user_memo = models.TextField(blank=True, null=True)

    # 重要度の選択肢 (機能4-3)
    PRIORITY_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
    ]

    # --- データベースのカラム定義 ---

    # 記事の所有者 (機能1)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    
    # URL (機能1)
    url = models.URLField(max_length=2000)
    
    # (以下はスクレイピングで取得する情報)
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(max_length=2000, blank=True, null=True)
    
    # 読了ステータス (機能4)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unread')
    
    # お気に入り (機能4-3)
    is_favorite = models.BooleanField(default=False)
    
    # 重要度 (機能4-3)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    # メモ・要約 (機能5)
    user_memo = models.TextField(blank=True, null=True)
    user_summary = models.TextField(blank=True, null=True)
    
    # 日時
    saved_at = models.DateTimeField(auto_now_add=True) # 保存日時
    last_read_at = models.DateTimeField(blank=True, null=True) # 最終閲覧日時

    # リマインド用 (機能3-2)
    next_reminder_date = models.DateField(blank=True, null=True)
    
    def __str__(self):
        return self.title or self.url
    
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
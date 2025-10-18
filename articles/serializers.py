from rest_framework import serializers
from .models import Article, Tag, Question, ActionItem

class ArticleSimpleSerializer(serializers.ModelSerializer):
    """
    関連する記事の提案など、最小限の情報を返すためのSerializer
    """
    class Meta:
        model = Article
        fields = ['id', 'title', 'url', 'saved_at']

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'article', 'text', 'created_at']
        # 記事の作成・更新時に article を指定できるようにする
        extra_kwargs = {'article': {'write_only': True}}

class ActionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionItem
        fields = ['id', 'article', 'text', 'is_done', 'created_at']
        extra_kwargs = {'article': {'write_only': True}}
# ★ここまで追加

class ArticleSerializer(serializers.ModelSerializer):

    # ★追加：タグ情報をIDだけでなく名前なども含めて表示するようにする
    tags = TagSerializer(many=True, read_only=True)
    
    # ★追加：記事作成・更新時にタグIDのリストを受け取れるようにする
    # (例: "tag_ids": [1, 5, 10])
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(), # (後でユーザー自身のタグのみに絞り込みます)
        write_only=True,
        source='tags' # 'tags' フィールドとして処理する
    )
    questions = QuestionSerializer(many=True, read_only=True)
    actions = ActionItemSerializer(many=True, read_only=True)


    class Meta:
        model = Article
        # APIを通じて外部に公開する項目を指定します
        # (userはセキュリティのため一旦除外)
        fields = [
            'id', 
            'url', 
            'title', 
            'description', 
            'status', 
            'is_favorite', 
            'priority', 
            'user_memo', 
            'user_summary', 
            'image_url',
            'saved_at',
            'tags',    # ★追加
            'tag_ids', # ★追加
            'questions', # ★追加
            'actions',
            'read_count',
        ]

# ★追加：記事作成(POST)時に、ログインユーザーのタグだけを対象にする
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # リクエスト情報(ユーザー)を取得
        request = self.context.get('request', None)
        if request and hasattr(request, "user"):
            user = request.user
            # tag_ids の選択肢を、ログインユーザーが所有するタグのみに限定する
            self.fields['tag_ids'].queryset = Tag.objects.filter(user=user)

    
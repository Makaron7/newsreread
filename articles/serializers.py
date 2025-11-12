from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Article, Tag, Question, ActionItem, CachedURL

# ★ここから追加
class RegisterSerializer(serializers.ModelSerializer):
    """
    ユーザー登録用のシリアライザー
    """
    # パスワード（書き込み専用）
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password] # Django標準のパスワード検証
    )
    # パスワード確認用（書き込み専用）
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email')
        extra_kwargs = {
            'email': {'required': True} # emailを必須に
        }

    def validate(self, attrs):
        """
        パスワードとパスワード確認が一致するか検証
        """
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        """
        検証済みデータからユーザーを作成
        """
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user
# ★ここまで追加

# ★ここから追加
class UserSerializer(serializers.ModelSerializer):
    """
    ログイン中のユーザー情報を返すためのシリアライザー
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'email')
# ★ここまで追加

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
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        write_only=True,
        source='tags'
    )
    questions = QuestionSerializer(many=True, read_only=True)
    actions = ActionItemSerializer(many=True, read_only=True)

    # ★追加：CachedURL から情報を取得して表示 (読み取り専用)
    url = serializers.URLField(source='cached_url.url', read_only=True)
    title = serializers.CharField(source='cached_url.title', read_only=True)
    description = serializers.CharField(source='cached_url.description', read_only=True)
    image_url = serializers.URLField(source='cached_url.image_url', read_only=True)

    # ★追加：記事保存時に URL を受け取るためのフィールド (書き込み専用)
    url_input = serializers.URLField(write_only=True, required=True)

    class Meta:
        model = Article
        fields = [
            'id', 
            # ★ cached_url から取得するフィールド
            'url', 
            'title', 
            'description', 
            'image_url', 
            'url_input', # ★ 書き込み用
            # ★ Articleモデル固有のフィールド
            'status', 
            'is_favorite', 
            'priority', 
            'read_count', 
            'user_memo', 
            'user_summary', 
            'saved_at',
            'last_read_at',
            'repetition_level',
            'next_reminder_date',
            'tags',    
            'tag_ids', 
            'questions', 
            'actions',   
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request', None)
        if request and hasattr(request, "user"):
            user = request.user
            self.fields['tag_ids'].queryset = Tag.objects.filter(user=user)


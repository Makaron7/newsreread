from django import forms
from .models import Article, Tag

class ArticleEditForm(forms.ModelForm):
    class Meta:
        model = Article
        # 追加したい項目をすべてここに書きます
        fields = [
            'status', 
            'priority', 
            'user_memo', 
            'user_summary',
            'read_count',
            'last_read_at',
            'repetition_level',
            'next_reminder_date',
            'tags'  # Articleモデルに tags = ManyToManyField がある前提です
        ]
        
        labels = {
            'status': '状態',
            'priority': '優先度',
            'user_memo': 'ひとことメモ',
            'user_summary': '要約・学んだこと',
            'read_count': '読んだ回数',
            'last_read_at': '前回読んだ日付',
            'repetition_level': '反復レベル (0~)',
            'next_reminder_date': '次回リマインド日時',
            'tags': 'タグ設定',
        }
        
        # カレンダー入力や数値入力を見やすくする設定
        widgets = {
            'user_memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'user_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'read_count': forms.NumberInput(attrs={'class': 'form-control'}),
            # 日付入力にはHTMLの type="datetime-local" や "date" を使います
            'last_read_at': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'repetition_level': forms.NumberInput(attrs={'class': 'form-control'}),
            'next_reminder_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            # タグは複数選択できるようにします
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'style': 'height: 100px;'}),
        }

    def __init__(self, *args, **kwargs):
        # ビューから渡された「ユーザー情報」を受け取る
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # タグの選択肢を「自分が作ったタグ」だけに絞り込む
        if user:
            self.fields['tags'].queryset = Tag.objects.filter(user=user)


class ArticleShareForm(forms.ModelForm):
    # URLはArticleモデルに直接ないので、ここで定義します
    url = forms.URLField(
        label='URL', 
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'})
    )

    class Meta:
        model = Article
        fields = ['status', 'priority', 'next_reminder_date']
        
        labels = {
            'status': '状態',
            'priority': '優先度',
            'next_reminder_date': '次回リマインド日時',
        }
        
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'next_reminder_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }            
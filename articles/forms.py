from django import forms

class ArticleCreateForm(forms.Form):
    # ユーザーに入力してもらうのはURLだけです
    url = forms.URLField(
        label='記事のURL', 
        widget=forms.TextInput(attrs={'placeholder': 'https://example.com/article...'})
    )
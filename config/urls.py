"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views # ★追加：ログイン機能を使うため
from articles import views as article_views # ★追加：先ほど作ったビューを読み込む

# simplejwt用のviewをインポート
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from articles.views import RegisterView, UserDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # /api/articles/ など
    path('api/', include('articles.urls')),
    
    # 認証用のURLを追加
    path('api/auth/register/', RegisterView.as_view(), name='register'), # ユーザー登録
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # トークン取得
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # トークン更新
    path('api/auth/user/', UserDetailView.as_view(), name='user_detail'), # ログイン中のユーザー情報

    # ログイン・ログアウト用URL
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'), # 1. ログイン画面のURLを 'accounts/login/' に変更します

    # トップページ ('') にアクセスしたら、記事一覧 (article_list) を表示するようにします
    # （ログインしていない場合は、上の accounts/login/ に自動で飛ばされるようになります）
    path('', article_views.article_list, name='home'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'), # ★追加：ログアウト用（必要であれば）


]
NewsReread（Django）
====================

ニュース記事を保存・分類・再読管理する Django アプリです。
REST API（DRF）と、ログイン後に使うシンプルな HTML 画面の両方を提供します。


主な機能
--------
- URL から記事を保存（重複保存防止あり）
- 記事ステータス管理（未読 / 後で読む / 読了 / 要再読 / 殿堂入り / アーカイブ / ゴミ箱）
- タグ管理、検索・フィルター・ソート
- 再読リマインド（間隔反復）
- 統計 API（ステータス別件数、タグ集計、月別件数）
- ユーザー登録 / JWT 認証


技術スタック
------------
- Python + Django 5
- Django REST Framework
- SimpleJWT（JWT 認証）
- django-filter
- Celery（開発環境では同期実行）
- SQLite（デフォルト）


セットアップ（Windows / PowerShell）
-----------------------------------
1) 仮想環境の作成と有効化

	python -m venv venv
	.\venv\Scripts\Activate.ps1

2) 依存パッケージのインストール

	pip install -r requirements.txt

3) `.env` の作成

	`.env.example` をコピーして `.env` を作成し、`SECRET_KEY` を設定します。

	例: SECRET_KEY を生成
	python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

4) マイグレーション

	python manage.py migrate

5) 管理ユーザー作成（任意だが推奨）

	python manage.py createsuperuser

6) 開発サーバー起動

	python manage.py runserver


環境変数
--------
`.env.example` にある主な設定:

- SECRET_KEY（必須）
- AI_CLASSIFICATION_ENGINE（任意）
  - lightweight（デフォルト）
  - transformers

補足:
- `DEBUG=True` 時は Celery タスクが同期実行されるため、通常のローカル開発ではワーカー起動なしでも動作します。
- 非同期運用する場合は Redis と Celery ワーカーを別途起動してください。


ログイン画面 / 管理画面
----------------------
- ログイン画面: http://127.0.0.1:8000/accounts/login/
- 管理画面: http://127.0.0.1:8000/admin/


主要 API
--------
認証:
- POST `/api/auth/register/`
- POST `/api/auth/token/`
- POST `/api/auth/token/refresh/`
- GET  `/api/auth/user/`

記事関連:
- `/api/articles/`（CRUD）
- POST `/api/articles/{id}/mark_as_read/`
- POST `/api/articles/{id}/reclassify/`
- POST `/api/articles/{id}/rescrape/`
- POST `/api/articles/reclassify_pending/`
- GET  `/api/articles/reminders/`
- GET  `/api/articles/random_pickup/`

その他:
- `/api/tags/`
- `/api/questions/`
- `/api/actions/`
- GET `/api/statistics/`


HTML 画面
---------
- `/` : 記事一覧（ログイン必須）
- `/articles/{id}/edit/` : 記事編集
- `/articles/{id}/delete/` : ゴミ箱移動
- `/api/share/` : 共有フォーム


テスト
------
最小確認:

python manage.py test


注意点
------
- API の多くは認証必須です（JWT またはセッション認証）。
- 既存 DB（`db.sqlite3`）がある場合、挙動確認時はデータ状態の影響を受けます。
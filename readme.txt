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


Celery worker / beat の違い
---------------------------
- worker: キューに入ったタスクを実際に実行するプロセス
- beat: 定期タスクをスケジュールし、キューに投入するプロセス

定期RSS同期を動かすには、通常 `worker` と `beat` の両方が必要です。


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


ngrok で外部公開（Windows / PowerShell）
---------------------------------------
1) Django サーバーを起動（別ターミナル）

	.\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000

2) ngrok を起動（別ターミナル）

	ngrok http 8000

	※ `ngrok` コマンドが通らない場合:
	& "C:\Users\masa0\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000

3) 確認

	- Forwarding に表示される `https://...` URL を共有用に使う
	- ngrok ローカル管理画面: http://127.0.0.1:4040

4) 停止

	- ngrok を実行しているターミナルで `Ctrl + C`


環境変数
--------
`.env.example` にある主な設定:

- SECRET_KEY（必須）
- DEBUG（任意、デフォルト True）
- AI_CLASSIFICATION_ENGINE（任意）
  - lightweight（デフォルト）
  - transformers
- AI_SBERT_MODEL（任意、`AI_CLASSIFICATION_ENGINE=transformers` のとき使用）
	- デフォルト: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- AI_DEVICE（任意、`AI_CLASSIFICATION_ENGINE=transformers` のとき使用）
	- `auto`（デフォルト）: `npu -> xpu -> cuda -> mps -> cpu` の順で自動選択
	- 手動指定: `cpu` / `cuda` / `xpu` / `npu` / `mps`
- AI_TRANSFORMERS_BACKEND（任意、`AI_CLASSIFICATION_ENGINE=transformers` のとき使用）
	- `sentence_transformers`（デフォルト）: 既存経路
	- `openvino_ir`: OpenVINO IR 経路
	- `auto`: OpenVINO IR が使えれば優先、不可なら既存経路
- AI_OPENVINO_IR_XML（任意）
	- OpenVINO IR の `.xml` パス（`.bin` は同ディレクトリにある想定）
- AI_OPENVINO_TOKENIZER_MODEL（任意）
	- OpenVINO IR 推論時のトークナイザー名（HuggingFace形式）
- AI_OPENVINO_DEVICE（任意）
	- OpenVINO 実行デバイス（例: `CPU`, `AUTO`）

補足:
- `DEBUG=True` 時は Celery タスクが同期実行されるため、通常のローカル開発ではワーカー起動なしでも動作します。
- 非同期運用する場合は Redis と Celery ワーカーを別途起動してください。
- `AI_CLASSIFICATION_ENGINE=lightweight` の場合、SBERT/KeyBERT を使わず軽量分類のみ実行します（起動が安定しやすい）。
- OpenVINO IR は**追加対応**です。既存の `sentence_transformers` 経路は維持され、設定で切り替えできます。


非同期運用（worker / beat 起動手順）
------------------------------------
前提:
- Redis が起動していること
- `.env` で `DEBUG=False` にすること（`DEBUG=True` だと eager 実行が優先される）

PowerShell でターミナルを3つ開いて実行:

1) Django

	python manage.py runserver

2) Celery worker

	.\venv\Scripts\python.exe -m celery -A config worker -l info

3) Celery beat

	.\venv\Scripts\python.exe -m celery -A config beat -l info

補足（Redis）:
- ローカルにRedisがある場合: `redis-server`
- Dockerの場合: `docker run --name newsreread-redis -p 6379:6379 -d redis:7`


ログイン画面 / 管理画面
----------------------
- ログイン画面: http://127.0.0.1:8000/accounts/login/
- 管理画面: http://127.0.0.1:8000/admin/


主要 API（Next.js 連携用）
--------------------------
すべてのAPIは JWT 認証必須（Authorization: Bearer <token>）。

■ 認証
  POST   /api/auth/register/          ユーザー登録
  POST   /api/auth/token/             JWTトークン取得 { username, password }
  POST   /api/auth/token/refresh/     トークン更新 { refresh }
  GET    /api/auth/user/              ログイン中ユーザー情報

■ 記事 (Article)
  GET    /api/articles/               一覧（ページネーション 12件/ページ）
    クエリパラメータ:
      ?search=<kw>           全文検索（タイトル・URL・メモ等）
      ?status=<状態>         unread / read_later / read / reread / hof / archived / trash
      ?priority=<高低>       high / medium / low
      ?is_favorite=true
      ?is_from_rss=true
      ?tag_id=<id>           タグIDで絞り込み
      ?suggested_category=<カテゴリ名>
      ?ordering=<field>      saved_at / priority / read_count / last_read_at（-付きで降順）
  POST   /api/articles/               記事保存 { url_input, status?, priority?, tags? }
  GET    /api/articles/{id}/          記事詳細
  PUT    /api/articles/{id}/          記事更新
  PATCH  /api/articles/{id}/          記事部分更新
  DELETE /api/articles/{id}/          記事削除

  POST   /api/articles/quick_save/            クイック保存 { url } ← Next.js拡張/共有機能向け
  POST   /api/articles/{id}/mark_as_read/     既読マーク＋リマインド日更新
  POST   /api/articles/{id}/reclassify/       AI分類再実行
  POST   /api/articles/{id}/rescrape/         メタデータ再取得
  POST   /api/articles/reclassify_pending/    未分類記事を一括再分類
  GET    /api/articles/reminders/             リマインド対象記事一覧
  GET    /api/articles/random_pickup/         ランダム1件

■ タグ (Tag)
  GET    /api/tags/                   タグ一覧
  POST   /api/tags/                   タグ作成 { name }
  GET    /api/tags/{id}/
  PUT    /api/tags/{id}/
  DELETE /api/tags/{id}/

■ 問い (Question)
  GET    /api/questions/              一覧 (?article=<id> で記事絞り込み可)
  POST   /api/questions/              作成 { article, text }
  PUT    /api/questions/{id}/
  DELETE /api/questions/{id}/

■ アクション (ActionItem)
  GET    /api/actions/                一覧 (?article=<id> で記事絞り込み可)
  POST   /api/actions/                作成 { article, text }
  PATCH  /api/actions/{id}/           is_done の更新等
  DELETE /api/actions/{id}/

■ RSS購読
  GET    /api/rss-subscriptions/      一覧
  POST   /api/rss-subscriptions/      作成 { name, feed_url }
  DELETE /api/rss-subscriptions/{id}/
  POST   /api/rss-subscriptions/{id}/sync_now/     即時同期
  POST   /api/rss-subscriptions/retry_metadata/    メタデータ再取得

■ 統計
  GET    /api/statistics/             記事数・タグ集計・月別データ


HTML 画面（Next.js移行後は不要）
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
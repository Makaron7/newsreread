import os
from celery import Celery

# Djangoの 'settings.py' を読み込むように環境変数を設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Celeryアプリを作成 (プロジェクト名 'config' を指定)
app = Celery('config')

# Djangoの settings.py から設定を読み込む
app.config_from_object('django.conf:settings', namespace='CELERY')

# Djangoアプリ内の 'tasks.py' ファイルを自動で検出するように設定
app.autodiscover_tasks()
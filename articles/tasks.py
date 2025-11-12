import requests
from bs4 import BeautifulSoup
from celery import shared_task
from .models import CachedURL
from django.utils import timezone

@shared_task
def fetch_article_metadata(cached_url_id):
    """
    CachedURLのIDを受け取り、スクレイピングしてキャッシュを更新するタスク
    """
    try:
        cache = CachedURL.objects.get(id=cached_url_id)
    except CachedURL.DoesNotExist:
        print(f"CachedURL {cached_url_id} not found. Task cancelled.")
        return

    # --- スクレイピング処理 ---
    try:
        headers = { 'User-Agent': 'YourAppName-Bookmark-Bot/1.0' }
        response = requests.get(cache.url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # タイトル取得
        title = None
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content')
        else:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()

        # 概要取得
        description = None
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            description = og_desc.get('content')
        else:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content')

        # 画像取得
        image_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image:
            image_url = og_image.get('content')

        # --- DB (CachedURL) に保存 ---
        cache.title = title
        cache.description = description
        cache.image_url = image_url
        cache.last_scraped_at = timezone.now()
        cache.save(update_fields=[
            'title', 'description', 'image_url', 'last_scraped_at'
        ])
        print(f"Successfully fetched metadata for {cache.url}")

    except requests.RequestException as e:
        print(f"Error fetching {cache.url}: {e}")
    except Exception as e:
        print(f"Error processing {cache.url}: {e}")
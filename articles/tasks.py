import requests
from bs4 import BeautifulSoup
from celery import shared_task
from .models import Article

@shared_task # これでCeleryがこの関数を「タスク」として認識します
def fetch_article_metadata(article_id):
    """
    記事のIDを受け取り、スクレイピングしてタイトルや概要を保存するタスク
    """
    try:
        # DBから対象の記事オブジェクトを取得
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        print(f"Article {article_id} not found. Task cancelled.")
        return

    # --- スクレイピング処理 ---
    try:
        # サイトにアクセスするためのヘッダー（身元証明）
        headers = {
            'User-Agent': 'YourAppName-Bookmark-Bot/1.0 (+http://your-app-domain.com)'
        }
        
        # タイムアウトを10秒に設定
        response = requests.get(article.url, headers=headers, timeout=10)
        
        # もしアクセス失敗したらエラー扱い
        response.raise_for_status() 

        # HTMLを解析
        soup = BeautifulSoup(response.content, 'html.parser')

        # タイトルの取得
        # (metaタグのog:title -> titleタグ の順で探す)
        title = None
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title['content']
        else:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()

        # 概要(Description)の取得
        description = None
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            description = og_desc['content']
        else:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc['content']

        # 画像(Image)の取得
        image_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image:
            image_url = og_image['content']

        # --- DBに保存 ---
        if title:
            article.title = title
        if description:
            article.description = description
        if image_url:
            article.image_url = image_url
            
        article.save(update_fields=['title', 'description', 'image_url'])
        
        print(f"Successfully fetched metadata for {article.url}")

    except requests.RequestException as e:
        # ネットワークエラーやHTTPエラー
        print(f"Error fetching {article.url}: {e}")
    except Exception as e:
        # その他のエラー (BeautifulSoupの解析エラーなど)
        print(f"Error processing {article.url}: {e}")
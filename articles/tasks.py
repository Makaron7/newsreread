import requests
from bs4 import BeautifulSoup
from celery import shared_task
from .models import CachedURL, Article, Tag
from django.utils import timezone
from django.conf import settings

# ★グローバルモデルキャッシュ（メモリ効率化のため）
_sbert_model = None

def get_sbert_model():
    """SBERT モデルをキャッシュから取得（初回はロード）"""
    global _sbert_model
    if _sbert_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sbert_model = SentenceTransformer('sonoisa/sentence-bert-base-ja-mean-tokens')
        except Exception:
            _sbert_model = None
    return _sbert_model

@shared_task
def fetch_article_metadata(cached_url_id, article_id=None):
    """
    CachedURLのIDを受け取り、スクレイピングしてキャッシュを更新するタスク
    article_id は互換性のため受け取る（現状は未使用）
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

        # サイト名取得
        site_name = None
        og_site_name = soup.find('meta', property='og:site_name')
        if og_site_name:
            site_name = og_site_name.get('content')
        else:
            # og:site_nameがない場合、application-nameやtwitterのサイト名を試す
            app_name = soup.find('meta', attrs={'name': 'application-name'})
            if app_name:
                site_name = app_name.get('content')
            else:
                twitter_site = soup.find('meta', attrs={'name': 'twitter:site'})
                if twitter_site:
                    site_name = twitter_site.get('content', '').lstrip('@')

        # --- DB (CachedURL) に保存 ---
        cache.title = title
        cache.description = description
        cache.image_url = image_url
        cache.site_name = site_name
        cache.last_scraped_at = timezone.now()
        cache.save(update_fields=[
            'title', 'description', 'image_url', 'site_name', 'last_scraped_at'
        ])
        print(f"Successfully fetched metadata for {cache.url}")

        # ★記事IDが渡されたら、自動分類タスクを実行
        if article_id:
            classify_article(article_id)

    except requests.RequestException as e:
        print(f"Error fetching {cache.url}: {e}")
    except Exception as e:
        print(f"Error processing {cache.url}: {e}")


@shared_task
def classify_article(article_id):
    """
    記事をAIで自動分類（カテゴリ・タグ）するタスク
    SBERT + KeyBERT（日本語特化版）を使用（失敗時は軽量版へ）
    """
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        print(f"Article {article_id} not found. Task cancelled.")
        return

    try:
        article.classification_status = 'processing'
        article.save(update_fields=['classification_status'])

        # テキストを組み立て
        title = article.cached_url.title or ""
        description = article.cached_url.description or ""
        combined_text = f"{title} {description}"

        # テキストが空の場合はスキップ
        if not combined_text.strip():
            article.classification_status = 'error'
            article.classification_error = "テキストが空"
            article.save(update_fields=['classification_status', 'classification_error'])
            return

        # ★処理A: カテゴリ判定 (SBERT 類似度)
        category, category_score = classify_category_sbert(combined_text)
        article.suggested_category = category
        article.suggested_category_score = category_score

        # ★処理B: タグ抽出 (KeyBERT)
        tags = extract_keywords_keybert(combined_text)
        article.suggested_tags = tags

        # 推奨タグを実タグとして付与
        tag_objects = []
        for tag in tags:
            name = tag.get('name') if isinstance(tag, dict) else None
            if not name:
                continue
            tag_obj, _ = Tag.objects.get_or_create(user=article.user, name=name)
            tag_objects.append(tag_obj)
        if tag_objects:
            article.tags.add(*tag_objects)

        # 完了
        article.classification_status = 'completed'
        article.classification_error = None
        article.save()

        print(
            f"Successfully classified article {article_id}: {category} "
            f"(score={category_score:.3f})"
        )

    except Exception as e:
        print(f"Error classifying article {article_id}: {e}")
        article.classification_status = 'error'
        article.classification_error = str(e)
        article.save(update_fields=['classification_status', 'classification_error'])


def classify_category_sbert(text):
    """
    SBERT で入力テキストとカテゴリ候補の類似度を計算
    戻り値: (カテゴリ名, スコア)
    """
    try:
        from sentence_transformers import util

        # SBERT モデルを取得
        model = get_sbert_model()
        if model is None:
            # フォールバック
            return predict_category_lightweight(text)

        # カテゴリ候補を取得
        categories = settings.AI_CATEGORY_CANDIDATES

        # テキストとカテゴリをベクトル化
        text_embedding = model.encode(text, convert_to_tensor=True)
        category_embeddings = model.encode(categories, convert_to_tensor=True)

        # コサイン類似度を計算
        cos_scores = util.cos_sim(text_embedding, category_embeddings)[0]

        # 最もスコアが高いカテゴリを取得
        max_score, max_idx = cos_scores.max(dim=0)
        best_category = categories[max_idx.item()]
        score = float(max_score.item())

        return best_category, score

    except Exception:
        return predict_category_lightweight(text)


def extract_keywords_keybert(text):
    """
    KeyBERT で日本語キーワードを抽出
    日本語分かち書きは fugashi を使用
    戻り値: [{"name": "キーワード", "score": 0.95}, ...]
    """
    try:
        from keybert import KeyBERT

        # SBERT モデルを取得
        model = get_sbert_model()
        if model is None:
            # フォールバック
            return extract_keywords_lightweight(text)

        # KeyBERT を初期化（モデル使い回し）
        kw_model = KeyBERT(model=model)

        # 日本語分かち書き
        wakati_text = tokenize_japanese(text)

        # キーワード抽出（トップ5、単語のみ）
        keywords = kw_model.extract_keywords(
            wakati_text,
            language='japanese',
            keyphrase_ngram_range=(1, 1),
            top_n=5,
            use_mmr=True,
            diversity=0.3
        )

        # 結果を JSON 形式に変換
        result_tags = [
            {"name": kw, "score": float(score)}
            for kw, score in keywords
        ]

        return result_tags

    except Exception:
        return extract_keywords_lightweight(text)


def tokenize_japanese(text):
    """
    日本語テキストを分かち書き（スペース区切り）
    """
    try:
        import fugashi
        tagger = fugashi.Tagger()
        words = [word.surface for word in tagger(text)]
        return ' '.join(words)
    except Exception:
        return text


def predict_category_lightweight(text):
    """
    軽量版カテゴリ分類（キーワードマッチング）
    フォールバック用
    """
    categories = settings.AI_CATEGORY_CANDIDATES

    # キーワードマッピング
    category_keywords = {
        "プログラミング": ["python", "javascript", "code", "programming", "コード"],
        "AI・機械学習": ["ai", "machine learning", "nlp", "deep learning", "AI", "学習"],
        "インフラ・クラウド": ["cloud", "aws", "azure", "gcp", "docker", "kubernetes", "インフラ"],
        "フロントエンド": ["react", "vue", "angular", "frontend", "css", "html", "フロント"],
        "ビジネス・キャリア": ["business", "career", "startup", "management", "ビジネス"],
        "ガジェット": ["gadget", "device", "hardware", "phone", "camera", "ガジェット"],
        "ニュース・時事": ["news", "technology news", "trend", "ニュース"],
        "その他・ポエム": ["poem", "misc", "その他"]
    }

    text_lower = text.lower()
    scores = {cat: 0 for cat in categories}

    for category, keywords in category_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                scores[category] += 1

    # 最高スコアのカテゴリを取得
    max_category = max(scores, key=scores.get)
    max_score = scores[max_category] / max(1, len(text_lower.split()))

    return max_category, min(max_score, 1.0)


def extract_keywords_lightweight(text):
    """
    軽量版キーワード抽出（パターンマッチング）
    フォールバック用
    """
    import re

    # 単語を抽出（英数字とハイフン/アンダースコア）
    words = re.findall(r'\b[a-zA-Z0-9_-]{3,}\b', text)

    # 単語の出現頻度をカウント
    word_freq = {}
    for word in words:
        word = word.lower()
        word_freq[word] = word_freq.get(word, 0) + 1

    # 頻度でソート、トップ5を取得
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    # 結果を JSON 形式に変換
    result_tags = [
        {"name": word, "score": min(freq / 10, 1.0)}
        for word, freq in top_words
    ]

    return result_tags
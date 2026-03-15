import warnings
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import xml.etree.ElementTree as ET

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
from urllib.parse import urlparse
from datetime import timedelta
import threading
import os
from celery import shared_task
from .models import CachedURL, Article, Tag, RSSSubscription
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

# ★グローバルモデルキャッシュ（メモリ効率化のため）
_sbert_model = None
_sbert_model_name = None
_sbert_device = None
_keybert_model = None
_fugashi_tagger = None
_category_embeddings = None
_category_embeddings_source = None
_openvino_embedder = None
_openvino_embedder_source = None
_model_lock = threading.Lock()


def _normalize_engine(value):
    engine_raw = str(value or 'lightweight').strip().lower()
    return engine_raw if engine_raw in ('transformers', 'lightweight') else 'lightweight'


def resolve_ai_device():
    """
    AIデバイスを解決する。
    - AI_DEVICE=auto: 利用可能性に応じて npu -> xpu -> cuda -> mps -> cpu
    - AI_DEVICE=cpu/cuda/xpu/npu/mps: 手動指定（未利用ならcpuへフォールバック）
    """
    preferred_raw = str(getattr(settings, 'AI_DEVICE', 'auto')).strip().lower()
    preferred = preferred_raw if preferred_raw in {'auto', 'cpu', 'cuda', 'xpu', 'npu', 'mps'} else 'auto'

    try:
        import torch
    except Exception:
        return 'cpu'

    def _available(device_name):
        if device_name == 'cpu':
            return True
        if device_name == 'cuda':
            return bool(getattr(torch.cuda, 'is_available', lambda: False)())
        if device_name == 'xpu':
            xpu = getattr(torch, 'xpu', None)
            return bool(xpu and getattr(xpu, 'is_available', lambda: False)())
        if device_name == 'npu':
            npu = getattr(torch, 'npu', None)
            return bool(npu and getattr(npu, 'is_available', lambda: False)())
        if device_name == 'mps':
            mps = getattr(getattr(torch, 'backends', None), 'mps', None)
            return bool(mps and getattr(mps, 'is_available', lambda: False)())
        return False

    if preferred != 'auto':
        if _available(preferred):
            return preferred
        print(f"AI_DEVICE='{preferred_raw}' is unavailable. Fallback to 'cpu'.")
        return 'cpu'

    for candidate in ('npu', 'xpu', 'cuda', 'mps', 'cpu'):
        if _available(candidate):
            return candidate
    return 'cpu'


def _normalize_transformers_backend(value):
    backend_raw = str(value or 'sentence_transformers').strip().lower()
    allowed = {'auto', 'sentence_transformers', 'openvino_ir'}
    return backend_raw if backend_raw in allowed else 'sentence_transformers'


class OpenVINOIREmbedder:
    """
    OpenVINO IR (.xml/.bin) から埋め込みを生成する軽量ラッパー。
    SentenceTransformer を置き換えるのではなく、利用可能時のみ追加経路として使用する。
    """
    def __init__(self, xml_path, tokenizer_model, device='CPU', max_length=256):
        import numpy as np
        # OpenVINO 2023+ は openvino 直接、旧版は openvino.runtime からインポート
        try:
            from openvino import Core  # type: ignore[import-untyped]
        except ImportError:
            from openvino.runtime import Core  # type: ignore[import-untyped]
        from transformers import AutoTokenizer  # type: ignore[import-untyped]

        self.np = np
        self.compiled_model = Core().compile_model(xml_path, device_name=device)
        self.input_names = [inp.any_name for inp in self.compiled_model.inputs]

        # 静的形状かどうかを自動検出（NPU は静的形状のみ対応）
        # 入力 shape の batch / seq_len が固定なら記録する
        self._static_batch_size = None
        self._static_seq_len = None
        for inp in self.compiled_model.inputs:
            shape = inp.partial_shape
            if shape.rank.is_static and shape.rank.get_length() >= 2:
                batch_dim = shape[0]
                seq_dim = shape[1]
                if batch_dim.is_static and self._static_batch_size is None:
                    self._static_batch_size = batch_dim.get_length()
                if seq_dim.is_static:
                    self._static_seq_len = seq_dim.get_length()
                    break

        # 静的形状ならそのサイズを max_length に採用、そうでなければ引数値を使う
        self.max_length = self._static_seq_len if self._static_seq_len else max_length
        self.is_static = self._static_seq_len is not None

        tok_path = os.path.dirname(xml_path) if os.path.isfile(xml_path) and not os.path.isdir(tokenizer_model) else tokenizer_model
        # まずモデルと同じフォルダのトークナイザーを優先、なければ model名から
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                os.path.dirname(xml_path),
                fix_mistral_regex=True,
            )
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_model,
                fix_mistral_regex=True,
            )

        device_label = device.upper()
        print(f"[OpenVINO] {'Static' if self.is_static else 'Dynamic'} shape={self.max_length} on {device_label}")

    def _build_inputs(self, texts):
        padding = 'max_length' if self.is_static else True
        encoded = self.tokenizer(
            texts,
            padding=padding,
            truncation=True,
            max_length=self.max_length,
            return_tensors='np'
        )

        inputs = {}
        for name in self.input_names:
            if name in encoded:
                inputs[name] = encoded[name].astype(self.np.int64)
            elif name == 'token_type_ids':
                # NPU は token_type_ids も要求する場合がある
                inputs[name] = self.np.zeros_like(encoded['input_ids'], dtype=self.np.int64)
        return inputs, encoded

    def _pick_output(self, result):
        preferred = {'sentence_embedding', 'pooler_output', 'token_embeddings', 'last_hidden_state'}
        for out in self.compiled_model.outputs:
            if out.any_name in preferred:
                return result[out]
        return result[self.compiled_model.outputs[0]]

    def _encode_batch(self, texts):
        """モデルに1バッチ分を流して埋め込みを返す（戻り値 shape: [batch, dim]）"""
        inputs, encoded = self._build_inputs(texts)
        result = self.compiled_model(inputs)
        output = self._pick_output(result)

        if output.ndim == 3:
            attention = encoded.get('attention_mask')
            if attention is None:
                embeddings = output.mean(axis=1)
            else:
                mask = attention[..., None].astype(output.dtype)
                summed = (output * mask).sum(axis=1)
                counts = self.np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
                embeddings = summed / counts
        else:
            embeddings = output

        norms = self.np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / self.np.clip(norms, a_min=1e-9, a_max=None)

    def encode(self, texts, convert_to_tensor=False):
        single = isinstance(texts, str)
        if single:
            texts = [texts]

        # 静的 batch モデル（例: [1, 128] 固定）では、入力数を固定 batch に合わせる
        static_batch = self._static_batch_size if self.is_static else None
        if static_batch and static_batch > 0:
            all_embeddings = []
            i = 0
            total = len(texts)
            while i < total:
                chunk = texts[i:i + static_batch]
                actual_len = len(chunk)

                # 固定 batch に満たない最後のチャンクは末尾要素で埋める
                if actual_len < static_batch:
                    chunk = chunk + [chunk[-1]] * (static_batch - actual_len)

                emb = self._encode_batch(chunk)
                all_embeddings.append(emb[:actual_len])
                i += static_batch

            embeddings = self.np.concatenate(all_embeddings, axis=0) if all_embeddings else self.np.empty((0, 0))
        else:
            embeddings = self._encode_batch(texts)

        if convert_to_tensor:
            try:
                import torch
                tensor = torch.from_numpy(embeddings)
                return tensor[0] if single else tensor
            except Exception:
                pass

        return embeddings[0] if single else embeddings


def get_openvino_ir_embedder():
    """OpenVINO IR 埋め込みモデルを取得（利用不可なら None）"""
    global _openvino_embedder, _openvino_embedder_source

    xml_path = str(getattr(settings, 'AI_OPENVINO_IR_XML', '') or '').strip()
    if not xml_path:
        return None
    if not os.path.exists(xml_path):
        print(f"AI_OPENVINO_IR_XML not found: {xml_path}")
        return None

    tokenizer_model = str(
        getattr(settings, 'AI_OPENVINO_TOKENIZER_MODEL', getattr(settings, 'AI_SBERT_MODEL', '')) or ''
    ).strip()
    if not tokenizer_model:
        return None

    device = str(getattr(settings, 'AI_OPENVINO_DEVICE', 'CPU') or 'CPU').strip()
    source = (xml_path, tokenizer_model, device)

    if _openvino_embedder is not None and _openvino_embedder_source == source:
        return _openvino_embedder

    with _model_lock:
        if _openvino_embedder is not None and _openvino_embedder_source == source:
            return _openvino_embedder
        try:
            _openvino_embedder = OpenVINOIREmbedder(
                xml_path=xml_path,
                tokenizer_model=tokenizer_model,
                device=device,
            )
            _openvino_embedder_source = source
        except Exception as exc:
            print(f"OpenVINO IR backend unavailable: {exc}")
            _openvino_embedder = None
            _openvino_embedder_source = None
    return _openvino_embedder


def get_embedding_model_and_backend():
    """
    transformers系埋め込みモデルを取得。
    戻り値: (model, backend_name)
    backend_name: 'openvino_ir' | 'sentence_transformers' | None
    """
    backend = _normalize_transformers_backend(getattr(settings, 'AI_TRANSFORMERS_BACKEND', 'sentence_transformers'))

    if backend in ('auto', 'openvino_ir'):
        ov_model = get_openvino_ir_embedder()
        if ov_model is not None:
            return ov_model, 'openvino_ir'
        if backend == 'openvino_ir':
            return None, None

    st_model = get_sbert_model()
    if st_model is None:
        return None, None
    return st_model, 'sentence_transformers'


def _calculate_retry_at(failure_count, base_minutes=30, max_hours=24):
    delay_minutes = min(base_minutes * (2 ** max(0, failure_count - 1)), max_hours * 60)
    return timezone.now() + timedelta(minutes=delay_minutes)


def _mark_fetch_failure(cache, status_code=None, is_not_found=False):
    cache.title = None
    cache.fetch_status = 'not_found' if is_not_found else 'failed'
    cache.failure_count = (cache.failure_count or 0) + 1
    cache.last_failure_at = timezone.now()
    cache.last_http_status = status_code
    cache.next_retry_at = _calculate_retry_at(cache.failure_count)
    cache.save(update_fields=[
        'title',
        'fetch_status',
        'failure_count',
        'last_failure_at',
        'last_http_status',
        'next_retry_at',
    ])


def _mark_fetch_success(cache, title, description, image_url, site_name, status_code):
    cache.title = title
    cache.description = description
    cache.image_url = image_url
    cache.site_name = site_name
    cache.last_scraped_at = timezone.now()
    cache.fetch_status = 'success' if title else 'failed'
    cache.failure_count = 0 if title else (cache.failure_count or 0) + 1
    cache.last_failure_at = None if title else timezone.now()
    cache.last_http_status = status_code
    cache.next_retry_at = None if title else _calculate_retry_at(cache.failure_count)
    cache.save(update_fields=[
        'title',
        'description',
        'image_url',
        'site_name',
        'last_scraped_at',
        'fetch_status',
        'failure_count',
        'last_failure_at',
        'last_http_status',
        'next_retry_at',
    ])

def get_sbert_model():
    """SBERT モデルをキャッシュから取得（初回はロード）"""
    global _sbert_model, _sbert_model_name, _sbert_device
    model_name = getattr(
        settings,
        'AI_SBERT_MODEL',
        'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    )
    device = resolve_ai_device()
    if _sbert_model is not None and _sbert_model_name == model_name and _sbert_device == device:
        return _sbert_model

    with _model_lock:
        if _sbert_model is not None and _sbert_model_name == model_name and _sbert_device == device:
            return _sbert_model
        try:
            import logging
            from transformers.utils import logging as hf_logging
            from sentence_transformers import SentenceTransformer
            logging.getLogger('sentence_transformers').setLevel(logging.ERROR)
            hf_logging.set_verbosity_error()
            _sbert_model = SentenceTransformer(model_name, device=device)
            _sbert_model_name = model_name
            _sbert_device = device
        except Exception:
            _sbert_model = None
            _sbert_model_name = None
            _sbert_device = None
    return _sbert_model


def get_keybert_model():
    """KeyBERT モデルをキャッシュから取得（初回は作成）"""
    global _keybert_model
    if _keybert_model is not None:
        return _keybert_model

    with _model_lock:
        if _keybert_model is not None:
            return _keybert_model
        model = get_sbert_model()
        if model is None:
            return None
        try:
            from keybert import KeyBERT
            _keybert_model = KeyBERT(model=model)
        except Exception:
            _keybert_model = None
    return _keybert_model


def get_fugashi_tagger():
    """fugashi Tagger をキャッシュして再利用"""
    global _fugashi_tagger
    if _fugashi_tagger is not None:
        return _fugashi_tagger

    with _model_lock:
        if _fugashi_tagger is not None:
            return _fugashi_tagger
        try:
            import fugashi
            _fugashi_tagger = fugashi.Tagger()
        except Exception:
            _fugashi_tagger = None
    return _fugashi_tagger


def get_category_embeddings(model, categories):
    """カテゴリ埋め込みをキャッシュして再利用"""
    global _category_embeddings, _category_embeddings_source
    source = (
        type(model).__name__,
        _sbert_model_name,
        _sbert_device,
        _openvino_embedder_source,
        tuple(categories)
    )
    if _category_embeddings is not None and _category_embeddings_source == source:
        return _category_embeddings

    with _model_lock:
        if _category_embeddings is not None and _category_embeddings_source == source:
            return _category_embeddings
        _category_embeddings = model.encode(categories, convert_to_tensor=True)
        _category_embeddings_source = source
    return _category_embeddings

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

    # 次回リトライ時刻に達していない場合はスキップ
    if cache.next_retry_at and cache.next_retry_at > timezone.now():
        return

    # --- スクレイピング処理 ---
    try:
        headers = { 'User-Agent': 'YourAppName-Bookmark-Bot/1.0' }
        response = requests.get(cache.url, headers=headers, timeout=10)
        status_code = response.status_code

        # 404/410は削除・移転の可能性が高いのでタイトルは空のままにする
        if status_code in (404, 410):
            _mark_fetch_failure(cache, status_code=status_code, is_not_found=True)
            print(f"Not found ({status_code}) for {cache.url}")
            return

        # 5xxやその他4xxは失敗として再試行
        if status_code >= 500 or status_code >= 400:
            _mark_fetch_failure(cache, status_code=status_code, is_not_found=False)
            print(f"HTTP error ({status_code}) for {cache.url}")
            return

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

        # サイト名のフォールバック（ドメインから）
        if not site_name:
            parsed = urlparse(cache.url)
            site_name = parsed.netloc.replace('www.', '') or None
        # タイトルが取れなかった場合は None のまま（再取得対象にするため URL 由来の仮タイトルは付けない）

        # --- DB (CachedURL) に保存 ---
        _mark_fetch_success(
            cache,
            title=title,
            description=description,
            image_url=image_url,
            site_name=site_name,
            status_code=status_code,
        )
        print(f"Successfully fetched metadata for {cache.url}")

        # ★記事IDが渡されたら、自動分類タスクを実行
        if article_id:
            classify_article(article_id)

    except requests.RequestException as e:
        _mark_fetch_failure(cache, status_code=None, is_not_found=False)
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
        combined_text = f"{title} {description}".strip()

        # タイトル/概要が取れない記事（404等）は URL/サイト名を補助テキストとして利用
        if not combined_text:
            fallback_parts = [
                article.cached_url.site_name or "",
                article.cached_url.url or "",
            ]
            combined_text = " ".join(part for part in fallback_parts if part).strip()

        # それでも空なら既定カテゴリで完了扱いにして再試行ループを避ける
        if not combined_text.strip():
            article.suggested_category = 'その他・ポエム'
            article.suggested_category_score = 0.0
            article.suggested_tags = []
            article.classification_status = 'completed'
            article.classification_error = "分類元テキストなし（タイトル/概要未取得）"
            article.save(update_fields=[
                'suggested_category',
                'suggested_category_score',
                'suggested_tags',
                'classification_status',
                'classification_error',
            ])
            return

        engine_raw = str(getattr(settings, 'AI_CLASSIFICATION_ENGINE', 'lightweight')).strip().lower()
        engine = _normalize_engine(engine_raw)
        if engine_raw != engine:
            print(f"Invalid AI_CLASSIFICATION_ENGINE='{engine_raw}'. Fallback to 'lightweight'.")

        if engine == 'transformers':
            # ★処理A: カテゴリ判定 (SBERT 類似度)
            category, category_score = classify_category_sbert(combined_text)
            # ★処理B: タグ抽出 (KeyBERT)
            tags = extract_keywords_keybert(combined_text)
        else:
            # 軽量モード: Transformers 依存を使わずに安定動作
            category, category_score = predict_category_lightweight(combined_text)
            tags = extract_keywords_lightweight(combined_text)

        article.suggested_category = category
        article.suggested_category_score = category_score
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
        # 埋め込みモデルを取得（OpenVINO IR / SentenceTransformers）
        model, _backend = get_embedding_model_and_backend()
        if model is None:
            return predict_category_lightweight(text)

        # カテゴリ候補を取得
        categories = settings.AI_CATEGORY_CANDIDATES

        # テキストとカテゴリをベクトル化
        text_embedding = model.encode(text, convert_to_tensor=True)
        category_embeddings = get_category_embeddings(model, categories)

        # コサイン類似度を計算（torch / numpy 両対応）
        try:
            import torch
            if isinstance(text_embedding, torch.Tensor):
                te = text_embedding if text_embedding.ndim == 2 else text_embedding.unsqueeze(0)
                ce = category_embeddings
                if not isinstance(ce, torch.Tensor):
                    ce = torch.as_tensor(ce)
                te = te / te.norm(dim=1, keepdim=True).clamp(min=1e-9)
                ce = ce / ce.norm(dim=1, keepdim=True).clamp(min=1e-9)
                cos_scores = torch.mm(te, ce.transpose(0, 1))[0]
                max_score, max_idx = cos_scores.max(dim=0)
                best_category = categories[max_idx.item()]
                score = float(max_score.item())
                return best_category, score
        except Exception:
            pass

        import numpy as np
        te = np.asarray(text_embedding, dtype=np.float32)
        ce = np.asarray(category_embeddings, dtype=np.float32)
        if te.ndim == 1:
            te = te[None, :]
        te = te / np.clip(np.linalg.norm(te, axis=1, keepdims=True), 1e-9, None)
        ce = ce / np.clip(np.linalg.norm(ce, axis=1, keepdims=True), 1e-9, None)
        cos_scores = np.matmul(te, ce.T)[0]
        max_idx = int(np.argmax(cos_scores))
        best_category = categories[max_idx]
        score = float(cos_scores[max_idx])

        return best_category, score

    except Exception as exc:
        print(f"classify_category_sbert fallback to lightweight: {exc}")
        return predict_category_lightweight(text)


def extract_keywords_openvino(text, model, top_n=5, max_candidates=50):
    """
    OpenVINO IR モデルを使ったKeyBERT相当のキーワード抽出。
    既存経路（sentence_transformers + KeyBERT）を置き換えるのではなく、
    openvino_ir バックエンド時のみ呼ばれる専用経路。

    手順:
      1. fugashi で分かち書き → 候補語リスト生成（名詞・英単語を優先）
      2. IRモデルで文書全体をベクトル化
      3. IRモデルで各候補語をバッチベクトル化
      4. コサイン類似度でランキング → top_n を返す
    """
    import re
    import numpy as np

    try:
        # 1. 候補語収集（fugashi 形態素解析 or 正規表現フォールバック）
        tagger = get_fugashi_tagger()
        if tagger is not None:
            candidates = []
            for word in tagger(text):
                surface = word.surface.strip()
                if not surface:
                    continue
                pos = ''
                try:
                    pos = word.feature.pos1  # UniDic
                except Exception:
                    pass
                if not pos:
                    try:
                        pos = word.feature[0]  # IPAdic
                    except Exception:
                        pass
                # 名詞・英語系 or 英数字2文字以上を候補に
                if len(surface) >= 2 and pos in ('名詞', '英語', ''):
                    candidates.append(surface)
                elif re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{1,}$', surface):
                    candidates.append(surface.lower())
        else:
            # fugashi なし: 英単語のみ
            candidates = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]{1,}\b', text)

        # 重複除去・上限
        seen = set()
        unique_candidates = []
        for c in candidates:
            cl = c.lower()
            if cl not in seen:
                seen.add(cl)
                unique_candidates.append(c)
        unique_candidates = unique_candidates[:max_candidates]

        if not unique_candidates:
            return extract_keywords_lightweight(text)

        # 2. 文書ベクトル
        doc_emb = np.asarray(model.encode(text), dtype=np.float32)
        if doc_emb.ndim == 1:
            doc_emb = doc_emb[None, :]
        doc_norm = np.linalg.norm(doc_emb, axis=1, keepdims=True)
        doc_emb = doc_emb / np.clip(doc_norm, 1e-9, None)

        # 3. 候補語ベクトル（バッチ処理）
        cand_embs = np.asarray(model.encode(unique_candidates), dtype=np.float32)
        if cand_embs.ndim == 1:
            cand_embs = cand_embs[None, :]
        cand_norm = np.linalg.norm(cand_embs, axis=1, keepdims=True)
        cand_embs = cand_embs / np.clip(cand_norm, 1e-9, None)

        # 4. コサイン類似度スコアリング → top_n
        cos_scores = np.matmul(doc_emb, cand_embs.T)[0]  # shape: (n_candidates,)
        top_indices = np.argsort(cos_scores)[::-1][:top_n]

        result = [
            {"name": unique_candidates[i], "score": float(cos_scores[i])}
            for i in top_indices
            if cos_scores[i] > 0.0
        ]
        return result if result else extract_keywords_lightweight(text)

    except Exception as exc:
        print(f"extract_keywords_openvino failed: {exc}")
        return extract_keywords_lightweight(text)


def extract_keywords_keybert(text):
    """
    KeyBERT で日本語キーワードを抽出
    日本語分かち書きは fugashi を使用
    戻り値: [{"name": "キーワード", "score": 0.95}, ...]
    """
    try:
        _model, backend = get_embedding_model_and_backend()
        if backend == 'openvino_ir':
            # OpenVINO IR 専用経路: IRモデルによる埋め込み類似度でKeyBERT相当を実行
            return extract_keywords_openvino(text, _model)

        # KeyBERT モデルを取得（初回のみ初期化）
        kw_model = get_keybert_model()
        if kw_model is None:
            # フォールバック
            return extract_keywords_lightweight(text)

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
        tagger = get_fugashi_tagger()
        if tagger is None:
            return text
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


def _entry_guid(entry):
    """
    RSSエントリの一意IDを決定する
    guid > id > link の順で利用
    """
    return entry.get('guid') or entry.get('id') or entry.get('link') or None


def _local_tag(tag_name):
    if not tag_name:
        return ''
    return tag_name.split('}')[-1].lower()


def _find_child_text(node, accepted_tags):
    accepted = {name.lower() for name in accepted_tags}
    for child in list(node):
        if _local_tag(child.tag) in accepted:
            text = (child.text or '').strip()
            if text:
                return text
    return None


def _find_link(node):
    for child in list(node):
        tag = _local_tag(child.tag)
        if tag != 'link':
            continue

        # RSS: <link>https://example.com</link>
        text_value = (child.text or '').strip()
        if text_value:
            return text_value

        # Atom: <link href="https://example.com" rel="alternate" />
        href = (child.attrib.get('href') or '').strip()
        if href:
            return href

    return None


def _parse_feed_entries(feed_url):
    headers = {'User-Agent': 'Newsreread-RSS-Bot/1.0'}
    response = requests.get(feed_url, headers=headers, timeout=15)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    parsed_entries = []

    for node in root.iter():
        local_name = _local_tag(node.tag)
        if local_name not in {'item', 'entry'}:
            continue

        link = _find_link(node)
        guid = _find_child_text(node, {'guid', 'id'}) or link
        title = _find_child_text(node, {'title'})
        description = _find_child_text(node, {'description', 'summary', 'content'})

        if not link or not guid:
            continue

        parsed_entries.append(
            {
                'link': link,
                'guid': guid,
                'title': title,
                'description': description,
            }
        )

    return parsed_entries


@shared_task
def sync_single_rss_feed(subscription_id):
    """
    単一購読のRSSを同期
    - 新規/更新を反映
    - feedから消えた未読RSS記事は即物理削除
    """
    try:
        subscription = RSSSubscription.objects.get(id=subscription_id, is_active=True)
    except RSSSubscription.DoesNotExist:
        return

    try:
        entries = _parse_feed_entries(subscription.feed_url)
    except Exception:
        return

    seen_guids = set()

    for entry in entries:
        link = entry.get('link')
        if not link:
            continue

        guid = _entry_guid(entry)
        if not guid:
            continue

        guid = str(guid).strip()
        if not guid:
            continue

        seen_guids.add(guid)

        cached_url, _ = CachedURL.objects.get_or_create(url=link)

        entry_title = entry.get('title')
        entry_description = entry.get('description')

        changed_fields = []
        if entry_title and cached_url.title != entry_title:
            cached_url.title = entry_title
            changed_fields.append('title')
        if entry_description and cached_url.description != entry_description:
            cached_url.description = entry_description
            changed_fields.append('description')

        if changed_fields:
            cached_url.last_scraped_at = timezone.now()
            cached_url.fetch_status = 'success' if cached_url.title else cached_url.fetch_status
            cached_url.failure_count = 0 if cached_url.title else cached_url.failure_count
            cached_url.last_failure_at = None if cached_url.title else cached_url.last_failure_at
            cached_url.next_retry_at = None if cached_url.title else cached_url.next_retry_at
            changed_fields.append('last_scraped_at')
            changed_fields.extend(['fetch_status', 'failure_count', 'last_failure_at', 'next_retry_at'])
            cached_url.save(update_fields=changed_fields)

        article, created = Article.objects.get_or_create(
            user=subscription.user,
            cached_url=cached_url,
            defaults={
                'status': 'unread',
                'rss_subscription': subscription,
                'is_from_rss': True,
                'rss_guid': guid,
            }
        )

        # RSSで取り込んだ新規記事は自動分類を開始
        if created:
            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                classify_article(article.id)
            else:
                classify_article.delay(article.id)

        if not created:
            fields_to_update = []
            if article.rss_subscription_id != subscription.id:
                article.rss_subscription = subscription
                fields_to_update.append('rss_subscription')
            if not article.is_from_rss:
                article.is_from_rss = True
                fields_to_update.append('is_from_rss')
            if article.rss_guid != guid:
                article.rss_guid = guid
                fields_to_update.append('rss_guid')
            if fields_to_update:
                article.save(update_fields=fields_to_update)

    if seen_guids:
        Article.objects.filter(
            user=subscription.user,
            rss_subscription=subscription,
            is_from_rss=True,
            status='unread',
        ).exclude(
            rss_guid__in=seen_guids
        ).delete()

    subscription.last_fetched_at = timezone.now()
    subscription.save(update_fields=['last_fetched_at'])


@shared_task
def sync_all_rss_feeds():
    """
    有効なRSS購読を全件同期
    """
    for subscription in RSSSubscription.objects.filter(is_active=True):
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            sync_single_rss_feed(subscription.id)
        else:
            sync_single_rss_feed.delay(subscription.id)


@shared_task
def retry_pending_metadata(batch_size=100):
    """
    タイトル未取得でリトライ可能なCachedURLを再取得
    """
    now = timezone.now()
    queryset = CachedURL.objects.filter(
        title__isnull=True
    ).filter(
        Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now)
    )

    targets = queryset.order_by('next_retry_at', 'id')[:batch_size]
    for cache in targets:
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            fetch_article_metadata(cache.id)
        else:
            fetch_article_metadata.delay(cache.id)
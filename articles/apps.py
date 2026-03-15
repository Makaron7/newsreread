from django.apps import AppConfig


class ArticlesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'articles'

    def ready(self):
        import os
        from django.conf import settings

        # ── 設定値を読む ──
        engine  = str(getattr(settings, 'AI_CLASSIFICATION_ENGINE',  'lightweight')).strip().lower()
        backend = str(getattr(settings, 'AI_TRANSFORMERS_BACKEND',   'sentence_transformers')).strip().lower()
        device  = str(getattr(settings, 'AI_DEVICE',                 'auto')).strip().lower()
        sbert_model   = str(getattr(settings, 'AI_SBERT_MODEL', '')).strip()
        ov_xml        = str(getattr(settings, 'AI_OPENVINO_IR_XML', '')).strip()
        ov_device     = str(getattr(settings, 'AI_OPENVINO_DEVICE', 'CPU')).strip()
        ov_tok_model  = str(getattr(settings, 'AI_OPENVINO_TOKENIZER_MODEL', sbert_model)).strip()

        # ── 実際に動くかを調べる（インポート試行・ファイル存在確認）──
        def _can_import(mod):
            try:
                __import__(mod)
                return True
            except Exception:
                return False

        actual_engine  = 'lightweight'
        actual_backend = None
        actual_notes   = []

        if engine == 'transformers':
            # OpenVINO IR 経路を試みるか
            try_ov = backend in ('openvino_ir', 'auto')
            ov_ok  = False
            if try_ov:
                if not ov_xml:
                    actual_notes.append("AI_OPENVINO_IR_XML 未設定")
                elif not os.path.exists(ov_xml):
                    actual_notes.append(f"XML not found: {ov_xml}")
                elif not _can_import('openvino'):
                    actual_notes.append("openvino 未インストール")
                elif not _can_import('transformers'):
                    actual_notes.append("transformers 未インストール（トークナイザー用）")
                else:
                    ov_ok = True

            if ov_ok:
                actual_engine  = 'transformers'
                actual_backend = 'openvino_ir'
            elif backend == 'openvino_ir':
                # openvino_ir 固定指定なのに使えない → lightweight へ
                actual_engine  = 'lightweight'
                actual_backend = None
            else:
                # sentence_transformers / auto（OV失敗分岐含む）
                if _can_import('sentence_transformers'):
                    actual_engine  = 'transformers'
                    actual_backend = 'sentence_transformers'
                else:
                    actual_notes.append("sentence_transformers 未インストール")
                    actual_engine  = 'lightweight'
                    actual_backend = None
        # engine == 'lightweight' はそのまま

        # ── 表示 ──
        sep = '─' * 52
        print(f"\n{sep}")
        print(f"  [NewsReread] AI Classification Config")
        print(sep)

        # 設定値ブロック
        print(f"  【設定値】")
        print(f"    ENGINE  : {engine}")
        if engine == 'transformers':
            print(f"    BACKEND : {backend}")
            if backend in ('sentence_transformers', 'auto'):
                print(f"    MODEL   : {sbert_model or '(default)'}")
                print(f"    DEVICE  : {device}  (auto=npu→xpu→cuda→mps→cpu)")
            if backend in ('openvino_ir', 'auto'):
                print(f"    OV XML  : {ov_xml or '(未設定)'}")
                print(f"    OV TOK  : {ov_tok_model or '(未設定)'}")
                print(f"    OV DEV  : {ov_device}")
        else:
            print(f"    MODE    : キーワードマッチング")

        print(f"  {'─' * 48}")

        # 実際に動くもの
        print(f"  【実際に動くもの】")
        if actual_engine == 'transformers' and actual_backend == 'openvino_ir':
            print(f"    → OpenVINO IR 推論  ({ov_xml})")
            print(f"       デバイス: {ov_device}  トークナイザー: {ov_tok_model}")
        elif actual_engine == 'transformers' and actual_backend == 'sentence_transformers':
            # 実際に解決されるデバイスを確認
            try:
                from articles.tasks import resolve_ai_device
                resolved_device = resolve_ai_device()
            except Exception:
                resolved_device = '(不明)'
            device_note = ''
            if device != 'auto' and resolved_device != device:
                device_note = f'  ※ {device} 不可 → {resolved_device} で動作'
            elif device == 'auto':
                device_note = f'  (auto → 実際: {resolved_device})'
            print(f"    → SentenceTransformers + KeyBERT")
            print(f"       モデル: {sbert_model or '(default)'}")
            print(f"       デバイス設定: {device}{device_note}")
        else:
            print(f"    → 軽量キーワードマッチング（AI依存なし）")

        if actual_notes:
            print(f"  {'─' * 48}")
            print(f"  【フォールバック理由】")
            for note in actual_notes:
                print(f"    [x] {note}")

        print(sep + "\n")

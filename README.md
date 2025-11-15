# SagiCheck API

Google マップの口コミから桜レビューや詐欺兆候をスコアリングする FastAPI 製のシンプルな Web API です。

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

`.env` などで `GOOGLE_MAPS_API_KEY` を設定してください。

## ローカル実行

```bash
uvicorn app.api:app --reload --port 8000
```

## エンドポイント

- `POST /analyze`

### リクエスト例

```json
{
  "google_maps_url": "https://www.google.com/maps/place/...",
  "tabelog_rating": 3.45,
  "tabelog_review_count": 27,
  "tabelog_name": "焼肉〇〇 渋谷店"
}
```

### レスポンス例

```json
{
  "sakura_score": 62,
  "fraud_score": 18,
  "risk_label": "medium",
  "signals": {
    "total_reviews": 87,
    "short_5_ratio": 0.56,
    "burst_7day_ratio": 0.42,
    "rating_diff_google_minus_tabelog": 0.8,
    "tabelog_missing": false,
    "name_similarity_google_vs_tabelog": 0.92,
    "low_star_ratio": 0.09,
    "fraud_keyword_ratio": 0.04
  },
  "fraud_keywords": [
    {"keyword": "詐欺", "count": 2}
  ],
  "comments_ja": [
    "短文または無言の★5口コミが全体の56%を占めています。",
    "短期間に口コミが集中して投稿されており、不自然な増え方です。"
  ]
}
```

## テスト

```bash
pytest
```

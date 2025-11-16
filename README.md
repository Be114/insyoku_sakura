# SagiCheck API

Google マップの口コミから桜レビュー（サクラ）や詐欺兆候をスコアリングする FastAPI 製の Web API です。

## 概要

飲食店などの店舗情報において、Google マップのレビューと食べログの情報を比較・分析し、不自然なレビューパターンや詐欺の兆候を検出します。

### 主な機能

- **桜レビュー（サクラ）検出**: 短文の高評価レビューの集中、不自然な投稿パターン、他サイトとの評価乖離などを検出
- **詐欺兆候検出**: 「詐欺」「ぼったくり」などのキーワード検出、低評価レビューの分析
- **リスク評価**: high/medium/low の3段階でリスクレベルを判定
- **詳細シグナル**: 分析に使用した各種指標とコメントを提供

## セットアップ

### 必要要件

- Python 3.11 以上
- Google Maps API キー（Places API と Places API (New) の有効化が必要）

### インストール

```bash
# 仮想環境の作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存パッケージのインストール
pip install -e .[dev]
```

### 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、Google Maps API キーを設定してください。

```bash
GOOGLE_MAPS_API_KEY=your_api_key_here
```

または、環境変数として直接設定することもできます。

```bash
export GOOGLE_MAPS_API_KEY=your_api_key_here
```

## ローカル実行

```bash
uvicorn app.api:app --reload --port 8000
```

サーバーが起動したら、以下の URL でアクセスできます。

- API ドキュメント: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API エンドポイント

### `POST /analyze`

指定された Google マップの店舗について、桜レビューと詐欺兆候を分析します。

#### リクエストボディ

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `google_maps_url` | string (URL) | ○ | Google マップの店舗ページ URL |
| `tabelog_rating` | float (0-5) | × | 食べログの評価（星の数） |
| `tabelog_review_count` | integer | × | 食べログの口コミ数 |
| `tabelog_name` | string | × | 食べログ上の店舗名 |

#### リクエスト例

```json
{
  "google_maps_url": "https://www.google.com/maps/place/焼肉店/@35.6581,139.7414,17z/data=!3m1!4b1!4m6!3m5!1s0x60188b5example:0x123456789abcdef!8m2!3d35.6581!4d139.7414",
  "tabelog_rating": 3.45,
  "tabelog_review_count": 27,
  "tabelog_name": "焼肉〇〇 渋谷店"
}
```

#### レスポンス例

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

#### レスポンスフィールドの説明

| フィールド | 説明 |
|-----------|------|
| `sakura_score` | 桜レビュー（サクラ）の疑いスコア (0-100) |
| `fraud_score` | 詐欺兆候のスコア (0-100) |
| `risk_label` | リスクレベル: `low`, `medium`, `high` |
| `signals.total_reviews` | 分析対象のレビュー総数 |
| `signals.short_5_ratio` | 短文（15文字以下）の★5レビューの割合 |
| `signals.burst_7day_ratio` | 7日間ウィンドウ内の最大集中投稿率 |
| `signals.rating_diff_google_minus_tabelog` | Google と食べログの評価差 |
| `signals.tabelog_missing` | 食べログ情報が提供されていない場合 true |
| `signals.name_similarity_google_vs_tabelog` | 店舗名の類似度 (0-1) |
| `signals.low_star_ratio` | ★1-2 の低評価レビューの割合 |
| `signals.fraud_keyword_ratio` | 詐欺関連キーワードを含むレビューの割合 |
| `fraud_keywords` | 検出された詐欺関連キーワードとその出現回数 |
| `comments_ja` | 検出された問題点の日本語コメント |

## スコアリングロジック

### 桜レビュー（sakura_score）の判定基準

以下の要素を総合的に評価します（最大100点）:

- **短文の★5レビュー率** (最大40点): 15文字以下の短文または無言の★5レビューが多い
- **短期集中投稿率** (最大25点): 7日間以内に大量のレビューが投稿されている
- **評価の乖離** (最大20点): Google の評価が食べログより高い
- **食べログ情報不足** (5点): 食べログに情報がない
- **店舗名の不一致** (最大15点): Google と食べログで店舗名が異なる
- **低評価の欠如** (10点): レビューが20件以上あるのに★1-2が10%未満

### 詐欺スコア（fraud_score）の判定基準

- **詐欺キーワード検出** (最大90点): 「詐欺」「ぼったくり」「rip-off」などのキーワード
- **低評価の集中** (10点): レビューが10件以上で、★1-2が30%以上

### リスクレベルの判定

- **high**: sakura_score ≥ 70 または fraud_score ≥ 70
- **medium**: sakura_score ≥ 40 または fraud_score ≥ 40
- **low**: 上記以外

## テスト

```bash
# すべてのテストを実行
pytest

# 詳細な出力付きで実行
pytest -v

# カバレッジを確認
pytest --cov=app --cov-report=html
```

## プロジェクト構成

```
.
├── app/
│   ├── __init__.py
│   ├── api.py              # FastAPI エンドポイント定義
│   ├── google_client.py    # Google Places API クライアント
│   ├── models.py           # Pydantic データモデル
│   └── scoring.py          # スコアリングロジック
├── tests/
│   ├── test_google_client.py
│   └── test_scoring.py
├── pyproject.toml          # プロジェクト設定
└── README.md
```

## 制限事項

- Google Places API には利用制限があります。大量のリクエストを行う場合は API クォータにご注意ください。
- レビューの取得は最大100件までです。
- 分析精度は提供される食べログ情報の有無に依存します。食べログ情報がない場合、一部の分析が制限されます。
- 店舗名の類似度判定は完全ではありません。表記揺れが大きい場合は正確に判定できない可能性があります。

## 技術スタック

- **FastAPI**: 高速な非同期 Web フレームワーク
- **httpx**: 非同期 HTTP クライアント
- **Pydantic**: データバリデーションとシリアライゼーション
- **pytest**: テストフレームワーク

## ライセンス

このプロジェクトは教育・研究目的で作成されています。

## 注意事項

このツールは参考情報を提供するものであり、検出結果が必ずしも実際の不正行為を示すものではありません。最終的な判断は人間が行う必要があります。

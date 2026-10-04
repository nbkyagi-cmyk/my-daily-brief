# My Daily Brief

スマホ向けの独立したニュースPWA。Python 3.11以上、標準ライブラリのみで動作します。既存のPPI Monitorとは別の保存先・設定・ワークフローを使います。

## PCで開始（PowerShell）

以前のサーバーのPowerShellで Ctrl+C を押して停止し、修正版ZIPを新しいフォルダに展開します。既存フォルダへの上書きは不要です。このREADMEのあるフォルダをPowerShellで開き、次の1行だけ実行してください。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-Demo.ps1
```

これはその子PowerShellだけに適用され、PC全体の実行ポリシーを変更しません。組織の制限で実行できない場合は下の手動手順を使ってください。

管理パスワードを尋ねられたら16文字以上の値を入力します。確認用には `MyDailyBrief-Test-2026!` も使えます。本番には別の十分長いパスワードを設定してください。入力は画面に表示されません。ブラウザで **http://127.0.0.1:8000** を開き、Ctrl+Shift+R で再読み込みし、同じパスワードでログインしてください。`localhost` へ置き換えないでください。

PythonがPATHにない場合、このPCの既存Pythonを自動的に使います。起動表示の Source が今回展開したフォルダの `app/main.py` であることを確認できます。ポート使用中なら新しいサーバーは起動しません。旧サーバーを停止して再実行してください。スクリプトはGitHub Actions・外部ニュース・AI APIを呼びません。

### 手動で開始する場合

このREADMEのあるフォルダに移動して実行します。PythonがPATHにない場合は後述の絶対パスで置き換えます。

```powershell
$env:MDB_ADMIN_PASSWORD = '自分で作った16文字以上の十分長いパスワード'
$env:MDB_ORIGIN = 'http://127.0.0.1:8000'
$env:MDB_DEMO = '1'
python -m app.main demo
python -m app.main serve
```

ブラウザで http://127.0.0.1:8000 を開きます。管理画面は上記パスワードでログインできます。PythonがPATHにない場合はインストール済みPythonの絶対パスを `& '絶対パス/python.exe'` の形で使用してください。本環境のPythonは `C:\Users\jyagi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` です。

デモは `data/demo.db`、実データは `data/news.db` に分離します。デモ記事は架空です。実ニュースに切り替えるにはサーバーを停止し `Remove-Item Env:MDB_DEMO` を実行してから再起動してください。

```powershell
python -m unittest discover -s tests -v
python -m app.main update --category 政治
python -m app.main update
```

これらの開発・手動テストはすべてローカルで実行され、GitHub Actionsは起動しません。`.env.example` は設定項目の説明用で、自動で読み込まれません。

## 取得元とAI設定

`sources.json` に HTTPSのRSS/Atomフィードを設定します。`name`、`category`（6カテゴリの正式名称）、`url` が必須です。初期設定はNHKの総合・政治・経済・国際です。水道・インフラ、無電柱化には国土交通省の公式プレスリリースRSSと新着情報RSSを追加しています。未設定のカテゴリを含む全更新は「一部失敗」になり、完全成功として記録しません。取得元の提供状況・利用条件は本番前に確認してください。

1ソースにつき最大20記事、最大2MB、20秒の取得制限。従来ソースはURL、keywords付きソースはカテゴリ＋URLで重複排除し、既存記事は再分析しません。同じ記事を両方の専門カテゴリに保存でき、同一カテゴリの複数フィード間では重複しません。本文を無断で全文転載せず、配信元の概要を最大3文表示します。概要がない場合は補作しません。

AI分析を有効にする場合はサーバーに `OPENAI_API_KEY` を設定します。`MDB_AI_MODEL`（既定 `gpt-4.1-mini`）と `MDB_AI_LIMIT`（既定12新着記事/回）で費用を制御します。キー未設定・分析失敗・件数上限超過では重要度や分析を「未評価」「未生成」と表示します。出典概要は事実欄、背景・重要性・展望はAI分析欄に分離。キーはブラウザに渡しません。API利用料金はActionsとは別です。推測の正しさは保証できないため原文確認を前提にしています。

## スマホ運用と本番

ローカルサーバーの管理画面を使う場合は、常時動くサーバー、永続ディスク、HTTPSのURLが必要です。GitHub Pagesの閲覧専用サイトは、下記GitHub Actions方式ならPCオフで更新できます。Pythonサーバーはローカル用HTTPのため、本番はTLS終端・アクセス制限・リクエスト上限を持つリバースプロキシの背後で1プロセスだけ起動してください。

1. サーバーにプロジェクトを配置し、データディスクを `MDB_DB` で指定（例 `/var/lib/mydailybrief/news.db`）。
2. 長い管理パスワードと別のランダム32文字以上の `MDB_SCHEDULE_TOKEN` を環境変数に設定。
3. `MDB_ORIGIN=https://実際の公開ホスト` を設定。プロキシでHTTPからHTTPSに転送し、Pythonのポートは外部に公開しません。
4. `python -m app.main serve --host 127.0.0.1` をサービス管理機能で常駐させます。サーバー再起動時の未完了更新は失敗として記録します。
5. スマホでHTTPS URLを開き、ホーム画面に追加します。ブラウザ・OSによってインストールUIやSVGアイコン対応は異なります。
6. 管理画面からログインし、全更新・カテゴリ単独更新を確認。スマホは指示を送るだけで、更新処理はサーバーで続きます。

保存・既読は端末のブラウザ内に保存し、端末間同期はありません。記事・検索履歴対象はサーバーの最新1000件（DBには全件を保持）。昨日との差分は初回取得件数の比較で、記事内容の改訂比較ではありません。PWAのオフライン対応は画面枠のみで、記事データ・管理APIをキャッシュしません。完全オフライン閲覧は今後の拡張です。

管理セッションは1時間、有効な操作元とCSRFトークンを確認、ログイン失敗は15分あたり5回まで。セッションはメモリ内で再起動時に失効します。スケジュールAPIは別トークン。並行更新はDBの一意制約で拒否。更新履歴は自動・手動・ローカルを区別し、成功・一部失敗・失敗・更新中を表示します。最新更新の失敗、19時以降の当日全更新未完了、最終全更新成功を画面に表示します。

開発時も同じ認証・Origin・CSRF・15分5回制限を適用します。5回失敗した後は正しいパスワードでも429になります。成功しても直前の失敗記録を消しません。失敗履歴とセッションは起動中の1プロセス内に保持し、再起動で失効します。プロキシ配下では接続元IP単位の制限となり、プロキシのIPを共有する場合は全ユーザーが制限を共有します。X-Forwarded-Forは信頼しません。本番で再起動をまたぐ制限が必要ならプロキシ側にも制限を設定してください。

パスワード・Originは起動時の環境変数を固定して使用します。別のPowerShellで値を変えても起動済みサーバーには反映されません。変更後はサーバーを停止して同じPowerShellから起動し直します。400はJSON形式、401は認証またはセッション/CSRF、403はOrigin、415はContent-Type、429はログイン失敗制限です。JSONはUTF-8のオブジェクトで4096バイト以下を送ります。パスワードを整形・trimする処理はありません。

PowerShellからAPIを直接使う場合も `Origin` が必須です。例：

```powershell
$body = [Text.Encoding]::UTF8.GetBytes((@{password=$env:MDB_ADMIN_PASSWORD} | ConvertTo-Json -Compress))
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/login' -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{Origin='http://127.0.0.1:8000'} -Body $body -SessionVariable mdbSession
```

通常は上の1行起動とブラウザ操作だけで十分です。日本語ソースをPowerShellで確認する際は `Get-Content -Encoding UTF8` を使い、文字化けして見えた出力をソースに書き戻さないでください。

## 修正版の確認結果

`REPAIR-REPORT.md` に元ZIPの再現結果・変更内容・テスト結果を記載しています。ZIPには元のDBとPythonキャッシュを混入させず、初回起動時にデモDBを生成します。元DBは変更していない元ZIPのバックアップに保存されています。テスト用の `MDB_DEMO_DB` を指定すればデモDBの保存先だけを分離できます（実データ用MDB_DBとは別設定）。

## GitHub Actionsで毎日更新（PCオフで利用可能）

毎日18:07 JST（09:07 UTC）にActions自身がニュースを取得します。Actions画面の「Daily production update → Run workflow」でも実行できます。スケジュールには遅延があり、非活動状態の公開リポジトリでは停止されることがあります。

初回設定:

1. Settings → Secrets and variables → Actions → Secrets に `OPENAI_API_KEY` を登録します。
2. 同画面の Variables に `MDB_AI_LIMIT` を設定します。既定12、新着の先頭から最大この件数を分析します。例: `3`。`0` はAI分析を無効にし、キーも不要です。既存記事は再分析しません。分析失敗も上限枠を消費し、自動再試行はありません。
3. Settings → Pages → Build and deployment → Source を **GitHub Actions** に変更します。公開対象は引き続きmainの `docs`、URLも同じです。ActionsのGITHUB_TOKENによる自動コミットは別のPagesビルドを起動しないため、このworkflowが `docs` を直接デプロイします。
4. Actionsの「Daily production update」でRun workflowを実行して確認します。mainへの書き込みがブランチ保護で拒否される場合は、Actionsの書き込みを許可する設定が必要です。

`python -m app.publish` は `docs/articles.json` を唯一の公開履歴として一時SQLite DBへ復元します。ID・日時・概要・分析を保持し、新着のみ取得・分析します。ローカル本番 `data/news.db` は開きません。更新後は `public/articles.json` と `docs/articles.json` を同じ内容で保存し、workflowがこの2ファイルだけをcommit/pushします。DB、バックアップ、APIキーはコミット・Pages成果物に含めません。取得元とローカルサーバーの機能は従来どおりです。旧Actions用のMDB_URLとMDB_SCHEDULE_TOKENはこのworkflowでは不要です。

全面取得失敗・履歴不正・APIキー未設定（上限が正数）では非ゼロ終了し公開ファイルを維持します。一部のRSSやAIだけが失敗した場合は取得できた記事を公開し、Actionsログに警告と更新結果を表示します。AI失敗記事は未評価のまま保存します。新着0件では更新日時を変えません。公開履歴は1000件で切り捨てず全件保持します（ローカル画面の表示上限は従来どおり1000件）。

並行workflowは直列化し、push時にmainが変更されていれば公開を止めます。最新mainから手動で再実行してください。テストは毎回APIキーを渡す前に実施します。実ニュース更新だけにキーを渡します。Actions更新はローカルPCのDBへ同期されません。

## 保存・バックアップ

DB、パスワード、APIキーをGitへ含めないでください。停止中にDBをコピーするかSQLite backup APIで一貫したバックアップを取得します。サーバーを複数起動しないでください。本番の取得元、AIモデル、HTTPS、バックアップを設定し、スマホ実機で動作確認してから運用を開始してください。

## 公式RSS・カテゴリフィルタ（2026-10-04確認）

[国土交通省の公式RSS案内](https://www.mlit.go.jp/page/rssinfo.html)に掲載された以下の2本を両カテゴリで使います。HTTPSで取得し、XMLとして読み取れることを確認しました。

- プレスリリース: https://www.mlit.go.jp/pressrelease.rdf
- 新着情報: https://www.mlit.go.jp/index.rdf

RSS 1.0（RDF）、Shift_JIS、dc:dateに対応しました。公式フィードの記事リンクはHTTP表記なので、`upgrade_mlit_links: true` のソースに限り `http://www.mlit.go.jp/` をHTTPSへ置き換えます。他ホストや危険なURLは置き換えません。

従来の `name`・`category`・`url` だけの設定もそのまま使えます。任意の `keywords` は空でない文字列配列で、タイトルと配信概要をHTML除去後に検索し、どれか1語を含む記事を採用します。正規表現ではなく部分一致です。フィード全体を検索してから採用上限20件を適用します。フィルタ結果0件は正常（追加0件）。通信失敗・XML不正・設定不正は従来どおり更新失敗に記録します。

水道・インフラ: 水道、上水道、下水道、上下水道、配水管、管路、耐震化、老朽化、更新。
無電柱化: 無電柱化、電線共同溝、共同溝、地中化、電線類地中化。
「更新」等は広い語なので水道以外の情報も含みます。ノイズが多ければ sources.json から広い語を外してください。RSSに概要がない場合はタイトルのみが対象で、リンク先本文は取得しません。RSS掲載期間外の記事を遡って取得する機能はありません。

### 実ニュースで開始

サーバー停止後、新しい展開フォルダで実行してください。既存ニュースを引き継ぐ場合は停止中の旧 `data/news.db` を新フォルダの同じ位置にコピーするか、`MDB_DB` に旧DBの絶対パスを指定します。DBスキーマ変更はありません。ZIPにはDB・キャッシュ・認証情報を含めません。

```powershell
Remove-Item Env:MDB_DEMO -ErrorAction SilentlyContinue
Remove-Item Env:MDB_DEMO_DB -ErrorAction SilentlyContinue
$env:MDB_ADMIN_PASSWORD = '自分で作った16文字以上の十分長いパスワード'
$env:MDB_ORIGIN = 'http://127.0.0.1:8000'
python -m app.main update
python -m app.main serve
```

`Start-Demo.ps1` は従来どおりデモ専用です。今回の検証ではAI API・GitHub Actionsを呼んでいません。新しい取得処理の結果は `SOURCE-UPDATE-REPORT.md` を参照してください。

# KALIDIAコート割 - CLAUDE.md

## プロジェクト概要

バドミントンサークル「KALIDIA」のコート振り分けツール。
単一HTMLファイル（index.html）で完結するバニラJS製Webアプリ。ビルド不要、ブラウザで開くだけで動く。

---

## ファイル構成

```
KALIDIAコート割/
├── index.html          # アプリ本体（CSS・JS全込み）
├── members.txt         # メンバーリスト（編集はここだけ）
├── update_members.py   # members.txt → index.html を同期するスクリプト
├── manifest.json       # PWAマニフェスト
├── service-worker.js   # オフライン対応キャッシュ
└── icon.svg            # アプリアイコン
```

---

## メンバーの更新手順

**名簿の原本は `バドミントン系/members.txt`（フリガナ付き・全アプリ共有）に移行した（2026-07-06）。**

1. `バドミントン系/members.txt` を編集（追加・削除・名前変更）
2. バドミントン系フォルダで以下を実行（3アプリへ一括反映）：
   ```
   python update_members.py
   ```
3. `index.html` をブラウザで開き直す

このフォルダ内の `members.txt` は原本から自動生成されるコピーなので直接編集しない。
（このフォルダの `update_members.py` はローカル単体同期用として残置。通常は原本側を使う）

**members.txt の書き方：**
```
[男性]
大野
小笠原
...

[女性]
浜島
...
```
`#` で始まる行はコメントとして無視される。index.html の RAW 定数は直接編集しない。

---

## コートプリセット（PRESETS定数）

| インデックス | 構成 | 内容 |
|---|---|---|
| 0 | 4コート | コートA〜D 各6名 |
| 1 | 2コート（2面） | コートA・B 各12名 |
| 2 | 混在 | コートA（2面・12名）＋ コートB・C（各6名） |

---

## 主な機能

| 機能 | 説明 |
|---|---|
| コート割り振り | タップ選択 or ドラッグ＆ドロップで参加者をコートへ配置 |
| ペア設定 | コート内でペア登録・色分け表示（6色） |
| ゲスト追加 | 最大2名まで名前を入力して参加可能 |
| 欠席管理 | 欠席者をプールから除外して表示 |
| コートスワップ | コート間でメンバーを入れ替え |
| 状態保存 | 全操作後に自動保存（`render()`末尾で`saveState()`。キー: `badminton_court_state_v1`） |
| Undo | ↩戻すボタンで直前の操作を取り消し（メモリ上スタック最大30件、リロードで消える） |
| バックアップ | コート割＋大会ペアをJSONでエクスポート/インポート（データ管理セクション） |
| 更新通知 | 新バージョンデプロイ時に「更新」トーストを表示→タップで適用＆自動リロード |
| スクリーンショット | html2canvas でコート画面を画像として保存 |
| プリセット切替 | ボタンでコート構成を即切替 |
| 大会ペア管理 | シーズン中固定ペアを永続登録（キー: `badminton_tournament_pairs_v1`）・適用/解除ボタンで一括反映、欠席者を含むペアは自動スキップ |
| PWA対応 | オフライン動作・ホーム画面追加（manifest.json + service-worker.js） |

---

## 使用ライブラリ

- **Noto Sans JP**（Google Fonts） — フォント
- **html2canvas 1.4.1**（CDN） — スクリーンショット機能

外部依存はこの2つのみ。オフライン時はフォントとスクリーンショットが機能しない。

---

## 主要関数一覧

| 関数名 | 役割 |
|---|---|
| `initState()` | 初期状態を生成（メンバー・コートをリセット） |
| `saveState()` | localStorageへ状態を保存（`render()`末尾から自動で呼ばれる） |
| `loadState()` | localStorageから状態を復元（RAWを正とするマージ型：欠席フラグと配置のみ引き継ぐ） |
| `migrateStorageIds()` | 旧連番ID(m1〜)を名前ベースIDへ一括移行（起動時・インポート時） |
| `pushHistory()` / `undoLast()` | Undoスタックへの記録・巻き戻し |
| `exportBackup()` / `importBackup()` | JSONバックアップの書き出し・読み込み |
| `assign()` | 参加者をコートに割り当て |
| `removeFromCourt()` | コートから参加者を外す |
| `applyPreset()` | コートプリセットを切り替え |
| `resetAll()` | 全員をプールに戻す |
| `swapCourts()` | 2コート間でメンバーを入れ替え |
| `makePair() / unpair()` | ペア登録・解除 |
| `markAbsent() / markPresent()` | 欠席・出席の切替 |
| `render()` | 画面全体を再描画 |
| `screenshotCourts()` | コートのスクリーンショットを保存 |
| `toggleCourts()` | サイドバー表示/非表示 |
| `addTournamentPair() / removeTournamentPair()` | 大会ペアの追加・削除（永続） |
| `applyTournamentPairs()` | 出席している大会ペアを一括でコート配置＋ペア化（欠席含むペアはスキップ） |
| `releaseTournamentPairs()` | 適用中の大会ペアをコートから一括解除 |
| `renderTournamentPairs()` | 大会ペアUIの再描画（一覧・選択ドロップダウン） |

---

## 状態管理

```js
let people = [];          // 参加者リスト {id, name, gender, courtId, absent}
let courts = [];          // コートリスト {id, name, max, wide, pids[], pairs[]}
let guests = [];          // ゲスト {id, name, enabled, courtId}
let sel = [];             // タップ選択中の参加者ID（複数可）
let pairSel = null;       // ペア選択中の参加者ID
let tournamentPairs = []; // 大会ペア {id, pidA, pidB} シーズン永続
```

---

## 修正時の注意点

- `render()` 呼び出しで画面全体が再描画される設計のため、DOM直接操作は原則不要
- **メンバーIDは名前ベース**（`M_大野` / `F_濱島`）。同性で同名がいる場合はmembers.txt側で表記を変えること
- **自動保存は`render()`末尾**で行われる。`render()`を通らない状態変更（input系）には個別に`saveState()`が必要
- **変更操作を追加したら`pushHistory()`を入れる**（Undo対象にするため。複数件まとめて1操作＝1スナップショット）
- **SW更新時は`service-worker.js`のCACHEバージョンを必ず上げる**（現在v10）。HTML本体はnetwork-firstなのでデプロイは自動で届き、更新トーストが出る
- ドラッグ処理はPointer Events APIで実装（`pointerdown / pointermove / pointerup`）
- スマホ対応済み（`user-scalable=no`、`touch-action: none`）
- CSSカスタムプロパティ（`--male`, `--female`, `--guest` など）で色を一元管理

# KALIDIAコート割 - CLAUDE.md

## プロジェクト概要

バドミントンサークル「KALIDIA」のコート振り分けツール。
単一HTMLファイル（index.html）で完結するバニラJS製Webアプリ。ビルド不要、ブラウザで開くだけで動く。

---

## ファイル構成

```
KALIDIAコート割/
├── index.html          # アプリ本体（CSS・JS全込み、約66KB）
├── members.txt         # メンバーリスト（編集はここだけ）
└── update_members.py   # members.txt → index.html を同期するスクリプト
```

---

## メンバーの更新手順

1. `members.txt` を編集（追加・削除・名前変更）
2. 以下のコマンドを実行：
   ```
   python update_members.py
   ```
3. `index.html` をブラウザで開き直す

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
| 状態保存 | `localStorage`（キー: `badminton_court_state_v1`）に自動保存 |
| スクリーンショット | html2canvas でコート画面を画像として保存 |
| プリセット切替 | ボタンでコート構成を即切替 |

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
| `saveState()` | localStorageへ状態を保存 |
| `loadState()` | localStorageから状態を復元 |
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

---

## 状態管理

```js
let people = [];    // 参加者リスト {id, name, gender, courtId, absent}
let courts = [];    // コートリスト {id, name, max, wide, pids[], pairs[]}
let guests = [];    // ゲスト {id, name, enabled, courtId}
let sel = [];       // タップ選択中の参加者ID（複数可）
let pairSel = null; // ペア選択中の参加者ID
```

---

## 修正時の注意点

- `render()` 呼び出しで画面全体が再描画される設計のため、DOM直接操作は原則不要
- ドラッグ処理はPointer Events APIで実装（`pointerdown / pointermove / pointerup`）
- スマホ対応済み（`user-scalable=no`、`touch-action: none`）
- CSSカスタムプロパティ（`--male`, `--female`, `--guest` など）で色を一元管理

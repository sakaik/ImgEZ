# ImgEZ

シンプルで使いやすい画像トリミングツール

## 使用方法

### EXEファイルを使用する場合（推奨）

1. [Releases](https://github.com/sakaik/ImgEZ/releases)から最新の`ImgEZ.exe`をダウンロード
2. ダウンロードした`ImgEZ.exe`をダブルクリックして起動
3. 以下の操作が可能です：
   - メニューから「ファイル」→「開く」を選択して画像を開く
   - または画像ファイルをウィンドウにドラッグ＆ドロップ
   - マウスドラッグで範囲を選択
   - 選択範囲の端やコーナーをドラッグしてサイズを調整
   - ダブルクリックまたはCtrl+Tでトリミング実行
   - Ctrl+C: 選択範囲（または全体）をクリップボードにコピー
   - Ctrl+Z: 直前の操作を取り消し
   - Ctrl+R: 最初の状態に戻す
   - Esc: 選択範囲をクリア

### ソースコードから実行する場合（開発者向け）

必要条件:
- Python 3.6以上
- PyQt5

インストール手順:

1. リポジトリをクローン:
```bash
git clone https://github.com/sakaik/ImgEZ.git
cd ImgEZ
```

2. 仮想環境を作成（推奨）:
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. 必要なパッケージをインストール:
```bash
pip install -r requirements.txt
```

4. プログラムを起動:
```bash
python src/ImgEZ.py
```

## 機能

- 画像のトリミング
- クリップボードへのコピー
- 直感的な選択範囲の操作
  - 端をドラッグして縦横個別にリサイズ
  - コーナーをドラッグして縦横同時にリサイズ
- 操作履歴（元に戻す機能）
- ドラッグ＆ドロップでの画像読み込み

## ライセンス

MIT License

## その他

本プロジェクトはCursorを用いて作成しています。


## History
1.1.0 2025/03/30 画像回転対応
1.0.1 2025/03/30 画面レイアウト調整。exifを見て縦型画像に対応
1.0.0 2025/03/30 Initial version
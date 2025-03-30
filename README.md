# ImgEZ

シンプルで使いやすい画像トリミングツール

## 機能

- 画像のトリミング
- クリップボードへのコピー
- 直感的な選択範囲の操作
- 操作履歴（元に戻す機能）
- ドラッグ＆ドロップでの画像読み込み

## 必要条件

- Python 3.6以上
- PyQt5

## インストール方法

1. リポジトリをクローン:
```bash
git clone https://github.com/あなたのユーザー名/ImgEZ.git
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

## 使用方法

1. プログラムを起動:
```bash
python src/ImgEZ.py
```

2. 画像を開く:
   - メニューから「ファイル」→「開く」を選択
   - または画像ファイルをウィンドウにドラッグ＆ドロップ

3. トリミング:
   - マウスドラッグで範囲を選択
   - 選択範囲の端をドラッグしてサイズを調整
   - ダブルクリックまたはCtrl+Tでトリミング実行

4. その他の操作:
   - Ctrl+C: 選択範囲（または全体）をクリップボードにコピー
   - Ctrl+Z: 直前の操作を取り消し
   - Ctrl+R: 最初の状態に戻す
   - Esc: 選択範囲をクリア

## ライセンス

MIT License 
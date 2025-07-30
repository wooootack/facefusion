# FaceFusion pipx インストールガイド

このドキュメントでは、FaceFusionをpipxを使用してインストールする手順を説明します。

## 前提条件

- Python 3.10以上がインストールされていること
- pipxがインストールされていること
- FFmpegがインストールされていること（動画処理に必要）

### pipxのインストール

```bash
# macOS/Linux
pip install pipx
pipx ensurepath

# Windows
pip install pipx
pipx ensurepath
```

### FFmpegのインストール

FaceFusionは動画処理にFFmpegが必要です。

**macOS:**
```bash
# Homebrewを使用（推奨）
brew install ffmpeg

# または condaを使用
conda install ffmpeg
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

**Windows:**
```bash
# Chocolateyを使用
choco install ffmpeg

# または公式サイトからダウンロード
# https://ffmpeg.org/download.html
```

**インストール確認:**
```bash
ffmpeg -version
```

## 基本的なインストール手順

1. FaceFusionのリポジトリをクローンまたはダウンロード
2. プロジェクトディレクトリに移動
3. pipxでインストール

```bash
git clone https://github.com/facefusion/facefusion.git
cd facefusion
pipx install .
```

### インストール後の確認

インストールが成功したら、以下で確認できます：

```bash
# コマンドが利用可能か確認
facefusion --help

# インストールされたパッケージの確認
pipx list
```

## トラブルシューティング

### Apple Silicon (M1/M2/M3) でのエラー

**エラー内容:**
```
clang++: error: unsupported option '-msse4.1' for target 'arm64-apple-darwin24.5.0'
```

**解決方法:**

1. **事前にonnxをインストール**
   ```bash
   pip install onnx onnxruntime
   pipx install .
   ```

2. **Rosetta 2を使用（x86_64エミュレーション）**
   ```bash
   arch -x86_64 pipx install .
   ```

3. **condaを使用**
   ```bash
   conda install onnx onnxruntime
   pipx install .
   ```

### その他の一般的なエラー

**FFmpegがインストールされていない:**
```
[FACEFUSION.CORE] FFMpeg is not installed
```

解決方法：
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg  # CentOS/RHEL

# Windows
choco install ffmpeg
```

**依存関係の競合:**
```bash
pip install --upgrade pip setuptools wheel
pipx install .
```

**権限エラー:**
```bash
# macOS/Linux
sudo pipx install .

# または、ユーザーディレクトリにインストール
pipx install --user .
```

## インストール後の使用方法

インストールが成功すると、以下のコマンドでFaceFusionを起動できます：

```bash
facefusion
```

### コマンドラインオプション

```bash
# 基本的な使用方法
facefusion --help

# ソースとターゲットを指定
facefusion --source path/to/source.jpg --target path/to/target.mp4

# UIを起動
facefusion --ui
```

### 初回セットアップ

初回使用時は、必要なモデルファイルをダウンロードしてください：

```bash
# 必要なモデルをダウンロード
facefusion force-download
```

### 使用例

```bash
# 基本的な顔交換
facefusion run --source source.jpg --target target.mp4 --output output.mp4

# バッチ処理
facefusion batch-run --source source.jpg --target target_folder --output output_folder

# ベンチマーク実行
facefusion benchmark
```

## アンインストール

```bash
pipx uninstall facefusion
```

## 更新

```bash
pipx upgrade facefusion
```

## 環境別の注意事項

### macOS
- Apple Siliconでは、onnxの互換性問題が発生する可能性があります
- 上記のトラブルシューティングを参照してください

### Linux
- 一般的に問題なくインストールできます
- GPUを使用する場合は、CUDAの設定が必要な場合があります

### Windows
- WSL2の使用を推奨します
- 直接Windowsで使用する場合は、Visual Studio Build Toolsが必要な場合があります

## 開発環境での使用

開発中に変更を反映させたい場合：

```bash
pipx install --editable .
```

これにより、ソースコードの変更が即座に反映されます。

## ログの確認

インストール時にエラーが発生した場合、詳細なログを確認できます：

```bash
# pipxのログディレクトリ
ls ~/.local/pipx/logs/

# 最新のエラーログを確認
cat ~/.local/pipx/logs/cmd_$(date +%Y-%m-%d)_*.log
```

## サポート

問題が解決しない場合は、以下を確認してください：

1. Pythonのバージョン（3.10以上）
2. pipxのバージョン
3. システムのアーキテクチャ（x86_64/arm64）
4. 利用可能なメモリとディスク容量

詳細なエラーログと共に、GitHubのIssuesで報告してください。

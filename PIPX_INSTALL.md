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
facefusion run --source source.jpg --target target.mp4 --output-path output.mp4

# バッチ処理
facefusion batch-run --source source.jpg --target target_folder --output-path output_folder

# ベンチマーク実行
facefusion benchmark
```

## 最適設定コマンド（女性の顔交換向け）

### 完全版（すべての最適設定）
```bash
facefusion run --source source_female.jpg --target target_video.mp4 --output-path output_video.mp4 --face-detector-model many --face-detector-size 640x640 --face-detector-score 0.7 --face-detector-angles 0 90 180 270 --face-landmarker-model many --face-landmarker-score 0.8 --face-selector-mode reference --face-selector-order best-worst --face-selector-gender female --face-selector-age-start 18 --face-selector-age-end 50 --reference-face-distance 0.6 --face-mask-types box occlusion area --face-mask-areas upper-face lower-face --face-mask-regions skin left-eye right-eye mouth --face-mask-blur 0.3 --face-mask-padding 10 10 10 10 --face-swapper-model inswapper_128 --face-swapper-pixel-boost 1024x1024 --face-enhancer-model gfpgan_1.4 --face-enhancer-blend 80 --face-enhancer-weight 1.0 --frame-enhancer-model ultra_sharp_x4 --frame-enhancer-blend 60 --output-video-encoder libx264 --output-video-preset slow --output-video-quality 95 --execution-providers cuda cpu --execution-thread-count 4 --execution-queue-count 2
```

### 簡略版（基本的な設定）
```bash
facefusion run --source source_female.jpg --target target_video.mp4 --output-path output_video.mp4 --face-detector-model many --face-detector-score 0.7 --face-selector-mode reference --face-swapper-model inswapper_128 --face-swapper-pixel-boost 1024x1024 --face-enhancer-model gfpgan_1.4 --output-video-quality 95
```

### 高品質版（品質重視）
```bash
facefusion run --source source_female.jpg --target target_video.mp4 --output-path output_video.mp4 --face-detector-model many --face-detector-score 0.7 --face-selector-mode reference --face-swapper-model inswapper_128 --face-swapper-pixel-boost 1024x1024 --face-enhancer-model gfpgan_1.4 --face-enhancer-blend 80 --face-enhancer-weight 1.0 --frame-enhancer-model ultra_sharp_x4 --output-video-quality 95 --output-video-preset slow
```

### 高速版（処理速度重視）
```bash
facefusion run --source source_female.jpg --target target_video.mp4 --output-path output_video.mp4 --face-detector-model yolo_face --face-detector-score 0.5 --face-swapper-model inswapper_128 --face-swapper-pixel-boost 512x512 --output-video-quality 85 --output-video-preset fast --execution-thread-count 8
```

## 主要オプション説明

### 顔検出設定
- `--face-detector-model many`: 複数モデルを組み合わせて高精度な顔検出
- `--face-detector-size 640x640`: 高解像度で詳細な顔の特徴を捉える
- `--face-detector-score 0.7`: 誤検出を減らしつつ、確実に顔を検出
- `--face-detector-angles 0 90 180 270`: 様々な角度からの顔を検出

### 顔選択設定
- `--face-selector-mode reference`: 参照顔ベースで特定の顔のみを選択
- `--face-selector-gender female`: 女性の顔のみを対象
- `--face-selector-age-start 18 --face-selector-age-end 50`: 年齢範囲を指定
- `--reference-face-distance 0.6`: 類似度の高い顔のみを選択

### マスク設定
- `--face-mask-types box occlusion area`: 基本的な顔領域、前面物体、特定部分をマスク
- `--face-mask-areas upper-face lower-face`: 顔の上半分と下半分をマスク
- `--face-mask-regions skin left-eye right-eye mouth`: 重要な顔の部分を正確にマスク
- `--face-mask-blur 0.3`: 自然な境界線を作成
- `--face-mask-padding 10 10 10 10`: 髪の毛やアクセサリーを含む適切な余白

### 顔交換設定
- `--face-swapper-model inswapper_128`: 最高精度の顔交換モデル
- `--face-swapper-pixel-boost 1024x1024`: 高解像度で細かい特徴を保持

### 品質向上設定
- `--face-enhancer-model gfpgan_1.4`: 最高品質の顔エンハンサー
- `--face-enhancer-blend 80`: 元の顔の特徴を保持しつつ品質向上
- `--face-enhancer-weight 1.0`: 最大の品質向上効果
- `--frame-enhancer-model ultra_sharp_x4`: 動画全体の品質向上

### 出力設定
- `--output-video-encoder libx264`: 高品質な動画エンコーダー
- `--output-video-preset slow`: 最高品質のエンコード
- `--output-video-quality 95`: 最高品質の出力

### 実行設定
- `--execution-providers cuda cpu`: GPU優先で処理
- `--execution-thread-count 4`: 効率的な並列処理
- `--execution-queue-count 2`: メモリ使用量と処理速度のバランス

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

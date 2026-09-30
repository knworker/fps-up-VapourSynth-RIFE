# fps-up-VapourSynth-RIFE

🎬 **基於 VapourSynth + RIFE 深度學習架構的即時電影/動畫補幀腳本 (Windows)**

專為 **MPC-BE**、**PotPlayer** 與 **AviSynth Filter** 設計，實現 24fps / 25fps / 30fps 視訊即時補幀至 48fps、60fps、120fps、144fps 或螢幕原生高刷新率，杜絕時鐘抖動與畫面撕裂。

---

## 🌟 核心特點

1. **防快轉機制 (Anti-Fast-Forward)**：清除舊渲染器殘留的 `_AbsoluteTime` 與時長屬性，重新封裝精準分數幀率（AssumeFPS），徹底消除電視或高刷螢幕上的 Catch-up 狂暴快轉。
2. **色彩與 HDR 完整保真**：完整維護 YUV ↔ RGB 矩陣轉換、`_SAR` 像素長寬比與完整 HDR 元數據（Mastering Display Primaries / Luminance / MaxCLL）。
3. **動態螢幕刷新率適配 (AUTO 模式)**：自動調用 Windows API 獲取當前螢幕刷新率，計算最佳無抖動整數倍率（如 120Hz 下 5x、144Hz 下 3x、240Hz 下 5x）。
4. **雙版本架構**：
   - `interpolate_auto.vpy`：旗艦全自動版，包含動態螢幕同步、GPU 負載保護、TRT 自動降級回退與可選 MVTools 混合管線。
   - `interpolate_base.vpy`：輕量精準版，預設目標模式（48 / 60 / 120 / 144 fps），極簡穩定，秒開秒播。
5. **TensorRT 與 CUDA 雙引擎**：支援 TensorRT 核心加速大幅降低 GPU 功耗，亦支援純 CUDA 模式秒開秒播。

---

## 📁 專案檔案結構

- [`interpolate_auto.vpy`](interpolate_auto.vpy)：旗艦自動適配即時補幀腳本（支援螢幕刷新率動態適配、HDR 保真、GPU 負載保護與 MVTools 混合補幀）。
- [`interpolate_base.vpy`](interpolate_base.vpy)：輕量精準即時補幀腳本（支援固定 48/60/120/144 模式快速切換）。
- [`.gitignore`](.gitignore)：針對 Python、PyTorch、TensorRT 模型快取、影片暫存與 Synology Drive 同步標記之忽略規則。

---

## 🛠️ 環境需求與安裝指南

> [!IMPORTANT]
> 請使用 **Python 3.10 ~ 3.12（推薦 64-bit 3.12）**。切勿使用 Python 3.13+，因為 PyTorch 與 TensorRT 的 Windows 預編譯輪子尚未完全適配。

### 1. 基礎環境
1. **Python 3.12 (64-bit)**：[官網下載](https://www.python.org/downloads/release/python-3128/)（安裝時務必勾選 `Add python.exe to PATH`）。
2. **VapourSynth R68+ (64-bit)**：[GitHub Releases 下載](https://github.com/vapoursynth/vapoursynth/releases)。
3. **AviSynth Filter**：[GitHub Releases 下載](https://github.com/CrendKing/avisynth_filter/releases)。
   - 解壓縮至固定目錄（例如 `C:\Program Files\AviSynthFilter`）。
   - 以系統管理員身分執行 `install.cmd` 完成 DirectShow COM 元件註冊。

### 2. 安裝 AI 補幀引擎 (PyTorch + CUDA + vsrife)
打開命令提示字元 (CMD) 或 PowerShell，依序執行：

```powershell
# 1. 升級基礎封裝工具
pip install -U packaging setuptools wheel vsrepo

# 2. 安裝 PyTorch (CUDA 12.6)
pip install -U torch torchvision --extra-index-url https://download.pytorch.org/whl/cu126

# 3. 安裝 vsrife
pip install -U vsrife
```

### 3. 可選功能套件
- **TensorRT 加速（大幅降低顯卡推論功耗）**：
  ```powershell
  pip install -U tensorrt torch_tensorrt --extra-index-url https://download.pytorch.org/whl/cu126 --extra-index-url https://pypi.nvidia.com
  ```
- **MVTools 光流外掛（可選 CPU 混合補滿高刷）**：
  ```powershell
  vsrepo install mvtools
  ```

---

## 📺 播放器掛載教學 (以 MPC-BE 為例)

1. 打開 **MPC-BE**，進入 `檢視` → `選項` → `外部濾鏡`。
2. 點擊 `新增濾鏡`，在清單中找到並選取 `AviSynth Filter`。
3. 將其設定為 **偏好 (Prefer)**。
4. 雙擊清單中的 `AviSynth Filter` 進入設定視窗：
   - **Script Type**：選擇 `VapourSynth`。
   - **Script Path / Inline Script**：指向本專案的 `interpolate_auto.vpy` 或 `interpolate_base.vpy`。
5. 點擊確定並重啟播放器即可開始體驗即時補幀。

---

## ⚙️ 腳本參數調整說明

### `interpolate_auto.vpy`
- `RUN_MODE`: `"AUTO"`（自動獲取螢幕刷新率並以整數倍無抖動對齊）或 `"FIXED"`（固定倍率）。
- `MAX_FACTOR`: AUTO 模式下的最大倍率上限（預設 `2`，保護顯卡負載；如需 120Hz/240Hz 滿幀可調高至 `5`）。
- `MODEL`: 預設 `"4.25"`（抗撕裂能力優異，首次載入會自動下載權重）。
- `USE_TRT`: `True` 啟用 TensorRT 加速；`False` 使用純 CUDA 推論（秒開秒播）。
- `ENABLE_SCENE_DETECT`: 場景變更防撕裂檢測（預設 `False` 即可流暢秒開，無撕裂）。

### `interpolate_base.vpy`
- `TARGET_MODE`:
  - `"60"`：24fps 補 2.5 倍至 60fps（低溫適配 60Hz 電視與螢幕）。
  - `"48"`：24fps 補 2.0 倍至 48fps（極低算力，適合 144Hz / 240Hz 螢幕）。
  - `"120"`：24fps 補 5.0 倍至 120fps（適配 120Hz / 240Hz 螢幕）。
  - `"144"`：24fps 補 6.0 倍至 144fps（適配 144Hz 電競螢幕）。

---

## 📄 授權條款

本專案採 MIT 授權條款開源。
各相關模型與第三方依賴庫（RIFE、VapourSynth、PyTorch、TensorRT）之版權歸屬原作者所有。

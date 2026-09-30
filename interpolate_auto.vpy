# -*- coding: utf-8 -*-
"""VapourSynth RIFE 即時補幀腳本 v2.3

適用環境: Windows + MPC-BE / PotPlayer + AviSynth Filter + VapourSynth
優化特性:
  1. 徹底防快轉：清除舊渲染器時間戳，以約分精確幀率重置 AssumeFPS。
  2. 穩定直通：移除 sys.exit(0)，全面採用 if-else 結構避免 DirectShow 崩潰。
  3. 色彩保真：完整維護 YUV↔RGB 矩陣方向、_SAR 像素比、HDR 元數據。
  4. 智能頻率：AUTO 螢幕同步 + FIXED 固定倍率，MAX_FACTOR GPU 預算限制。
  5. 混合補幀：RIFE (GPU) + MVTools (CPU) 雙層管線，低負載高絲滑。
  6. 效能優化：FrameEval 延遲色彩偵測、合併 resize、TRT 自動退回。

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                         依賴套件安裝指南                                 ║
# ╠════════════════════════════════════════════════════════════════════════════╣
# ║                                                                          ║
# ║  【必要】基礎環境                                                        ║
# ║  ────────────────────────────────────────────────────────────────         ║
# ║  ① Python 3.12（64-bit 推薦）                                            ║
# ║     https://www.python.org/downloads/release/python-3128/                ║
# ║     ⚠ 請安裝 Python 3.10 ~ 3.12（64-bit）。                              ║
# ║     ⚠ 切勿安裝 Python 3.13 或 3.14+！PyTorch / TensorRT 尚未適配 Windows   ║
# ║        預編譯輪子，會導致 pip 安裝出現「No matching distribution」錯誤。 ║
# ║     ⚠ 安裝時務必勾選「Add python.exe to PATH」                           ║
# ║                                                                          ║
# ║  ② VapourSynth R68+ / R69+ / R70+（64-bit）                              ║
# ║     https://github.com/vapoursynth/vapoursynth/releases                  ║
# ║     ⚠ 請確認 VapourSynth 版本與 Python 3.12 相容（通常官方 installer 會  ║
# ║        自動綁定對應的 Python 環境）。                                    ║
# ║     確認方式：python -c "import vapoursynth as vs; print(vs.core.version())"║
# ║                                                                          ║
# ║  ③ avisynth_filter（DirectShow 橋接濾鏡）                               ║
# ║     https://github.com/CrendKing/avisynth_filter/releases                ║
# ║     安裝與播放器掛載步驟：                                               ║
# ║       a. 解壓縮至固定目錄（例：C:\Program Files\AviSynthFilter）         ║
# ║       b. 右鍵 install.cmd →「以系統管理員身分執行」完成 COM 元件註冊     ║
# ║       c. 打開 MPC-BE →「檢視」→「選項」→「外部濾鏡」                     ║
# ║       d. 點擊「新增濾鏡」→ 在清單中選擇「AviSynth Filter」               ║
# ║       e. 在右側設為「偏好 (Prefer)」                                     ║
# ║       f. 雙擊該濾鏡進入屬性頁面，設定 Script Type 為「VapourSynth」       ║
# ║                                                                          ║
# ║  【必要】AI 補幀引擎 (PyTorch + CUDA + vsrife)                           ║
# ║  ────────────────────────────────────────────────────────────────         ║
# ║  ④ PyTorch (CUDA 12.6) + vsrife                                          ║
# ║     pip install -U packaging setuptools wheel                            ║
# ║     pip install -U torch torchvision --extra-index-url                   ║
# ║         https://download.pytorch.org/whl/cu126                           ║
# ║     pip install -U vsrife                                                ║
# ║     確認方式：python -c "import torch; print(torch.cuda.is_available(),   ║
# ║                          torch.cuda.get_device_name(0))"                 ║
# ║                                                                          ║
# ║  【可選】TensorRT 加速推論（USE_TRT = True 時需要）                      ║
# ║  ────────────────────────────────────────────────────────────────         ║
# ║  ⑤ TensorRT + Torch-TensorRT                                            ║
# ║     pip install -U tensorrt torch_tensorrt --extra-index-url             ║
# ║         https://download.pytorch.org/whl/cu126 --extra-index-url         ║
# ║         https://pypi.nvidia.com                                          ║
# ║     ⚠ 需安裝 tensorrt 與 torch_tensorrt 兩個套件。                        ║
# ║     ⚠ 首次啟動某解析度時會自動編譯 TRT 引擎（約需 1-3 分鐘）。           ║
# ║     ⚠ 若不想編譯或安裝複雜，設 USE_TRT = False 即可退回純 CUDA 模式，    ║
# ║        RTX 40/50 系列純 CUDA 即可達到全即時流暢補幀且秒開秒播。         ║
# ║                                                                          ║
# ║  【可選】MVTools 光流補幀（FILL_MODE = "MVTOOLS" 時需要）                ║
# ║  ────────────────────────────────────────────────────────────────         ║
# ║  ⑥ MVTools 外掛（CPU 混合補幀到 120/144/240Hz 螢幕滿幀）                 ║
# ║     方法 A（推薦）：                                                     ║
# ║       pip install vsrepo                                                 ║
# ║       vsrepo install mvtools                                             ║
# ║     方法 B（手動）：                                                     ║
# ║       下載: https://github.com/dubhater/vapoursynth-mvtools/releases     ║
# ║       將 mvtools.dll 放入 %APPDATA%\VapourSynth\plugins64                ║
# ║     ⚠ 若未安裝，腳本會自動跳過 MVTools 改用螢幕整數倍重複顯示（零負擔）  ║
# ║                                                                          ║
# ║  【快速安裝指令（複製貼上至命令提示字元 CMD）】                          ║
# ║  ────────────────────────────────────────────────────────────────         ║
# ║  [步驟 1: 基礎補幀套件 (純 CUDA 秒開秒播，強烈推薦)]                     ║
# ║  pip install -U packaging setuptools wheel vsrepo vsrife                 ║
# ║  pip install -U torch torchvision --extra-index-url https://download.pytorch.org/whl/cu126
# ║                                                                          ║
# ║  [步驟 2: 可選加裝 TensorRT (極致降低 GPU 負載)]                         ║
# ║  pip install -U tensorrt torch_tensorrt --extra-index-url https://download.pytorch.org/whl/cu126 --extra-index-url https://pypi.nvidia.com
# ║                                                                          ║
# ║  [步驟 3: 可選安裝 MVTools (CPU 混合補滿高刷)]                           ║
# ║  vsrepo install mvtools                                                  ║
# ║                                                                          ║
# ╚════════════════════════════════════════════════════════════════════════════╝
"""

import ctypes
from ctypes import wintypes
import math
import os
import vapoursynth as vs
from vapoursynth import core

# ==============================================================================
# 依賴套件執行期檢測 (Dependency Runtime Checks)
# ==============================================================================
_WARNINGS = []  # 收集所有警告，最後統一顯示在畫面上

# [必要] vsrife — AI 補幀核心
try:
  from vsrife import rife
except ImportError:
  raise RuntimeError(
      "【致命錯誤】未安裝 vsrife 模組！\n"
      "請在命令列執行：\n"
      "  pip install -U torch torchvision --extra-index-url "
      "https://download.pytorch.org/whl/cu126\n"
      "  pip install -U vsrife\n"
      "詳細說明請參閱本腳本開頭的安裝指南。"
  )

# [可選] MVTools / MVUtensils — CPU 光流補幀
_HAS_MVTOOLS = hasattr(core, "mvu") or hasattr(core, "mv")

# [可選] TensorRT — GPU 加速推論
_HAS_TRT = False
try:
  import torch_tensorrt  # noqa: F401
  _HAS_TRT = True
except ImportError:
  pass

# ==============================================================================
# 0. 使用者配置區 (User Configuration)
# ==============================================================================
# 運作模式: "AUTO" (根據螢幕刷新率動態適配) | "FIXED" (使用固定倍率)
RUN_MODE = "AUTO"

# FIXED 模式倍率設定: 可為整數或分數 Tuple，例如 2、(5, 2) 代表 2.5 倍
FIXED_FPS_FACTOR = 2

# RIFE 最大補幀倍率上限 (GPU 負載保護，AUTO 模式生效)
#   AUTO 模式僅使用整數倍率（2, 3, 4, 5...），確保：
#     - 每個原始幀都被直接復用（零浪費推論，效率最高）
#     - 輸出幀率能被螢幕刷新率整除（零抖動、零聲音 Lag）
#   會從 MAX_FACTOR 往下搜尋最大的合法整數倍率。
#   常見匹配範例 (24fps 影片)：
#     120Hz: x5=120fps(1:1) ← 需 MAX_FACTOR≥5
#     144Hz: x3=72fps(2:2), x2=48fps(3:3) ← MAX_FACTOR=3 即可
#     240Hz: x5=120fps(2:2), x2=48fps(5:5) ← MAX_FACTOR=5 即可
#   設為 0 或 None 表示不限制（AUTO 會搜尋到 10 倍）
MAX_FACTOR = 2

# 高幀率直通保護: 原生幀率 >= 48fps 時不進行補幀，直接直通輸出
BYPASS_HIGH_FPS = True
HIGH_FPS_THRESHOLD = 48.0

# RIFE 模型與推論參數
MODEL = "4.25"  # 推薦: "4.25", "4.25_lite", "4.18" 等
USE_TRT = True  # 是否啟用 TensorRT 加速 (設為 False 可免編譯秒開，RTX 5070 Ti 純 CUDA 效能已極佳)
RIFE_SCALE = 1.0  # 推論縮放，若顯卡負載過高可設為 0.5

# 場景切換防撕裂偵測 (vsrife v5.6+ 內建支援，預設即可安全啟用)
ENABLE_SCENE_DETECT = False
SC_THRESHOLD = 0.15  # 場景變更靈敏度 (vsrife v5.6+ 預設值即為 0.15)

# 4K / 超高解析度降採樣 (避免即時補幀顯存溢出)
AUTO_DOWNSCALE_4K = False
MAX_WIDTH = 1920
MAX_HEIGHT = 1080

# 混合補幀模式：RIFE 之後用輕量級方法填充剩餘幀到螢幕滿幀
#   "NONE"    : 不額外補幀，由螢幕重複顯示（最省 GPU/CPU，強烈推薦！）
#               在 240Hz 螢幕上，48fps 恰好為整數 5 倍 (5:5 節奏)，完全無抖動、零延遲
#   "MVTOOLS" : 用 MVTools 光流補幀（需 API 4 相容版本，不建議在 240Hz 啟用以防 CPU 算力爆滿卡死）
#   "BLEND"   : 簡易幀混合（最省效能但有殘影，適合極低端硬體）
FILL_MODE = "NONE"

# FILL 目標幀率：0 = 自動使用螢幕 Hz; 或手動指定如 120, 144
FILL_TARGET_HZ = 0

# MVTools 調整參數 (進階用戶)
MV_BLKSIZE = 16    # 運動區塊大小: 8=精細但慢, 16=平衡, 32=快但粗
MV_OVERLAP = 8     # 區塊重疊像素: 建議為 blksize/2
MV_SEARCH = 3      # 搜尋演算法: 3=Hexagonal(推薦), 4=UMH(最精確)
MV_PEL = 2         # 運動向量精度: 1=整像素(快), 2=半像素(推薦), 4=1/4像素(慢)

# 系統資源配置
core.num_threads = 4  # CPU 餵圖執行緒數
core.max_cache_size = 4096  # 分配 4GB 記憶體快取

# 預設回退螢幕刷新率 (當 Windows API 探測失敗時使用)
FALLBACK_SCREEN_HZ = 60


# ==============================================================================
# 1. 螢幕刷新率探測模組 (Windows GDI API — ctypes 零依賴)
# ==============================================================================
# 將 DEVMODEW 定義在模組層級，避免每次呼叫重新定義
class _DEVMODEW(ctypes.Structure):
  _fields_ = [
      ("dmDeviceName", wintypes.WCHAR * 32),
      ("dmSpecVersion", wintypes.WORD),
      ("dmDriverVersion", wintypes.WORD),
      ("dmSize", wintypes.WORD),
      ("dmDriverExtra", wintypes.WORD),
      ("dmFields", wintypes.DWORD),
      ("dmOrientation", wintypes.SHORT),
      ("dmPaperSize", wintypes.SHORT),
      ("dmPaperLength", wintypes.SHORT),
      ("dmPaperWidth", wintypes.SHORT),
      ("dmScale", wintypes.SHORT),
      ("dmCopies", wintypes.SHORT),
      ("dmDefaultSource", wintypes.SHORT),
      ("dmPrintQuality", wintypes.SHORT),
      ("dmColor", wintypes.SHORT),
      ("dmDuplex", wintypes.SHORT),
      ("dmYResolution", wintypes.SHORT),
      ("dmTTOption", wintypes.SHORT),
      ("dmCollate", wintypes.SHORT),
      ("dmFormName", wintypes.WCHAR * 32),
      ("dmLogPixels", wintypes.WORD),
      ("dmBitsPerPel", wintypes.DWORD),
      ("dmPelsWidth", wintypes.DWORD),
      ("dmPelsHeight", wintypes.DWORD),
      ("dmDisplayFlags", wintypes.DWORD),
      ("dmDisplayFrequency", wintypes.DWORD),
      ("dmICMMethod", wintypes.DWORD),
      ("dmICMIntent", wintypes.DWORD),
      ("dmMediaType", wintypes.DWORD),
      ("dmDitherType", wintypes.DWORD),
      ("dmReserved1", wintypes.DWORD),
      ("dmReserved2", wintypes.DWORD),
      ("dmPanningWidth", wintypes.DWORD),
      ("dmPanningHeight", wintypes.DWORD),
  ]


def get_primary_screen_refresh_rate() -> int:
  """透過 Windows Win32 API 取得主螢幕即時垂直刷新率 (Hz)"""
  try:
    devmode = _DEVMODEW()
    devmode.dmSize = ctypes.sizeof(_DEVMODEW)
    if ctypes.windll.user32.EnumDisplaySettingsW(
        None, -1, ctypes.byref(devmode)
    ):
      hz = int(devmode.dmDisplayFrequency)
      if hz > 0:
        return hz
  except Exception:
    pass
  return FALLBACK_SCREEN_HZ


# ==============================================================================
# 2. 輸入視訊驗證與安全常態化
# ==============================================================================
# avisynth_filter 注入 VpsFilterSource；PotPlayer 注入 video_in
if "VpsFilterSource" in globals():
  clip = VpsFilterSource
elif "video_in" in globals():
  clip = video_in
elif "clip" not in globals():
  raise RuntimeError(
      "未檢測到輸入視訊 clip，本腳本需在 AviSynth Filter / VapourSynth Filter 下運行。"
  )

# 格式常態化 (處理 Variable Format)
if clip.format is not None:
  orig_format_id = clip.format.id
else:
  clip = core.resize.Bicubic(clip, format=vs.YUV420P8)
  orig_format_id = vs.YUV420P8

# 幀率安全檢查 (處理 VFR 或無幀率情況)
if clip.fps_den > 0:
  fps_in = clip.fps_num / clip.fps_den
else:
  fps_in = 23.976
  clip = core.std.AssumeFPS(clip, fpsnum=24000, fpsden=1001)

orig_width = clip.width
orig_height = clip.height
screen_hz = get_primary_screen_refresh_rate()


# ==============================================================================
# 3. 自適應整數倍率計算 (Adaptive Integer Factor Computation)
# ==============================================================================
# 設計原則：
#   1. 僅使用整數倍率（2, 3, 4, 5...），確保每個原始幀都被直接復用（零浪費推論）。
#   2. 輸出幀率必須能被螢幕刷新率整除（screen_hz / output_fps ≈ 正整數），
#      確保螢幕以均勻節奏顯示（零抖動、零聲音 Lag）。
#   3. 在 MAX_FACTOR 預算內選取最高整數倍率，優先最大化絲滑度。
#   4. 若無匹配倍率，顯示建議的螢幕刷新率或 MAX_FACTOR 設定。


def compute_factor(
    fps_in: float, run_mode: str, screen_hz: int
) -> tuple[int, int, float]:
  """計算補幀所需的 factor_num, factor_den 以及 target_fps

  AUTO 模式限定整數倍率，同時確保：
    - 每個原始幀都被直接復用（整數倍 = 零浪費推論）
    - 輸出幀率能被螢幕刷新率整除（零抖動、零聲音 Lag）

  回傳: (factor_num, factor_den, target_fps)
    factor_den 在整數倍率下固定為 1。
  """
  # --- FIXED 模式：使用者手動指定倍率 ---
  if run_mode == "FIXED":
    if isinstance(FIXED_FPS_FACTOR, tuple):
      fn, fd = FIXED_FPS_FACTOR
    else:
      fn, fd = int(FIXED_FPS_FACTOR), 1
    t_fps = fps_in * fn / fd
    return fn, fd, t_fps

  # --- AUTO 模式：自適應整數倍率 ---
  max_f = int(MAX_FACTOR) if (MAX_FACTOR and MAX_FACTOR > 0) else 10

  best_factor = None
  best_repeat = None

  # 從最大倍率往下搜尋，找到第一個能整除螢幕 Hz 的整數倍率
  for f in range(max_f, 1, -1):
    output_fps = fps_in * f
    # 輸出幀率不應超過螢幕刷新率 (容許 NTSC 0.1% 誤差)
    if output_fps > screen_hz * 1.01:
      continue
    ratio = screen_hz / output_fps
    nearest_int = round(ratio)
    # 檢查是否接近正整數 (容許 NTSC 23.976 vs 24.000 的 0.1% 誤差)
    if nearest_int >= 1 and abs(ratio - nearest_int) < 0.02:
      best_factor = f
      best_repeat = nearest_int
      break

  if best_factor is not None:
    target_fps = fps_in * best_factor
    if best_repeat == 1:
      cadence_desc = "1:1 fullframe"
    else:
      cadence_desc = f"{best_repeat}:{best_repeat} repeat"
    _WARNINGS.append(
        f"[AUTO] x{best_factor} = {target_fps:.1f}fps on {screen_hz}Hz "
        f"({cadence_desc}, integer factor, all originals reused)"
    )
    return best_factor, 1, target_fps

  # --- 無法匹配：生成詳細建議 ---
  warn_parts = [
      f"[WARNING] No integer factor 2~{max_f} evenly divides {screen_hz}Hz "
      f"for {fps_in:.3f}fps."
  ]

  # 建議 1：超過 MAX_FACTOR 但能匹配當前螢幕的倍率
  for f in range(max_f + 1, 11):
    output_fps = fps_in * f
    if output_fps > screen_hz * 1.01:
      continue
    ratio = screen_hz / output_fps
    nearest_int = round(ratio)
    if nearest_int >= 1 and abs(ratio - nearest_int) < 0.02:
      warn_parts.append(
          f"Suggest: MAX_FACTOR={f} -> x{f}={output_fps:.0f}fps "
          f"({nearest_int}:{nearest_int} on {screen_hz}Hz)."
      )
      break

  # 建議 2：若要使用 MAX_FACTOR，螢幕應切換到哪個 Hz
  max_f_fps = fps_in * max_f
  suggested_hz = []
  for repeat in range(1, 11):
    hz = round(max_f_fps * repeat)
    if 48 <= hz <= 480 and hz != screen_hz:
      suggested_hz.append(f"{hz}Hz")
  if suggested_hz:
    warn_parts.append(
        f"Or for x{max_f}({max_f_fps:.0f}fps), switch screen to: "
        + ", ".join(suggested_hz[:5]) + "."
    )

  _WARNINGS.append(" ".join(warn_parts))

  # 退回使用最大倍率（有抖動風險但仍可播放）
  fallback_fps = fps_in * max_f
  _WARNINGS.append(
      f"[FALLBACK] Using x{max_f} = {fallback_fps:.1f}fps "
      f"(screen {screen_hz}Hz / {fallback_fps:.1f}fps = "
      f"{screen_hz / fallback_fps:.2f}, not integer -> possible judder)"
  )
  return max_f, 1, fallback_fps


run_mode_upper = RUN_MODE.upper()
factor_num, factor_den, target_fps = compute_factor(
    fps_in, run_mode_upper, screen_hz
)


# ==============================================================================
# 4. 決策分支：直通判斷 vs 補幀管線 (避免 sys.exit)
# ==============================================================================
def _ensure_mod2(val: float) -> int:
  """強制確保解析度數值為偶數 (mod 2)，避免色度取樣錯誤"""
  iv = int(round(val))
  return iv if (iv % 2 == 0) else (iv + 1)


# 直通判定條件:
# 1. 幀率本身已達高幀率標準 (>=48fps)，且開啟了保護開關
# 2. 輸入幀率已達到或超越目標幀率 (例如倍率為 1 或目標幀率接近輸入)
should_bypass = False
if BYPASS_HIGH_FPS and (fps_in >= HIGH_FPS_THRESHOLD):
  should_bypass = True
elif fps_in >= (target_fps - 0.5):
  should_bypass = True

if should_bypass:
  # 直通輸出：不額外處理，安全保持原視訊
  clip.set_output()

else:
  # ============================================================================
  # 5. 補幀主流程
  # ============================================================================

  # --- 5.1 解析度控制 (4K 自動降頻以保障流暢即時渲染) ---
  is_downscaled = False
  if AUTO_DOWNSCALE_4K and (
      orig_width > MAX_WIDTH or orig_height > MAX_HEIGHT
  ):
    scale_ratio = min(MAX_WIDTH / orig_width, MAX_HEIGHT / orig_height)
    proc_w = max(_ensure_mod2(orig_width * scale_ratio), 2)
    proc_h = max(_ensure_mod2(orig_height * scale_ratio), 2)
    clip_work = core.resize.Bicubic(clip=clip, width=proc_w, height=proc_h)
    is_downscaled = True
  else:
    clip_work = clip

  # --- 5.2 讀取色彩元數據 (使用 get_frame(0) 讀取真實 frame props) ---
  # [v2.3.1 修正] 恢復 get_frame(0) 讀取真實色彩屬性。
  # 推斷模式會導致輸出 clip 缺少 _Matrix/_Transfer/_ColorRange 等 frame props，
  # 使 MPC-BE 渲染器反覆偵測/切換色彩空間，造成間歇性音畫不同步。
  # get_frame(0) 只在腳本初始化時呼叫一次（此時 RIFE 尚未串入 filter chain），
  # 讀取的是原始 clip 的第 0 幀，不會觸發 RIFE 模型載入。
  f0_props = clip.get_frame(0).props
  matrix_val = f0_props.get("_Matrix", None)
  transfer_val = f0_props.get("_Transfer", None)
  range_val = f0_props.get("_ColorRange", 1)
  chroma_val = f0_props.get("_ChromaLocation", None)

  is_hdr = (transfer_val in [14, 16, 18]) or (matrix_val == 9)

  if is_hdr:
    matrix_str = "2020ncl"
  elif orig_width >= 1280 or orig_height >= 720 or matrix_val == 1:
    matrix_str = "709"
  elif orig_width > 1024 or orig_height > 576:
    matrix_str = "709"
  else:
    matrix_str = "601"

  range_str = "full" if range_val == 0 else "limited"
  chroma_map = {0: "left", 1: "center", 2: "topleft", 3: "top"}
  chroma_str = chroma_map.get(chroma_val, "left")

  _guess_hdr = is_hdr

  # --- 5.3 轉換色彩空間至 RGBS (單精度 32-bit Float RGB) ---
  resize_in_args = {
      "format": vs.RGBS,
      "matrix_in_s": matrix_str,
      "range_in_s": range_str,
      "chromaloc_in_s": chroma_str,
  }
  if _guess_hdr:
    resize_in_args["transfer_in_s"] = "st2084"  # PQ
    resize_in_args["transfer_s"] = "st2084"
    resize_in_args["primaries_in_s"] = "2020"  # BT.2020
    resize_in_args["primaries_s"] = "2020"

  clip_rgb = core.resize.Bicubic(clip=clip_work, **resize_in_args)

  # --- 5.4 執行 RIFE 神經網絡補幀 ---
  # 智能檢測 TRT 引擎快取：若該解析度已有預編譯引擎則秒開 TRT，
  # 若無預編譯快取則自動改用純 CUDA 推論（0.16 秒秒開），杜絕播放器在 DirectShow 執行緒中卡死 3 分鐘編譯引擎
  _use_trt = False
  if USE_TRT and _HAS_TRT:
    try:
      import tensorrt
      import torch
      from vsrife import model_dir
      _pw = math.ceil(clip_work.width / 32) * 32
      _ph = math.ceil(clip_work.height / 32) * 32
      _dev_name = torch.cuda.get_device_name(0)
      _engine_name = f"flownet_v{MODEL}.pkl_{_pw}x{_ph}_fp32_scale-{RIFE_SCALE}_ensemble-False_{_dev_name}_trt-{tensorrt.__version__}.ts"
      _engine_path = os.path.join(model_dir, _engine_name)
      if os.path.isfile(_engine_path):
        _use_trt = True
    except Exception:
      _use_trt = False

  try:
    clip_rife = rife(
        clip=clip_rgb,
        model=MODEL,
        auto_download=True,
        factor_num=factor_num,
        factor_den=factor_den,
        scale=RIFE_SCALE,
        sc=ENABLE_SCENE_DETECT,
        sc_threshold=SC_THRESHOLD,
        trt=_use_trt,
        trt_static_shape=True,
    )
  except Exception:
    # TensorRT 失敗時自動退回 CUDA 推論
    if _use_trt:
      _WARNINGS.append("[WARNING] TensorRT init failed, fallback to pure CUDA inference.")
    clip_rife = rife(
        clip=clip_rgb,
        model=MODEL,
        auto_download=True,
        factor_num=factor_num,
        factor_den=factor_den,
        scale=RIFE_SCALE,
        sc=ENABLE_SCENE_DETECT,
        sc_threshold=SC_THRESHOLD,
        trt=False,
    )

  # --- 5.5 色彩空間還原 + 解析度恢復 (合併為單次 resize 減少記憶體拷貝) ---
  # [v2.2 效能優化] 將「放大回原解析度」與「RGBS→YUV 色彩還原」合併為一次 resize.Bicubic，
  # 避免在 float32 空間做不必要的 4K 放大（節省 ~30% 記憶體頻寬）
  resize_out_args = {
      "format": orig_format_id,
      "matrix_s": matrix_str,
      "range_s": range_str,
      "chromaloc_s": chroma_str,
  }
  if _guess_hdr:
    resize_out_args["transfer_in_s"] = "st2084"
    resize_out_args["transfer_s"] = "st2084"
    resize_out_args["primaries_in_s"] = "2020"
    resize_out_args["primaries_s"] = "2020"

  # 若有降頻，同時在此步驟放大回原解析度
  if is_downscaled:
    resize_out_args["width"] = orig_width
    resize_out_args["height"] = orig_height

  clip_out = core.resize.Bicubic(clip=clip_rife, **resize_out_args)

  # --- 5.6 【核心防快轉機制】清除舊時間戳並重設精確幀率 ---
  # 僅清除影響 DirectShow 渲染時鐘追幀的屬性，保留 _SAR (像素比) 防止畫面變形
  props_to_clean = ["_AbsoluteTime", "_DurationNum", "_DurationDen"]
  clip_out = core.std.RemoveFrameProps(clip=clip_out, props=props_to_clean)

  # 計算 RIFE 輸出幀率分子分母，並使用最大公因數 (GCD) 約分化簡
  rife_fpsnum = factor_num * clip.fps_num
  rife_fpsden = factor_den * clip.fps_den
  g = math.gcd(rife_fpsnum, rife_fpsden)
  rife_fpsnum //= g
  rife_fpsden //= g

  clip_out = core.std.AssumeFPS(
      clip=clip_out, fpsnum=rife_fpsnum, fpsden=rife_fpsden
  )

  # --- 5.6.1 回寫色彩與 HDR 元數據 (與原版行為一致) ---
  # 確保輸出 clip 攜帶正確的 _Matrix, _Transfer 等 frame props，
  # 讓 MPC-BE 渲染器無需重新偵測色彩空間
  _preserve_props = {}
  _keys_to_preserve = [
      "_Matrix", "_Transfer", "_Primaries", "_ColorRange", "_ChromaLocation",
      "MasteringDisplayColorPrimaries", "MasteringDisplayLuminance",
      "ContentLightLevelAverage", "ContentLightLevelMax",
  ]
  for _key in _keys_to_preserve:
    if _key in f0_props:
      _preserve_props[_key] = f0_props[_key]
  if _preserve_props:
    clip_out = core.std.SetFrameProps(clip=clip_out, **_preserve_props)

  # --- 5.7 混合補幀：用輕量級方法填充剩餘幀到螢幕滿幀 ---
  rife_fps_out = rife_fpsnum / rife_fpsden
  fill_hz = FILL_TARGET_HZ if (FILL_TARGET_HZ and FILL_TARGET_HZ > 0) else screen_hz

  # 只在 RIFE 輸出幀率 < 螢幕刷新率時才執行填充
  if FILL_MODE.upper() != "NONE" and rife_fps_out < (fill_hz - 0.5):

    if FILL_MODE.upper() == "MVTOOLS":
      # ================================================================
      # MVTools 光流補幀 (CPU 運算，輕量級)
      # ================================================================
      # 原理：RIFE 已把大幅度運動補好 (24→48fps)，
      #       MVTools 只需在已經很接近的 48fps 幀之間做細分，
      #       運動向量小、計算量低、品質高。
      # 範例：48fps → 144fps = 3倍細分，CPU 負擔極輕
      if not _HAS_MVTOOLS:
        _WARNINGS.append(
            f"[WARNING] FILL_MODE='MVTOOLS' but MVTools/MVUtensils not loaded! "
            f"Fallback to screen repeat ({rife_fps_out:.1f}fps -> {fill_hz}Hz)."
        )
      else:
        try:
          if hasattr(core, "mvu"):
            mv = core.mvu
            sup = mv.Super(clip_out, blksize=MV_BLKSIZE, overlap=MV_OVERLAP, pel=MV_PEL)
            fvec = mv.Analyse(sup, blksize=MV_BLKSIZE, overlap=MV_OVERLAP, delta=1, chroma=True, search=MV_SEARCH)
            bvec = mv.Analyse(sup, blksize=MV_BLKSIZE, overlap=MV_OVERLAP, delta=-1, chroma=True, search=MV_SEARCH)
            clip_out = mv.FlowFPS(
                clip_out, sup, vectors=[fvec, bvec],
                num=fill_hz, den=1,
                thscd1=400,
                thscd2=51.0,
            )
          else:
            mv = core.mv
            sup = mv.Super(clip_out, pel=MV_PEL, hpad=MV_BLKSIZE, vpad=MV_BLKSIZE)
            bvec = mv.Analyse(sup, blksize=MV_BLKSIZE, overlap=MV_OVERLAP, isb=True, chroma=True, search=MV_SEARCH)
            fvec = mv.Analyse(sup, blksize=MV_BLKSIZE, overlap=MV_OVERLAP, isb=False, chroma=True, search=MV_SEARCH)
            clip_out = mv.FlowFPS(
                clip_out, sup, bvec, fvec,
                num=fill_hz, den=1,
                mask=2,
                thscd1=400,
                thscd2=130,
            )
        except Exception as e:
          _WARNINGS.append(
              f"[WARNING] MVTools execution failed: {e}. Fallback to screen repeat."
          )

    elif FILL_MODE.upper() == "BLEND":
      # ================================================================
      # 簡易幀混合 (極輕量，但有殘影)
      # ================================================================
      # 將相鄰幀混合產生中間幀，再 Interleave 插入
      # 適合極低端硬體或不介意殘影的場景
      fill_ratio = round(fill_hz / rife_fps_out)
      if fill_ratio >= 2:
        blended = core.std.Merge(clip_out, clip_out[1:] + clip_out[-1],
                                 weight=0.5)
        if fill_ratio == 2:
          clip_out = core.std.Interleave([clip_out, blended])
        elif fill_ratio == 3:
          blend_a = core.std.Merge(clip_out, clip_out[1:] + clip_out[-1],
                                   weight=0.333)
          blend_b = core.std.Merge(clip_out, clip_out[1:] + clip_out[-1],
                                   weight=0.667)
          clip_out = core.std.Interleave([clip_out, blend_a, blend_b])
        # 重設幀率
        clip_out = core.std.AssumeFPS(clip_out, fpsnum=fill_hz, den=1)

    # 填充後重新清除時間戳
    clip_out = core.std.RemoveFrameProps(
        clip=clip_out, props=["_AbsoluteTime", "_DurationNum", "_DurationDen"]
    )



  # --- 5.8 最終輸出與螢幕提示 ---
  if _WARNINGS:
    warn_text = " | ".join(
        w.split("\n")[0] for w in _WARNINGS  # 只取每則警告的第一行 (純英文避免編碼錯誤)
    )
    print(f"[AviSynthFilter/RIFE] {warn_text}")
    try:
      clip_warn = core.text.Text(clip_out, warn_text, alignment=7)
      # 前 300 幀在螢幕左上角顯示英文提示，之後正常播放
      # 使用 FrameEval 動態切換，杜絕 Splice 切割 DirectShow streaming clip 造成的緩衝卡死
      def _show_warn_overlay(n):
        if n < 300:
          return clip_warn
        return clip_out

      clip_out = core.std.FrameEval(clip_out, _show_warn_overlay)
    except Exception:
      pass

  clip_out.set_output()

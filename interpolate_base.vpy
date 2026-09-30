import fractions
import math
from vapoursynth import core
import vapoursynth as vs
from vsrife import rife

# ============================== 用戶設定區 ==============================
# 目標模式選擇 (TARGET_MODE)：
#    "60"  : 【預設】24fps 補 2.5 倍至 60fps（完美適配 60Hz 螢幕，低溫順暢）
#    "48"  : 24fps 補 2.0 倍至 48fps（適配 144Hz / 240Hz 螢幕，算力極低）
#    "120" : 24fps 補 5.0 倍至 120fps（適配 120Hz / 240Hz 螢幕，極致絲滑）
#    "144" : 24fps 補 6.0 倍至 144fps（適配 144Hz 滿幀電競螢幕）
TARGET_MODE = "48"

# 模型設定
MODEL = "4.25"  # 推薦 4.25（抗大動態撕裂能力最佳）
USE_TRT = True  # 開啟 TensorRT 核心加速
RIFE_SCALE = 1.0  # 採樣精度（1.0 為原生 1:1，畫質最細緻）

# 安全分鏡檢測（即時播放保持 False 即可秒開秒播，無撕裂）
ENABLE_SCENE_DETECT = False
SC_THRESHOLD = 0.15

# 系統資源配置
core.num_threads = 4  # CPU 餵圖執行緒數
core.max_cache_size = 4096  # 分配 4GB 記憶體快取
# =======================================================================


# 1. 取得視訊來源
if "VpsFilterSource" in globals():
  clip = VpsFilterSource
elif "video_in" in globals():
  clip = video_in
else:
  raise RuntimeError("未檢測到輸入視訊源！")

# 2. 原始幀率檢測（大於等於 48fps 視訊直接直通，不重複補幀）
fps_in = clip.fps_num / clip.fps_den

if fps_in >= 48.0:
  clip.set_output()
else:
  # 3. 根據 TARGET_MODE 計算倍率
  if TARGET_MODE == "48":
    target_fps = 48.0
  elif TARGET_MODE == "144":
    target_fps = 144.0
  elif TARGET_MODE == "120":
    target_fps = 120.0
  else:
    target_fps = 60.0

  # 針對常見視訊標準進行精準整數分數對齊，杜絕時鐘抖動
  if 23.5 <= fps_in <= 24.5:
    # 24fps 視訊適配
    if TARGET_MODE == "48":
      factor_num, factor_den = (2, 1)  # 2.0x -> 48 fps
    elif TARGET_MODE == "144":
      factor_num, factor_den = (6, 1)  # 6.0x -> 144 fps
    elif TARGET_MODE == "120":
      factor_num, factor_den = (5, 1)  # 5.0x -> 120 fps
    else:
      factor_num, factor_den = (5, 2)  # 2.5x -> 60 fps（預設）

  elif 24.8 <= fps_in <= 25.5:
    # 25fps (PAL) 視訊適配
    if TARGET_MODE == "48":
      factor_num, factor_den = (2, 1)  # 50 fps
    elif TARGET_MODE == "144":
      factor_num, factor_den = (144, 25)  # 144 fps
    elif TARGET_MODE == "120":
      factor_num, factor_den = (24, 5)  # 120 fps
    else:
      factor_num, factor_den = (12, 5)  # 60 fps

  elif 29.5 <= fps_in <= 30.5:
    # 30fps 視訊適配
    if TARGET_MODE == "144":
      factor_num, factor_den = (24, 5)  # 144 fps
    elif TARGET_MODE == "120":
      factor_num, factor_den = (4, 1)  # 120 fps
    else:
      factor_num, factor_den = (2, 1)  # 60 fps

  else:
    # 其他非常規幀率自動以最佳分數近似
    ratio = fractions.Fraction(target_fps / fps_in).limit_denominator(20)
    factor_num, factor_den = ratio.numerator, ratio.denominator

  # 4. 讀取色彩中繼屬性 (自動識別 HDR / SDR)
  f0_props = clip.get_frame(0).props
  matrix_val = f0_props.get("_Matrix", None)
  transfer_val = f0_props.get("_Transfer", None)
  range_val = f0_props.get("_ColorRange", 1)
  chroma_val = f0_props.get("_ChromaLocation", None)

  is_hdr = (transfer_val in [14, 16, 18]) or (matrix_val == 9)

  if is_hdr:
    matrix_str = "2020ncl"
  elif clip.width > 1024 or clip.height > 576 or matrix_val == 1:
    matrix_str = "709"
  else:
    matrix_str = "601"

  range_str = "full" if range_val == 0 else "limited"
  chroma_map = {0: "left", 1: "center", 2: "topleft", 3: "top"}
  chroma_str = chroma_map.get(chroma_val, "left")

  # 5. 轉換為 vs.RGBS (FP32 全精度輸入，杜絕雜訊)
  clip_rgb = core.resize.Bicubic(
      clip=clip,
      format=vs.RGBS,
      matrix_in_s=matrix_str,
      range_in_s=range_str,
      chromaloc_in_s=chroma_str,
  )

  # 6. 安全分鏡標記（預設關閉）
  if ENABLE_SCENE_DETECT:

    def set_sc_props(n: int, f: list[vs.VideoFrame]) -> vs.VideoFrame:
      fout = f[0].copy()
      diff = f[1].props.get("PlaneStatsDiff", 0.0)
      if diff > SC_THRESHOLD:
        fout.props["_SceneChangePrev"] = 1
      return fout

    sc_clip = clip_rgb.resize.Bicubic(format=vs.GRAY8, matrix_s="709")
    sc_clip = sc_clip.std.PlaneStats(sc_clip[0] + sc_clip[:-1])
    clip_rgb = clip_rgb.std.ModifyFrame(
        clips=[clip_rgb, sc_clip], selector=set_sc_props
    )

  # 7. 呼叫 RIFE TensorRT 進行補幀
  clip_rife = rife(
      clip=clip_rgb,
      model=MODEL,
      auto_download=True,
      factor_num=factor_num,
      factor_den=factor_den,
      scale=RIFE_SCALE,
      sc=False,
      trt=USE_TRT,
      trt_static_shape=True,
  )

  # 8. 色彩還原回原始格式 (P010 / NV12 等)
  clip_out = core.resize.Bicubic(
      clip=clip_rife,
      format=clip.format,
      matrix_s=matrix_str,
      range_s=range_str,
      chromaloc_s=chroma_str,
  )

  # 9. 【核心修復】清除殘留的舊時間戳與舊時長屬性
  # RIFE 生成幀時會複製前一幀的 _AbsoluteTime 與 _DurationNum。
  # 在 60Hz 固定電視上，重複/過期的時間戳會被渲染器誤判為嚴重落後幀，
  # 進而觸發 Catch-up 狂暴快轉機制。此處清除可徹底消除衝突。
  props_to_clean = ["_AbsoluteTime", "_DurationNum", "_DurationDen"]
  clip_out = core.std.RemoveFrameProps(clip=clip_out, props=props_to_clean)

  # 10. 【核心修復】精確重新封裝 60fps（59.94fps）時間基準
  clip_out = core.std.AssumeFPS(
      clip=clip_out,
      fpsnum=factor_num * clip.fps_num,
      fpsden=factor_den * clip.fps_den,
  )

  # 11. 僅保留色彩與 HDR 元數據
  preserve_props = {}
  keys_to_preserve = [
      "_Matrix",
      "_Transfer",
      "_Primaries",
      "_ColorRange",
      "_ChromaLocation",
      "MasteringDisplayColorPrimaries",
      "MasteringDisplayLuminance",
      "ContentLightLevelAverage",
      "ContentLightLevelMax",
  ]
  for key in keys_to_preserve:
    if key in f0_props:
      preserve_props[key] = f0_props[key]

  if preserve_props:
    clip_out = core.std.SetFrameProps(clip=clip_out, **preserve_props)

  # 12. 輸出視訊（DirectShow 接收到乾淨穩定的 60fps 幀流）
  clip_out.set_output()

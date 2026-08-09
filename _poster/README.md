# DeepNirvana 扫码海报（公众号纯图片版）

交付物是**一张图**，不是网页：`dn-poster-1080x1920.png` 上传到公众号即可。

```
_src/design-poster.dc.html     设计稿（可回传 Claude Design 继续改）
_src/build-poster.py           设计稿 → 自包含 HTML → 定尺 PNG
_poster/
  dn-poster-1080x1920.png        A 版（纯净底）🟩 发公众号用这张
  dn-poster-2160x3840@2x.png     A 版母版，留给印刷 / 后期二次裁切
  dn-poster-brush-1080x1920.png  B 版（书法背景）
  dn-poster-brush-*@2x.png       B 版母版
  dn-poster*.html                中间产物，自包含单文件（字体和二维码都内联）
  _*                             审查过程的诊断图，可删
```

## A 版 / B 版

同一份文案版式，差别只在背景：

- **A** `_src/design-poster.dc.html` —— 纯净底，只有顶部一圈暖光 + 细颗粒
- **B** `_src/design-poster-brush.dc.html` —— 加一个出血的大「破」字书法背景

原稿本来是有书法背景的，但强度只有 Δ(8,6,2)，而且 1180px 的「破局」两个字合起来
2600px 宽、画布只有 1080px，只露出中间一截，看着像蹭脏了。B 版按内测发布页的实测
强度重做：Δ(23,18,11)（发布页原值），单字、从右侧出血。

代价量过：五不那五格的灰色小字，底色被垫高的两格对比度从 5.64:1 掉到 4.82:1，
仍在 AA 线（4.5:1）以上。两版二维码四种情况都实测可解。

改 B 版不要手改 `design-poster-brush.dc.html`——它是从 A 版派生的，A 版改了要重新派生。

## 重建

```bash
/tmp/fontenv/bin/python _src/build-poster.py --url "https://ai.umobai.com/beta/"
```

工具链（同 `build-fonts.py`）：

```bash
python3 -m venv /tmp/fontenv && /tmp/fontenv/bin/pip install fonttools brotli segno pillow
```

二维码目标换一个地址就改 `--url`，脚本会重新生成并重新截图，不用手工换图。

## 三条不能省的验收

海报和网页不一样：发出去就改不了了，也没有"用户刷新一下"这回事。每次改完跑一遍：

```bash
# 1) 二维码真能解码（别只看着像二维码）
/Users/oasis/Documents/Development/AI/creditor-pre/.venv/bin/python -c "
import cv2;print(cv2.QRCodeDetector().detectAndDecode(cv2.imread('_poster/dn-poster-1080x1920.png'))[0])"

# 2) 微信会把图重压成 JPEG，压完还得能扫
# 3) 在手机上是缩到约 390px 宽显示的，缩完还得能扫
```

本轮三项都过（含 q80 二压、缩到 390px 宽两种情况）。

## 字体

「破局」用 Ma Shan Zheng 毛笔体，复用 `beta/fonts/ma-shan-zheng-400.woff2`（已子集到这两个字，
1.6 KB），构建时**内联成 data: URI**。原因和 `beta/README.md` 一样——fonts.googleapis.com
大陆不可达——但海报还多一条：**截图必须是确定性的**。字体没加载上不会报错，只会静默退回
宋体，「破局」两个字直接换一张脸，图发出去才发现就晚了。

设计稿里那行 Google Fonts `<link>` 是留给 Claude Design 预览用的，构建时会被丢掉；
脚本对产物做外链自检，只要还剩一条 http(s) 外链就直接报错退出。

## 改文案要注意

只有「破局」两个字用毛笔体，其余全走系统字（PingFang SC），所以改文案**不需要**重跑
`build-fonts.py`——除非你把毛笔体用到了别的字上，那两个字的子集里没有别的字形。

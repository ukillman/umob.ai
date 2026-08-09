#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把海报设计稿（.dc.html）转成**一个自包含的 HTML**，再截成 PNG。

海报和网页不一样：最终交付物是**一张图片**，发到微信公众号。所以这里没有
build.py 那套 `{{ }}` 绑定转换——海报没有交互，一行 JS 都不该有。这个脚本只做
四件事：

  1. 剥掉设计工具的外壳（`<x-dc>` / `<helmet>` / `<script>`）
  2. 毛笔体 woff2 **内联成 data: URI** —— 设计稿引 Google Fonts，
     fonts.googleapis.com 在中国大陆不可达；而且截图必须是确定性的，
     字体没加载上就会静默退回宋体，「破局」两个字直接换了一张脸，
     图片发出去才发现就晚了。内联之后这个 HTML 单文件到哪都一样。
  3. `<image-slot>` 占位换成真实二维码 PNG（同样内联）
  4. headless Chrome 定尺截图

用法：
    /tmp/fontenv/bin/python _src/build-poster.py            # 建 + 截图
    /tmp/fontenv/bin/python _src/build-poster.py --no-shot  # 只建 HTML

依赖：fonttools + brotli + segno（二维码）
    python3 -m venv /tmp/fontenv && /tmp/fontenv/bin/pip install fonttools brotli segno
"""
import argparse
import base64
import pathlib
import re
import subprocess
import sys

SRC = pathlib.Path(__file__).parent
ROOT = SRC.parent
OUT = ROOT / "_poster"

DESIGN = SRC / "design-poster.dc.html"
BRUSH = ROOT / "beta" / "fonts" / "ma-shan-zheng-400.woff2"   # 已子集到「破局」两字，1.6 KB
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

W, H = 1080, 1920


def qr_png(data: str, px: int = 1200) -> bytes:
    """生成二维码。

    🟥 纠错等级用 **Q（25% 冗余）不用 H**，这条是踩出来的：

    H 会把这条 27 字的网址顶到 version 4 = 37×37 模块；同样 272px 的白块里
    每个模块只有 7.35px，缩到手机常见的 390px 宽显示时**每模块 2.65px**，
    已经在识别阈值边缘——实测同一条网址、同样大小，左对齐的版本能解、
    居中的版本解不出来，差别只是缩放时的亚像素对齐。**那不是余量，那是运气。**
    Q 降到 version 3 = 33×33，每模块大 12%；再把白块从 300px 放到 320px，
    合起来每模块 +21%，才算真有余量。

    冗余从 30% 掉到 25% 不影响这个用途：H 的场景是二维码上压 logo 或者会被
    物理磨损，我们两样都没有。
    `border=2` 是留白（quiet zone），低于 2 个模块很多扫码器直接不认。
    """
    import segno
    import io
    q = segno.make(data, error="q")
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=max(1, px // (q.symbol_size(border=2)[0])), border=2,
           dark="#000000", light="#FFFFFF")
    return buf.getvalue()


def build(design: pathlib.Path, out_html: pathlib.Path, qr_url: str) -> pathlib.Path:
    raw = design.read_text(encoding="utf-8")

    helmet = re.search(r"<helmet[^>]*>(.*?)</helmet>", raw, re.S).group(1)
    title = re.search(r"<title>(.*?)</title>", helmet, re.S).group(1).strip()
    style = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", helmet, re.S)).strip()

    body = re.search(r"<body[^>]*>(.*)</body>", raw, re.S).group(1)
    body = re.sub(r"<helmet[^>]*>.*?</helmet>", "", body, flags=re.S)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = body.replace("<x-dc>", "").replace("</x-dc>", "").strip()

    # ---- 二维码：占位组件 → 内联 <img> ----
    qr_b64 = base64.b64encode(qr_png(qr_url)).decode()
    img = (f'<img alt="扫码申请内测资格" src="data:image/png;base64,{qr_b64}" '
           f'style="width:100%;height:100%;display:block;image-rendering:pixelated">')
    body, n_qr = re.subn(r"<image-slot\b[^>]*>.*?</image-slot>|<image-slot\b[^>]*/?>",
                         lambda _: img, body, flags=re.S)

    # ---- 毛笔体内联 ----
    font_b64 = base64.b64encode(BRUSH.read_bytes()).decode()
    face = ("@font-face{font-family:'Ma Shan Zheng';font-style:normal;font-weight:400;"
            f"font-display:block;src:url(data:font/woff2;base64,{font_b64}) format('woff2')}}")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
/* 「破局」毛笔体 Ma Shan Zheng（SIL OFL），已子集到这两个字，内联约 2 KB。
   不引 fonts.googleapis.com：大陆不可达，且截图必须确定性。 */
{face}
{style}
/* 截图用：画布正好一屏，不要滚动条、不要额外留白 */
html,body{{margin:0;padding:0;background:#08090B;overflow:hidden}}
</style>
</head>
<body>
{body}
</body>
</html>
"""
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html, encoding="utf-8")

    ext = re.findall(r'(?:href|src)="(https?://[^"]+)"', html)
    if ext:
        raise SystemExit(f"!! {out_html.name} 仍有外链，截图会不确定：{ext[:3]}")
    if n_qr != 1:
        raise SystemExit(f"!! 二维码占位替换了 {n_qr} 处，期望正好 1 处"
                         "（微信长按识别要求图里只有一个二维码）")
    print(f"{out_html.relative_to(ROOT)}  {len(html.encode()):,} bytes  二维码→{qr_url}")
    return out_html


def verify_fit(html: pathlib.Path) -> None:
    """海报是定高画布（1920px）+ overflow:hidden —— 内容超了**不会报错**，
    只会把最后一段悄悄切掉一半，截图上看着像设计如此。踩过两次（折中版、三段版），
    两次都是页脚被吃掉。所以构建期直接问浏览器要真实高度。

    做法：给产物注入一段探针，把 section 最后一个子元素的底边（含 margin）写进
    <title>，再用 --dump-dom 读回来。不能靠"截图底部有没有字"来判断——
    overflow:hidden 已经把超出的部分裁掉了，图上看不出来。
    """
    probe = html.with_name(html.stem + ".__fit.html")
    src = html.read_text(encoding="utf-8")
    probe.write_text(src.replace("</body>", """<script>
addEventListener('load', function(){
  var s = document.getElementById('poster');
  var kids = [].filter.call(s.children, function(e){ return getComputedStyle(e).position !== 'absolute' });
  var last = kids[kids.length-1];
  var mb = parseFloat(getComputedStyle(last).marginBottom) || 0;
  var need = last.offsetTop + last.offsetHeight + mb;
  document.title = 'FIT:' + Math.round(need) + '/' + s.offsetHeight;
});
</script></body>"""), encoding="utf-8")
    dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu",
                          f"--window-size={W},{H}", "--virtual-time-budget=8000",
                          "--dump-dom", probe.as_uri()],
                         capture_output=True, text=True).stdout
    probe.unlink(missing_ok=True)
    m = re.search(r"FIT:(\d+)/(\d+)", dom)
    if not m:
        print("  ⚠️ 高度探针没跑起来，跳过溢出检查"); return
    need, have = int(m.group(1)), int(m.group(2))
    slack = have - need
    if slack < 0:
        raise SystemExit(f"!! 内容溢出 {-slack}px（需要 {need}px，画布 {have}px）——"
                         f"最后一段会被 overflow:hidden 切掉，截图上看不出来。先减版面再出图。")
    print(f"  版面占用 {need}/{have}px，余量 {slack}px")


def shoot(html: pathlib.Path, png: pathlib.Path, scale: int = 1) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--default-background-color=00000000",
        f"--force-device-scale-factor={scale}",
        f"--window-size={W},{H}",
        "--virtual-time-budget=8000",          # 等字体真正加载完再截，否则会截到退化字形
        f"--screenshot={png}", html.as_uri(),
    ], check=True, capture_output=True)
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(png)],
                         capture_output=True, text=True).stdout
    dims = dict(re.findall(r"(pixel\w+):\s*(\d+)", out))
    print(f"  → {png.relative_to(ROOT)}  "
          f"{dims.get('pixelWidth')}×{dims.get('pixelHeight')}  "
          f"{png.stat().st_size:,} bytes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DESIGN))
    ap.add_argument("--name", default="dn-poster")
    ap.add_argument("--url", default="https://ai.umobai.com/beta/")
    ap.add_argument("--no-shot", action="store_true")
    a = ap.parse_args()

    h = build(pathlib.Path(a.src), OUT / f"{a.name}.html", a.url)
    verify_fit(h)
    if not a.no_shot:
        shoot(h, OUT / f"{a.name}-1080x1920.png", scale=1)
        shoot(h, OUT / f"{a.name}-2160x3840@2x.png", scale=2)

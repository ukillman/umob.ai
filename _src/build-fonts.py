#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为每个页面下载并**本地子集化**它实际用到的字体。

**为什么必须本地化**：设计稿引 Google Fonts（fonts.googleapis.com），该域名在
中国大陆不可达。目标用户是境内破产管理人，外链字体不只是退化成系统字，
`<link>` 还会阻塞首屏渲染直到超时。

**为什么不能用 Google 的 `&text=` 子集参数**：踩过一次——传 672 个汉字时它
**静默截断**，返回的 woff2 里只有 12 个字形（文件 2.7KB，看着像"子集做得真小"，
其实是废的，上线会大面积缺字）；传 404 字时又正常。有个不声明的长度上限，
超了不报错。所以改成：下载完整字库 → 本地裁剪 → **当场核对字形数**。

**为什么按页面分别打包**：内测首页正文走 PingFang SC（系统自带，不用打包），
只有「破局」两个字用毛笔体，字体成本 1.8 KB；而 pojiu.html 用了 Noto Serif SC
全套，成本 800 KB 量级。混在一起打，首页会白白背上几百 KB。

依赖：fonttools + brotli。
    python3 -m venv /tmp/fontenv && /tmp/fontenv/bin/pip install fonttools brotli
    /tmp/fontenv/bin/python _src/build-fonts.py

🟥 **改了页面文案就要重跑本脚本**，否则新出现的汉字会掉回系统字体
（同一段话里字形不一致，很显眼）。顺序：先 build.py 生成页面，再跑本脚本。
"""
import pathlib
import re
import sys
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont

SRC = pathlib.Path(__file__).parent
ROOT = SRC.parent
CACHE = SRC / ".font-cache"
CACHE.mkdir(exist_ok=True)

# 页面 → (产物 html, 字体输出目录, 该页运行时)
PAGES = {
    "dn": (ROOT / "beta" / "index.html", ROOT / "beta" / "fonts", SRC / "runtime-dnhome.js"),
    "pojiu": (ROOT / "pojiu.html", ROOT / "pojiu-fonts", SRC / "runtime-pojiu.js"),
}

# 原始字库取自 Google Fonts 官方仓库（全部 SIL OFL，可商用）。
# 不走 fonts.googleapis.com：那边按 UA 决定给什么，两条路都拿不到整字库——
# 现代 UA 给按 unicode-range 切好的 woff2 碎片（CJK 上百个，拼不回来），
# 老式 UA 给 /l/font?kit=… 也是切过的。只有官方仓库里是完整字库。
GF = "https://raw.githubusercontent.com/google/fonts/main/"
SOURCES = {
    "Noto Serif SC": "ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf",
    "Ma Shan Zheng": "ofl/mashanzheng/MaShanZheng-Regular.ttf",
    "Archivo": "ofl/archivo/Archivo%5Bwdth,wght%5D.ttf",
    "IBM Plex Mono": "ofl/ibmplexmono/IBMPlexMono-Regular.ttf",
}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# 「破局」两个字是唯一用毛笔体的地方，单独限定字符集，
# 否则会把整个 5.8MB 中文字库按页面用字裁一遍，白白多几百 KB。
BRUSH_ONLY = {"Ma Shan Zheng": "破局"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def full_font(family: str) -> pathlib.Path:
    cached = CACHE / f"{family.replace(' ', '-')}.ttf"
    if cached.exists():
        return cached
    blob = fetch(GF + SOURCES[family])
    if blob[:4] not in (b"\x00\x01\x00\x00", b"true", b"ttcf", b"OTTO"):
        raise SystemExit(f"!! {family}: 拿到的不是 ttf/otf（前 4 字节 {blob[:4]!r}）")
    cached.write_bytes(blob)
    print(f"  ↓ {family}  {cached.stat().st_size:,} bytes（已缓存）")
    return cached


def page_chars(html_path: pathlib.Path, runtime: pathlib.Path) -> str:
    """页面 + 运行时里出现过的全部字符。运行时 JS 也要扫——错误提示、
    成功文案都写在那儿，漏了会在用户真正看到那句话时才发现字形不对。"""
    src = html_path.read_text(encoding="utf-8")
    src = re.sub(r"<script.*?</script>", "", src, flags=re.S)
    src = re.sub(r"<style.*?</style>", "", src, flags=re.S)
    attrs = " ".join(re.findall(r'(?:placeholder|title|content|alt)="([^"]*)"', src))
    text = re.sub(r"<[^>]+>", " ", src) + " " + attrs
    if runtime.exists():
        text += " " + runtime.read_text(encoding="utf-8")
    # 兜一点余量：改文案时最容易新冒出来的全角标点与数字
    text += "０１２３４５６７８９，。、；：？！（）《》〈〉【】—…·～％＋－×÷＝"
    text += "".join(chr(i) for i in range(32, 127))
    return "".join(sorted({c for c in text if c.isprintable() and not c.isspace()}))


def families_used(html_path: pathlib.Path) -> dict:
    """页面里实际声明过的自定义字体族 → 用到的字重。
    系统字体（PingFang SC 等）不打包，跳过。"""
    src = html_path.read_text(encoding="utf-8")
    used = {}
    for fam in SOURCES:
        if fam not in src:
            continue
        weights = sorted({int(w) for w in re.findall(r"font-weight:\s*(\d{3})", src)})
        # 毛笔体只有一个字重，浏览器合成即可
        used[fam] = [400] if fam in BRUSH_ONLY else (weights or [400])
    return used


def build(key: str) -> None:
    html_path, out_dir, runtime = PAGES[key]
    if not html_path.exists():
        print(f"  跳过 {key}：{html_path.name} 还没生成")
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    chars = page_chars(html_path, runtime)
    used = families_used(html_path)
    if not used:
        print(f"{key}: 全部走系统字体，无需打包")
        return

    css = ["/* 本地字体。由 _src/build-fonts.py 生成，请勿手改。\n"
           "   改页面文案后重跑该脚本，否则新出现的汉字会掉回系统字体。 */"]
    total = 0
    for family, weights in used.items():
        subset_chars = BRUSH_ONLY.get(family, chars)
        src_path = full_font(family)
        for w in weights:
            font = TTFont(str(src_path))
            if "fvar" in font:
                from fontTools.varLib import instancer
                # 必须把**每一条轴**都钉死，只钉 wght 会留下 gvar，
                # 子集时报 KeyError（Archivo 是 wdth+wght 双轴，踩过）。
                axes = {a.axisTag: (w if a.axisTag == "wght" else a.defaultValue)
                        for a in font["fvar"].axes}
                font = instancer.instantiateVariableFont(font, axes, updateFontNames=False)
            have = set(font.getBestCmap())
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.desubroutinize = True
            opts.layout_features = ["*"]
            sub = subset.Subsetter(options=opts)
            sub.populate(text=subset_chars)
            sub.subset(font)
            name = f"{family.lower().replace(' ', '-')}-{w}.woff2"
            font.flavor = "woff2"
            font.save(str(out_dir / name))
            got = len(font.getBestCmap())
            # 字形数当场核对——这正是 Google &text= 那次翻车没被发现的地方。
            # 期望值按「字库里本来就有的字」算：拉丁字库没有中文标点是正常的，
            # 按请求字数比会一直误报。
            want = len({ord(c) for c in subset_chars} & have)
            size = (out_dir / name).stat().st_size
            total += size
            css.append(f"@font-face{{font-family:'{family}';font-style:normal;"
                       f"font-weight:{w};font-display:swap;"
                       f"src:url('./{name}') format('woff2')}}")
            flag = "" if got >= want else f"  ⚠️ 少了 {want - got} 个字形"
            print(f"  {family:<14} {w:>3}  {got:>4}/{want} 字形  {size:>8,} bytes{flag}")

    (out_dir / "fonts.css").write_text("\n".join(css) + "\n", encoding="utf-8")
    print(f"  → {out_dir.relative_to(ROOT)} 合计 {total:,} bytes（{total/1024:.1f} KB）\n")


for k in (sys.argv[1:] or list(PAGES)):
    print(f"[{k}]")
    build(k)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把设计稿转成可独立运行的静态页面。

设计稿是设计工具导出的**规格件**：`<x-dc>` + `<helmet>` + `sc-if` + `{{ }}` 绑定 +
自带的 DCLogic 运行时。本脚本只做机械转换，不改一个字文案、不动一条样式：

  <sc-if value="{{ X }}">   →  <div data-if="X">      运行时切 display
  onClick="{{ h }}"         →  data-on-click="h"      运行时挂事件
  onSubmit / onInput        →  data-on-submit / -input
  style="{{ s }}"           →  data-style="s"         运行时写 cssText
  {{ v }}（文本位置）        →  <span data-txt="v"></span>

唯一一处刻意偏离设计稿的是**字体**：设计稿引 Google Fonts，
fonts.googleapis.com 在中国大陆不可达。目标用户是境内破产管理人，外链字体
不只是退化成系统字，`<link>` 还会阻塞首屏渲染直到超时。改走本地
`fonts/fonts.css`（由 `_build-fonts.py` 子集化生成）。

用法：
    python3 _build.py            # 全部重建
    python3 _build.py dn         # 只建首页

改完设计稿或运行时，重跑本脚本；如果改动引入了新汉字，**再跑一次
`_build-fonts.py`**，否则新字会掉回系统字体。
"""
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).parent
ROOT = SRC.parent

# key: (设计稿, 运行时, 产物)
# key: (设计稿, 运行时, 产物路径, 字体目录相对产物的位置)
TARGETS = {
    # 内测主页：整个 beta/ 目录可直接部署（index.html + fonts/）
    "dn":    ("design-dnhome.html", "runtime-dnhome.js", "beta/index.html", "./fonts/fonts.css"),
    # 备选发布页，暂不上线
    "pojiu": ("design-pojiu.html",  "runtime-pojiu.js",  "pojiu.html",      "./pojiu-fonts/fonts.css"),
}

FONT_NOTE = """
/* 本地字体。@font-face 见 fonts/fonts.css，由 _build-fonts.py 子集化生成。
   设计稿原本引 Google Fonts —— fonts.googleapis.com 在中国大陆不可达，
   而这个页面是给境内破产管理人看的，外链会阻塞首屏直到超时。
   「破局」用 Ma Shan Zheng 毛笔体，只子集了这两个字（约 1.8 KB）。 */
"""


def build(key: str) -> None:
    src_name, rt_name, out_name, fonts_href = TARGETS[key]
    raw = (SRC / src_name).read_text(encoding="utf-8")

    helmet = re.search(r"<helmet[^>]*>(.*?)</helmet>", raw, re.S).group(1)
    body = re.search(r"<body[^>]*>(.*)</body>", raw, re.S).group(1)
    body = re.sub(r"<helmet[^>]*>.*?</helmet>", "", body, flags=re.S)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = body.replace("<x-dc>", "").replace("</x-dc>", "").strip()

    title = re.search(r"<title>(.*?)</title>", helmet, re.S).group(1).strip()
    m = re.search(r'<meta name="description" content="([^"]*)"', helmet)
    desc = m.group(1) if m else ""
    style = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", helmet, re.S)).strip()
    # 设计稿自带的 Google Fonts @font-face 一律丢掉，改用本地子集
    style = re.sub(r"@font-face\s*\{[^}]*\}", "", style)

    # ---- 绑定转换 ----
    body = re.sub(r'<sc-if\s+value="\{\{\s*([\w.]+)\s*\}\}"[^>]*>',
                  lambda x: f'<div data-if="{x.group(1)}">', body)
    body = body.replace("</sc-if>", "</div>")
    for evt, attr in (("onClick", "click"), ("onSubmit", "submit"), ("onInput", "input")):
        body = re.sub(evt + r'="\{\{\s*([\w.]+)\s*\}\}"',
                      lambda x, a=attr: f'data-on-{a}="{x.group(1)}"', body)
    body = re.sub(r'style="\{\{\s*([\w.]+)\s*\}\}"',
                  lambda x: f'data-style="{x.group(1)}"', body)
    # 🟥 其余**属性位置**的绑定（disabled / value / placeholder …）必须在通用文本
    # 插值之前处理。漏了这条会掉进下面那条规则，生成
    #   disabled="<span data-txt="codeBusy"></span>"
    # —— 嵌套引号把属性提前闭合，按钮变成永久 disabled，点了毫无反应且不报错。
    # 这个 bug 真发生过（获取验证码按钮整个是死的），所以下面还有一道自检。
    body = re.sub(r'\s([a-zA-Z][\w-]*)="\{\{\s*([\w.]+)\s*\}\}"',
                  lambda x: f' data-bind-{x.group(1)}="{x.group(2)}"', body)
    body = re.sub(r"\{\{\s*([\w.]+)\s*\}\}",
                  lambda x: f'<span data-txt="{x.group(1)}"></span>', body)

    runtime = (SRC / rt_name).read_text(encoding="utf-8")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<link rel="stylesheet" href="{fonts_href}">
<style>{FONT_NOTE}
{style}
</style>
</head>
<body>
{body}
<script>
{runtime}
</script>
</body>
</html>
"""
    out = ROOT / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    left = html.count("{{")
    # 只查真外链（href/src/@import），不查注释里提到的域名——
    # 上面那段说明本身就写着 fonts.googleapis.com，按字面 grep 会自己绊自己。
    ext = re.findall(r'(?:href|src)="(https?://[^"]+)"|@import[^;]*?(https?://[^\s;\'"]+)', html)
    # 唯一白名单：ICP 备案号按工信部要求必须链到备案管理系统，不算"外链资源"。
    # 它不阻塞渲染、不加载任何资源，只是一个 <a>。
    ext = [e for e in ext if "beian.miit.gov.cn" not in (e[0] or e[1])]
    # 自检：`<span data-txt=...>` 绝不能出现在属性值里。出现即说明某条属性绑定
    # 没被上面的规则接住，生成了嵌套引号的坏标签（按钮会静默失效，不报错）。
    bad = re.findall(r'=\"[^\"]*<span data-txt', html)
    if bad:
        raise SystemExit(f"!! {out_name}: {len(bad)} 处属性绑定漏转换，生成了嵌套引号坏标签")
    # 报字节不报字符：UTF-8 下一个汉字 3 字节，报 len(str) 会跟 ls 对不上
    print(f"{out_name:<16} {len(html.encode('utf-8')):>8,} bytes  "
          f"if={html.count('data-if=')} click={html.count('data-on-click=')} "
          f"txt={html.count('data-txt=')} style={html.count('data-style=')}  "
          f"残留{{{{={left} 外链={len(ext)}")
    if left or ext:
        raise SystemExit(f"!! {out_name} 仍有未转换的绑定或外链资源：{ext[:3]}")


keys = sys.argv[1:] or list(TARGETS)
for k in keys:
    build(k)

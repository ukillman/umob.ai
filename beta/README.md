# DeepNirvana 内测主页

整个 `beta/` 目录就是可部署产物，直接 nginx 静态伺服即可，**不需要任何进程**。

```
beta/
  index.html                 页面（自包含，样式内联）
  fonts/
    ma-shan-zheng-400.woff2  「破局」两个字的毛笔体，1.6 KB
    fonts.css                @font-face
```

正文用 PingFang SC / 苹方 / 微软雅黑等系统字，不打包。全站唯一的字体依赖就是
那 1.6 KB 毛笔体——**不引 Google Fonts**，因为 fonts.googleapis.com 在中国大陆
不可达，而这个页面是给境内破产管理人看的，外链不只是字体退化，`<link>` 还会
阻塞首屏渲染直到超时。

## 改页面

**不要直接改 `index.html`** —— 它是生成物，下次构建会被覆盖。改这两处：

| 改什么 | 改哪个文件 |
|---|---|
| 版式、文案、结构 | `../_src/design-dnhome.html`（设计稿） |
| 交互逻辑、接口地址、名额数字 | `../_src/runtime-dnhome.js` |

改完重新构建：

```bash
python3 _src/build.py dn
/tmp/fontenv/bin/python _src/build-fonts.py dn
```

第二步在**文案里出现了新汉字时必须跑**，否则新字会掉回系统字体——同一段话里
两种字形，很显眼。字体工具链：

```bash
python3 -m venv /tmp/fontenv && /tmp/fontenv/bin/pip install fonttools brotli
```

## 接后端

`runtime-dnhome.js` 顶部：

```js
var ENDPOINTS = window.DN_APPLY_ENDPOINTS || { apply: null, sms: null, waitlist: null };
```

三个都是 `null` 时走前端模拟：表单能填、能校验、能走到成功页，但**不发任何
请求、不落库**。后端就位后填上真实路径即可，页面其余部分不用改。

计划中的三个端点（方案见 `优破案4.0-audit/`）：

- `POST /api/dn/invite/apply` —— 登记，匿名可访问
- `POST /api/dn/invite/apply/sms` —— 发验证码
- `POST /api/dn/invite/apply/waitlist` —— 非管理人候补名单

## 上线前还没做的

- 页面里 demo 那一屏的四条法条原文，需要罗师傅本人核一遍
- 检索轨迹里的「41 / 9」两个中间数是占位，要用真实回答替换
- 表单接口、admin 审核发码页
- CTA 目前不指向 dn 应用（罗师傅定：暂不放 DN 的 URL 和超链）

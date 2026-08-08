/* DeepNirvana 内测首页运行时。
 *
 * 设计稿自带的 DCLogic 是设计工具的运行时，不进生产。这里用原生 JS 复刻它的
 * 全部行为，计算逻辑与设计稿 `renderVals()` 逐条对齐，文案一字未改：
 *   · 引证面板 p1–p5 展开/收起（金色为采用，灰色删除线为已废止被排除）
 *   · 申请弹层四步：gate → form / wait → done / done-wait
 *   · 短信验证码 60 秒倒计时
 *
 * 与设计稿的差异只有一处，是刻意的：提交改为真调后端。设计稿只在前端置成功
 * 态（它是规格件，本来就不该带网络请求）。后端未就位时走本地模拟，形态照常
 * 能看；接口就位后把 ENDPOINTS 填上即可，其余代码不动。
 */
(function () {
  'use strict';

  /* 后端接口。null = 前端模拟（不发请求，直接置成功态）。
     后端就位后填真实路径即可，页面其余部分不用改。
     计划：POST /api/v1/beta-apply、/api/v1/beta-apply/sms、/api/v1/beta-apply/waitlist */
  var ENDPOINTS = window.DN_APPLY_ENDPOINTS || { apply: null, sms: null, waitlist: null };

  /* 首批名额。改这里就改页面上所有出现「5–10 位」的地方（共 3 处）。 */
  var BATCH = '5–10';

  /* 演示环境提示语。接上真短信网关后置 false。 */
  var DEMO_CODE = true;

  var CODE_BASE = 'padding:11px 15px;white-space:nowrap;background:none;font-size:13px;font-family:inherit;border-radius:2px;transition:all .2s;';
  var CODE_ON = CODE_BASE + 'border:1px solid #8A6A2F;color:#D4A24C;cursor:pointer;';
  var CODE_OFF = CODE_BASE + 'border:1px solid #1E2027;color:#71717A;opacity:.45;cursor:not-allowed;';

  var PICK = 'padding:10px 18px;background:none;font-size:13.5px;font-family:inherit;letter-spacing:.06em;cursor:pointer;transition:all .2s;';
  var PICK_ON = PICK + 'border:1px solid #D4A24C;color:#D4A24C;background:rgba(212,162,76,.08);';
  var PICK_OFF = PICK + 'border:1px solid #1E2027;color:#A1A1AA;';

  /* 图形验证码。罗师傅 2026-08-08 定的顺序：**先过图形，再发短信**。
   * 理由：匿名端点能直接触发真实短信 = SMS pumping 的教科书形态，一晚上能烧光
   * 短信预算；服务端校验的验证码把脚本挡在发短信之前，号码真实性与攻击面两头都保住。
   *
   * 这里只留挂载点。接入时把 window.DN_CAPTCHA 换成真实实现（腾讯云/阿里云验证码，
   * 境内可达）——必须是**服务端出题、服务端校验、一次性 ticket**；前端自绘那种
   * 「答案存在 JS 里」的改一行就绕过去了，等于没加。
   * 未接入时返回空 ticket，后端应据此拒发（不能默认放行）。 */
  var captcha = window.DN_CAPTCHA || { verify: function () { return Promise.resolve(''); } };

  var phoneOk = function (v) { return /^1[3-9]\d{9}$/.test(v); };

  /* 同一手机号最多发几次验证码（罗师傅 2026-08-08）。第 3 次直接让他换号。
   *
   * 🟥 前端这份计数**只是提示**——刷新页面就清零，绕不过任何有心人。
   * 真正的闸门必须在后端：按 mobile + scene='apply' 数 dn_sms_code 的行数。
   * 前端做它只是为了不让用户白等一次网络往返才看到"换个号码"。 */
  var MAX_SMS_PER_PHONE = 2;

  var state = {
    applyOpen: false,
    step: 'gate',
    panels: {},
    formErr: '',
    waitErr: '',
    left: 0,          // 验证码倒计时剩余秒
    codeSent: false,
    phone: '',
    cmax: '',         // 是否正在使用优破案：'yes' | 'no'
    sentCount: {},    // 手机号 → 本次会话已发次数
    busy: false       // 网络请求中
  };
  var timer = null;

  function vals() {
    var busy = state.left > 0;
    return {
      batch: BATCH,
      applyOpen: state.applyOpen,
      stepGate: state.step === 'gate',
      stepWait: state.step === 'wait',
      stepForm: state.step === 'form',
      stepDone: state.step === 'done',
      stepDoneWait: state.step === 'done-wait',
      codeBusy: busy,
      codeLabel: busy ? state.left + ' 秒后重发' : (state.codeSent ? '重新获取' : '获取验证码'),
      codeBtnStyle: busy ? CODE_OFF : CODE_ON,
      codeSent: state.codeSent,
      codeHint: DEMO_CODE ? '演示环境：验证码可填任意 6 位数字。' : '验证码已发送，5 分钟内有效。',
      cmaxYesStyle: state.cmax === 'yes' ? PICK_ON : PICK_OFF,
      cmaxNoStyle: state.cmax === 'no' ? PICK_ON : PICK_OFF,
      formErr: state.formErr,
      waitErr: state.waitErr,
      p1: !!state.panels.p1, p2: !!state.panels.p2, p3: !!state.panels.p3,
      p4: !!state.panels.p4, p5: !!state.panels.p5
    };
  }

  function toggle(id) { state.panels[id] = !state.panels[id]; render(); }

  /* 后端未就位时 fetch 一律短路成 resolve，形态照常能走完。 */
  function post(url, payload) {
    if (!url) return Promise.resolve();
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) { if (!r.ok) throw new Error('http ' + r.status); });
  }

  function sendCode() {
    if (state.busy) return;
    var phone = state.phone;
    if (!phoneOk(phone)) { state.formErr = '请先填写正确的 11 位手机号。'; return render(); }
    /* 上限检查必须排在倒计时之前：已经用满 2 次的人再点，应当当场看到
       「换个号码」，而不是一个毫无反应的按钮——那看起来像功能坏了。 */
    if ((state.sentCount[phone] || 0) >= MAX_SMS_PER_PHONE) {
      state.formErr = '这个号码已经发过 ' + MAX_SMS_PER_PHONE + ' 次验证码了，换一个手机号试试。';
      return render();
    }
    if (state.left > 0) return;          // 倒计时中，静默（按钮本身也是 disabled）
    state.formErr = '';
    state.busy = true; render();

    /* 顺序是刻意的：**先过图形验证码，再请求发短信**。
       验证码不通过就一条短信都不发，脚本刷不动。 */
    captcha.verify().then(function (ticket) {
      return post(ENDPOINTS.sms, { phone: phone, captcha_ticket: ticket });
    }).then(function () {
      state.sentCount[phone] = (state.sentCount[phone] || 0) + 1;
      state.codeSent = true;
      state.left = 60;
      clearInterval(timer);
      timer = setInterval(function () {
        state.left -= 1;
        if (state.left <= 0) { state.left = 0; clearInterval(timer); }
        render();
      }, 1000);
    }).catch(function (err) {
      // 后端是权威：它认为这个号超额了，就照它说的提示，不看前端计数
      var over = err && /\b429\b/.test(String(err.message || ''));
      state.formErr = over
        ? '这个号码已经发过 ' + MAX_SMS_PER_PHONE + ' 次验证码了，换一个手机号试试。'
        : '验证码没发出去，稍后再试一次。';
    }).then(function () { state.busy = false; render(); });
  }

  function submitApply(e) {
    e.preventDefault();
    if (state.busy) return;
    var f = e.target;
    var val = function (n) { var el = f.querySelector('[name=' + n + ']'); return el ? (el.value || '').trim() : ''; };
    var okBox = f.querySelector('[name=ok]');
    if (!val('name')) { state.formErr = '请填写姓名。'; return render(); }
    if (!val('org')) { state.formErr = '请填写所在机构。'; return render(); }
    if (!val('role')) { state.formErr = '请选择职位 · 角色。'; return render(); }
    if (!state.cmax) { state.formErr = '请选择是否正在使用优破案。'; return render(); }
    if (!phoneOk(val('phone'))) { state.formErr = '请填写正确的 11 位手机号。'; return render(); }
    if (!/^\d{6}$/.test(val('code'))) { state.formErr = '请填写 6 位短信验证码。'; return render(); }
    if (!okBox || !okBox.checked) { state.formErr = '请先阅读并勾选信息使用说明。'; return render(); }

    /* 蜜罐：这个输入框在视觉上被移出屏幕，真人看不见也不会填，脚本会照着
       name 属性填。填了就静默当成功——不告诉对方被识破了，否则等于教他怎么绕。
       后端要做同样的判断，前端这层照例只是省一次往返。 */
    var honey = f.querySelector('[name=website]');
    if (honey && honey.value.trim()) { state.step = 'done'; return render(); }

    state.formErr = '';
    state.busy = true; render();
    post(ENDPOINTS.apply, {
      name: val('name'), org: val('org'), role: val('role'),
      uses_cmax: state.cmax === 'yes', need: val('need'),
      phone: val('phone'), code: val('code'), is_administrator: true
    }).then(function () {
      clearInterval(timer);
      state.step = 'done'; state.left = 0; state.codeSent = false;
    }).catch(function () {
      state.formErr = '提交没成功，可能是网络问题。稍后再试一次。';
    }).then(function () { state.busy = false; render(); });
  }

  function submitWait(e) {
    e.preventDefault();
    if (state.busy) return;
    var el = e.target.querySelector('[name=phone]');
    var p = el ? (el.value || '').trim() : '';
    if (!phoneOk(p)) { state.waitErr = '请填写正确的 11 位手机号。'; return render(); }
    state.waitErr = '';
    state.busy = true; render();
    post(ENDPOINTS.waitlist, { phone: p }).then(function () {
      state.step = 'done-wait';
    }).catch(function () {
      state.waitErr = '提交没成功，稍后再试一次。';
    }).then(function () { state.busy = false; render(); });
  }

  var handlers = {
    openApply: function () { state.applyOpen = true; state.step = 'gate'; state.formErr = ''; state.waitErr = ''; render(); },
    closeApply: function () { state.applyOpen = false; render(); },
    stop: function (e) { e.stopPropagation(); },
    goForm: function () { state.step = 'form'; state.formErr = ''; render(); },
    goWait: function () { state.step = 'wait'; state.waitErr = ''; render(); },
    onPhone: function (e) { state.phone = e.target.value.trim(); },
    pickCmaxYes: function () { state.cmax = 'yes'; state.formErr = ''; render(); },
    pickCmaxNo: function () { state.cmax = 'no'; state.formErr = ''; render(); },
    sendCode: sendCode,
    submitApply: submitApply,
    submitWait: submitWait,
    toggleP1: function () { toggle('p1'); },
    toggleP2: function () { toggle('p2'); },
    toggleP3: function () { toggle('p3'); },
    toggleP4: function () { toggle('p4'); },
    toggleP5: function () { toggle('p5'); }
  };

  function render() {
    var v = vals();
    document.querySelectorAll('[data-txt]').forEach(function (n) {
      var t = v[n.getAttribute('data-txt')];
      n.textContent = (t === undefined || t === null) ? '' : String(t);
    });
    document.querySelectorAll('[data-if]').forEach(function (n) {
      n.style.display = v[n.getAttribute('data-if')] ? '' : 'none';
    });
    document.querySelectorAll('[data-style]').forEach(function (n) {
      var s = v[n.getAttribute('data-style')];
      if (typeof s === 'string') n.style.cssText = s;
    });
    /* 属性绑定（disabled 等）。布尔值按「有/无属性」处理——写
       disabled="false" 在 HTML 里仍然是禁用，必须整个移除属性。 */
    document.querySelectorAll('*').forEach(function (n) {
      for (var i = n.attributes.length - 1; i >= 0; i--) {
        var a = n.attributes[i];
        if (a.name.indexOf('data-bind-') !== 0) continue;
        var attr = a.name.slice('data-bind-'.length);
        var val = v[a.value];
        if (typeof val === 'boolean') {
          if (val) n.setAttribute(attr, '');
          else n.removeAttribute(attr);
        } else if (val !== undefined && val !== null) {
          n.setAttribute(attr, String(val));
        }
      }
    });
    document.querySelectorAll('[data-on-submit] button[type=submit]').forEach(function (b) {
      b.disabled = state.busy;
      b.style.opacity = state.busy ? '.55' : '';
    });
  }

  function bind() {
    ['click', 'submit', 'input'].forEach(function (evt) {
      document.querySelectorAll('[data-on-' + evt + ']').forEach(function (n) {
        var h = handlers[n.getAttribute('data-on-' + evt)];
        if (h) n.addEventListener(evt, h);
      });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && state.applyOpen) { state.applyOpen = false; render(); }
    });
    render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
})();

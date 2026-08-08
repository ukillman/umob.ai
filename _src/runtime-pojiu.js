/* 「破局」内测发布首页运行时。
 *
 * 设计稿自带的 DCLogic 是设计工具的运行时，不进生产。这里用原生 JS 复刻
 * 它的全部行为（倒计时 / 短信·邮箱切换 / 表单校验 / 登记成功态 / 弹层），
 * 计算逻辑与设计稿 `renderVals()` 逐条对齐，文案一字未改。
 *
 * 与设计稿的两处差异，都是刻意的：
 *  ① 提交改为真调后端 POST /api/v1/beta-signup（设计稿只在前端置成功态）。
 *     后端未就位时走 window.DN_SIGNUP_ENDPOINT = null 的本地模拟，
 *     便于先看形态；一旦填上真地址就自动切真请求。
 *  ② 联系方式做掩码后才显示（设计稿已有），另加提交中/失败态——
 *     真网络请求会失败，设计稿没有这个状态。
 */
(function () {
  'use strict';

  /* 内测发布时刻。改这里就改倒计时目标。 */
  var TARGET = new Date('2026-08-08T20:08:00+08:00').getTime();

  /* 后端登记接口。null = 前端模拟（不发请求，只走成功态）。
     接口就位后填 '/api/v1/beta-signup' 即可，其余代码不用动。 */
  var ENDPOINT = window.DN_SIGNUP_ENDPOINT || null;

  var TAB = 'padding:11px 22px;background:none;border:none;font-family:"Noto Serif SC","Songti SC",serif;font-size:14px;font-weight:300;letter-spacing:.14em;cursor:pointer;';
  var TAB_ON = TAB + 'background:rgba(199,167,109,.16);color:#e8dcc2;';
  var TAB_OFF = TAB + 'color:rgba(240,237,232,.5);';

  var state = {
    now: Date.now(),
    channel: 'sms',
    sentTo: '',
    error: '',
    modalOpen: false,
    busy: false
  };

  var pad = function (n) { return String(Math.max(0, Math.floor(n))).padStart(2, '0'); };

  function vals() {
    var diff = TARGET - state.now;
    var live = diff > 0;
    var cd = live
      ? { d: pad(diff / 86400000), h: pad((diff / 3600000) % 24), m: pad((diff / 60000) % 60), s: pad((diff / 1000) % 60), note: '距 DeepNirvana 内测发布' }
      : { d: '00', h: '00', m: '00', s: '00', note: 'DeepNirvana 内测已发布' };
    var sms = state.channel === 'sms';
    return {
      'cd.d': cd.d, 'cd.h': cd.h, 'cd.m': cd.m, 'cd.s': cd.s, 'cd.note': cd.note,
      showCountdown: live,
      genFourLine: 'DeepNirvana 引擎内测开放，与 4.0 同期。',
      engineLead: 'DeepNirvana™️（破局）是优破案团队打造的破产实务引擎，归属 Umob.AI。做优破案的这支团队，把十年在管理人现场攒下的办案口径写进了它——从接管到终结，一条完整的程序线。',
      sent: !!state.sentTo,
      notSent: !state.sentTo,
      sentMsg: '收到了，谢谢您。邀请码会发到 ' + state.sentTo + '，之后有人和您联系。用起来哪里别扭，直接告诉我们。',
      hasError: !!state.error,
      error: state.error,
      contactLabel: sms ? '手机号' : '邮箱',
      contactHint: sms ? '138 0000 0000' : 'name@firm.com',
      smsStyle: sms ? TAB_ON : TAB_OFF,
      mailStyle: sms ? TAB_OFF : TAB_ON,
      modalOpen: state.modalOpen
    };
  }

  var handlers = {
    openModal: function () { state.modalOpen = true; state.error = ''; render(); },
    closeModal: function () { state.modalOpen = false; render(); },
    pickSms: function () { state.channel = 'sms'; state.error = ''; render(); },
    pickMail: function () { state.channel = 'mail'; state.error = ''; render(); },
    reset: function () { state.sentTo = ''; state.error = ''; render(); },
    stop: function (e) { e.stopPropagation(); },
    submit: submit
  };

  function mask(contact, sms) {
    return sms
      ? contact.slice(0, 3) + '****' + contact.slice(7)
      : contact.replace(/^(.{2}).*(@.*)$/, '$1***$2');
  }

  function submit(e) {
    e.preventDefault();
    if (state.busy) return;
    var f = e.target;
    var name = ((f.querySelector('[name=name]') || {}).value || '').trim();
    var org = ((f.querySelector('[name=org]') || {}).value || '').trim();
    var pain = ((f.querySelector('[name=pain]') || {}).value || '').trim();
    var contact = ((f.querySelector('[name=contact]') || {}).value || '').trim();
    var sms = state.channel === 'sms';

    if (!name) { state.error = '请留个称呼，我们好称呼您。'; return render(); }
    var ok = sms ? /^1[3-9]\d{9}$/.test(contact) : /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact);
    if (!ok) { state.error = sms ? '请填写 11 位手机号。' : '请填写可用的邮箱地址。'; return render(); }

    state.error = '';
    if (!ENDPOINT) {                       // 后端未就位：只走形态
      state.sentTo = mask(contact, sms);
      return render();
    }
    state.busy = true; render();
    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, org: org, pain: pain, channel: state.channel, contact: contact })
    }).then(function (r) {
      if (!r.ok) throw new Error('http ' + r.status);
      state.sentTo = mask(contact, sms);
    }).catch(function () {
      state.error = '提交没成功，可能是网络问题。稍后再试一次，或直接扫码联系我们。';
    }).then(function () {
      state.busy = false; render();
    });
  }

  function render() {
    var v = vals();
    document.querySelectorAll('[data-txt]').forEach(function (n) {
      var k = n.getAttribute('data-txt');
      var t = v[k];
      n.textContent = (t === undefined || t === null) ? '' : String(t);
    });
    document.querySelectorAll('[data-if]').forEach(function (n) {
      n.style.display = v[n.getAttribute('data-if')] ? '' : 'none';
    });
    document.querySelectorAll('[data-style]').forEach(function (n) {
      var s = v[n.getAttribute('data-style')];
      if (typeof s === 'string') n.style.cssText = s;
    });
    /* placeholder 跟着通道切换（设计稿里是 contactHint） */
    var c = document.querySelector('[name=contact]');
    if (c) {
      c.setAttribute('placeholder', v.contactHint);
      c.setAttribute('inputmode', state.channel === 'sms' ? 'numeric' : 'email');
    }
    document.querySelectorAll('[data-on-submit] button[type=submit]').forEach(function (b) {
      b.disabled = state.busy;
      b.style.opacity = state.busy ? '.55' : '';
    });
  }

  function bind() {
    document.querySelectorAll('[data-on-click]').forEach(function (n) {
      var h = handlers[n.getAttribute('data-on-click')];
      if (h) n.addEventListener('click', h);
    });
    document.querySelectorAll('[data-on-submit]').forEach(function (n) {
      var h = handlers[n.getAttribute('data-on-submit')];
      if (h) n.addEventListener('submit', h);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && state.modalOpen) { state.modalOpen = false; render(); }
    });
    setInterval(function () { state.now = Date.now(); render(); }, 1000);
    render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
})();

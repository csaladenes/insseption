
(function () {
  var KEY_RE = /^[A-Za-z0-9_\\-]{0,80}$/, PH = 'YOUR_KEY', T = window.INSSE_T || {};
  var store = function (kind) { try { return window[kind]; } catch (x) { return null; } };
  var get = function (kind, k) { try { return store(kind).getItem(k); } catch (x) { return null; } };
  var put = function (kind, k, v) { try { store(kind).setItem(k, v); } catch (x) {} };
  var blocks = Array.prototype.slice.call(document.querySelectorAll('.code pre code'));
  blocks.forEach(function (c) { c.setAttribute('data-src', c.textContent); });
  var key = '';
  function paint() {
    blocks.forEach(function (c) {
      c.textContent = c.getAttribute('data-src').split(PH).join(key || PH);
      c.removeAttribute('data-highlighted');
      if (window.hljs && c.className.indexOf('language-') >= 0) { try { hljs.highlightElement(c); } catch (x) {} }
    });
    document.querySelectorAll('a[data-keyed]').forEach(function (a) {
      var u = a.getAttribute('data-url');
      a.href = key ? u + (u.indexOf('?') >= 0 ? '&' : '?') + 'api_key=' + encodeURIComponent(key) : u;
      a.title = key ? T.title_with_key : T.title_no_key;
    });
  }
  function lang(l) {
    document.querySelectorAll('.tabs button').forEach(function (b) {
      b.setAttribute('aria-selected', b.getAttribute('data-lang') === l ? 'true' : 'false');
    });
    document.querySelectorAll('.variants').forEach(function (v) {
      var own = v.querySelector('.code[data-lang="' + l + '"]'), first = v.querySelector('.code');
      v.querySelectorAll('.code').forEach(function (c) { c.hidden = c !== (own || first); });
      var note = v.querySelector('.only'); if (note) note.hidden = !!own;
    });
    put('localStorage', 'insse-docs-lang', l);
  }
  document.querySelectorAll('.tabs button').forEach(function (b) {
    b.addEventListener('click', function () { lang(b.getAttribute('data-lang')); });
  });
  var input = document.getElementById('key');
  if (input) {
    key = get('sessionStorage', 'insse-docs-key') || '';
    if (!KEY_RE.test(key)) key = '';
    input.value = key;
    input.addEventListener('input', function () {
      var v = input.value.trim();
      if (!KEY_RE.test(v)) { input.setCustomValidity(T.key_invalid); input.reportValidity(); return; }
      input.setCustomValidity(''); key = v; put('sessionStorage', 'insse-docs-key', v); paint();
    });
  }
  document.querySelectorAll('.code .copy').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = b.parentNode.querySelector('code').textContent;
      var done = function () { b.textContent = T.copied; setTimeout(function () { b.textContent = T.copy; }, 1600); };
      if (navigator.clipboard) navigator.clipboard.writeText(t).then(done, function () {});
    });
  });
  var f = document.getElementById('dsfilter');
  if (f) f.addEventListener('input', function () {
    var q = f.value.toLowerCase();
    document.querySelectorAll('table.catalogue tbody tr').forEach(function (r) {
      r.style.display = r.textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
    });
  });
  var links = Array.prototype.slice.call(document.querySelectorAll('aside.toc a'));
  var targets = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
  function spy() {
    var on = 0;
    targets.forEach(function (t, i) { if (t && t.getBoundingClientRect().top < 160) on = i; });
    links.forEach(function (a, i) { a.classList.toggle('on', i === on); });
  }
  window.addEventListener('scroll', spy, { passive: true });
  var sw = document.querySelector('details.lang-switch');
  if (sw) document.addEventListener('click', function (ev) { if (!sw.contains(ev.target)) sw.open = false; });
  if (sw) document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') sw.open = false; });
  lang(get('localStorage', 'insse-docs-lang') || 'curl');
  paint(); spy();
})();

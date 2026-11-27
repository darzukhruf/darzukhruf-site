/* يضيف مصدر الزيارة (من رابط البايو/البن) لنص رسالة واتساب الجاهزة — بلا كوكيز ولا تتبع خارجي */
/* عدّ زيارات نسخة github.io: طلب صورة SVG صغيرة موجودة أصلاً من darzukhruf.netlify.app؛ المرجع (الصفحة وutm) يظهر في إحصاءات Netlify. بلا كوكيز ولا بيانات شخصية */
(function(){
  try {
    if (!/github\.io$/.test(location.hostname)) return;
    var k = 'dz_px_' + location.pathname;
    try { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1'); } catch (e) {}
    var i = new Image();
    i.referrerPolicy = 'unsafe-url';
    i.src = 'https://darzukhruf.netlify.app/favicon.svg?gh=1';
    /* عدّاد مجهول مقروء (27-11، الـ CEO): Netlify ما يسجّل طلبات البكسل، فنعدّ بعدّاد عام بلا كوكيز (اسم الصفحة + المصدر فقط). يقراه site-health.yml يومياً */
    var pg = (location.pathname.split('/').pop() || 'index').replace(/\.html$/, '').replace(/[^\w\-]/g, '').slice(0, 30) || 'index';
    var sr = '';
    try { sr = (new URLSearchParams(location.search).get('utm_source') || '').replace(/[^\w\-]/g, '').slice(0, 20); } catch (e) {}
    var C = 'https://abacus.jasoncameron.dev/hit/darzukhruf/';
    var hit = function(key){ try { fetch(C + key, {mode: 'no-cors', keepalive: true}); } catch (e) {} };
    hit('pg-' + pg); hit('src-' + (sr || 'none')); hit('all-views');
  } catch (e) {}
})();
(function(){
  var s = '';
  try {
    var q = new URLSearchParams(location.search);
    s = (q.get('utm_source') || q.get('ref') || '').replace(/[^\w.\-]/g, '').slice(0, 24);
    try { if (s) sessionStorage.setItem('dz_src', s); else s = sessionStorage.getItem('dz_src') || ''; } catch (e) {}
  } catch (e) {}
  /* E-50 (20-11): بلا utm على github.io = زائر بحث قوقل/مباشر — نوسم باسم الصفحة عشان نعرف من وين جت المحادثة */
  if (!s && /github\.io$/.test(location.hostname)) {
    var pg = (location.pathname.split('/').pop() || 'index').replace(/\.html$/, '').replace(/[^\w\-]/g, '').slice(0, 20) || 'index';
    s = 'gh-' + pg;
  }
  if (!s) return;
  var tag = '\n[مصدر: ' + s + ']';
  /* عدّاد نقرات واتساب: طلب favicon صغير من Netlify عند الضغط (نفس آلية البكسل، بلا كوكيز ولا بيانات شخصية) */
  document.addEventListener('click', function(ev){
    try {
      var a = ev.target.closest && ev.target.closest('a[href*="wa.me/966578771717"]');
      if (!a) return;
      var im = new Image(); im.referrerPolicy = 'unsafe-url';
      im.src = 'https://darzukhruf.netlify.app/favicon.svg?wa=' + encodeURIComponent(s) + '&t=' + Date.now();
      if (/github\.io$/.test(location.hostname)) { try { fetch('https://abacus.jasoncameron.dev/hit/darzukhruf/wa-' + s.replace(/[^\w\-]/g, '').slice(0, 30), {mode: 'no-cors', keepalive: true}); } catch (e) {} }
    } catch (e) {}
  }, true);
  var links = document.querySelectorAll('a[href^="https://wa.me/966578771717"]');
  for (var i = 0; i < links.length; i++) {
    var a = links[i], h = a.getAttribute('href');
    if (h.indexOf('text=') > -1) { if (h.indexOf(encodeURIComponent(tag)) < 0) a.setAttribute('href', h + encodeURIComponent(tag)); }
    else a.setAttribute('href', h + '?text=' + encodeURIComponent('السلام عليكم، أبي أصمم مساحتي' + tag));
  }
  /* الرابط الذي يبنيه نموذج الطلب عند النجاح */
  var f = document.getElementById('f-wa');
  if (f) new MutationObserver(function(){ var h = f.getAttribute('href'); if (h.indexOf(encodeURIComponent('[مصدر:')) < 0 && h.indexOf('text=') > -1) f.setAttribute('href', h + encodeURIComponent(tag)); }).observe(f, {attributes: true, attributeFilter: ['href']});
})();

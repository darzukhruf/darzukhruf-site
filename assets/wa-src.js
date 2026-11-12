/* يضيف مصدر الزيارة (من رابط البايو/البن) لنص رسالة واتساب الجاهزة — بلا كوكيز ولا تتبع خارجي */
(function(){
  var s = '';
  try {
    var q = new URLSearchParams(location.search);
    s = (q.get('utm_source') || q.get('ref') || '').replace(/[^\w.\-]/g, '').slice(0, 24);
    try { if (s) sessionStorage.setItem('dz_src', s); else s = sessionStorage.getItem('dz_src') || ''; } catch (e) {}
  } catch (e) {}
  if (!s) return;
  var tag = '\n[مصدر: ' + s + ']';
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

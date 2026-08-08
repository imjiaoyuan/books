// Registers the service worker and wires the "offline download" button.
// __CACHE_VERSION__ is replaced at build time (git short SHA) by epub2html.py.
(function () {
  'use strict';
  var CACHE = 'bookshelf-__CACHE_VERSION__';

  // baseDir = directory containing this script = site root.
  // Resolved from the script's own URL so it works under any subpath
  // (e.g. user.github.io/repo/), no hardcoded "/".
  var me = document.currentScript;
  var baseDir = me ? new URL('.', me.src).href : location.href;

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker
        .register(new URL('sw.js', baseDir).href, { scope: baseDir })
        .catch(function () { /* offline feature unavailable, ignore */ });
    });
  }

  var btn = document.getElementById('dl-offline');
  if (!btn || !('caches' in window)) return;
  var folder = btn.getAttribute('data-folder');
  var total = parseInt(btn.getAttribute('data-total'), 10) || 0;
  if (!folder || !total) return;

  btn.addEventListener('click', function () {
    btn.disabled = true;
    var done = 0;
    btn.textContent = '缓存中 0/' + total;

    caches.open(CACHE).then(function (cache) {
      var chapters = [];
      for (var i = 1; i <= total; i++) {
        chapters.push(baseDir + 'books/' + folder + '/chapters/' + i + '.html');
      }
      var progress = function () { btn.textContent = '缓存中 ' + done + '/' + total; };
      var add = function (u) {
        return cache.add(u).then(
          function () { done++; },
          function () { done++; } // tolerate a missing chapter, keep going
        ).then(progress);
      };
      return Promise.all(chapters.map(add)).then(function () {
        // also cache this book's TOC + the bookshelf so offline nav doesn't break
        return Promise.all([
          cache.add(baseDir + 'books/' + folder + '/index.html').catch(function () {}),
          cache.add(baseDir + 'index.html').catch(function () {}),
        ]);
      });
    }).then(function () {
      btn.textContent = '✓ 已离线 (' + total + ' 章)';
      btn.disabled = false;
    }, function () {
      btn.textContent = '下载失败，请重试';
      btn.disabled = false;
    });
  });
})();

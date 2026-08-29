// Registers the service worker and wires the "offline download" button.
// __CACHE_VERSION__ is replaced at build time (git short SHA) by epub2html.py.
(function () {
  'use strict';
  var CACHE = 'bookshelf-__CACHE_VERSION__';
  var CONCURRENCY = 6;

  // baseDir = directory containing this script = site root.
  // Resolved from the script's own URL so it works under any subpath
  // (e.g. user.github.io/repo/), no hardcoded "/".
  var me = document.currentScript;
  var baseDir = me ? new URL('.', me.src).href : location.href;

  // Without a service worker nothing serves the cache offline, so the
  // download button is useless (some in-app browsers have caches but no SW).
  var swBroken = false;
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker
        .register(new URL('sw.js', baseDir).href, { scope: baseDir })
        .catch(function () { swBroken = true; });
    });
  }

  var btn = document.getElementById('dl-offline');
  if (!btn) return;

  if (!('caches' in window) || !('serviceWorker' in navigator)) {
    btn.disabled = true;
    btn.textContent = 'Unsupported';
    return;
  }

  var folder = btn.getAttribute('data-folder');
  var total = parseInt(btn.getAttribute('data-total'), 10) || 0;
  if (!folder || !total) return;

  btn.addEventListener('click', function () {
    if (swBroken) {
      btn.disabled = true;
      btn.textContent = 'Unsupported';
      return;
    }
    var urls = [];
    for (var i = 1; i <= total; i++) {
      urls.push(baseDir + 'books/' + folder + '/chapters/' + i + '.html');
    }
    // also cache this book's TOC + the bookshelf so offline nav doesn't break
    urls.push(baseDir + 'books/' + folder + '/index.html');
    urls.push(baseDir + 'index.html');

    btn.disabled = true;
    btn.textContent = 'Saving 0/' + urls.length;
    caches.open(CACHE).then(function (cache) {
      return downloadAll(cache, urls);
    }).then(function (failed) {
      btn.textContent = failed > 0 ? 'Failed (' + failed + '), retry' : 'Saved ✓';
      btn.disabled = false;
    }, function () {
      btn.textContent = 'Failed, retry';
      btn.disabled = false;
    });
  });

  // Small worker pool: firing hundreds of fetches at once stalls or kills
  // the tab on phones. Skips URLs already cached, so a retry only
  // re-downloads what failed.
  function downloadAll(cache, urls) {
    var failed = 0;
    var done = 0;
    var next = 0;
    function worker() {
      if (next >= urls.length) return Promise.resolve();
      var i = next++;
      return cache.match(urls[i]).then(function (hit) {
        if (hit) return;
        return cache.add(urls[i]).then(null, function () { failed++; });
      }).then(function () {
        done++;
        btn.textContent = 'Saving ' + done + '/' + urls.length;
        return worker();
      });
    }
    var workers = [];
    for (var w = 0; w < Math.min(CONCURRENCY, urls.length); w++) {
      workers.push(worker());
    }
    return Promise.all(workers).then(function () { return failed; });
  }
})();

(function () {
  'use strict';
  var LS = window.localStorage;

  // ---------------------------------------------------------------
  //  1) Klappbare Sidebar (Baum-Knoten + ganze Leiste)
  // ---------------------------------------------------------------
  function loadSet(key) {
    try { return new Set(JSON.parse(LS.getItem(key) || '[]')); }
    catch (e) { return new Set(); }
  }
  function saveSet(key, set) {
    try { LS.setItem(key, JSON.stringify(Array.from(set))); } catch (e) {}
  }

  var collapsedKey = 'wiki.collapsedNodes';
  var collapsed = loadSet(collapsedKey);

  function initTree() {
    // gespeicherte eingeklappte Knoten anwenden
    document.querySelectorAll('.tnode[data-key]').forEach(function (node) {
      if (collapsed.has(node.getAttribute('data-key'))) node.classList.add('collapsed');
    });
    // Pfad zur aktiven Seite immer aufklappen
    var active = document.querySelector('.sidebar a.active');
    if (active) {
      var el = active.closest('.tnode');
      while (el) { el.classList.remove('collapsed'); el = el.parentElement.closest('.tnode'); }
    }
    // Klick auf Pfeil = auf/zuklappen
    document.querySelectorAll('.sidebar .ttoggle').forEach(function (tog) {
      tog.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation();
        var node = tog.closest('.tnode');
        if (!node) return;
        node.classList.toggle('collapsed');
        var key = node.getAttribute('data-key');
        if (node.classList.contains('collapsed')) collapsed.add(key); else collapsed.delete(key);
        saveSet(collapsedKey, collapsed);
      });
    });
  }

  function initSidebarToggle() {
    if (LS.getItem('wiki.sidebarCollapsed') === '1') document.body.classList.add('sidebar-collapsed');
    var btn = document.getElementById('sidebar-toggle');
    if (btn) btn.addEventListener('click', function () {
      var on = document.body.classList.toggle('sidebar-collapsed');
      try { LS.setItem('wiki.sidebarCollapsed', on ? '1' : '0'); } catch (e) {}
    });
  }

  // ---------------------------------------------------------------
  //  2) Schnellsuche / Command-Palette (Strg+K)
  // ---------------------------------------------------------------
  function initPalette() {
    var overlay = document.getElementById('palette');
    if (!overlay) return;
    var input = document.getElementById('palette-input');
    var list = document.getElementById('palette-results');
    var url = (document.currentScript && document.currentScript.getAttribute('data-quickfind'))
              || document.querySelector('script[data-quickfind]').getAttribute('data-quickfind');
    var items = [], sel = -1, timer = null;

    function open() {
      overlay.hidden = false;
      input.value = ''; list.innerHTML = ''; items = []; sel = -1;
      setTimeout(function () { input.focus(); }, 10);
    }
    function close() { overlay.hidden = true; }
    window.__openPalette = open;

    function render() {
      list.innerHTML = '';
      items.forEach(function (it, i) {
        var li = document.createElement('li');
        li.className = 'pres' + (i === sel ? ' sel' : '');
        li.innerHTML = '<span class="pres-title"></span><span class="pres-space"></span>';
        li.querySelector('.pres-title').textContent = it.title;
        li.querySelector('.pres-space').textContent = it.space;
        li.addEventListener('mousedown', function (e) { e.preventDefault(); go(it); });
        list.appendChild(li);
      });
    }
    function go(it) { if (it && it.url) window.location.href = it.url; }

    function search(q) {
      if (!q) { items = []; sel = -1; render(); return; }
      fetch(url + '?q=' + encodeURIComponent(q), { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) { items = d.results || []; sel = items.length ? 0 : -1; render(); })
        .catch(function () {});
    }

    input.addEventListener('input', function () {
      clearTimeout(timer);
      var q = input.value.trim();
      timer = setTimeout(function () { search(q); }, 150);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (items.length) { sel = (sel + 1) % items.length; render(); } }
      else if (e.key === 'ArrowUp') { e.preventDefault(); if (items.length) { sel = (sel - 1 + items.length) % items.length; render(); } }
      else if (e.key === 'Enter') { e.preventDefault(); if (sel >= 0) go(items[sel]); }
      else if (e.key === 'Escape') { close(); }
    });
    overlay.addEventListener('mousedown', function (e) { if (e.target === overlay) close(); });

    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        if (overlay.hidden) open(); else close();
      }
    });
  }

  // ---------------------------------------------------------------
  //  3) Inhaltsverzeichnis (aus Ueberschriften der Seite)
  // ---------------------------------------------------------------
  function slugify(s) {
    return s.toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/[\s_]+/g, '-') || 'abschnitt';
  }
  function initToc() {
    var content = document.getElementById('page-content');
    var toc = document.getElementById('page-toc');
    if (!content || !toc) return;
    var heads = content.querySelectorAll('h2, h3');
    if (heads.length < 3) return;   // lohnt sich erst ab 3
    var ul = toc.querySelector('ul');
    var used = {};
    heads.forEach(function (h) {
      if (!h.id) {
        var base = slugify(h.textContent), id = base, n = 2;
        while (used[id] || document.getElementById(id)) { id = base + '-' + n; n++; }
        h.id = id;
      }
      used[h.id] = true;
      var li = document.createElement('li');
      li.className = 'toc-' + h.tagName.toLowerCase();
      var a = document.createElement('a');
      a.href = '#' + h.id; a.textContent = h.textContent;
      li.appendChild(a); ul.appendChild(li);
    });
    toc.hidden = false;
    document.querySelector('.page-body').classList.add('has-toc');

    // aktiven Abschnitt beim Scrollen hervorheben
    if ('IntersectionObserver' in window) {
      var links = {};
      toc.querySelectorAll('a').forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            toc.querySelectorAll('a.active').forEach(function (a) { a.classList.remove('active'); });
            if (links[en.target.id]) links[en.target.id].classList.add('active');
          }
        });
      }, { rootMargin: '-80px 0px -70% 0px' });
      heads.forEach(function (h) { obs.observe(h); });
    }
  }

  // ---------------------------------------------------------------
  //  4) Design-Umschalter (System / Hell / Dunkel)
  // ---------------------------------------------------------------
  function initTheme() {
    var btn = document.getElementById('theme-toggle');
    var order = ['system', 'light', 'dark'];
    var icon = { system: '🌓', light: '☀️', dark: '🌙' };
    var label = { system: 'System', light: 'Hell', dark: 'Dunkel' };
    function get() { try { return LS.getItem('wiki.theme') || 'system'; } catch (e) { return 'system'; } }
    function apply(mode) {
      if (mode === 'dark' || mode === 'light') document.documentElement.setAttribute('data-theme', mode);
      else document.documentElement.removeAttribute('data-theme');
      if (btn) {
        btn.textContent = icon[mode];
        btn.title = 'Design: ' + label[mode] + ' – klicken zum Wechseln';
      }
    }
    apply(get());
    if (btn) btn.addEventListener('click', function () {
      var next = order[(order.indexOf(get()) + 1) % order.length];
      try { LS.setItem('wiki.theme', next); } catch (e) {}
      apply(next);
    });
  }

  // ---------------------------------------------------------------
  //  5) Drag & Drop im Seitenbaum (umhaengen / verschieben)
  // ---------------------------------------------------------------
  function initDnD() {
    var script = document.querySelector('script[data-move]');
    if (!script) return;
    var MOVE = script.getAttribute('data-move');
    var CSRF = script.getAttribute('data-csrf');
    var dragged = null;

    function clearOver() {
      document.querySelectorAll('.trow.drop-into').forEach(function (r) { r.classList.remove('drop-into'); });
    }

    document.querySelectorAll('.sidebar .trow').forEach(function (row) {
      var node = row.closest('.tnode');
      if (row.getAttribute('draggable') === 'true') {
        row.addEventListener('dragstart', function (e) {
          dragged = node; row.classList.add('dragging');
          e.dataTransfer.effectAllowed = 'move';
          try { e.dataTransfer.setData('text/plain', node.getAttribute('data-key') || ''); } catch (_) {}
        });
        row.addEventListener('dragend', function () { row.classList.remove('dragging'); clearOver(); dragged = null; });
      }
      row.addEventListener('dragover', function (e) {
        if (!dragged || node === dragged) return;
        e.preventDefault(); e.dataTransfer.dropEffect = 'move';
        clearOver(); row.classList.add('drop-into');
      });
      row.addEventListener('dragleave', function () { row.classList.remove('drop-into'); });
      row.addEventListener('drop', function (e) {
        e.preventDefault(); row.classList.remove('drop-into');
        if (!dragged || node === dragged) return;
        var payload = {
          kind: dragged.getAttribute('data-kind'),
          id: parseInt(dragged.getAttribute('data-id'), 10),
          ref_kind: node.getAttribute('data-kind'),
          ref_id: parseInt(node.getAttribute('data-id'), 10)
        };
        fetch(MOVE, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
          credentials: 'same-origin',
          body: JSON.stringify(payload)
        })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (res.ok) { location.reload(); }
          else { alert('Verschieben nicht möglich: ' + (res.d.error || 'Fehler')); }
        })
        .catch(function () { alert('Verschieben fehlgeschlagen (Netzwerk).'); });
      });
    });
  }

  // ---------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initTree();
    initSidebarToggle();
    initPalette();
    initToc();
    initTheme();
    initDnD();
  });
})();

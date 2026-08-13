/* Helpers compartilhados entre as páginas do frontend novo — extraídos dos
   protótipos (contagem animada, curva suave, tooltip, reveal on-scroll,
   relógio, glow que segue o cursor, toast, e um cliente fetch pequeno). */

const LifeOS = (() => {
  "use strict";
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const fmt = n => Math.round(n).toLocaleString('pt-BR');

  function countUp(el, to, opts) {
    opts = opts || {};
    const from = parseFloat(el.dataset.raw || 0);
    const format = opts.format || (v => fmt(v));
    if (reduced) { el.textContent = format(to); el.dataset.raw = to; return; }
    const dur = opts.dur || 800;
    const start = performance.now();
    function tick(t) {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = from + (to - from) * eased;
      el.textContent = format(val);
      if (p < 1) requestAnimationFrame(tick); else { el.dataset.raw = to; el.textContent = format(to); }
    }
    requestAnimationFrame(tick);
  }

  function catmullRom(points) {
    if (points.length < 2) return '';
    let d = `M ${points[0][0].toFixed(1)},${points[0][1].toFixed(1)} `;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i - 1] || points[i], p1 = points[i], p2 = points[i + 1], p3 = points[i + 2] || p2;
      const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
      const c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += `C ${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)} `;
    }
    return d;
  }

  function showTT(el, x, y, html) { el.innerHTML = html; el.classList.add('show'); el.style.left = x + 'px'; el.style.top = y + 'px'; }
  function hideTT(el) { el.classList.remove('show'); }

  function initReveal(selector) {
    const els = document.querySelectorAll(selector || '[data-reveal]');
    if (reduced || !('IntersectionObserver' in window)) { els.forEach(el => el.classList.add('in')); return; }
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: .12 });
    els.forEach(el => io.observe(el));
  }

  /* "YYYY-MM-DD" da data LOCAL de um Date (não Date.toISOString(), que
     converte pra UTC primeiro — vira o dia seguinte depois das 21h no
     fuso do Brasil, UTC-3). */
  function isoLocal(d) {
    const dt = d || new Date();
    const m = String(dt.getMonth() + 1).padStart(2, '0');
    const day = String(dt.getDate()).padStart(2, '0');
    return `${dt.getFullYear()}-${m}-${day}`;
  }

  /* Atalhos de período usados pelos pills "hoje"/"ontem"/"esta semana" em
     todas as páginas que filtram por data — cada página mantém seu próprio
     periodoIso() pros demais casos (mês/ano/tudo/personalizado variam de
     comportamento entre elas), só delega os 3 atalhos novos pra cá. */
  function periodoRapido(periodo) {
    const hoje = new Date();
    const fim = isoLocal(hoje);
    if (periodo === 'hoje') return { inicio: fim, fim };
    if (periodo === 'ontem') {
      const o = new Date(hoje);
      o.setDate(o.getDate() - 1);
      const iso = isoLocal(o);
      return { inicio: iso, fim: iso };
    }
    if (periodo === 'semana') {
      const dow = hoje.getDay(); // dom=0
      const diff = dow === 0 ? 6 : dow - 1; // volta até segunda-feira
      const i = new Date(hoje);
      i.setDate(i.getDate() - diff);
      return { inicio: isoLocal(i), fim };
    }
    return null;
  }

  function initClock(elId) {
    const el = document.getElementById(elId || 'clock');
    if (!el) return;
    const tick = () => { el.textContent = new Date().toLocaleTimeString('pt-BR'); };
    tick(); setInterval(tick, 1000);
  }

  function initGlow(elId) {
    if (reduced) return;
    const blob = document.getElementById(elId || 'glowBlob');
    if (!blob) return;
    let raf = null, tx = 0, ty = 0;
    window.addEventListener('mousemove', e => {
      tx = e.clientX; ty = e.clientY;
      if (!raf) raf = requestAnimationFrame(() => { blob.style.left = tx + 'px'; blob.style.top = ty + 'px'; raf = null; });
    });
  }

  function initSegmented(containerId, onChange) {
    const wrap = document.getElementById(containerId);
    if (!wrap) return;
    const thumb = wrap.querySelector('.thumb');
    const btns = [...wrap.querySelectorAll('button')];
    const place = el => { thumb.style.left = el.offsetLeft + 'px'; thumb.style.width = el.offsetWidth + 'px'; };
    btns.forEach(b => b.addEventListener('click', () => {
      btns.forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      place(b);
      onChange(b.dataset.val);
    }));
    requestAnimationFrame(() => place(wrap.querySelector('button.active') || btns[0]));
    window.addEventListener('resize', () => place(wrap.querySelector('button.active') || btns[0]));
  }

  function initPills(containerId, onChange) {
    const pills = [...document.querySelectorAll(`#${containerId} .pill`)];
    pills.forEach(p => p.addEventListener('click', () => {
      if (p.classList.contains('active')) return;
      pills.forEach(x => x.classList.remove('active'));
      p.classList.add('active');
      onChange(p.dataset.val);
    }));
  }

  const MODULES = [
    { key: 'musica', label: 'Música', href: '/musica/estatisticas.html' },
    { key: 'livros', label: 'Livros', href: '/livros/estante.html' },
    { key: 'habitos', label: 'Hábitos', href: '/habitos/habitos.html' },
    { key: 'projetos', label: 'Projetos', href: '/projetos/projetos.html' },
    { key: 'humor', label: 'Humor', href: '/humor/humor.html' },
    { key: 'timeline', label: 'Timeline', href: '/timeline/timeline.html' },
    { key: 'analytics', label: 'Analytics', href: '/analytics/analytics.html' },
    { key: 'financeiro', label: 'Financeiro', href: '/financeiro/gastos.html' },
  ];

  /* Transforma o primeiro ".id" do .topbar (o rótulo "LIFEOS · MÓDULO X")
     num botão que abre um dropdown com todos os módulos — sem precisar
     editar o HTML de cada página, só chamar isso uma vez no final do
     script de cada uma. */
  function initModuleSwitcher(activeKey) {
    const trigger = document.querySelector('.topbar .id');
    if (!trigger || trigger.dataset.modSwitchInit) return;
    trigger.dataset.modSwitchInit = '1';
    trigger.classList.add('mod-switch-trigger');
    trigger.insertAdjacentHTML('beforeend', ' <span class="mod-switch-chevron">▾</span>');

    const wrap = document.createElement('div');
    wrap.className = 'mod-switch';
    trigger.parentNode.insertBefore(wrap, trigger);
    wrap.appendChild(trigger);

    const menu = document.createElement('div');
    menu.className = 'mod-switch-menu';
    menu.innerHTML = MODULES.map(m => m.href
      ? `<a href="${m.href}" class="${m.key === activeKey ? 'active' : ''}"><span class="msm-dot"></span>${m.label}</a>`
      : `<a class="disabled"><span class="msm-dot"></span>${m.label}<span style="margin-left:auto;font-size:.64rem;color:var(--ink-dim);">em breve</span></a>`
    ).join('') + `<hr/><a href="/" class="mod-switch-back">← todos os módulos</a>`;
    wrap.appendChild(menu);

    trigger.addEventListener('click', e => { e.stopPropagation(); wrap.classList.toggle('open'); });
    document.addEventListener('click', () => wrap.classList.remove('open'));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') wrap.classList.remove('open'); });
  }

  function initWheelScrollX(el) {
    if (!el) return;
    el.addEventListener('wheel', e => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    }, { passive: false });
  }

  function initTableToggles() {
    document.querySelectorAll('.tbl-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const t = document.getElementById(btn.dataset.target);
        if (!t) return;
        const hidden = t.hasAttribute('hidden');
        if (hidden) { t.removeAttribute('hidden'); btn.textContent = 'gráfico'; }
        else { t.setAttribute('hidden', ''); btn.textContent = 'tabela'; }
      });
    });
  }

  let toastTimer = null;
  function toast(msg, isError) {
    let el = document.getElementById('lifeosToast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'lifeosToast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.toggle('error', !!isError);
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
  }

  async function api(path, opts) {
    opts = opts || {};
    const res = await fetch(path, opts);
    if (!res.ok) {
      let msg = `Erro ${res.status}`;
      try { const body = await res.json(); if (body.detail) msg = body.detail; } catch (e) { /* corpo não era JSON */ }
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  return {
    reduced, fmt, countUp, catmullRom, showTT, hideTT, isoLocal, periodoRapido,
    initReveal, initClock, initGlow, initSegmented, initPills, initTableToggles, initModuleSwitcher, initWheelScrollX,
    toast, api,
  };
})();

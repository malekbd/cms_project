/* ═══════════════════════════════════════════════════════════════════════════
   FRC CMS & TICKETS ADMIN PANEL — JavaScript
   ═══════════════════════════════════════════════════════════════════════════ */

// ─── Modal Management ───────────────────────────────────────────────────────

function openModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.remove('open');
    document.body.style.overflow = '';
  }
}

// Close on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
    document.body.style.overflow = '';
  }
});

// Close on ESC
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => {
      m.classList.remove('open');
    });
    document.body.style.overflow = '';
  }
});


// ─── Status Dropdown ────────────────────────────────────────────────────────

function toggleStatusMenu(btn, pk) {
  const menu = document.getElementById(`menu-${pk}`);
  document.querySelectorAll('.status-menu.show').forEach(m => {
    if (m !== menu) m.classList.remove('show');
  });
  menu.classList.toggle('show');
  event.stopPropagation();
}

document.addEventListener('click', () => {
  document.querySelectorAll('.status-menu.show').forEach(m => m.classList.remove('show'));
});


// ─── Toast Notification ─────────────────────────────────────────────────────

function showToast(msg, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `alert alert-${type}`;
  toast.style.cssText = 'position:fixed; top:20px; right:24px; z-index:9999; min-width:280px; max-width:400px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);';
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  toast.innerHTML = `${icon} <span>${msg}</span>`;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = '0.4s';
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}


// ─── CSRF Cookie Helper ─────────────────────────────────────────────────────

function getCookie(name) {
  let value = null;
  document.cookie.split(';').forEach(c => {
    const [k, v] = c.trim().split('=');
    if (k === name) value = decodeURIComponent(v);
  });
  return value;
}


// ─── Live Clock ─────────────────────────────────────────────────────────────

function updateClock() {
  const el = document.getElementById('liveTime');
  if (el) {
    const now = new Date();
    const opts = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true };
    el.textContent = now.toLocaleTimeString('en-US', opts);
  }
}

setInterval(updateClock, 1000);
updateClock();


// ─── Auto-dismiss Alerts ────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    const alerts = document.getElementById('alertsContainer');
    if (alerts) {
      alerts.style.transition = 'opacity 0.5s';
      alerts.style.opacity = '0';
      setTimeout(() => alerts.remove(), 500);
    }
  }, 5000);
});


// ─── Chart Renderers ────────────────────────────────────────────────────────

/**
 * Render a vertical bar chart
 */
function renderBarChart(containerId, labels, values, color = '#3b82f6', showLabels = true) {
  const container = document.getElementById(containerId);
  const points = labels.map((label, i) => ({
    label: String(label ?? ''),
    value: Number(values[i]) || 0,
  }));

  if (!container || points.length === 0 || !points.some(point => point.value > 0)) {
    if (container) container.innerHTML = '<p style="color:var(--text3); font-size:13px; text-align:center; padding:40px; width:100%;">No data available</p>';
    return;
  }

  const formatNumber = value => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
  const escapeHtml = value => String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const niceStep = value => {
    if (value <= 0) return 1;
    const power = Math.pow(10, Math.floor(Math.log10(value)));
    const fraction = value / power;
    const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
    return niceFraction * power;
  };

  const maxVal = Math.max(...points.map(point => point.value), 1);
  const tickStep = Math.max(1, niceStep(maxVal / 4));
  const axisMax = Math.max(tickStep, Math.ceil(maxVal / tickStep) * tickStep);
  const ticks = [];
  for (let tick = axisMax; tick >= 0 && ticks.length < 7; tick -= tickStep) {
    ticks.push(Math.max(0, Math.round(tick)));
  }
  if (ticks[ticks.length - 1] !== 0) ticks.push(0);

  const softColor = color.startsWith('#') ? `${color}99` : color;
  const shadowColor = color.startsWith('#') ? `${color}33` : 'rgba(59, 130, 246, 0.2)';
  const gridRows = ticks.map(tick => `
    <div class="vchart-grid-row">
      <span>${formatNumber(tick)}</span>
      <i></i>
    </div>
  `).join('');

  container.innerHTML = `
    <div class="vchart" style="--chart-columns:${points.length}; --bar-color:${color}; --bar-color-soft:${softColor}; --bar-shadow:${shadowColor};">
      <div class="vchart-grid">${gridRows}</div>
      <div class="vchart-plot">
        ${points.map(point => {
          const height = point.value > 0 ? Math.max((point.value / axisMax) * 100, 3) : 0;
          const label = escapeHtml(point.label);
          return `
            <div class="chart-col">
              <div class="chart-bar-wrap">
                ${point.value > 0 ? `<span class="chart-value" style="bottom:calc(${height}% + 8px);">${formatNumber(point.value)}</span>` : ''}
                <div class="chart-bar-v" style="height:${height}%;"></div>
                <div class="chart-tooltip">${label}: ${formatNumber(point.value)}</div>
              </div>
              ${showLabels ? `<div class="chart-label" title="${label}">${label}</div>` : ''}
            </div>
          `;
        }).join('')}
      </div>
    </div>
  `;

  requestAnimationFrame(() => {
    container.querySelectorAll('.chart-bar-v').forEach((bar, i) => {
      const h = bar.style.height;
      bar.style.height = '0%';
      setTimeout(() => { bar.style.height = h; }, i * 45);
    });
  });
}

/**
 * Render horizontal bar chart
 */
function renderHorizontalBars(containerId, data, color = '#8b5cf6') {
  const container = document.getElementById(containerId);
  if (!container || data.length === 0) {
    if (container) container.innerHTML = '<p style="color:var(--text3); font-size:13px; text-align:center; padding:24px;">No data available</p>';
    return;
  }

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const maxVal = Math.max(...data.map(d => Number(d.value) || 0), 1);

  container.innerHTML = data.map(d => {
    const label = escapeHtml(d.label);
    const value = Number(d.value) || 0;
    const width = (value / maxVal * 100).toFixed(1);
    return `
      <div class="hbar-item">
        <div class="hbar-head">
          <span class="hbar-name" title="${label}">${label}</span>
          <span class="hbar-count">${value}</span>
        </div>
        <div class="hbar-track">
          <div class="hbar-fill" style="width: 0%; background: linear-gradient(90deg, ${color}, ${color}88);" data-width="${width}%"></div>
        </div>
      </div>
    `;
  }).join('');

  // Animate fills
  requestAnimationFrame(() => {
    setTimeout(() => {
      container.querySelectorAll('.hbar-fill').forEach(fill => {
        fill.style.width = fill.dataset.width;
      });
    }, 100);
  });
}

/**
 * Render donut chart using SVG
 */
function renderDonut(chartId, legendId, data) {
  const chartEl = document.getElementById(chartId);
  const legendEl = document.getElementById(legendId);
  if (!chartEl || !legendEl) return;

  const svg = chartEl.querySelector('.donut-svg');
  if (!svg) return;

  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (total === 0) {
    svg.innerHTML = '<circle cx="60" cy="60" r="48" fill="none" stroke="var(--border)" stroke-width="10"/>';
    legendEl.innerHTML = '<p style="color:var(--text3); font-size:12px;">No data</p>';
    return;
  }

  const cx = 60, cy = 60, r = 48;
  const circumference = 2 * Math.PI * r;
  let offset = 0;
  let paths = '';
  let legend = '';

  data.forEach(d => {
    if (d.value === 0) return;
    const pct = d.value / total;
    const dashLen = circumference * pct;
    const dashGap = circumference - dashLen;

    paths += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
      stroke="${d.color}" stroke-width="12"
      stroke-dasharray="${dashLen} ${dashGap}"
      stroke-dashoffset="${-offset}"
      style="transition: stroke-dasharray 0.8s ease, stroke-dashoffset 0.8s ease;"
    />`;

    offset += dashLen;

    legend += `
      <div class="legend-item">
        <div class="legend-dot" style="background: ${d.color};"></div>
        <span class="legend-text">${d.label}</span>
        <span class="legend-val">${d.value}</span>
      </div>
    `;
  });

  svg.innerHTML = paths;
  legendEl.innerHTML = legend;
}


// ─── Sidebar Mobile Close on Navigation ─────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('sidebar');
  if (sidebar && window.innerWidth <= 900) {
    sidebar.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', () => {
        sidebar.classList.remove('open');
      });
    });
  }
});


// ─── Animated Counter for Stat Values ───────────────────────────────────────

function animateCounters() {
  document.querySelectorAll('.stat-value, .highlight-value, .donut-value').forEach(el => {
    const rawValue = el.textContent.trim();
    const suffix = rawValue.endsWith('%') ? '%' : '';
    const target = parseFloat(rawValue);
    if (isNaN(target)) return;

    const isFloat = rawValue.includes('.');
    const duration = 1200;
    const startTime = performance.now();

    el.textContent = `0${suffix}`;

    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = eased * target;
      el.textContent = `${isFloat ? current.toFixed(1) : Math.round(current)}${suffix}`;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setTimeout(animateCounters, 200);
});


// SN hover details rendered on body to avoid table overflow clipping
document.addEventListener('DOMContentLoaded', () => {
  const hoverCards = document.querySelectorAll('.sn-hover-card');
  if (!hoverCards.length) return;

  const floating = document.createElement('div');
  floating.className = 'sn-floating-popover';
  document.body.appendChild(floating);

  let activeCard = null;

  const positionFloating = card => {
    if (!card) return;

    const trigger = card.querySelector('.sn-trigger');
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const margin = 12;
    const width = floating.offsetWidth || 310;
    const height = floating.offsetHeight || 190;

    let left = rect.left;
    let top = rect.bottom + margin;
    let arrowLeft = 18;

    if (left + width > window.innerWidth - margin) {
      left = Math.max(margin, window.innerWidth - width - margin);
      arrowLeft = Math.min(width - 26, rect.left - left + rect.width / 2);
    }

    if (top + height > window.innerHeight - margin) {
      top = Math.max(margin, rect.top - height - margin);
      floating.style.transformOrigin = 'bottom left';
      floating.style.setProperty('--sn-arrow-top', 'auto');
      floating.style.setProperty('--sn-arrow-bottom', '-6px');
    } else {
      floating.style.transformOrigin = 'top left';
      floating.style.setProperty('--sn-arrow-top', '-6px');
      floating.style.setProperty('--sn-arrow-bottom', 'auto');
    }

    floating.style.left = `${left}px`;
    floating.style.top = `${top}px`;
    floating.style.setProperty('--sn-arrow-left', `${arrowLeft}px`);
  };

  const showFloating = card => {
    const template = card.querySelector('.sn-popover');
    if (!template) return;

    activeCard = card;
    floating.innerHTML = template.innerHTML;
    floating.classList.add('show');
    positionFloating(card);
  };

  const hideFloating = () => {
    activeCard = null;
    floating.classList.remove('show');
  };

  hoverCards.forEach(card => {
    card.addEventListener('mouseenter', () => showFloating(card));
    card.addEventListener('mouseleave', hideFloating);
  });

  window.addEventListener('scroll', () => {
    if (activeCard) positionFloating(activeCard);
  }, true);

  window.addEventListener('resize', () => {
    if (activeCard) positionFloating(activeCard);
  });
});

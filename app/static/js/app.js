/* ============================================================
   CurioSync — Frontend JS
   Theme management, HTMX events, toasts, counters, shortcuts
   ============================================================ */

(function () {
  'use strict';

  /* —————————————————————————————————————————————
     1. Theme Management
     ————————————————————————————————————————————— */
  const THEME_KEY = 'theme';

  function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  }

  function getStoredTheme() {
    return localStorage.getItem(THEME_KEY);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    updateToggleIcon(theme);
  }

  function updateToggleIcon(theme) {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.textContent = theme === 'dark' ? '☀️' : '🌙';
    btn.setAttribute('aria-label',
      theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  }

  function initTheme() {
    const stored = getStoredTheme();
    applyTheme(stored || getSystemTheme());
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || getSystemTheme();
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  }

  // Listen for system theme changes (real-time sync when no stored pref)
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!getStoredTheme()) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });

  /* —————————————————————————————————————————————
     2. Toast Notifications
     ————————————————————————————————————————————— */
  const TOAST_DURATION = 4000;

  const TOAST_ICONS = {
    success: '✅',
    error: '❌',
    info: 'ℹ️',
    warning: '⚠️',
  };

  const TOAST_TITLES = {
    success: 'Success',
    error: 'Error',
    info: 'Info',
    warning: 'Warning',
  };

  /**
   * Show a toast notification.
   * @param {string} message - The message to display
   * @param {'success'|'error'|'info'|'warning'} type - Toast variant
   * @param {number} [duration] - Auto-dismiss ms (0 = manual close only)
   */
  function showToast(message, type = 'info', duration = TOAST_DURATION) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span class="toast__icon">${TOAST_ICONS[type] || 'ℹ️'}</span>
      <div class="toast__content">
        <div class="toast__title">${TOAST_TITLES[type] || 'Notice'}</div>
        <div class="toast__message">${escapeHtml(message)}</div>
      </div>
      <button class="toast__close" aria-label="Dismiss">&times;</button>
    `;

    // Close button
    toast.querySelector('.toast__close').addEventListener('click', () => {
      dismissToast(toast);
    });

    container.appendChild(toast);

    // Auto-dismiss
    if (duration > 0) {
      setTimeout(() => dismissToast(toast), duration);
    }
  }

  function dismissToast(el) {
    if (!el || el.classList.contains('toast--removing')) return;
    el.classList.add('toast--removing');
    el.addEventListener('animationend', () => el.remove());
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Expose globally for inline use and HTMX event handlers
  window.showToast = showToast;

  /* —————————————————————————————————————————————
     3. HTMX Event Listeners
     ————————————————————————————————————————————— */
  document.addEventListener('htmx:afterSwap', function (evt) {
    // Check for flash messages embedded as a meta element in the swapped content
    const flashEl = evt.detail.target.querySelector('[data-flash]');
    if (flashEl) {
      const msg = flashEl.getAttribute('data-flash');
      const type = flashEl.getAttribute('data-flash-type') || 'success';
      showToast(msg, type);
      flashEl.remove();
    }
  });

  document.addEventListener('htmx:responseError', function (evt) {
    const status = evt.detail.xhr?.status;
    let msg = 'Something went wrong. Please try again.';

    if (status === 401) {
      msg = 'Session expired. Please sign in again.';
    } else if (status === 403) {
      msg = 'You don\'t have permission to do that.';
    } else if (status === 429) {
      msg = 'Too many requests. Please wait a moment.';
    } else if (status >= 500) {
      msg = 'Server error. Our team has been notified.';
    }

    showToast(msg, 'error');
  });

  // Show a subtle indicator when HTMX requests are in-flight
  document.addEventListener('htmx:beforeRequest', function (evt) {
    const trigger = evt.detail.elt;
    if (trigger && trigger.classList.contains('btn')) {
      trigger.classList.add('btn--loading');
    }
  });

  document.addEventListener('htmx:afterRequest', function (evt) {
    const trigger = evt.detail.elt;
    if (trigger && trigger.classList.contains('btn')) {
      trigger.classList.remove('btn--loading');
    }
  });

  /* —————————————————————————————————————————————
     4. Character & Word Count for Draft Textarea
     ————————————————————————————————————————————— */
  function updateDraftCounts() {
    const textarea = document.getElementById('draft-textarea');
    if (!textarea) return;

    const text = textarea.value || '';
    const charCount = text.length;
    const wordCount = text.trim() === '' ? 0 : text.trim().split(/\s+/).length;

    const charEl = document.querySelector('.char-count');
    const wordEl = document.querySelector('.word-count');

    if (charEl) charEl.textContent = charCount.toLocaleString();
    if (wordEl) wordEl.textContent = wordCount.toLocaleString();

    // LinkedIn character limit warning (3000 chars)
    if (charCount > 3000) {
      charEl?.parentElement?.classList.add('text-warning');
    } else {
      charEl?.parentElement?.classList.remove('text-warning');
    }
  }

  function initDraftCounter() {
    const textarea = document.getElementById('draft-textarea');
    if (textarea) {
      textarea.addEventListener('input', updateDraftCounts);
      updateDraftCounts(); // initial count
    }
  }

  // Re-init counts when draft partial is swapped in by HTMX
  document.addEventListener('htmx:afterSwap', function (evt) {
    if (evt.detail.target.id === 'draft-content' ||
        evt.detail.target.closest?.('#draft-content')) {
      initDraftCounter();
    }
  });

  /* —————————————————————————————————————————————
     5. Publish Confirmation
     ————————————————————————————————————————————— */
  // HTMX has built-in hx-confirm which native modal handles automatically.

  /* —————————————————————————————————————————————
     6. Keyboard Shortcuts
     ————————————————————————————————————————————— */
  document.addEventListener('keydown', function (e) {
    // Ctrl+Enter or Cmd+Enter → Publish
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      const publishBtn = document.getElementById('publish-btn');
      if (publishBtn && !publishBtn.disabled) {
        e.preventDefault();
        if (confirm('Publish this post to LinkedIn?')) {
          publishBtn.click();
        }
      }
    }
  });

  /* —————————————————————————————————————————————
     7. Smooth Scroll to Sections
     ————————————————————————————————————————————— */
  function scrollToSection(sectionId) {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  window.scrollToSection = scrollToSection;

  /* —————————————————————————————————————————————
     8. Auto-refresh scheduler (fallback for HTMX)
     ————————————————————————————————————————————— */
  // The scheduler panel uses hx-trigger="load, every 60s" so this is
  // a JS fallback in case the element is dynamically added after load.
  function ensureSchedulerRefresh() {
    const panel = document.getElementById('scheduler-info');
    if (panel && !panel.hasAttribute('data-refresh-init')) {
      panel.setAttribute('data-refresh-init', 'true');
      // HTMX handles the polling; just mark as initialised
    }
  }

  /* —————————————————————————————————————————————
     9. DOM Ready
     ————————————————————————————————————————————— */
  document.addEventListener('DOMContentLoaded', function () {
    // Theme
    initTheme();

    // Theme toggle button
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggleTheme);
    }

    // Draft counter
    initDraftCounter();

    // Scheduler
    ensureSchedulerRefresh();

    // Smooth-scroll nav links
    document.querySelectorAll('a[href^="#"]').forEach(function (link) {
      link.addEventListener('click', function (e) {
        const target = this.getAttribute('href').slice(1);
        if (target) {
          e.preventDefault();
          scrollToSection(target);
        }
      });
    });
  });
})();

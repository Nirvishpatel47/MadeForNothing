// MADE FOR NOTHING - Professional Editorial Interactions

(function() {
  'use strict';

  var STORAGE_KEY = 'mfn_theme';
  var root = document.documentElement;

  // --- Theme Management ---
  function getSystemTheme() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function getStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) || getSystemTheme();
    } catch (e) {
      return getSystemTheme();
    }
  }

  function applyTheme(theme) {
    if (theme === 'dark') {
      root.setAttribute('data-theme', 'dark');
    } else {
      root.removeAttribute('data-theme');
    }
    updateToggleUI(theme);
  }

  function updateToggleUI(theme) {
    var label = document.getElementById('theme-label');
    var btn = document.getElementById('theme-toggle');
    if (label) {
      label.textContent = theme === 'dark' ? 'Light' : 'Dark';
    }
    if (btn) {
      btn.setAttribute('aria-label', 'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' mode');
      btn.setAttribute('title', 'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' mode');
    }
  }

  // --- GPU-Accelerated Reading Progress Bar ---
  function setupReadingProgress() {
    var progressBar = document.getElementById('reading-progress-bar');
    if (!progressBar) return;

    var article = document.querySelector('.post-article') || document.querySelector('.detail-article');
    if (!article) {
      progressBar.style.display = 'none';
      return;
    }

    var ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        window.requestAnimationFrame(function() {
          var articleTop = article.offsetTop;
          var articleHeight = article.offsetHeight;
          var windowHeight = window.innerHeight;
          var scrollTop = window.scrollY || window.pageYOffset;

          var totalScrollable = articleHeight - windowHeight + 100;
          if (totalScrollable > 0) {
            var progress = ((scrollTop - articleTop) / totalScrollable);
            progress = Math.max(0, Math.min(1, progress));
            progressBar.style.transform = 'scaleX(' + progress + ')';
          } else {
            progressBar.style.transform = 'scaleX(0)';
          }
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // --- Code Block Copy Button ---
  function setupCodeCopy() {
    var preBlocks = document.querySelectorAll('.content-body pre, .detail-body pre');
    preBlocks.forEach(function(pre) {
      if (pre.querySelector('.copy-code-btn')) return;

      var btn = document.createElement('button');
      btn.className = 'copy-code-btn';
      btn.type = 'button';
      btn.textContent = 'Copy';
      btn.setAttribute('aria-label', 'Copy code snippet to clipboard');

      btn.addEventListener('click', function() {
        var originalWidth = btn.getBoundingClientRect().width;
        btn.style.width = originalWidth + 'px';

        var code = pre.querySelector('code');
        var text = code ? code.innerText : pre.innerText;

        navigator.clipboard.writeText(text).then(function() {
          btn.textContent = 'Copied!';
          setTimeout(function() {
            btn.textContent = 'Copy';
            btn.style.width = '';
          }, 2000);
        }).catch(function() {
          btn.textContent = 'Failed';
          setTimeout(function() {
            btn.textContent = 'Copy';
            btn.style.width = '';
          }, 2000);
        });
      });

      pre.appendChild(btn);
    });
  }

  // --- Responsive Table Wrappers ---
  function setupTableWrappers() {
    var tables = document.querySelectorAll('.content-body table, .detail-body table');
    tables.forEach(function(table) {
      if (!table.parentElement.classList.contains('table-wrap')) {
        var wrapper = document.createElement('div');
        wrapper.className = 'table-wrap';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
      }
    });
  }

  // --- Newsletter Subscription Handler (With Live Feedback) ---
  function setupNewsletter() {
    var form = document.getElementById('newsletter-form');
    if (!form) return;

    var input = document.getElementById('newsletter-email');
    var btn = document.getElementById('newsletter-btn');
    var msg = document.getElementById('newsletter-msg');

    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      var email = (input.value || '').trim();

      // Clear previous states
      msg.className = 'newsletter-feedback';
      msg.textContent = '';

      if (!email || !email.includes('@')) {
        msg.className = 'newsletter-feedback error';
        msg.textContent = 'Please provide a valid email address.';
        input.focus();
        return;
      }

      btn.disabled = true;
      btn.innerText = 'Sending...';

      try {
        var response = await fetch('/api/newsletter/subscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({ email: email })
        });

        var data = await response.json();

        if (response.ok && data.success) {
          if (data.status === 'added') {
            msg.className = 'newsletter-feedback success';
            msg.textContent = '✓ ' + (data.message || 'Subscribed successfully.');
            input.value = '';
          } else if (data.status === 'already_subscribed') {
            msg.className = 'newsletter-feedback notice';
            msg.textContent = '• ' + (data.message || 'This email is already registered.');
          }
        } else {
          msg.className = 'newsletter-feedback error';
          msg.textContent = (data && data.detail) ? data.detail : 'Unable to subscribe. Please try again.';
        }
      } catch (err) {
        msg.className = 'newsletter-feedback error';
        msg.textContent = 'Network error. Please check your connection.';
      } finally {
        btn.disabled = false;
        btn.innerText = 'Subscribe';
      }
    });
  }

  // --- Initialize on DOMContentLoaded ---
  document.addEventListener('DOMContentLoaded', function() {
    var currentTheme = root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    updateToggleUI(currentTheme);

    var toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', function() {
        var isDark = root.getAttribute('data-theme') === 'dark';
        var nextTheme = isDark ? 'light' : 'dark';
        try {
          localStorage.setItem(STORAGE_KEY, nextTheme);
        } catch (e) {}
        applyTheme(nextTheme);
      });
    }

    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!localStorage.getItem(STORAGE_KEY)) {
          applyTheme(e.matches ? 'dark' : 'light');
        }
      });
    }

    setupReadingProgress();
    setupCodeCopy();
    setupTableWrappers();
    setupNewsletter();
  });
})();
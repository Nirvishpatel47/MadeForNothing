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

  // --- GPU-Accelerated Reading Progress Bar (transform: scaleX) ---
  function setupReadingProgress() {
    var progressBar = document.getElementById('reading-progress-bar');
    if (!progressBar) return;

    var article = document.querySelector('.post-article');
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
            // Animate via scaleX to force GPU acceleration and eliminate layout thrashing
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

  // --- Code Block Copy Button with Layout Jitter Prevention ---
  function setupCodeCopy() {
    var preBlocks = document.querySelectorAll('.content-body pre');
    preBlocks.forEach(function(pre) {
      if (pre.querySelector('.copy-code-btn')) return;

      var btn = document.createElement('button');
      btn.className = 'copy-code-btn';
      btn.type = 'button';
      btn.textContent = 'Copy';
      btn.setAttribute('aria-label', 'Copy code snippet to clipboard');

      btn.addEventListener('click', function() {
        // Freeze calculated width to prevent layout jitter during state transition
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
    var tables = document.querySelectorAll('.content-body table');
    tables.forEach(function(table) {
      if (!table.parentElement.classList.contains('table-wrap')) {
        var wrapper = document.createElement('div');
        wrapper.className = 'table-wrap';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
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
  });
})();

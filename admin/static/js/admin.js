// MADE FOR NOTHING - Local Admin Interactions

document.addEventListener('DOMContentLoaded', function() {
  'use strict';

  // --- Auto-generate Slug ---
  const titleInput = document.getElementById('title');
  const slugInput = document.getElementById('slug');
  const isEditMode = document.body.dataset.mode === 'edit';

  if (titleInput && slugInput && !isEditMode) {
    titleInput.addEventListener('input', function() {
      if (!slugInput.dataset.manual) {
        slugInput.value = generateSlug(titleInput.value);
      }
    });

    slugInput.addEventListener('input', function() {
      slugInput.dataset.manual = 'true';
    });
  }

  function generateSlug(text) {
    return text
      .toString()
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '-')           // Replace spaces with -
      .replace(/[^\w\-]+/g, '')       // Remove all non-word chars
      .replace(/\-\-+/g, '-')         // Replace multiple - with single -
      .replace(/^-+/, '')             // Trim - from start of text
      .replace(/-+$/, '');            // Trim - from end of text
  }

  // --- Live Markdown Preview with 500ms Debounce & Loading State ---
  const markdownTextarea = document.getElementById('content_markdown');
  const previewPane = document.getElementById('markdown-preview');

  let previewTimeout = null;
  function updatePreview() {
    if (!markdownTextarea || !previewPane) return;
    const text = markdownTextarea.value;
    if (!text.trim()) {
      previewPane.innerHTML = '<em>Preview will render here as you write...</em>';
      return;
    }

    // Visual loading state confirming background processing
    previewPane.style.opacity = '0.5';

    fetch('/api/preview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ markdown: text })
    })
    .then(response => response.json())
    .then(data => {
      previewPane.innerHTML = data.html || '';
    })
    .catch(err => {
      console.error('Preview fetch error:', err);
    })
    .finally(() => {
      previewPane.style.opacity = '1';
    });
  }

  if (markdownTextarea && previewPane) {
    // Initial render
    updatePreview();

    // 500ms debounce to prevent redundant requests during fast typing
    markdownTextarea.addEventListener('input', function() {
      clearTimeout(previewTimeout);
      previewTimeout = setTimeout(updatePreview, 500);
    });

    // --- Synchronized Scrolling ---
    let isSyncingTextarea = false;
    let isSyncingPreview = false;

    markdownTextarea.addEventListener('scroll', function() {
      if (!isSyncingTextarea) {
        isSyncingPreview = true;
        const maxScrollText = markdownTextarea.scrollHeight - markdownTextarea.clientHeight;
        const maxScrollPreview = previewPane.scrollHeight - previewPane.clientHeight;
        if (maxScrollText > 0 && maxScrollPreview > 0) {
          const scrollRatio = markdownTextarea.scrollTop / maxScrollText;
          previewPane.scrollTop = scrollRatio * maxScrollPreview;
        }
      }
      isSyncingTextarea = false;
    });

    previewPane.addEventListener('scroll', function() {
      if (!isSyncingPreview) {
        isSyncingTextarea = true;
        const maxScrollText = markdownTextarea.scrollHeight - markdownTextarea.clientHeight;
        const maxScrollPreview = previewPane.scrollHeight - previewPane.clientHeight;
        if (maxScrollText > 0 && maxScrollPreview > 0) {
          const scrollRatio = previewPane.scrollTop / maxScrollPreview;
          markdownTextarea.scrollTop = scrollRatio * maxScrollText;
        }
      }
      isSyncingPreview = false;
    });
  }

  // --- Keyboard Shortcut (Ctrl+S / Cmd+S) to Save Post ---
  document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      const form = document.querySelector('form');
      if (form) {
        e.preventDefault();
        if (validateForm(form)) {
          form.submit();
        }
      }
    }
  });

  // --- External Links Dynamic Rows & Validation ---
  const linksContainer = document.getElementById('external-links-container');
  const addLinkBtn = document.getElementById('add-link-btn');

  if (linksContainer && addLinkBtn) {
    addLinkBtn.addEventListener('click', function() {
      const row = document.createElement('div');
      row.className = 'link-row';
      row.innerHTML = `
        <input type="text" name="link_title[]" placeholder="Link Title / Source" class="form-control">
        <input type="url" name="link_url[]" placeholder="https://..." class="form-control url-input">
        <button type="button" class="btn btn-danger btn-sm remove-link-btn" aria-label="Remove link">&times;</button>
      `;
      linksContainer.appendChild(row);
      attachRemoveHandler(row.querySelector('.remove-link-btn'));
    });

    linksContainer.querySelectorAll('.remove-link-btn').forEach(function(btn) {
      attachRemoveHandler(btn);
    });
  }

  function attachRemoveHandler(btn) {
    if (!btn) return;
    btn.addEventListener('click', function() {
      const row = btn.closest('.link-row');
      if (row) {
        row.remove();
      }
    });
  }

  // --- Form Validation (Validates http:// or https:// for external links) ---
  function validateForm(form) {
    const urlInputs = form.querySelectorAll('input[name="link_url[]"]');
    for (let i = 0; i < urlInputs.length; i++) {
      const val = urlInputs[i].value.trim();
      if (val && !/^https?:\/\//i.test(val)) {
        alert('External link URL must begin with http:// or https://: ' + val);
        urlInputs[i].focus();
        return false;
      }
    }
    return true;
  }

  const postForm = document.querySelector('form');
  if (postForm) {
    postForm.addEventListener('submit', function(e) {
      if (!validateForm(postForm)) {
        e.preventDefault();
      }
    });
  }
});

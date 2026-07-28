// Scroll-reveal: elements with class "reveal-up" fade + slide up into view
// the first time they cross into the viewport. Cards inside the same grid
// row get a small staggered delay so they don't all pop at once.
document.addEventListener("DOMContentLoaded", () => {
  const revealEls = document.querySelectorAll(".reveal-up:not(.in-view)");

  // Assign a stagger index per parent container so siblings cascade in.
  const counters = new WeakMap();
  revealEls.forEach((el) => {
    const parent = el.parentElement;
    const count = counters.get(parent) || 0;
    counters.set(parent, count + 1);
    el.style.setProperty("--stagger", count % 8); // cap so long lists don't lag forever
  });

  if (!("IntersectionObserver" in window)) {
    // Fallback: just show everything immediately.
    revealEls.forEach((el) => el.classList.add("in-view"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          obs.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );

  revealEls.forEach((el) => observer.observe(el));
});

// ---------- "Những tựa sách mới được yêu thích" carousel ----------
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".popular-carousel").forEach((carousel) => {
    const slides = Array.from(carousel.querySelectorAll(".popular-slide"));
    const total = slides.length;
    if (!total) return;

    const counterEl = carousel.querySelector(".popular-current");
    const authorEl = carousel.querySelector(".popular-author");
    const prevBtn = carousel.querySelector(".popular-prev");
    const nextBtn = carousel.querySelector(".popular-next");
    const AUTOPLAY_MS = 6000;
    let index = 0;
    let timer = null;

    function render() {
      slides.forEach((slide, i) => slide.classList.toggle("active", i === index));
      if (counterEl) counterEl.textContent = index + 1;
      if (authorEl) authorEl.textContent = slides[index].dataset.author || "";
      // Loop around instead of disabling — matches MangaDex's own widget,
      // and buttons stay usable even when there are only 2-3 new titles.
      if (prevBtn) prevBtn.disabled = total <= 1;
      if (nextBtn) nextBtn.disabled = total <= 1;
    }

    function goTo(newIndex) {
      index = (newIndex + total) % total;
      render();
    }

    function startAutoplay() {
      stopAutoplay();
      if (total > 1) timer = setInterval(() => goTo(index + 1), AUTOPLAY_MS);
    }
    function stopAutoplay() {
      if (timer) clearInterval(timer);
      timer = null;
    }

    if (prevBtn) prevBtn.addEventListener("click", () => { goTo(index - 1); startAutoplay(); });
    if (nextBtn) nextBtn.addEventListener("click", () => { goTo(index + 1); startAutoplay(); });

    // Pause while the user is looking at/interacting with the carousel.
    carousel.addEventListener("mouseenter", stopAutoplay);
    carousel.addEventListener("mouseleave", startAutoplay);
    carousel.addEventListener("focusin", stopAutoplay);
    carousel.addEventListener("focusout", startAutoplay);

    render();
    startAutoplay();
  });
});

// ---------- Reader page auto-retry ----------
// MangaDex serves chapter images through its community-run @Home CDN.
// Individual nodes occasionally fail or block requests, so a few images
// can come back broken on first try. We retry a few times with backoff
// before giving up and letting the reader manually reload that page.
document.addEventListener("DOMContentLoaded", () => {
  const MAX_ATTEMPTS = 3;

  function retryImage(img) {
    let attempts = parseInt(img.dataset.attempts || "0", 10);
    attempts += 1;
    img.dataset.attempts = attempts;

    const url = new URL(img.src, window.location.href);
    url.searchParams.set("_retry", Date.now());

    if (attempts <= MAX_ATTEMPTS) {
      setTimeout(() => { img.src = url.toString(); }, 700 * attempts);
    } else {
      img.classList.add("reader-page-failed");
      img.alt = "Không tải được ảnh — bấm để thử lại";
    }
  }

  document.querySelectorAll(".reader-page").forEach((img) => {
    img.addEventListener("error", () => retryImage(img));
    img.addEventListener("click", () => {
      if (img.classList.contains("reader-page-failed")) {
        img.dataset.attempts = "0";
        img.classList.remove("reader-page-failed");
        retryImage(img);
      }
    });
  });
});

// ---------- Site-wide DNS/VPN notice: auto-hide after 5s, or on close ----------
document.addEventListener("DOMContentLoaded", () => {
  const notice = document.getElementById("siteNotice");
  const closeBtn = document.getElementById("siteNoticeClose");
  if (!notice) return;

  const hideTimer = setTimeout(() => notice.classList.add("hidden"), 5000);

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      clearTimeout(hideTimer);
      notice.classList.add("hidden");
    });
  }
});

// ---------- Dark / Light theme toggle ----------
document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll("[data-theme-toggle]");
  if (!buttons.length) return;

  const root = document.documentElement;
  const STORAGE_KEY = "mangaverse-theme";

  function syncIcons() {
    const isLight = root.getAttribute("data-theme") === "light";
    const iconClass = isLight ? "fa-solid fa-moon" : "fa-solid fa-sun";
    buttons.forEach((btn) => {
      const isMobileLabeled = btn.classList.contains("mobile-menu-theme-btn");
      btn.innerHTML = isMobileLabeled
        ? `<i class="${iconClass}"></i> Đổi giao diện sáng/tối`
        : `<i class="${iconClass}"></i>`;
      btn.setAttribute("aria-label", isLight ? "Chuyển sang giao diện tối" : "Chuyển sang giao diện sáng");
    });
  }

  syncIcons();

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const isLight = root.getAttribute("data-theme") === "light";
      if (isLight) {
        root.removeAttribute("data-theme");
        try { localStorage.setItem(STORAGE_KEY, "dark"); } catch (e) {}
      } else {
        root.setAttribute("data-theme", "light");
        try { localStorage.setItem(STORAGE_KEY, "light"); } catch (e) {}
      }
      syncIcons();
    });
  });
});

// ---------- Mobile hamburger menu ----------
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("mobileMenuToggle");
  const menu = document.getElementById("mobileMenu");
  if (!toggle || !menu) return;

  toggle.addEventListener("click", () => {
    const isOpen = menu.classList.toggle("open");
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    toggle.innerHTML = isOpen ? '<i class="fa-solid fa-xmark"></i>' : '<i class="fa-solid fa-bars"></i>';
  });

  // Close the drawer after navigating to a link inside it.
  menu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      menu.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.innerHTML = '<i class="fa-solid fa-bars"></i>';
    });
  });
});

// ---------- Chapter list: mark-all-read + index view toggle ----------
document.addEventListener("DOMContentLoaded", () => {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  const markBtn = document.getElementById("markAllReadBtn");
  if (markBtn) {
    markBtn.addEventListener("click", async () => {
      const container = document.getElementById("chapterGroupsContainer");
      if (!container) return;

      const visibleGroups = Array.from(container.children).filter(
        (el) => el.classList.contains("chapter-group-block") && el.style.display !== "none"
      );
      const rows = [];
      visibleGroups.forEach((g) => rows.push(...g.querySelectorAll(".chapter-entry-row:not(.is-read)")));
      const chapterIds = rows.map((r) => r.dataset.chapterId).filter(Boolean);
      if (!chapterIds.length) return;

      markBtn.disabled = true;
      const originalHtml = markBtn.innerHTML;
      markBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đánh dấu...';

      try {
        const res = await fetch(markBtn.dataset.markUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: JSON.stringify({ chapter_ids: chapterIds }),
        });
        if (res.ok) {
          rows.forEach((r) => {
            r.classList.add("is-read");
            const eyeSpan = r.querySelector(".chapter-entry-eye");
            if (eyeSpan) eyeSpan.innerHTML = '<i class="fa-solid fa-eye"></i>';
          });
          visibleGroups.forEach((g) => {
            const headerEye = g.querySelector(".chapter-group-eye");
            if (headerEye) headerEye.innerHTML = '<i class="fa-solid fa-eye"></i>';
          });
          // Reflect the same chapters in the compact index grid, if present.
          chapterIds.forEach((id) => {
            const chip = document.querySelector(`.chapter-index-chip[href*="${id}"]`);
            if (chip) chip.classList.add("is-read");
          });
        }
      } catch (e) {
        // Network hiccup — leave rows as-is, user can retry.
      } finally {
        markBtn.disabled = false;
        markBtn.innerHTML = originalHtml;
      }
    });
  }

  const indexToggle = document.getElementById("chapterIndexToggle");
  const overlay = document.getElementById("indexModalOverlay");
  const closeBtn = document.getElementById("indexModalClose");

  if (indexToggle && overlay) {
    indexToggle.addEventListener("click", () => overlay.classList.add("open"));
  }
  if (closeBtn && overlay) {
    closeBtn.addEventListener("click", () => overlay.classList.remove("open"));
  }
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.classList.remove("open");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") overlay.classList.remove("open");
    });
  }

  // Each volume row expands/collapses its own chapter list.
  document.querySelectorAll(".index-volume-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const panel = btn.nextElementSibling;
      const willOpen = !panel.classList.contains("open");
      panel.classList.toggle("open", willOpen);
      panel.hidden = !willOpen;
      btn.classList.toggle("open", willOpen);
    });
  });

  // Each chapter sub-row expands to show every translation/group entry.
  document.querySelectorAll(".index-chapter-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const panel = btn.nextElementSibling;
      const willOpen = !panel.classList.contains("open");
      panel.classList.toggle("open", willOpen);
      panel.hidden = !willOpen;
      btn.classList.toggle("open", willOpen);
    });
  });

  // Jump-to Chapter / Volume steppers — scroll to and briefly highlight
  // the matching row instead of filtering the whole list.
  const chapterValueEl = document.getElementById("indexChapterValue");
  const volumeValueEl = document.getElementById("indexVolumeValue");
  let chapterVal = 0;
  let volumeVal = 0;

  function flashHighlight(el) {
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("index-flash");
    setTimeout(() => el.classList.remove("index-flash"), 1200);
  }

  document.querySelectorAll(".index-stepper-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dir = parseInt(btn.dataset.dir, 10);
      if (btn.dataset.step === "chapter") {
        chapterVal = Math.max(0, chapterVal + dir);
        if (chapterValueEl) chapterValueEl.value = chapterVal;
        if (chapterVal > 0) {
          const target = document.querySelector(`.index-chapter-row[data-chapter-number="${chapterVal}"]`);
          if (target) {
            const volumePanel = target.closest(".index-volume-chapters");
            if (volumePanel) {
              volumePanel.classList.add("open");
              volumePanel.hidden = false;
              const volumeToggle = volumePanel.previousElementSibling;
              if (volumeToggle) volumeToggle.classList.add("open");
            }
            flashHighlight(target);
          }
        }
      } else {
        volumeVal = Math.max(0, volumeVal + dir);
        if (volumeValueEl) volumeValueEl.value = volumeVal;
        if (volumeVal > 0) {
          const row = document.querySelector(`.index-volume-row[data-volume-number="${volumeVal}"]`);
          if (row) {
            const panel = row.querySelector(".index-volume-chapters");
            const toggleBtn = row.querySelector(".index-volume-toggle");
            if (panel) { panel.classList.add("open"); panel.hidden = false; }
            if (toggleBtn) toggleBtn.classList.add("open");
            flashHighlight(row);
          }
        }
      }
    });
  });

  const clearBtn = document.getElementById("indexClearBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      chapterVal = 0;
      volumeVal = 0;
      if (chapterValueEl) chapterValueEl.value = 0;
      if (volumeValueEl) volumeValueEl.value = 0;
    });
  }
});

// ---------- Manga detail: Chương / Bình luận / Tranh vẽ / Đề xuất tabs ----------
document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".detail-tab");
  const panels = document.querySelectorAll(".detail-tab-panel");
  if (!tabs.length) return;

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.tab;
      panels.forEach((p) => { p.hidden = p.dataset.panel !== target; });
    });
  });
});

// ---------- Discussion room: poll for new messages ----------
document.addEventListener("DOMContentLoaded", () => {
  const chatWindow = document.getElementById("chatWindow");
  if (!chatWindow) return;

  const pollUrl = chatWindow.dataset.pollUrl;
  let lastId = parseInt(chatWindow.dataset.lastId || "0", 10);

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }
  scrollToBottom();

  function appendMessage(m) {
    const div = document.createElement("div");
    div.className = "chat-message" + (m.is_me ? " chat-message-me" : "");
    div.dataset.msgId = m.id;

    let inner = `<span class="chat-avatar">${escapeHtml(m.username.charAt(0).toUpperCase())}</span><div class="chat-bubble">`;
    inner += `<div class="chat-bubble-header"><span class="chat-username">${escapeHtml(m.username)}</span><span class="chat-time">${escapeHtml(m.created_at)}</span></div>`;
    if (m.content_html) inner += `<div class="chat-content">${m.content_html}</div>`;
    if (m.image_url) inner += `<img src="${escapeHtml(m.image_url)}" alt="" class="chat-media-img" loading="lazy">`;
    if (m.video_url) inner += `<video src="${escapeHtml(m.video_url)}" controls class="chat-media-video"></video>`;
    inner += "</div>";

    div.innerHTML = inner;
    chatWindow.appendChild(div);
  }

  async function poll() {
    try {
      const res = await fetch(`${pollUrl}?after=${lastId}`);
      const data = await res.json();
      if (data.messages && data.messages.length) {
        const wasNearBottom = chatWindow.scrollHeight - chatWindow.scrollTop - chatWindow.clientHeight < 120;
        data.messages.forEach((m) => {
          appendMessage(m);
          lastId = Math.max(lastId, m.id);
        });
        if (wasNearBottom) scrollToBottom();
      }
    } catch (e) {
      // network hiccup — just try again next interval
    }
  }

  setInterval(poll, 4000);
});

// ---------- Chapter list: client-side sort + pagination ----------
// Everything is already rendered server-side (all chapter groups), so this
// just reorders/hides DOM nodes — no page reload, no extra API calls.
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("chapterGroupsContainer");
  if (!container) return;

  const allGroups = Array.from(container.children).filter((el) =>
    el.classList.contains("chapter-group-block")
  );
  if (!allGroups.length) return;

  const PAGE_SIZE = 20;
  const sortBtn = document.getElementById("chapterSortToggle");
  const sortLabel = document.getElementById("chapterSortLabel");
  const sortIcon = sortBtn ? sortBtn.querySelector("i") : null;
  const countEl = document.getElementById("chapterShownCount");
  const paginationEl = document.getElementById("chapterPagination");

  let descending = true; // matches the server's default render order (newest chapter first)
  let currentPage = 1;

  function buildPageRange(current, totalPages, windowSize = 2) {
    if (totalPages <= 1) return [1];
    const keep = new Set([1, totalPages, current]);
    for (let d = 1; d <= windowSize; d++) {
      keep.add(current - d);
      keep.add(current + d);
    }
    const pages = Array.from(keep).filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b);
    const result = [];
    let prev = null;
    pages.forEach((p) => {
      if (prev !== null && p - prev > 1) result.push(null);
      result.push(p);
      prev = p;
    });
    return result;
  }

  function scrollToListTop() {
    const header = document.querySelector(".chapter-list-header");
    if (header) header.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function render() {
    const ordered = descending ? allGroups.slice() : allGroups.slice().reverse();
    const totalPages = Math.max(1, Math.ceil(ordered.length / PAGE_SIZE));
    currentPage = Math.min(Math.max(1, currentPage), totalPages);
    const start = (currentPage - 1) * PAGE_SIZE;
    const pageItems = ordered.slice(start, start + PAGE_SIZE);

    allGroups.forEach((el) => { el.style.display = "none"; });
    pageItems.forEach((el) => {
      el.style.display = "";
      container.appendChild(el); // re-inserts in the correct sorted position
    });

    if (countEl) {
      countEl.textContent = `Đã hiển thị ${pageItems.length} / ${allGroups.length} chương`;
    }

    if (paginationEl) {
      paginationEl.innerHTML = "";
      if (totalPages > 1) {
        const frag = document.createDocumentFragment();

        const prevBtn = document.createElement("button");
        prevBtn.type = "button";
        prevBtn.className = "page-arrow" + (currentPage === 1 ? " disabled" : "");
        prevBtn.innerHTML = '<i class="fa-solid fa-chevron-left"></i>';
        prevBtn.addEventListener("click", () => {
          if (currentPage > 1) { currentPage -= 1; render(); scrollToListTop(); }
        });
        frag.appendChild(prevBtn);

        buildPageRange(currentPage, totalPages).forEach((p) => {
          if (p === null) {
            const span = document.createElement("span");
            span.className = "page-ellipsis";
            span.textContent = "…";
            frag.appendChild(span);
          } else {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "page-num" + (p === currentPage ? " active" : "");
            btn.textContent = p;
            btn.addEventListener("click", () => { currentPage = p; render(); scrollToListTop(); });
            frag.appendChild(btn);
          }
        });

        const nextBtn = document.createElement("button");
        nextBtn.type = "button";
        nextBtn.className = "page-arrow" + (currentPage === totalPages ? " disabled" : "");
        nextBtn.innerHTML = '<i class="fa-solid fa-chevron-right"></i>';
        nextBtn.addEventListener("click", () => {
          if (currentPage < totalPages) { currentPage += 1; render(); scrollToListTop(); }
        });
        frag.appendChild(nextBtn);

        paginationEl.appendChild(frag);
      }
    }
  }

  if (sortBtn) {
    sortBtn.addEventListener("click", () => {
      descending = !descending;
      currentPage = 1;
      if (sortLabel) sortLabel.textContent = descending ? "Descending" : "Ascending";
      if (sortIcon) sortIcon.className = descending ? "fa-solid fa-arrow-down-9-1" : "fa-solid fa-arrow-up-1-9";
      render();
    });
  }

  render();
});

// ---------- Advanced search: 3-state tag pills ----------
document.addEventListener("DOMContentLoaded", () => {
  const pills = document.querySelectorAll(".advtag-pill");
  if (!pills.length) return;

  function syncState(pill) {
    const includeBox = pill.querySelector('input[name="include_tag"]');
    const excludeBox = pill.querySelector('input[name="exclude_tag"]');
    const state = includeBox.checked ? "include" : excludeBox.checked ? "exclude" : "none";
    pill.dataset.state = state;
  }

  pills.forEach((pill) => {
    syncState(pill); // reflect any state already checked server-side (e.g. after a search)

    pill.addEventListener("click", () => {
      const includeBox = pill.querySelector('input[name="include_tag"]');
      const excludeBox = pill.querySelector('input[name="exclude_tag"]');
      const state = pill.dataset.state;

      if (state === "none") {
        includeBox.checked = true;
        excludeBox.checked = false;
      } else if (state === "include") {
        includeBox.checked = false;
        excludeBox.checked = true;
      } else {
        includeBox.checked = false;
        excludeBox.checked = false;
      }
      syncState(pill);
    });
  });
});

// ---------- Live search-suggest dropdown ----------
document.addEventListener("DOMContentLoaded", () => {
  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function initSearchSuggest(inputId, boxId) {
    const input = document.getElementById(inputId);
    const box = document.getElementById(boxId);
    if (!input || !box) return;

    const suggestUrl = input.dataset.suggestUrl;
    let debounceTimer = null;
    let currentQuery = "";
    let requestToken = 0;

    function hide() {
      box.classList.remove("open");
      box.innerHTML = "";
    }

    function render(data, query) {
      if (!data.results.length) {
        box.innerHTML = '<div class="search-suggest-empty">Không tìm thấy truyện nào.</div>';
        box.classList.add("open");
        return;
      }
      let html = `<div class="search-suggest-header"><span>Kết quả tìm kiếm</span><span>${data.total} kết quả</span></div>`;
      data.results.forEach((r) => {
        html += `<a href="${r.url}" class="search-suggest-item">`;
        html += r.cover_url
          ? `<img src="${escapeHtml(r.cover_url)}" alt="" class="search-suggest-thumb" loading="lazy">`
          : `<span class="search-suggest-thumb search-suggest-thumb-empty"></span>`;
        html += '<span class="search-suggest-info">';
        html += `<span class="search-suggest-title">${escapeHtml(r.title)}</span>`;
        if (r.authors && r.authors.length) {
          html += `<span class="search-suggest-meta">Tác giả: ${escapeHtml(r.authors.join(", "))}</span>`;
        }
        if (r.tags && r.tags.length) {
          html += '<span class="search-suggest-tags">' + r.tags.map((t) => `<span>${escapeHtml(t)}</span>`).join("") + "</span>";
        }
        html += "</span></a>";
      });
      html += `<a href="/tim-kiem/?q=${encodeURIComponent(query)}" class="search-suggest-viewall">Xem tất cả ${data.total} kết quả <i class="fa-solid fa-arrow-right"></i></a>`;
      box.innerHTML = html;
      box.classList.add("open");
    }

    async function fetchResults(query) {
      const token = ++requestToken;
      try {
        const res = await fetch(`${suggestUrl}?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (token !== requestToken) return; // a newer keystroke already superseded this request
        render(data, query);
      } catch (e) {
        hide();
      }
    }

    input.addEventListener("input", () => {
      const q = input.value.trim();
      currentQuery = q;
      clearTimeout(debounceTimer);
      if (q.length < 2) { hide(); return; }
      debounceTimer = setTimeout(() => fetchResults(q), 300);
    });

    input.addEventListener("focus", () => {
      if (currentQuery.length >= 2 && box.innerHTML) box.classList.add("open");
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hide();
    });

    document.addEventListener("click", (e) => {
      if (e.target !== input && !box.contains(e.target)) hide();
    });
  }

  initSearchSuggest("desktopSearchInput", "desktopSearchSuggest");
  initSearchSuggest("mobileSearchInput", "mobileSearchSuggest");
});

// ---------- Reader: remember & resume scroll position within a chapter ----------
// Progress is stored client-side (localStorage) keyed by chapter id — it's
// purely a reading-position nicety, not account data, so no login needed.
document.addEventListener("DOMContentLoaded", () => {
  const strip = document.querySelector(".reader-strip");
  const banner = document.getElementById("continueBanner");
  if (!strip || !strip.dataset.chapterId) return;

  const chapterId = strip.dataset.chapterId;
  const STORAGE_KEY = `mangaverse-progress:${chapterId}`;

  function getScrollPercent() {
    const doc = document.documentElement;
    const scrollable = doc.scrollHeight - doc.clientHeight;
    if (scrollable <= 0) return 0;
    const top = window.scrollY || doc.scrollTop;
    return Math.min(100, Math.max(0, Math.round((top / scrollable) * 100)));
  }

  function saveProgress() {
    const percent = getScrollPercent();
    try {
      if (percent >= 96) {
        localStorage.removeItem(STORAGE_KEY); // finished the chapter — nothing to resume
      } else if (percent >= 3) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ percent, savedAt: Date.now() }));
      }
    } catch (e) { /* localStorage unavailable — silently skip saving progress */ }
  }

  let ticking = false;
  window.addEventListener("scroll", () => {
    if (!ticking) {
      requestAnimationFrame(() => { saveProgress(); ticking = false; });
      ticking = true;
    }
  }, { passive: true });
  window.addEventListener("beforeunload", saveProgress);

  if (banner) {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (e) {}

    if (saved && saved.percent >= 3) {
      banner.classList.add("open");

      const resumeBtn = document.getElementById("continueBannerResume");
      const dismissBtn = document.getElementById("continueBannerDismiss");

      if (resumeBtn) {
        resumeBtn.addEventListener("click", () => {
          const doc = document.documentElement;
          const scrollable = doc.scrollHeight - doc.clientHeight;
          window.scrollTo({ top: (saved.percent / 100) * scrollable, behavior: "smooth" });
          banner.classList.remove("open");
        });
      }
      if (dismissBtn) {
        dismissBtn.addEventListener("click", () => {
          try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
          banner.classList.remove("open");
        });
      }
    }
  }
});

// ---------- Floating reader toolbar (auto-hide on scroll) ----------
document.addEventListener("DOMContentLoaded", () => {
  const toolbar = document.getElementById("readerToolbar");
  if (!toolbar) return;

  const scrollTopBtn = document.getElementById("rtScrollTop");
  const selectTrigger = document.getElementById("rtSelectTrigger");
  const selectDropdown = document.getElementById("rtSelectDropdown");
  const moreTrigger = document.getElementById("rtMoreTrigger");
  const moreDropdown = document.getElementById("rtMoreDropdown");

  // Show/hide based on scroll direction, with a small threshold so tiny
  // jitter (mobile rubber-banding etc.) doesn't flicker the toolbar.
  let lastY = window.scrollY;
  let ticking = false;

  function handleScroll() {
    const currentY = window.scrollY;
    const delta = currentY - lastY;

    if (Math.abs(delta) > 8) {
      if (delta > 0 && currentY > 120) {
        toolbar.classList.add("rt-hidden");   // scrolling down -> hide
        selectDropdown && selectDropdown.classList.remove("open");
        moreDropdown && moreDropdown.classList.remove("open");
      } else {
        toolbar.classList.remove("rt-hidden"); // scrolling up -> reveal
      }
      lastY = currentY;
    }
    ticking = false;
  }

  window.addEventListener("scroll", () => {
    if (!ticking) {
      requestAnimationFrame(handleScroll);
      ticking = true;
    }
  }, { passive: true });

  if (scrollTopBtn) {
    scrollTopBtn.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  if (selectTrigger && selectDropdown) {
    selectTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      selectDropdown.classList.toggle("open");
      moreDropdown && moreDropdown.classList.remove("open");
    });
  }
  if (moreTrigger && moreDropdown) {
    moreTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      moreDropdown.classList.toggle("open");
      selectDropdown && selectDropdown.classList.remove("open");
    });
  }
  document.addEventListener("click", () => {
    selectDropdown && selectDropdown.classList.remove("open");
    moreDropdown && moreDropdown.classList.remove("open");
  });
});
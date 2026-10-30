(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;
  var THEME_KEY = "dr-docs-theme";

  function isMac() {
    return /Mac|iPhone|iPad|iPod/.test(navigator.platform || "");
  }

  /* --------------------------------------------------------------- theme */

  function currentTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function updateThemeButtons() {
    var dark = currentTheme() === "dark";
    doc.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", dark ? "true" : "false");
      btn.setAttribute(
        "aria-label",
        dark ? "Ativar tema claro" : "Ativar tema escuro"
      );
      btn.setAttribute(
        "title",
        dark ? "Ativar tema claro" : "Ativar tema escuro"
      );
    });
  }

  function setTheme(theme, persist) {
    root.setAttribute("data-theme", theme);
    if (persist) {
      try {
        localStorage.setItem(THEME_KEY, theme);
      } catch (e) {
        /* armazenamento indisponível */
      }
    }
    updateThemeButtons();
  }

  doc.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setTheme(currentTheme() === "dark" ? "light" : "dark", true);
    });
  });
  updateThemeButtons();

  /* ------------------------------------------------------ mobile sidebar */

  var sidebar = doc.getElementById("docs-sidebar");
  var sidebarOverlay = doc.getElementById("sidebar-overlay");
  var menuToggle = doc.getElementById("menu-toggle");

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add("is-open");
    if (sidebarOverlay) sidebarOverlay.classList.add("is-open");
    if (menuToggle) menuToggle.setAttribute("aria-expanded", "true");
    doc.body.style.overflow = "hidden";
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove("is-open");
    if (sidebarOverlay) sidebarOverlay.classList.remove("is-open");
    if (menuToggle) menuToggle.setAttribute("aria-expanded", "false");
    doc.body.style.overflow = "";
  }

  if (menuToggle) {
    menuToggle.addEventListener("click", function () {
      if (sidebar && sidebar.classList.contains("is-open")) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }
  if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);
  if (sidebar) {
    sidebar.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.matchMedia("(max-width: 900px)").matches) closeSidebar();
      });
    });
  }
  window.addEventListener("resize", function () {
    if (window.innerWidth > 900) closeSidebar();
  });

  /* --------------------------------------------------------- code blocks */

  var copyIcon =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
  var checkIcon =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4.5 4.5L19 7"></path></svg>';

  function legacyCopy(text) {
    var area = doc.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    area.style.opacity = "0";
    doc.body.appendChild(area);
    area.select();
    var ok = false;
    try {
      ok = doc.execCommand("copy");
    } catch (e) {
      ok = false;
    }
    doc.body.removeChild(area);
    return ok;
  }

  doc.querySelectorAll(".markdown-body pre").forEach(function (pre) {
    var btn = doc.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.setAttribute("aria-label", "Copiar bloco de código");
    btn.innerHTML = copyIcon + '<span>Copiar</span>';
    pre.appendChild(btn);

    btn.addEventListener("click", function () {
      var code = pre.querySelector("code");
      var text = (code || pre).innerText.replace(/\n$/, "");
      function done(ok) {
        if (!ok) return;
        btn.classList.add("is-copied");
        btn.innerHTML = checkIcon + '<span>Copiado</span>';
        window.setTimeout(function () {
          btn.classList.remove("is-copied");
          btn.innerHTML = copyIcon + '<span>Copiar</span>';
        }, 1600);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            done(true);
          },
          function () {
            done(legacyCopy(text));
          }
        );
      } else {
        done(legacyCopy(text));
      }
    });
  });

  /* ------------------------------------------------------------ callouts */

  doc.querySelectorAll(".markdown-body blockquote").forEach(function (quote) {
    var text = (quote.textContent || "").trim();
    if (/^aten[cç][aã]o/i.test(text)) {
      quote.classList.add("callout-warning");
    } else if (/^nota/i.test(text)) {
      quote.classList.add("callout-info");
    }
  });

  /* ------------------------------------------------------ heading anchors */

  doc
    .querySelectorAll(".markdown-body h2[id], .markdown-body h3[id], .markdown-body h4[id]")
    .forEach(function (heading) {
      var anchor = doc.createElement("a");
      anchor.className = "heading-anchor";
      anchor.href = "#" + heading.id;
      anchor.textContent = "#";
      anchor.setAttribute("aria-label", "Link para esta seção");
      heading.appendChild(anchor);
    });

  /* ------------------------------------------------------- scroll update */

  var tocLinks = Array.prototype.slice.call(
    doc.querySelectorAll(".docs-toc .toc-link")
  );
  var tocTargets = tocLinks
    .map(function (link) {
      var id = decodeURIComponent((link.hash || "").slice(1));
      return { link: link, el: id ? doc.getElementById(id) : null };
    })
    .filter(function (item) {
      return item.el;
    });

  var progressBar = doc.getElementById("scroll-progress-bar");
  var ticking = false;

  function updateScrollUI() {
    ticking = false;

    if (progressBar) {
      var docHeight = root.scrollHeight - window.innerHeight;
      var pct = docHeight > 0 ? (window.scrollY / docHeight) * 100 : 0;
      progressBar.style.width = Math.max(0, Math.min(100, pct)) + "%";
    }

    if (!tocTargets.length) return;

    var current = tocTargets[0];
    var threshold = 96;
    tocTargets.forEach(function (item) {
      if (item.el.getBoundingClientRect().top <= threshold) current = item;
    });

    // No fim da página as últimas seções não alcançam o topo; destaca a última.
    if (window.innerHeight + window.scrollY >= root.scrollHeight - 4) {
      current = tocTargets[tocTargets.length - 1];
    }

    tocLinks.forEach(function (link) {
      link.classList.remove("is-active");
      link.removeAttribute("aria-current");
    });
    if (current) {
      current.link.classList.add("is-active");
      current.link.setAttribute("aria-current", "location");
    }
  }

  function onScroll() {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(updateScrollUI);
    }
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  updateScrollUI();

  /* ---------------------------------------------------------- mobile toc */

  doc.querySelectorAll(".mobile-toc .toc-link").forEach(function (link) {
    link.addEventListener("click", function () {
      var details = link.closest(".mobile-toc");
      if (details) details.removeAttribute("open");
    });
  });

  /* ------------------------------------------------------ external links */

  doc.querySelectorAll('.markdown-body a[href^="http"]').forEach(function (link) {
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  });

  /* -------------------------------------------------------------- search */

  var overlay = doc.getElementById("search-overlay");
  var input = doc.getElementById("search-input");
  var resultsBox = doc.getElementById("search-results");
  var countBox = doc.getElementById("search-count");
  var trigger = doc.getElementById("search-trigger");
  var closeBtn = doc.getElementById("search-close");
  var index = Array.isArray(window.DOCS_SEARCH_INDEX)
    ? window.DOCS_SEARCH_INDEX
    : [];
  var selected = -1;
  var lastFocused = null;

  function normalize(text) {
    return (text || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function searchIcon() {
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path></svg>'
    );
  }

  function resultItem(item, idx) {
    var a = doc.createElement("a");
    a.className = "search-result";
    a.href = item.page + ".html" + (item.id ? "#" + item.id : "");
    a.setAttribute("role", "option");
    a.setAttribute("aria-selected", "false");
    a.dataset.index = String(idx);

    var icon = doc.createElement("span");
    icon.className = "search-result-icon";
    icon.innerHTML = searchIcon();

    var body = doc.createElement("span");
    body.className = "search-result-body";

    var top = doc.createElement("span");
    top.className = "search-result-top";

    var title = doc.createElement("span");
    title.className = "search-result-title";
    title.textContent = item.title;

    var page = doc.createElement("span");
    page.className = "search-result-page";
    page.textContent = item.pageLabel;

    top.appendChild(title);
    top.appendChild(page);

    var snippet = doc.createElement("span");
    snippet.className = "search-result-snippet";
    snippet.textContent = item.text || "";

    body.appendChild(top);
    body.appendChild(snippet);
    a.appendChild(icon);
    a.appendChild(body);
    return a;
  }

  function setSelected(next) {
    var items = Array.prototype.slice.call(
      resultsBox.querySelectorAll(".search-result")
    );
    if (!items.length) return;
    selected = (next + items.length) % items.length;
    items.forEach(function (item, i) {
      var on = i === selected;
      item.classList.toggle("is-selected", on);
      item.setAttribute("aria-selected", on ? "true" : "false");
      if (on) item.scrollIntoView({ block: "nearest" });
    });
  }

  function render(query) {
    if (!resultsBox) return;
    resultsBox.innerHTML = "";
    selected = -1;

    var q = normalize(query).trim();
    var matches = [];

    if (!q) {
      matches = index.slice(0, 8);
    } else {
      var terms = q.split(/\s+/).filter(Boolean);
      index.forEach(function (item) {
        var title = normalize(item.title);
        var text = normalize(item.text);
        var page = normalize(item.pageLabel);
        var score = 0;
        var all = true;
        terms.forEach(function (term) {
          var inTitle = title.indexOf(term) !== -1;
          var inText = text.indexOf(term) !== -1;
          var inPage = page.indexOf(term) !== -1;
          if (!inTitle && !inText && !inPage) all = false;
          if (inTitle) score += 6;
          if (inPage) score += 2;
          if (inText) score += 1;
          if (title.indexOf(term) === 0) score += 5;
        });
        if (all) matches.push({ item: item, score: score });
      });
      matches.sort(function (a, b) {
        return b.score - a.score;
      });
      matches = matches.slice(0, 14).map(function (m) {
        return m.item;
      });
    }

    if (!matches.length) {
      var empty = doc.createElement("div");
      empty.className = "search-empty";
      empty.textContent = "Nenhuma seção encontrada para “" + query + "”.";
      resultsBox.appendChild(empty);
      if (countBox) countBox.textContent = "0 resultados";
      return;
    }

    matches.forEach(function (item, i) {
      resultsBox.appendChild(resultItem(item, i));
    });
    if (countBox) {
      countBox.textContent =
        matches.length + (matches.length === 1 ? " resultado" : " resultados");
    }
    setSelected(0);
  }

  function openSearch() {
    if (!overlay || !input) return;
    lastFocused = doc.activeElement;
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    doc.body.style.overflow = "hidden";
    input.value = "";
    render("");
    window.setTimeout(function () {
      input.focus();
    }, 20);
  }

  function closeSearch() {
    if (!overlay) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    doc.body.style.overflow = "";
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
  }

  if (trigger) trigger.addEventListener("click", openSearch);
  if (closeBtn) closeBtn.addEventListener("click", closeSearch);
  if (overlay) {
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) closeSearch();
    });
  }

  if (input) {
    input.addEventListener("input", function () {
      render(input.value);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelected(selected + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelected(selected - 1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        var selectedEl = resultsBox.querySelector(".search-result.is-selected");
        if (selectedEl) selectedEl.click();
      } else if (event.key === "Escape") {
        event.preventDefault();
        closeSearch();
      }
    });
  }

  doc.addEventListener("keydown", function (event) {
    var key = event.key;
    var typing =
      /^(INPUT|TEXTAREA|SELECT)$/.test(doc.activeElement.tagName) ||
      doc.activeElement.isContentEditable;

    if ((event.metaKey || event.ctrlKey) && key.toLowerCase() === "k") {
      event.preventDefault();
      if (overlay && overlay.classList.contains("is-open")) {
        closeSearch();
      } else {
        openSearch();
      }
      return;
    }

    if (key === "/" && !typing) {
      event.preventDefault();
      openSearch();
      return;
    }

    if (key === "Escape" && overlay && overlay.classList.contains("is-open")) {
      closeSearch();
    }
  });

  if (isMac()) {
    doc.querySelectorAll("#search-kbd, .search-footer .kbd-shortcut").forEach(
      function (el) {
        el.textContent = "⌘ K";
      }
    );
  }
})();

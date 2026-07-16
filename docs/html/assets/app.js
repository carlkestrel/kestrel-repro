/**
 * dl-paper-repro HTML Documentation JavaScript
 * - Full-text search (no external API)
 * - Theme toggle (light/dark)
 * - Mobile menu toggle
 * - Collapsible TOC
 * - Code copy functionality
 * - Scroll spy for TOC
 * - Keyboard navigation for search results
 * - CSP compatible (no eval, no new Function, no document.write)
 */

(function() {
  'use strict';

  // State
  let searchIndex = null;
  let searchOpen = false;
  let selectedResultIndex = -1;
  let currentResults = [];

  // DOM Elements
  const html = document.documentElement;
  const body = document.body;
  const sidebar = document.querySelector('.sidebar');
  const sidebarOverlay = document.querySelector('.sidebar-overlay');
  const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
  const searchInput = document.querySelector('.search-input');
  const searchResults = document.querySelector('.search-results');
  const themeToggle = document.querySelector('.theme-toggle');
  const tocLinks = document.querySelectorAll('.toc-link');
  const backToTop = document.querySelector('.back-to-top');

  // Initialize
  function init() {
    loadTheme();
    setupEventListeners();
    loadSearchIndex();
    setupScrollSpy();
    setupCodeCopy();
    setupBackToTop();
  }

  // Theme Management
  function loadTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (saved === 'dark' || (!saved && prefersDark)) {
      html.classList.add('dark');
    }
    updateThemeIcon();
  }

  function toggleTheme() {
    const isDark = html.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateThemeIcon();
  }

  function updateThemeIcon() {
    const isDark = html.classList.contains('dark');
    
    if (themeToggle) {
      // Clear existing content
      while (themeToggle.firstChild) {
        themeToggle.removeChild(themeToggle.firstChild);
      }
      
      // Create SVG element
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('fill', 'none');
      svg.setAttribute('stroke', 'currentColor');
      svg.setAttribute('stroke-width', '2');
      svg.setAttribute('stroke-linecap', 'round');
      svg.setAttribute('stroke-linejoin', 'round');
      
      if (isDark) {
        // Moon icon
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z');
        svg.appendChild(path);
        themeToggle.setAttribute('aria-label', 'Switch to light mode');
      } else {
        // Sun icon
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', '12');
        circle.setAttribute('cy', '12');
        circle.setAttribute('r', '5');
        svg.appendChild(circle);
        
        const lines = ['12 1', '12 3', '4.22 4.22', '5.64 5.64', '18.36 18.36', '19.78 19.78', '1 12', '3 12', '21 12', '23 12', '4.22 19.78', '5.64 18.36', '18.36 5.64', '19.78 4.22'];
        for (const line of lines) {
          const [x1, y1] = line.split(' ');
          const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          ln.setAttribute('x1', x1);
          ln.setAttribute('y1', y1);
          ln.setAttribute('x2', x1);
          ln.setAttribute('y2', y1);
          svg.appendChild(ln);
        }
        themeToggle.setAttribute('aria-label', 'Switch to dark mode');
      }
      
      themeToggle.appendChild(svg);
    }
  }

  // Mobile Menu
  function toggleMobileMenu() {
    sidebar.classList.toggle('open');
    sidebarOverlay.classList.toggle('active');
  }

  function closeMobileMenu() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('active');
  }

  // Search
  async function loadSearchIndex() {
    try {
      const response = await fetch('assets/search-index.json');
      if (response.ok) {
        searchIndex = await response.json();
      }
    } catch (e) {
      // Search index not available
      console.debug('Search index not available');
    }
  }

  function normalizeText(text) {
    return text.toLowerCase()
      .replace(/[^\w\s\u4e00-\u9fff]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function tokenize(text) {
    const normalized = normalizeText(text);
    // Split into tokens for Chinese and English
    const tokens = [];
    
    // Chinese character sequences
    const chineseMatch = normalized.match(/[\u4e00-\u9fff]+/g);
    if (chineseMatch) {
      tokens.push(...chineseMatch);
    }
    
    // English words
    const englishMatch = normalized.match(/[a-z0-9]+/g);
    if (englishMatch) {
      tokens.push(...englishMatch);
    }
    
    return tokens;
  }

  function fuzzyMatch(text, query) {
    const normalized = normalizeText(text);
    const queryTokens = tokenize(query);
    
    // Exact substring match
    if (normalized.includes(normalizeText(query))) {
      return { score: 2, matched: true };
    }
    
    // Prefix match
    for (const token of queryTokens) {
      if (token.length >= 2 && normalized.includes(token)) {
        return { score: 1.5, matched: true };
      }
    }
    
    // Token matching
    const textTokens = tokenize(normalized);
    let matchCount = 0;
    
    for (const queryToken of queryTokens) {
      for (const textToken of textTokens) {
        if (textToken.startsWith(queryToken) || queryToken.startsWith(textToken)) {
          matchCount++;
          break;
        }
      }
    }
    
    if (matchCount > 0) {
      return { score: matchCount / queryTokens.length, matched: true };
    }
    
    return { score: 0, matched: false };
  }

  function search(query) {
    if (!searchIndex || !query || query.length < 2) {
      return [];
    }

    const results = [];
    const queryLower = query.toLowerCase();

    for (const item of searchIndex) {
      // Check title
      const titleMatch = fuzzyMatch(item.title || '', query);
      // Check content
      const contentMatch = fuzzyMatch(item.content || '', query);
      // Check section
      const sectionMatch = item.section && fuzzyMatch(item.section, query);

      let score = 0;
      if (titleMatch.matched) score += titleMatch.score * 3;
      if (contentMatch.matched) score += contentMatch.score * 2;
      if (sectionMatch && sectionMatch.matched) score += sectionMatch.score;

      if (score > 0) {
        // Generate snippet
        let snippet = '';
        const content = (item.content || '').toLowerCase();
        const queryNorm = normalizeText(query);
        const idx = content.indexOf(queryNorm);
        
        if (idx !== -1) {
          const start = Math.max(0, idx - 40);
          const end = Math.min(content.length, idx + queryNorm.length + 60);
          snippet = (start > 0 ? '...' : '') + 
                    item.content.substring(start, end).trim() + 
                    (end < item.content.length ? '...' : '');
        } else {
          snippet = item.content.substring(0, 100).trim() + (item.content.length > 100 ? '...' : '');
        }

        results.push({
          id: item.id,
          title: item.title,
          section: item.section,
          type: item.type,
          snippet: snippet,
          score: score,
          url: item.url || ''
        });
      }
    }

    // Sort by score
    results.sort((a, b) => b.score - a.score);

    return results.slice(0, 20);
  }

  function highlightMatch(text, query) {
    if (!query || query.length < 2) return text;
    
    const queryNorm = normalizeText(query);
    const idx = text.toLowerCase().indexOf(queryNorm);
    
    if (idx === -1) return text;
    
    return text.substring(0, idx) + 
           '<mark>' + text.substring(idx, idx + queryNorm.length) + '</mark>' + 
           text.substring(idx + queryNorm.length);
  }

  function renderSearchResults(results, query) {
    if (results.length === 0) {
      const div = document.createElement('div');
      div.className = 'search-result';
      div.style.cssText = 'color: var(--text-muted);';
      div.textContent = 'No results found';
      return div;
    }

    const fragment = document.createDocumentFragment();
    results.forEach((result, index) => {
      const div = document.createElement('div');
      div.className = 'search-result';
      div.setAttribute('data-index', index.toString());
      div.setAttribute('data-url', result.url || '');
      div.setAttribute('tabindex', '0');
      
      const titleDiv = document.createElement('div');
      titleDiv.className = 'search-result-title';
      titleDiv.innerHTML = highlightMatch(result.title || 'Untitled', query);
      
      const sectionDiv = document.createElement('div');
      sectionDiv.className = 'search-result-section';
      sectionDiv.textContent = (result.section || 'Documentation') + ' — ' + (result.type || 'PAGE').toUpperCase();
      
      const snippetDiv = document.createElement('div');
      snippetDiv.className = 'search-result-snippet';
      snippetDiv.innerHTML = highlightMatch(result.snippet || '', query);
      
      div.appendChild(titleDiv);
      div.appendChild(sectionDiv);
      div.appendChild(snippetDiv);
      fragment.appendChild(div);
    });
    return fragment;
  }

  function handleSearch(query) {
    if (!searchInput) return;
    
    currentResults = search(query);
    selectedResultIndex = -1;
    
    if (searchResults) {
      // Clear existing results
      while (searchResults.firstChild) {
        searchResults.removeChild(searchResults.firstChild);
      }
      
      // Add new results
      const results = renderSearchResults(currentResults, query);
      if (results) {
        searchResults.appendChild(results);
      }
      searchResults.classList.toggle('active', currentResults.length > 0 || query.length >= 2);
      
      // Add click handlers
      searchResults.querySelectorAll('.search-result[data-url]').forEach(el => {
        el.addEventListener('click', function() {
          const url = this.dataset.url;
          if (url) {
            window.location.href = url;
          }
        });
      });
    }
  }

  function closeSearch() {
    searchOpen = false;
    selectedResultIndex = -1;
    if (searchResults) {
      searchResults.classList.remove('active');
    }
  }

  // Scroll Spy
  function setupScrollSpy() {
    const headings = document.querySelectorAll('.content h1[id], .content h2[id], .content h3[id]');
    
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            
            // Update TOC
            tocLinks.forEach(link => {
              link.classList.toggle('active', link.getAttribute('href') === '#' + id);
            });
            
            // Update URL hash
            if (window.history.pushState) {
              window.history.replaceState(null, '', '#' + id);
            }
          }
        }
      },
      {
        rootMargin: '-80px 0px -80% 0px',
        threshold: 0
      }
    );

    headings.forEach(heading => observer.observe(heading));
  }

  // Code Copy
  function setupCodeCopy() {
    document.querySelectorAll('.code-block').forEach(block => {
      const button = block.querySelector('.copy-button');
      if (!button) return;
      
      button.addEventListener('click', async function() {
        const code = block.querySelector('code');
        if (!code) return;
        
        try {
          await navigator.clipboard.writeText(code.textContent || '');
          this.textContent = 'Copied!';
          this.classList.add('copied');
          setTimeout(() => {
            this.textContent = 'Copy';
            this.classList.remove('copied');
          }, 2000);
        } catch (e) {
          // Clipboard not available
          this.textContent = 'Failed';
          setTimeout(() => {
            this.textContent = 'Copy';
          }, 2000);
        }
      });
    });
  }

  // Back to Top
  function setupBackToTop() {
    if (!backToTop) return;
    
    window.addEventListener('scroll', () => {
      backToTop.classList.toggle('visible', window.scrollY > 300);
    });
    
    backToTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // Event Listeners
  function setupEventListeners() {
    // Theme toggle
    if (themeToggle) {
      themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Mobile menu
    if (mobileMenuToggle) {
      mobileMenuToggle.addEventListener('click', toggleMobileMenu);
    }
    
    if (sidebarOverlay) {
      sidebarOverlay.addEventListener('click', closeMobileMenu);
    }
    
    // Search
    if (searchInput) {
      let debounceTimer;
      
      searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          handleSearch(this.value);
        }, 150);
      });
      
      searchInput.addEventListener('focus', function() {
        if (this.value.length >= 2 && currentResults.length > 0) {
          searchResults.classList.add('active');
        }
      });
      
      searchInput.addEventListener('keydown', function(e) {
        if (!searchResults.classList.contains('active')) return;
        
        const results = searchResults.querySelectorAll('.search-result[data-url]');
        
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          selectedResultIndex = Math.min(selectedResultIndex + 1, results.length - 1);
          updateSelectedResult(results);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          selectedResultIndex = Math.max(selectedResultIndex - 1, 0);
          updateSelectedResult(results);
        } else if (e.key === 'Enter' && selectedResultIndex >= 0) {
          e.preventDefault();
          const selected = results[selectedResultIndex];
          if (selected && selected.dataset.url) {
            window.location.href = selected.dataset.url;
          }
        } else if (e.key === 'Escape') {
          closeSearch();
          this.blur();
        }
      });
    }
    
    // Close search on outside click
    document.addEventListener('click', function(e) {
      if (!e.target.closest('.search-container')) {
        closeSearch();
      }
    });
    
    // Heading anchors
    document.querySelectorAll('h1[id], h2[id], h3[id], h4[id]').forEach(heading => {
      const anchor = heading.querySelector('.heading-anchor');
      if (!anchor) {
        const link = document.createElement('a');
        link.className = 'heading-anchor';
        link.href = '#' + heading.id;
        link.textContent = '¶';
        link.setAttribute('aria-label', 'Link to section');
        heading.appendChild(link);
      }
    });
    
    // Keyboard navigation for nav items
    document.addEventListener('keydown', function(e) {
      // Press / to focus search
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        if (searchInput) {
          searchInput.focus();
        }
      }
    });
    
    // TOC collapse
    document.querySelectorAll('.toc-section-toggle').forEach(toggle => {
      toggle.addEventListener('click', function() {
        const section = this.closest('.toc-section');
        if (section) {
          section.classList.toggle('collapsed');
          const isCollapsed = section.classList.contains('collapsed');
          this.setAttribute('aria-expanded', !isCollapsed);
        }
      });
    });
  }

  function updateSelectedResult(results) {
    results.forEach((el, index) => {
      el.classList.toggle('selected', index === selectedResultIndex);
    });
    
    if (selectedResultIndex >= 0 && results[selectedResultIndex]) {
      results[selectedResultIndex].scrollIntoView({ block: 'nearest' });
    }
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

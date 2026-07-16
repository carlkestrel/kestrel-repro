#!/usr/bin/env python3
"""
Build script for dl-paper-repro HTML documentation.
Combines all HTML pages into complete_manual.html with inlined assets.
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime

PLUGIN_ROOT = Path(__file__).parent.parent.parent
HTML_DIR = PLUGIN_ROOT / "docs" / "html"
PAGES_DIR = HTML_DIR / "pages"
ASSETS_DIR = HTML_DIR / "assets"
REPORTS_DIR = HTML_DIR / "reports"
GENERATED_DIR = PLUGIN_ROOT / "docs" / "generated"


def read_file(path):
    """Read file contents."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(path, content):
    """Write file contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def build_complete_manual():
    """Build complete_manual.html with inlined CSS, JS, and all content."""
    print("Building complete_manual.html...")
    
    # Read assets
    css = read_file(ASSETS_DIR / "styles.css")
    js = read_file(ASSETS_DIR / "app.js")
    icons_svg = read_file(ASSETS_DIR / "icons.svg")
    logo_svg = read_file(ASSETS_DIR / "logo.svg")
    
    # Read search index
    try:
        search_index = read_file(ASSETS_DIR / "search-index.json")
    except:
        search_index = "[]"
    
    # Read all pages
    pages = []
    for page_file in sorted(PAGES_DIR.glob("*.html")):
        pages.append((page_file.stem, read_file(page_file)))
    
    # Also read index
    pages.insert(0, ("index", read_file(HTML_DIR / "index.html")))
    
    # Build navigation
    nav_items = []
    for name, content in pages:
        title_match = re.search(r'<title>([^<]+)</title>', content)
        if title_match:
            title = title_match.group(1).replace(' - dl-paper-repro', '')
            if name == "index":
                nav_items.append(f'    <li><a href="#chapter-index" class="toc-link active">{title}</a></li>')
            else:
                nav_items.append(f'    <li><a href="#chapter-{name}" class="toc-link">{title}</a></li>')
    
    nav_html = '\n'.join(nav_items)
    
    # Build chapters
    chapters = []
    for i, (name, content) in enumerate(pages):
        title_match = re.search(r'<title>([^<]+)</title>', content)
        title = title_match.group(1).replace(' - dl-paper-repro', '') if title_match else name.title()
        
        # Extract body content
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
        body_content = body_match.group(1) if body_match else ""
        
        # Remove sidebar and TOC from chapter content
        body_content = re.sub(r'<aside class="sidebar">.*?</aside>', '', body_content, flags=re.DOTALL)
        body_content = re.sub(r'<aside class="toc">.*?</aside>', '', body_content, flags=re.DOTALL)
        body_content = re.sub(r'<header class="topbar">.*?</header>', '', body_content, flags=re.DOTALL)
        body_content = re.sub(r'<div class="sidebar-overlay"></div>', '', body_content)
        
        if name == "index":
            chapters.append(f'''
        <section id="chapter-index" class="manual-chapter" data-title="{title}">
          <h1>{title}</h1>
          <div class="chapter-content">
            {body_content}
          </div>
        </section>
''')
        else:
            chapters.append(f'''
        <section id="chapter-{name}" class="manual-chapter" data-title="{title}">
          <h1>{title}</h1>
          <div class="chapter-content">
            {body_content}
          </div>
        </section>
''')
    
    chapters_html = '\n'.join(chapters)
    
    # Build complete HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Complete Manual - dl-paper-repro</title>
  <meta name="description" content="Complete offline manual for dl-paper-repro v0.2.0">
  <style>
{css}
    
    /* Complete manual specific styles */
    .manual-layout {{
      display: flex;
      min-height: 100vh;
    }}
    
    .manual-nav {{
      position: fixed;
      top: 0;
      left: 0;
      width: 260px;
      height: 100vh;
      background: var(--bg-secondary);
      border-right: 1px solid var(--border-color);
      overflow-y: auto;
      z-index: 100;
    }}
    
    .manual-nav-header {{
      padding: 1rem;
      border-bottom: 1px solid var(--border-color);
      font-weight: 600;
    }}
    
    .manual-nav ul {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}
    
    .manual-nav li {{
      border-bottom: 1px solid var(--border-color);
    }}
    
    .manual-nav a {{
      display: block;
      padding: 0.75rem 1rem;
      color: var(--text-secondary);
      text-decoration: none;
      transition: background 0.15s;
    }}
    
    .manual-nav a:hover {{
      background: var(--bg-tertiary);
      color: var(--text-primary);
    }}
    
    .manual-nav a.active {{
      background: var(--accent-primary);
      color: white;
    }}
    
    .manual-main {{
      flex: 1;
      margin-left: 260px;
      padding: 2rem 3rem;
      max-width: 900px;
    }}
    
    .manual-chapter {{
      border-bottom: 2px solid var(--border-color);
      padding-bottom: 3rem;
      margin-bottom: 3rem;
    }}
    
    .manual-chapter:last-child {{
      border-bottom: none;
    }}
    
    .manual-chapter h1 {{
      font-size: 1.75rem;
      margin-bottom: 1.5rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border-color);
    }}
    
    .chapter-content .sidebar,
    .chapter-content .topbar,
    .chapter-content .toc,
    .chapter-content .sidebar-overlay,
    .chapter-content .back-to-top {{
      display: none !important;
    }}
    
    .chapter-content .content {{
      max-width: 100%;
      margin: 0;
      padding: 0;
    }}
    
    .chapter-content .content-header {{
      display: none;
    }}
    
    .chapter-content .page-nav {{
      display: none;
    }}
    
    @media (max-width: 768px) {{
      .manual-nav {{
        display: none;
      }}
      .manual-main {{
        margin-left: 0;
        padding: 1rem;
      }}
    }}
    
    @media print {{
      .manual-nav {{
        display: none;
      }}
      .manual-main {{
        margin-left: 0;
      }}
    }}
  </style>
</head>
<body>
  <div class="manual-layout">
    <nav class="manual-nav">
      <div class="manual-nav-header">
        <svg width="24" height="24" viewBox="0 0 32 32" style="vertical-align: middle; margin-right: 0.5rem;">
          <rect width="32" height="32" rx="6" fill="#2563eb"/>
          <path d="M8 12h6v2H10v6h4v2H8V12z" fill="white"/>
          <path d="M16 8h8v2h-6v4h5v2h-5v6h-2V8z" fill="white"/>
        </svg>
        dl-paper-repro v0.2.0
      </div>
      <ul>
{nav_html}
      </ul>
    </nav>
    
    <main class="manual-main">
{chapters_html}
    </main>
  </div>
  
  <!-- Inlined assets for offline use -->
  <div style="display: none;">
    <div id="inline-icons">{icons_svg}</div>
    <div id="inline-search">{search_index}</div>
  </div>
  
  <script>
{js}
    
    // Initialize complete manual
    document.addEventListener('DOMContentLoaded', function() {{
      // Scroll spy for nav
      const observer = new IntersectionObserver(
        (entries) => {{
          entries.forEach(entry => {{
            if (entry.isIntersecting) {{
              const id = entry.target.id;
              document.querySelectorAll('.manual-nav a').forEach(a => {{
                a.classList.toggle('active', a.getAttribute('href') === '#' + id);
              }});
            }}
          }});
        }},
        {{ rootMargin: '-20% 0px -70% 0px' }}
      );
      
      document.querySelectorAll('.manual-chapter').forEach(ch => observer.observe(ch));
      
      // Click to scroll
      document.querySelectorAll('.manual-nav a').forEach(a => {{
        a.addEventListener('click', function(e) {{
          e.preventDefault();
          const id = this.getAttribute('href').substring(1);
          document.getElementById(id)?.scrollIntoView({{ behavior: 'smooth' }});
        }});
      }});
    }});
  </script>
</body>
</html>
'''
    
    write_file(HTML_DIR / "complete_manual.html", html)
    print(f"  Created complete_manual.html")


def main():
    print("Building dl-paper-repro HTML documentation...")
    print(f"  Plugin root: {PLUGIN_ROOT}")
    print(f"  HTML dir: {HTML_DIR}")
    
    # Ensure directories exist
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Build complete manual
    build_complete_manual()
    
    print("\nBuild complete!")


if __name__ == "__main__":
    main()

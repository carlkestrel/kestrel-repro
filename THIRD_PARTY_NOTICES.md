# Third Party Notices

This document acknowledges external projects, papers, and services that inspired the design and workflow of this project. This project does **not** copy source code from these projects. It studies architectural patterns and re-implements relevant concepts based on clean-room development principles.

---

## External Projects & Architectural Inspirations

### 1. NORA (Night Owl Research Agent)

- **URL**: https://github.com/GRIND-Lab-Core/night_owl_research_agent
- **License**: MIT
- **Category**: Design inspiration (architectural patterns)
- **Local modules affected**: `scripts/orchestrator/*` (policy_engine.py, approval_gate.py, etc.)
- **Note**: Architecture patterns were studied and reimplemented from scratch. The policy-driven agent loop, approval gate pattern, and orchestration concepts were referenced as design inspiration and independently implemented.

---

### 2. SiamKPConv

- **URL**: From paper "Fully Sparse 3D Object Detection" and related KPConv work
- **License**: MIT (if open source; verify before use)
- **Category**: Workflow inspiration (paper reproduction workflow)
- **Local modules affected**: `templates/`, `workflows/`
- **Note**: The end-to-end paper reproduction pipeline structure and experiment organization patterns influenced the project's workflow templates. Concepts were re-implemented independently.

---

### 3. AI-Researcher

- **Reference**: From literature on autonomous research agents
- **URL**: Referenced from academic literature
- **Category**: Workflow inspiration
- **Local modules affected**: `scripts/research_crawler.py`
- **Note**: Literature survey automation and research crawling workflow patterns influenced the design. Implemented independently based on described concepts.

---

## External APIs & Services

This project uses the following external APIs (no source code copied):

| Service | Purpose | Terms/License |
|---------|---------|---------------|
| **GitHub API** | Repository scouting, code search | GitHub Terms of Service |
| **ArXiv API** | Paper search and metadata retrieval | ArXiv usage policy |
| **Semantic Scholar API** | Literature review, citation graph traversal | Semantic Scholar API terms |

---

## License Notes

- **MIT Licensed Projects**: When architectural patterns from MIT-licensed projects are studied and reimplemented, the resulting implementation is original work. MIT permits this as long as the original copyright notice is retained if any licensed code is directly used.
- **Clean-Room Development**: All concepts were implemented based on publicly documented designs, API specifications, and research papers without direct code copying.
- **Paper References**: Workflow ideas from academic papers are based on described methods and are independently implemented.

---

## Attribution Disclaimer

If any attribution is missing or incorrect, please open an issue or submit a correction. We strive to properly credit all sources of inspiration while maintaining the originality of our implementation.

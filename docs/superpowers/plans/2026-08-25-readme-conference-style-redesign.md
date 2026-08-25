# Zhiyan Agent Conference-style README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Zhiyan Agent README as a Chinese-first top-conference project page with crisp SVG identity, a publication-style Fast-Slow architecture figure, evidence-led results, reproducible assets, and no interview-oriented copy.

**Architecture:** Keep all quantitative visuals deterministic and derived from checked-in JSON. Extend the existing Python figure generator to own the wordmark, method figure, results figure, and section icons; keep README responsible only for research narrative, navigation, reproduction, and citation. Tests enforce copy exclusions, asset order, data provenance, and output integrity.

**Tech Stack:** Markdown/HTML, SVG, Python 3.11+, Matplotlib, NumPy, Pytest, GitHub README rendering.

## Global Constraints

- Chinese is the primary language; English is limited to accepted research terms and bilingual labels.
- README must not contain interview-oriented sections such as “30 秒看懂项目”, “面试官关心的问题”, or “核心页面”.
- Public result claims are limited to `56.98 simulation steps/s`, `0.43%` historical peak-density reproduction error, and `23.10%` maximum peak-density reduction.
- `93 / 52 / 25` are knowledge-base scale statistics, not retrieval accuracy; do not publish unsupported `Recall@5 85%-90%` or estimated `18%-27%` as reproducible results.
- README embeds SVG assets for clarity; PNG counterparts remain available for preview and archival use.
- All secrets remain environment-only; no real API key or private material may enter generated assets, Markdown, commits, or Git history.

---

### Task 1: Lock the README and visual asset contract

**Files:**
- Modify: `tests/test_readme_figures.py`
- Test: `tests/test_readme_figures.py`

**Interfaces:**
- Consumes: `README.md`, `docs/results/*.json`, and generated files under `docs/assets/`.
- Produces: executable assertions defining required asset names, section order, excluded copy, and machine-result provenance.

- [ ] **Step 1: Replace the old README assertions with the approved contract**

```python
def test_readme_follows_research_repository_narrative() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = ["摘要 / Abstract", "方法概览 / Method", "主要贡献 / Contributions", "实验结果 / Results", "系统演示 / Demo", "作者贡献 / Author Contributions"]
    for heading in required:
        assert heading in readme
    for rejected in ("30 秒看懂项目", "面试官关心的问题", "核心页面"):
        assert rejected not in readme
    assert readme.index("docs/assets/method-architecture.svg") < readme.index("系统演示 / Demo")


def test_readme_uses_crisp_generated_assets() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for asset in ("zhiyan-wordmark.svg", "method-architecture.svg", "results-overview.svg"):
        assert f"docs/assets/{asset}" in readme
```

- [ ] **Step 2: Add asset presence and evidence-language assertions**

```python
def test_publication_assets_are_present_and_nontrivial() -> None:
    for name in ("zhiyan-wordmark.svg", "method-architecture.svg", "method-architecture.png", "results-overview.svg", "results-overview.png"):
        assert (ROOT / "docs" / "assets" / name).stat().st_size > 10_000


def test_result_language_preserves_evidence_boundaries() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "复现相对误差 **0.43%**" in readme
    assert "峰值密度降低 **23.10%**" in readme
    assert "Recall@5 约 85%" not in readme
    assert "99.57%" not in readme
```

- [ ] **Step 3: Run the focused test and confirm the old README fails**

Run: `python -m pytest tests/test_readme_figures.py -q`

Expected: FAIL because the new asset names and approved headings do not exist yet.

- [ ] **Step 4: Commit the failing contract**

```bash
git add tests/test_readme_figures.py
git commit -m "test: define conference-style README contract"
```

### Task 2: Generate the wordmark, architecture, results, and icon system

**Files:**
- Modify: `scripts/generate_readme_figures.py`
- Modify: `docs/assets/README.md`
- Create: `docs/assets/zhiyan-wordmark.svg`
- Create: `docs/assets/method-architecture.svg`
- Create: `docs/assets/method-architecture.png`
- Create: `docs/assets/results-overview.svg`
- Create: `docs/assets/results-overview.png`
- Create: `docs/assets/icons/abstract.svg`
- Create: `docs/assets/icons/method.svg`
- Create: `docs/assets/icons/contributions.svg`
- Create: `docs/assets/icons/results.svg`
- Create: `docs/assets/icons/demo.svg`
- Create: `docs/assets/icons/reproduction.svg`
- Create: `docs/assets/icons/structure.svg`
- Create: `docs/assets/icons/limitations.svg`
- Create: `docs/assets/icons/author.svg`
- Create: `docs/assets/icons/references.svg`
- Test: `tests/test_readme_figures.py`

**Interfaces:**
- Consumes: `docs/results/benchmark.json`, `docs/results/interventions.json`, and `docs/results/historical-calibration.json`.
- Produces: `build_wordmark()`, `build_method_architecture()`, `build_results_overview()`, and `build_section_icons()` called by the script entry point.

- [ ] **Step 1: Implement a vector wordmark and a consistent icon writer**

Use a transparent SVG, path-outlined title text, a restrained blue pulse/bolt motif, and no raster background. Write each section icon as a standalone 24-by-24 SVG using the same `#2878B5` stroke and round line caps.

- [ ] **Step 2: Replace the cramped four-column method figure**

Build a 16-by-9 inch figure with two non-overlapping computational paths: the upper Fast Brain path (`Scenario Encoding -> Interaction Layers -> Temporal Evolution -> Crowd State`) and the lower Slow Brain path (`Risk Context -> Evidence Retrieval -> Reasoning -> Intervention Head`). Place Risk-aware Gating between them and Matched-seed Replay on the right. Use minimum 14 pt labels, no crossing arrows, and no text outside its owning panel.

- [ ] **Step 3: Replace absolute-value-led charts with an evidence overview**

Read all three result JSON files. Plot intervention reduction percentages with Baseline at `0%`, display the calibration pair as a `0.43%` relative-error annotation, and show throughput with its workload context. Include the `93 -> 52 -> 25` knowledge-base funnel as project-scale statistics, visually separated from reproducible metrics.

- [ ] **Step 4: Generate all assets**

Run: `python scripts/generate_readme_figures.py`

Expected: exits `0`; all SVG and PNG files are created; no external API or network call occurs.

- [ ] **Step 5: Inspect raster previews at original size**

Open `docs/assets/method-architecture.png` and `docs/assets/results-overview.png`. Expected: all labels are readable, remain inside boxes, arrows do not intersect unrelated modules, and both images are nonblank.

- [ ] **Step 6: Document asset origin and metric provenance**

Update `docs/assets/README.md` to identify each generated asset, its source JSON, and the distinction between reproducible metrics and project-scale statistics.

- [ ] **Step 7: Run asset tests and commit**

Run: `python -m pytest tests/test_readme_figures.py -q`

Expected: asset presence/provenance assertions pass; narrative assertions may still fail until Task 3.

```bash
git add scripts/generate_readme_figures.py docs/assets tests/test_readme_figures.py
git commit -m "feat: generate conference-style research visuals"
```

### Task 3: Rewrite README as a research project page

**Files:**
- Modify: `README.md`
- Modify: `CITATION.cff` only if the final public title changes
- Test: `tests/test_readme_figures.py`

**Interfaces:**
- Consumes: the generated SVG assets from Task 2, `docs/results/*.json`, portfolio source wording, public setup commands, and verified references in `sources/research_foundational_methods.md`.
- Produces: the complete GitHub landing page and stable anchors used by its top navigation.

- [ ] **Step 1: Build the title block and abstract**

Embed `zhiyan-wordmark.svg`, use the approved bilingual subtitle, official award/role line, restrained HTML tags, and paper-style navigation. Write a 180-250 Chinese-character abstract based on the portfolio problem statement: slow risk identification and fragmentation between rule retrieval and evacuation simulation.

- [ ] **Step 2: Add Method and Contributions**

Embed `method-architecture.svg` immediately after the abstract. Explain the Fast Brain, risk gate, Slow Brain, and matched-seed replay in four concise paragraphs. State the four approved research contributions without interview framing.

- [ ] **Step 3: Add Results and Demo**

Embed `results-overview.svg`, foreground the `0.43%` reproduction error and `23.10%` intervention reduction, and retain exact experimental conditions plus links to JSON. Place two verified system screenshots after results under `系统演示 / Demo`, each with one evidence-focused caption.

- [ ] **Step 4: Preserve reproducibility and repository guidance**

Keep tested install, no-key local mode, optional LLM/RAG mode, experiment commands, security scan, API summary, and focused repository tree. Use `.env.example` placeholders only.

- [ ] **Step 5: Add limitations, CRediT-style ownership, references, and citation**

Describe scene-generalization, sample-size, RAG-evaluation, and LLM uncertainty limits. Attribute Conceptualization, Methodology, Software, Validation, Visualization, and Project Administration to the project lead. Keep verified foundational citations, `CITATION.cff`, MIT License, and the professional-safety disclaimer.

- [ ] **Step 6: Run focused tests and link checks**

Run: `python -m pytest tests/test_readme_figures.py -q`

Expected: PASS.

Run a local Markdown path audit that extracts relative image/link targets and verifies every local target exists.

Expected: zero missing local targets.

- [ ] **Step 7: Commit the README**

```bash
git add README.md CITATION.cff tests/test_readme_figures.py
git commit -m "docs: present Zhiyan Agent as a research project"
```

### Task 4: Verify, sanitize, and publish

**Files:**
- Modify: only files required to fix verification failures
- Test: `tests/`, `scripts/security_scan.py`

**Interfaces:**
- Consumes: the completed README, generated assets, repository tests, and existing security scanner.
- Produces: a verified commit range pushed to `origin/codex/public-release` or the configured upstream branch.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run deterministic regeneration and diff check**

Run: `python scripts/generate_readme_figures.py`, then `git diff --check`.

Expected: no unexpected generated-asset changes and no whitespace errors.

- [ ] **Step 3: Run the repository security scan**

Run: `python scripts/security_scan.py --worktree --staged --history`

Expected: exit `0` and no exposed secret or private material.

- [ ] **Step 4: Review the final commit range and repository status**

Run: `git diff origin/main...HEAD --stat`, `git status --short`, and `git log --oneline origin/main..HEAD`.

Expected: only approved design, tests, generated assets, README, and closely related documentation changes are present; the worktree is clean.

- [ ] **Step 5: Push the completed branch**

Run: `git push -u origin codex/public-release`

Expected: the remote reports the new commits and establishes/updates the upstream branch.

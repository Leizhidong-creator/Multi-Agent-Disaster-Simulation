# Zhiyan Agent Abstract Positioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved Chinese and English Agent-Based Modeling positioning statement immediately above the existing README abstract.

**Architecture:** Keep the change entirely in Markdown. Extend the existing README contract test to enforce exact copy, semantic placement, and restrained formatting; then insert one bold Chinese paragraph and one italic English paragraph without changing the existing abstract or figures.

**Tech Stack:** Markdown, Pytest, GitHub README rendering.

## Global Constraints

- Chinese positioning copy: `一个基于 Agent-Based Modeling 的具身多智能体人群仿真与风险治理系统，通过事件触发的 Slow Brain、RAG 证据检索与同种子反事实复演，实现风险诊断、策略生成与干预验证。`
- English positioning copy: `An embodied multi-agent crowd simulation and risk-governance system built on Agent-Based Modeling, with event-triggered Slow Brain reasoning, retrieval-augmented evidence grounding, and matched-seed counterfactual evaluation.`
- Place both statements after `摘要 / Abstract` and before the existing paragraph beginning `面向高密度人群场景中`.
- Use bold Markdown for Chinese and italic Markdown for English.
- Do not add a card, heading, image, badge, blockquote, or unsupported LLM Agent claim.

---

### Task 1: Lock the abstract positioning contract

**Files:**
- Modify: `tests/test_readme_figures.py`
- Test: `tests/test_readme_figures.py`

**Interfaces:**
- Consumes: `README.md` as UTF-8 text.
- Produces: `test_readme_positions_agent_paradigm_before_abstract_body()` enforcing exact copy, Markdown emphasis, and order.

- [ ] **Step 1: Add the failing test**

```python
def test_readme_positions_agent_paradigm_before_abstract_body() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = "**一个基于 Agent-Based Modeling 的具身多智能体人群仿真与风险治理系统，通过事件触发的 Slow Brain、RAG 证据检索与同种子反事实复演，实现风险诊断、策略生成与干预验证。**"
    english = "*An embodied multi-agent crowd simulation and risk-governance system built on Agent-Based Modeling, with event-triggered Slow Brain reasoning, retrieval-augmented evidence grounding, and matched-seed counterfactual evaluation.*"
    abstract_body = "面向高密度人群场景中"

    assert chinese in readme
    assert english in readme
    assert readme.index("摘要 / Abstract") < readme.index(chinese)
    assert readme.index(chinese) < readme.index(english) < readme.index(abstract_body)
```

- [ ] **Step 2: Verify the test fails for the missing positioning copy**

Run: `python -m pytest tests/test_readme_figures.py::test_readme_positions_agent_paradigm_before_abstract_body -q`

Expected: one assertion failure because the approved Chinese statement is not yet in `README.md`.

### Task 2: Insert the approved positioning statement

**Files:**
- Modify: `README.md`
- Test: `tests/test_readme_figures.py`

**Interfaces:**
- Consumes: the exact strings enforced by Task 1.
- Produces: two Markdown paragraphs immediately before the existing abstract body.

- [ ] **Step 1: Insert the exact Markdown**

```markdown
**一个基于 Agent-Based Modeling 的具身多智能体人群仿真与风险治理系统，通过事件触发的 Slow Brain、RAG 证据检索与同种子反事实复演，实现风险诊断、策略生成与干预验证。**

*An embodied multi-agent crowd simulation and risk-governance system built on Agent-Based Modeling, with event-triggered Slow Brain reasoning, retrieval-augmented evidence grounding, and matched-seed counterfactual evaluation.*
```

- [ ] **Step 2: Run the focused README tests**

Run: `python -m pytest tests/test_readme_figures.py -q`

Expected: all README figure and copy tests pass.

### Task 3: Verify and publish

**Files:**
- Modify only files required to correct verification failures.

**Interfaces:**
- Consumes: final README, tests, links, and security scanner.
- Produces: a verified commit pushed to remote `main`.

- [ ] Run `python -m pytest -q`; expect zero failures.
- [ ] Run the README local-link audit; expect zero missing targets.
- [ ] Run `python scripts/security_scan.py --worktree --staged --history`; expect three PASS lines.
- [ ] Run `git diff --check`; expect no whitespace errors.
- [ ] Commit the plan, test, and README with `git commit -m "docs: clarify the project agent paradigm"`.
- [ ] Push with `git -c http.proxy=http://127.0.0.1:7892 push origin HEAD:main` and confirm remote `main` resolves to local `HEAD`.

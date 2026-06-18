# Argus 仓库 Blueprint · 2026-06-17

> **本文位置**: `~/Documents/01-Agent/designing-ai-agents/docs/BLUEPRINT-2026-06-17.md`
>
> **scope 锁定**: 本文只针对 `~/Documents/01-Agent/designing-ai-agents/` 这一个仓库。
> `~/Documents/01-Agent/agent-design-patterns/` 是 ADPS 共同体资产, **不在本次工作范围**。
>
> **触发**: 用户读了 Willem 的 `关于Agrus.txt` 4 句话, 结合 Phase A 5 个并行 discovery 的发现, 决定整理立场并设计 Ch1→Ch10 完整方案。

---

## §0 · 立场整理 (用户原意)

```
designing-ai-agents/ 这一个仓库内部, 同时承载两类代码:

  ┌─────────────────────────────────────────────────────────────────┐
  │ 轨 A · Argus (一条线, cumulative)                                │
  │   一个真正能跑、有结构、清晰的 coding agent (PR review agent)    │
  │   Ch2 出生 → Ch3 +眼 → Ch4 +记忆 → ... → Ch10 完整体             │
  │   每章 = 在前一章 Argus 基础上 + 1 个 cognitive module           │
  │   后一章 import 前一章 (真 cumulative, 非独立 stub)              │
  │                                                                  │
  │ 轨 B · patterns/* (配合书中代码的独立程序 / 片段)                │
  │   不是所有 pattern 都进得了 Argus — 不强求                       │
  │   每个 pattern 一个独立 demo, 不依赖 Argus, 不互相 import        │
  │   书里的 Listing 7.X / 6.X 等大量是这类 (Willem 已确认)          │
  └─────────────────────────────────────────────────────────────────┘

  原则:
    1. 能集成进 Argus 的 pattern, 在 argus/ 写一个 thin facade 把
       pattern 接进 Argus (Ch4 ArgusMemory wraps HierarchicalMemory
       是金本位)
    2. 集成不进的 pattern, 只在 patterns/ 独立存在, 不强行塞 Argus
    3. 书里出现的所有 code listing, 仓库都要有对应文件 (前后描述一致)
    4. Argus 必须真的能 end-to-end 跑, 不是 import-clean 就算
```

---

## §1 · 现状 reality check (来自 Phase A discovery)

### 当前仓库的真实状态 vs README 自述

| README 声称 | 实际 | 差距 |
|------------|------|------|
| Argus 一章一章 cumulative 长出来 | 每章 stub 独立, **0 cross-chapter import** (`grep -rn 'from ch0'` 零命中) | **致命** — Argus 不是 cumulative |
| ch02-ch10 覆盖 | 实际 ch01-ch05 五章, **ch06-ch10 完全不存在** | **致命** — 缺 5 章代码 |
| `argus/__init__.py` 应有 re-export | 4 个 `__init__.py` 全部 byte-identical 一行 docstring | **致命** — 没有 accumulation API |
| 22 runnable / 23 total | smoke_test 只查 AST + 模块 import, **不跑 main(), 不验 end-to-end** | 验证太弱 |
| `argus/core.py` Argus 主体 | Ch2 的 38 行 `review_diff` 是唯一能跑的 Argus, **后续章节没接上去** | 主线断了 |

### Argus 每章实际状态

```
ch01-paradigm-shift/simple_agent.py  — 30 LOC, 两个空 class 骨架, .perceive/.reason 全是 placeholder
                                       (Ch1 本来就不该有真代码 ✓)

ch02-architecture/argus/core.py       — 38 LOC, review_diff(diff, ctx) 单函数, 一次 LLM call
                                       (是当前唯一能跑的 Argus, 但 P/R/A 退化为单 prompt)
ch02-architecture/argus/runtime.py    — 31 LOC, 引用 Sandbox/MCPHost/SkillRegistry 等都不存在
                                       (README 自己说 "structural pseudocode")
ch02-architecture/argus/coding_agent_simplified.py — 20 LOC, self.llm / self.execute_tool 未定义

ch03-perception/argus/perception.py   — 126 LOC, gather_review_context, FileContext + PerceptionTrace
                                       (最实质的一份, 但 NOT 接回 core.py — Ch3 没有 Listing 把它接进去)

ch04-memory/argus/memory.py           — 26 LOC, ArgusMemory wraps HierarchicalMemory
                                       (唯一一个 "facade 包装 pattern" 的例子 — 这是金本位模板)
                                       (但仍 NOT import ch03 perception, 不 cumulative)

ch05-reasoning/argus/reasoning.py     — 42 LOC, 3 个顶层 def 函数 (self 作 first arg, 没有 class 包它)
                                       (引用 Argus / ReviewResult / run_in_sandbox / HypothesisTester
                                        — 全是未定义) (README 自己说 "method fragments")

ch06-action/    — 不存在
ch07-reflection/ — 不存在
ch08-collaboration/ — 不存在
ch09-governance/ — 不存在
ch10-methodology/ — 不存在
```

### 书里 Ch10 §10.10 的硬承诺 (这是关键)

```
"This is not a toy example. Every method call maps to a working class from
 Chapters 3-9. The composition is the simplest possible code that wires
 them together."
```

—— Ch10 §10.10 Listing 10.1 (`argus/orchestrator.py` 或 `argus/agent.py` — 命名冲突见 §3.5) 是书对读者的硬承诺: **每个 method call 都映射到 Ch3-Ch9 的真 class**。当前 repo 兑现不了这句, 就是 liability。

### 书声称但章里没有 listing 的位置

| 章 | 检查点表声称 | 章里实际 | 状态 |
|----|------------|---------|------|
| Ch4 §4.8 | `argus/memory.py` (ArgusMemory wraps HierarchicalMemory) | ✅ 有 listing | OK |
| Ch5 §x | `argus/reasoning.py` (3 b-listing) | ✅ 有 3 个 listing | OK |
| **Ch6 §6.8** | `argus/action.py` (5 capabilities: lint, test, fix, gate, trace) | ❌ **0 个 argus/ listing**, 全是 patterns/ | **gap** |
| **Ch7 §7.x** | `argus/reflection.py` + `argus/self_heal.py` | ❌ **0 个 argus/ listing**, 全是 patterns/ | **gap** |
| Ch8 §8.8 | `argus/collaboration.py` | 未读 (推测同 Ch6/Ch7) | 需查 |
| Ch9 §9.8 | `argus/governance.py` | 未读 | 需查 |
| Ch10 §10.10 | `argus/orchestrator.py` Listing 10.1 | ✅ 有 listing | OK |

**重要**: Willem 说 "第七章示例代码不太可能集成到 argus 项目中" — Phase A 实证: **Ch6 + Ch7 章里所有 listing 都标 `patterns/`, 0 个标 `argus/`**。Willem 是对的。

### 其他 Phase A 发现

- 模型 id `claude-sonnet-4-6` 出现在 ch02/core.py 和 ch05/chain_of_thought.py — **不是公开 Anthropic 模型 id**, 跑会 404
- `requirements.txt` 缺 vector DB (chromadb / faiss), Ch4 RAG 跑不起来
- `[CA]` 怪标记出现在多个 listing 里 (typesetter cue leakage, MD 卫生问题)
- Ch3 PerceptionTrace 是 trace dataclass 的 canonical template, Ch4 MemoryTrace 缺失

---

## §2 · Argus 双轨架构 (Ch1→Ch10 完整设计)

### 轨道分工

```
designing-ai-agents/
  chNN-name/
    argus/                  ← 轨 A · Argus cumulative 主线
      __init__.py           ← re-export 前一章的全部 + 本章新增
      <module>.py           ← 本章新增的 cognitive module (薄 facade)
      cli.py                ← 本章末段读者跑这个看 "Now Argus can..."
    patterns/               ← 轨 B · 独立 pattern demos
      <pattern_a>.py        ← 一个 pattern 一个文件, 不依赖 Argus
      <pattern_b>.py
      ...
    demos/                  ← (可选) 第三方框架对比版 (OpenAI Agents SDK / LangGraph)
    README.md               ← 本章 What's new + 怎么跑
```

### Argus 演进表 (轨 A · 真 cumulative · ch02 → ch10)

| 章 | Argus += 什么 | 关键 module | demo command | cumulative? |
|----|-------------|-----------|-------------|-----|
| **Ch2** | 出生 — 单 prompt review_diff | `argus/core.py` | `python -m ch02.argus.cli "<diff>"` | (起点) |
| **Ch3** | + 眼 (perception) — 自动 gather context, 优先级裁剪 | `argus/perception.py` + 接 `core.py` | `python -m ch03.argus.cli /path/to/repo /path/to/diff` | ✅ import ch02 |
| **Ch4** | + 记忆 (memory) — 跨 PR 复用 lessons, RAG 历史 | `argus/memory.py` (薄 facade 包 HierarchicalMemory) | `python -m ch04.argus.cli ...` | ✅ import ch03 |
| **Ch5** | + 推理 (reasoning) — Plan-and-Execute / CoT / complexity routing | `argus/reasoning.py` (重写, 不再是 free-floating def) | `python -m ch05.argus.cli ...` | ✅ import ch04 |
| **Ch6** | + 手 (action) — tool dispatch (lint, test, gh CLI), guardrail sandwich | **新建** `argus/action.py` (满足 §6.8 承诺) | `python -m ch06.argus.cli ...` | ✅ import ch05 |
| **Ch7** | + 自省 (reflection) — generator-critic 跑在每个 review 上 | **新建** `argus/reflection.py` + `argus/self_heal.py` (满足 §7.x 承诺) | `python -m ch07.argus.cli ...` | ✅ import ch06 |
| **Ch8** | + 协作 (collaboration) — 调 sub-agent (security review / style review) | **新建** `argus/collaboration.py` | `python -m ch08.argus.cli ...` | ✅ import ch07 |
| **Ch9** | + 治理 (governance) — permission gates, trust levels, audit log | **新建** `argus/governance.py` | `python -m ch09.argus.cli ...` | ✅ import ch08 |
| **Ch10** | composition — orchestrator 把 7 module 接起来 | **新建** `argus/orchestrator.py` (= Listing 10.1) | `python -m ch10.argus.cli ...` | ✅ import ch09 |

### Argus 必须能跑的"金句场景"

书里 Ch5-Ch9 章首每个都有一段第一人称叙事 (token-waste / scope-creep / critic-loop / four-agent chaos / espionage)。这些是 Argus 的灵魂。**至少 Ch10 的 demo 要能让读者真感受到**:

- Ch5 token waste 故事 → demo 跑一次, 不带 complexity_routing 撞预算 → 带 complexity_routing 省 80% token, 输出差异
- Ch6 scope creep 故事 → demo 跑一次, 不带 guardrail 改了 3 个文件 → 带 guardrail 拒绝 2 个 → audit log
- Ch7 critic-loop 故事 → demo 跑一次, 不带 reflection 5 issues 假阳 2 个 → 带 reflection 跑 pytest 砍假阳 → 3/5 → 3/3
- Ch10 composition → 把以上全部 wire 起来跑一个端到端 PR review

**用户原话** "真正能用、有点用、结构非常清晰" 就是这件事 — Argus 应该是 reader-runnable 的实际 agent, 不是 Listing 抄本。

---

## §3 · 章节级 patterns 清单 (轨 B · 独立 demo)

依据 Phase A · ch4-7 discovery, 每章 patterns/ 应该有的独立 demo:

| 章 | patterns/ 模块 (独立 demo, 不进 Argus) | 状态 |
|----|---------------------------------------|------|
| Ch3 | `context_triage.py` / `semantic_compaction.py` / `progressive_discovery.py` / `multimodal_fusion.py` | ✅ 已有 4 个 (但 `chain_of_thought` 等 import 引用未定义符号) |
| Ch4 | `hierarchical_memory.py` / `rag_pipeline.py` / `progress_tracker.py` / `failure_journal.py` | ✅ 已有 4 个 (需补 vector_db 默认实现) |
| Ch5 | `reasoning_trace.py` / `chain_of_thought.py` / `complexity_routing.py` / `tree_of_thoughts.py` / `hypothesis_testing.py` | ⚠️ 5 个有, 部分 import error |
| **Ch6** | `action_trace.py` / `prompt_chain.py` / `tool_dispatch.py` / `mcp_client.py` / `plan_and_execute.py` / `guardrail_sandwich.py` | ❌ **全缺** (整章不存在) |
| **Ch7** | `reflection_trace.py` / `generator_critic.py` / `skill_library.py` / `experience_replay.py` / `self_heal_loop.py` | ❌ **全缺** (整章不存在) |
| **Ch8** | `collaboration_trace.py` / `handoff_chain.py` / `fan_out_gather.py` / `adversarial_review.py` / `hierarchical_delegation.py` / `swarm_intelligence.py` | ❌ **全缺** |
| **Ch9** | `governance_trace.py` / `permission_gate.py` / `sandbox.py` / `trust_levels.py` / `audit_log.py` / `policy_engine.py` | ❌ **全缺** |
| Ch10 | (本章不写新 pattern, 写 orchestrator) | — |

**总缺**: ch06-ch09 整章 (轨 A + 轨 B 都缺)。

### 书中已确认的 patterns 数量统计

| 章 | argus/ listing 数 | patterns/ listing 数 |
|----|----------------|------------------|
| Ch4 | 1 (memory.py) | 8 (多个跟 hierarchical_memory 相关的 sub-listing) |
| Ch5 | 3 (reasoning.py 三 b-listing 合并) | 7 |
| **Ch6** | **0** (但 §6.8 声称有 action.py) | 12 |
| **Ch7** | **0** (但 §7.x 声称有 reflection.py / self_heal.py) | 18 |

Ch6 / Ch7 的不一致是书层面的 — 见 §4 文字调整建议。

---

## §4 · 必须改文字的位置 (最小化)

用户原则: **能用代码搞定就别动文字**。下面只列代码完全无法 reconcile 的位置:

### F1 · Ch6 §6.8 检查点表 → 加 listing 或改措辞 🔴

**问题**: Ch6 §6.8 Table 6.11 列出 `argus/action.py` 5 个 capability, 但章里 0 个 argus/ listing。两条路:
- **路 A** (优先, 用户偏好): 我在仓库写 `argus/action.py` (集成 5 capability), 书不改
- **路 B** (fallback): 把表格从 "argus/action.py" 改成 "这些 pattern 可以组合进 Argus, 见 repo `ch06-action/argus/`"

**推荐**: 路 A — 写代码搞定。

### F2 · Ch7 §x 检查点 → 同 F1 🔴

**问题**: `argus/reflection.py` + `argus/self_heal.py` 声称存在, 章里 0 个 argus/ listing。
**推荐**: 路 A — 我在 ch07-reflection/argus/ 写两个薄 facade 包 patterns/generator_critic + patterns/self_heal_loop。

### F3 · Ch10 文件名命名冲突 🟡

**问题**: Listing 10.1 caption 写 `argus/orchestrator.py`, Table 10.13 写 `argus/agent.py`。**两个名字指同一文件**。
**推荐**: **改书** — 选一个 (建议 `argus/orchestrator.py`, 因为 Listing caption 是 figurer 引用源, 更权威), 把 Table 10.13 那行 Ch10 改成 orchestrator.py。
**位置**: `Chapters/v6/ch10/Chapter-10-Composing-Patterns-20260512.md` 找 `agent.py` Ch10 行。

### F4 · Ch3 §3.7 perception 没接 core 🟡

**问题**: Ch3 §3.7 引入 `argus/perception.py`, 但**章里没 Listing 把它接回 `argus/core.py`**。用户期待"一章一章长出来", 但 Ch3 实际只长了个孤儿模块。
**推荐**: 代码搞定 — Ch3 仓库加一个 cli.py 或 README 显式演示 "perception → core" 接法 (不动书)。如果太重要也可考虑书加一个 Listing 3.6 "wiring perception into review_diff" (2-3 行 import + 一行调用)。

### F5 · 模型 id `claude-sonnet-4-6` 不存在 🔴

**问题**: 几个文件用 `claude-sonnet-4-6`, 这不是公开模型 id。
**推荐**: 代码搞定 — 全仓库替换为 **`claude-sonnet-4-5-20250929`** (实际公开 id), 加 `model_config.py` 集中管理。**书不改** (书写 sonnet-4-6 是 placeholder, 真实 model id 应在配套 repo 的 config 里)。

—— 以上 5 条, 4 条用代码完成, **只有 F3 一处必须改书** (8 个字符的命名修正, 不动 listing 内容)。

---

## §5 · 实施 plan (分 5 阶段, 用户决定何时启动)

### Phase 1 · 仓库基础整顿 (1 天) 🔴

1. 加 `model_config.py` 集中模型 id (统一改 sonnet-4-5)
2. 补 `requirements.txt`: 加 `chromadb` (Ch4 RAG 用) + `pytest`
3. 修 README: 把"cumulative"承诺降级为"chapter-keyed + Ch10 orchestrator integrates", **或** 实施 Phase 2 后保留 cumulative 承诺
4. 清 `[CA]` 怪标记 (MD typesetter cue leakage)
5. 重写 `tools/smoke_test.py` — 加 "end-to-end 跑得起来" 验证 (不只是 import 干净)

### Phase 2 · Argus 主线 cumulative 改造 (3-4 天) 🔴

按 §2 表格, **每章 argus/ 必须 import 前章 argus/**:

```python
# ch04-memory/argus/__init__.py
from designing_ai_agents.ch03_perception.argus import (
    gather_review_context, FileContext, PerceptionTrace
)
from .memory import ArgusMemory, MemoryTrace

__all__ = [
    'gather_review_context', 'FileContext', 'PerceptionTrace',  # from ch03
    'ArgusMemory', 'MemoryTrace',                                # ch04 new
]
```

让 ch04 `__init__.py` 真的 re-export ch03 — 这样读者 `from ch04.argus import *` 拿到 ch02+ch03+ch04 全部 API。

- 单元任务: 7 章 × 1 章 = 7 个 PR-sized unit (可并行 worktree)

### Phase 3 · 补齐 Ch6-Ch9 缺失章节 (5-7 天) 🔴

按 §3 表格, 每章:
- 写 `argus/<module>.py` (薄 facade, 兑现 §6.8 / §7.x / §8.8 / §9.8 检查点表承诺)
- 写 `patterns/*.py` (每章 5-6 个独立 demo, 跟书 listing 一一对应)
- 写 `cli.py` + README

### Phase 4 · Ch10 orchestrator + 端到端 demo (2 天) 🔴

- 实施 `argus/orchestrator.py` (Listing 10.1 的真实可跑版本)
- 写 4 个 demo: token-waste 故事 / scope-creep 故事 / critic-loop 故事 / 完整 PR review
- 跑得起来, 输出真实差异 (有 reflection 跑 pytest 后 precision 3/5 → 3/3)
- 这是"真正能用"的兑现, 是 §10.10 那句"This is not a toy example"的硬背书

### Phase 5 · 文字微调 + 一致性扫尾 (0.5 天) 🟢

- 改书: §3 列的 F3 一处 (orchestrator.py vs agent.py)
- 改 repo README: 把"cumulative 承诺"换成实际兑现的措辞
- 仓库 root 加 `CONTRIBUTING.md` + chapter README 模板
- 跑全章 smoke + end-to-end demo, 出 status badge

### 工作量估算

| Phase | 持续 | 并行单元 |
|-------|------|--------|
| 1 基础整顿 | 1 天 | 1 |
| 2 cumulative 改造 | 3-4 天 | 7 (worktree) |
| 3 补 Ch6-9 章 | 5-7 天 | 4 (worktree, 一章一 worktree) |
| 4 Ch10 orchestrator | 2 天 | 1 (必须串行, 集大成) |
| 5 文字 + 扫尾 | 0.5 天 | 1 |
| **合计** | **~14 天单串行 / ~6-8 天用 worktree 并行** | |

---

## §6 · 风险 + 注意

| 风险 | 应对 |
|------|------|
| 用户在书已 ship 到 MEAP, repo 改动跟 MEAP v01 的 5 章发生 reference 偏移 | Phase 2 改 Ch2-Ch5 时**保持 listing 字面跟书一致**, 只改 `__init__.py` re-export 层 + 接通 cumulative — 书里的 Listing 都不动 |
| Ch7 0615.docx 刚发出去, repo 落地后 §F2 提到的 `argus/reflection.py` 措辞如果跟书不一致, 反而给 Rebecca 添 confusion | Phase 3 写 `argus/reflection.py` 时 method 命名按书 §7.x 检查点表的 capability 描述 (critic loop on review quality / bounded retry with rollback) — 跟书前后描述对得上, Willem 那条"前后描述一致就可以" |
| Ch10 §10.10 那句"Every method call maps to a working class"是硬承诺, Phase 4 没兑现 Phase 1-3 都白费 | Phase 4 必做且必须严格 — Listing 10.1 的每个 `from argus import ...` 都要在 repo 找到真 class |
| 模型 id `sonnet-4-6` 真换成 `sonnet-4-5` 后, 书 Listing 里 `model='claude-sonnet-4-6'` 字面看着不对 | 仓库 `model_config.py` 里抽常量, 书 Listing 可保留 `MODEL = config.SONNET` 这种间接引用 (不动书更稳, 加 config 即可) |
| Phase 2 改 ch04/ch05 的 facade 类时, 跟 v7_after_0601 Willem 批注里的 ArgusMemory / Argus reasoning fragment 描述要 reconcile | 参照 `21-Agent设计模式/02-Designing-AI-Agents/03-书稿/Chapters/v6/ch4/willem_comments/` (如有) 或 ch4-7 discovery 拿到的描述 |

---

## §7 · 下一步

3 个选择:

1. **先做 Phase 1 (1 天)** — 基础整顿先, 低风险, 不动主线, 看完先有信心再推进
2. **直接进 Phase 2-3 并行** — worktree 启动 7+4=11 个并行 unit, 6-8 天完成 Ch2-Ch9
3. **先单做 Ch10 §10.10 兑现 (Phase 4 优先)** — 把书的硬承诺先兑现, 之后回填 Ch2-Ch9 (反向工作, 有风险但 marketing impact 大)

我推荐 **1 → 2 → 4 → 3 → 5** 串行 + 部分并行, 在 ~7-10 天内完成全部。

**等你点头哪条先走。** 上述 blueprint 已落档, 如果你想改任何一节直接说。

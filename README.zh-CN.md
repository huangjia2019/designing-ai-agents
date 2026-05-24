# Designing AI Agents — 配套代码

<a href="https://www.manning.com/books/designing-ai-agents">
  <img src="./docs/manning-book-card.png" alt="Designing AI Agents — Manning Publications, MEAP" width="480">
</a>

**[Designing AI Agents — Manning Publications](https://www.manning.com/books/designing-ai-agents)** · 黄佳 · MEAP 已开放 · ISBN 9781633433632

本仓库是这本书的官方源码——每个 listing 按章节组织，全部在 Python 3.12 上验证可导入。

English: [README.md](README.md)

> **想按双轴矩阵而不是按章节看每个模式？** 配套目录在
> [**huangjia2019/agent-design-patterns**](https://github.com/huangjia2019/agent-design-patterns)
> —— 28 个模式，每个按 7 × 6 矩阵坐标放置，每个独立可跑。本仓库按
> 书的章节叙事组织（Argus 一章一章长出来）；那个仓库是你可以直接
> 拎进项目用的模式参考。

---

## 目录结构

```
designing-ai-agents/
├── ch01-paradigm-shift/     第 1 章 — 范式对比（无需 API）
├── ch02-architecture/       第 2 章 — PRA 循环、Runtime VM、跨框架实现
├── ch03-perception/         第 3 章 — 4 种感知模式 + Argus 集成
├── ch04-memory/             第 4 章 — 4 种记忆模式 + Argus 集成
└── ch05-reasoning/          第 5 章 — 4 种推理模式 + Argus 集成
```

每一章独立，内部有两个同级目录：

- **`patterns/`** — 每个模式一个文件，无框架耦合。构造函数接受可注入
  的 `llm` / `vector_db`。
- **`argus/`** — Argus（贯穿全书的代码审查示例智能体）的累积快照，
  第 2–10 章逐模块演进。

## 安装

```bash
git clone https://github.com/huangjia2019/designing-ai-agents
cd designing-ai-agents
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 填入 ANTHROPIC_API_KEY / OPENAI_API_KEY
```

需要 Python **3.10+**（书中用的是 3.12）。

## 运行

大多数 pattern 文件是自包含的。进入某一章后执行：

```bash
cd ch03-perception
python patterns/context_triage.py    # 纯 Python 实现，无需 API Key
```

需要调用 LLM 的文件会读取 `ANTHROPIC_API_KEY`（OpenAI SDK 示例读
`OPENAI_API_KEY`）。没有 key 也能 import 干净，但 `main()` 执行需要。

## 书与代码的对应关系

| 章节 | 目录 | Listing 编号 |
|------|------|--------------|
| 第 1 章 范式转变 | `ch01-paradigm-shift/` | 示例代码，无 Listing |
| 第 2 章 Agent 架构 | `ch02-architecture/` | 2.1 – 2.6 |
| 第 3 章 感知 | `ch03-perception/` | 3.1 – 3.5e |
| 第 4 章 记忆 | `ch04-memory/` | 4.1 – 4.8 |
| 第 5 章 推理 | `ch05-reasoning/` | 5.1 – 5.5c |

各章 README 给出 listing 到文件的完整映射。第 6-10 章将在书稿评审完成
后陆续上线。

## 少数文件是 *概念性* 的，不独立可跑

书中有些架构草图和方法片段不是完整文件：

- `ch02-architecture/argus/runtime.py` — 引用了书中未定义的辅助类
  （`RuntimeConfig`、`Sandbox`、`MCPHost` 等），属于结构伪代码。
- `ch05-reasoning/argus/reasoning.py` — 3 段代码（Listings 5.2b、5.3b、
  5.5c）是 `Argus` 类的方法片段，仅作概念参考。

这两个文件的 docstring 开头已明确标注。第 1–5 章其他 21 个 Python 文件
都能干净 import，无任何副作用。

## 自检

代码在抽取时经过：

- 语法检查（AST 解析）
- 导入检查（模块体能无错执行）
- 自动剥除 `[CA]` 排版续行标记

状态：**22 可运行 / 23 总数**（1 个为设计意图上的概念性文件）。自己跑
冒烟测试：

```bash
python3 tools/smoke_test.py
```

## 许可证

MIT，见 [LICENSE](LICENSE)。

## 引用

如果这些代码帮到了你，请引用本书：

> 黄佳. *Designing AI Agents*. Manning Publications, 2027 年出版.

## 联系

- 勘误与讨论：Manning liveBook 论坛（MEAP 发布后）
- 代码问题：本仓库的 GitHub Issues
- 作者：[@huangjia2019](https://github.com/huangjia2019)

# Designing AI Agents — 配套代码

<a href="https://hubs.la/Q04hCsH10">
  <img src="./docs/manning-book-card.png" alt="Designing AI Agents — Manning" width="480">
</a>

**[*Designing AI Agents*](https://hubs.la/Q04hCsH10)** 是一本面向生产系统的
AI Agent 设计模式书。本仓库是全书的官方配套代码。

English: [README.md](README.md)

> 如果你想按 7 × 6 双轴矩阵查找 28 个独立模式，而不是按书的章节阅读，
> 请使用 [huangjia2019/agent-design-patterns](https://github.com/huangjia2019/agent-design-patterns)。
> 那是模式目录；本仓库负责书中的渐进式实现与 Argus 贯穿案例。

## 两条代码线

每章目录包含两类代码：

- **`argus/`**：代码审查 Agent Argus 的章级快照。从第 2 章到第 10 章，
  感知、记忆、推理、行动、反思、协作和治理模块逐章累积。
- **`patterns/`**：本章模式的独立、可运行示例。并非每个模式都需要接入
  Argus；未接入的模式仍保留为教学实现。

这是按章节组织的教学仓库，不是一个全局可导入的 Python 包。目录名带连字符，
章内代码也使用本地模块导入，因此请先进入目标章节再运行。不要把多个章节目录
同时加入同一个 Python 进程的模块搜索路径。

## 目录

```text
designing-ai-agents/
├── ch01-paradigm-shift/     第 1 章 — 范式转变
├── ch02-architecture/       第 2 章 — Agent 架构与 PRA 循环
├── ch03-perception/         第 3 章 — 感知
├── ch04-memory/             第 4 章 — 记忆
├── ch05-reasoning/          第 5 章 — 推理
├── ch06-action/             第 6 章 — 行动
├── ch07-reflection/         第 7 章 — 反思
├── ch08-collaboration/      第 8 章 — 协作
├── ch09-governance/         第 9 章 — 治理
├── ch10-methodology/        第 10 章 — 组合方法与完整 Argus
└── tools/smoke_test.py      全仓语法与导入冒烟测试
```

各章 README 在需要时给出 Listing 到源码文件的映射。Listing 可能省略模块
说明、导入语句或演示入口；对应源码文件提供可运行的完整上下文。

## 安装

需要 Python **3.10+**；书稿和仓库主要以 Python 3.12 验证。

```bash
git clone https://github.com/huangjia2019/designing-ai-agents
cd designing-ai-agents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

根目录的 `requirements.txt` 安装共享依赖以及第 2、8 章跨框架示例使用的
OpenAI Agents SDK、LangGraph 和 Google ADK。MCP、向量数据库或 notebook
等其他可选依赖，会在相应章节 README 中说明。没有 API Key 时，所有章节
仍可做语法和导入检查；Google ADK 示例是 live-only，运行时需配置
`GOOGLE_API_KEY` 和 `GOOGLE_GENAI_USE_VERTEXAI=FALSE`。

## 运行

运行第 10 章的离线完整示例：

```bash
cd ch10-methodology
python3 demos/demo_end_to_end_review.py
```

运行某个独立模式：

```bash
cd ch03-perception
python3 patterns/context_triage.py
```

## 自检

```bash
python3 tools/smoke_test.py
```

当前基线：

- **219/219** 个 Python 文件通过 AST 解析
- **10/10** 个章节级 Argus 导入检查通过
- 第 5 章另有 **16** 个离线行为测试（含 30 个累计快照子测试）

冒烟测试验证语法和导入边界；涉及审批、路径约束、信任升级或多 Agent
失败处理的行为，还应运行相应的语义测试。

## 许可证与反馈

MIT，见 [LICENSE](LICENSE)。代码问题请提交 GitHub Issue；书稿勘误请使用
Manning liveBook 的反馈渠道。

引用：黄佳，*Designing AI Agents*，Manning Publications。

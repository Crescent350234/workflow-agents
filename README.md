# Homework 2 · 多 Agent 协作系统（编码 Agent + 修复 Agent + 编排器）

在 Homework 1「单 Agent 代码助手」之上扩展出的多 Agent 系统，实现「生成 → 验证 → 修复」
自动化编码闭环。**零第三方依赖**，直接可运行。

## 目录结构

```
homework2-agent/
├── run.py                 # 启动入口
├── Design.md              # 设计文档（架构与评审对应）
├── README.md              # 本文件
├── .env.example           # 真实 LLM 接入配置样例
├── src/
│   ├── __init__.py
│   ├── agent.py           # CodeAgent（ReAct 循环，支持注入 tools/prompt）
│   ├── tools.py           # 工具集（5 个基础 + write_file + edit_file）
│   ├── llm.py             # LLMClient（复用 Homework 1，真实/Mock）
│   ├── memory.py          # Memory（复用 Homework 1）
│   ├── orchestrator.py    # 多 Agent 编排器（新增核心）
│   ├── scripted_llm.py    # 离线脚本化 LLM（演示用）
│   └── cli.py             # 命令行交互
└── samples/
    ├── calc.py            # 示例被测代码（含 Bug，供演示起点）
    └── test_calc.py       # 零依赖测试套件（退出码判定通过与否）
```

## 快速开始

### 1) 离线演示（无需 API Key）

```bash
python run.py --demo
```

会依次看到：
1. 编码 Agent 用 `write_file` 生成一份含 Bug 的 `calc.py`（`add` 写成减法、`div` 未处理除零）；
2. 编排器运行 `python test_calc.py` → **失败**；
3. 修复 Agent 读文件 → 用 `edit_file` 修正 `add`、给 `div` 加除零保护 → 自验；
4. 编排器再次运行测试 → **通过**，打印结果报告并退出码 0。

### 2) 接入真实 LLM 运行

```bash
cp .env.example .env      # 填入 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
python run.py --task "实现 calc.py：add 与 div，并通过测试" --workdir samples --test "python test_calc.py"
```

`LLMClient` 兼容 OpenAI / 通义千问 DashScope / DeepSeek 等 OpenAI 风格接口。

### 3) 直接验证测试

```bash
cd samples && python test_calc.py     # 观察通过/失败（退出码 0 / 1）
```

## 角色说明

| 角色 | 职责 | 关键工具 |
|------|------|----------|
| 编码 Agent (coder) | 按需求生成可运行代码并落盘 | `write_file` + 5 个基础工具 |
| 修复 Agent (fixer) | 针对测试失败做最小、精准修改 | `edit_file` + 读/列/运行/检索 |
| 编排器 (Orchestrator) | 调度两 Agent、统一运行测试、迭代修复（≤3 轮） | — |

## 安全约束

- 写/改操作只能落在 `workdir` 内，越权路径直接拒绝；
- `edit_file` 要求 `old_string` 精确匹配，避免误改；
- `run_command` 仅允许白名单命令前缀，禁止任意执行。

详见 `Design.md`。

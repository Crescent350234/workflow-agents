"""便捷启动入口。

用法：
  python run.py --demo              # 离线脚本化演示（无需 API Key）
  python run.py --task "..."        # 用真实 LLM 运行（需在 .env 配置 Key）
  python run.py --task "..." --workdir samples --test "python test_calc.py"
"""
from src import cli

if __name__ == "__main__":
    cli.main()

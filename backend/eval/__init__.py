"""评测 harness：与 src 业务代码分离的独立评测目录。

检索层（Phase 2）：
- dataset/qa_eval.jsonl：黄金测试集（半自动构造）
- metrics.py：检索指标（hit@1 / hit@k / recall@k / MRR，纯函数）
- run_retrieval_eval.py：检索跑分并输出报告
- dump_qa.py：导出数据库问答，辅助维护测试集

生成层（Phase 3）：
- judge.py：LLM-as-judge（答案正确性 / 忠实度）
- run_answer_eval.py：跑完整 RAG 问答并判定答案质量

- reports/：每次运行的结果（按 --tag 存档），用于前后对比
"""

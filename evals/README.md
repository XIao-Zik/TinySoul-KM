# TinySoul-KM 评测

## QA 评测集（06 文档 §2.1 的落地）

- `qa_set.jsonl`：每行一题 `{id, question, answers, source_refs, kind}`。
  - `answers`：可接受的答案要点（小写子串匹配）；
  - `source_refs`：标准答案所在的知识文档（km_id 或 store 相对路径），hit@k 以"返回 ref 命中任一 source"计；
  - `kind`：`fact`（单文档事实）/ `synthesis`（跨文档综合）/ `holdout`（防泄漏对照，never-touch）。
- 构建流程与人工复核要求见 `docs/pkm/06-testing-eval-and-packaging.md`。
- 当前集合基于程序化生成的基准 vault（`bench5k`：5000 笔记，主题/双链/标签已知），作为检索质量的回归基线；真实个人笔记的题目随数据接入滚动补充（人工复核比例 ≥ 80% 的要求适用于真实数据题）。

## 运行

```bash
python evals/run_eval.py --root my-pkm --vault <vault> --qa evals/qa_set.jsonl
```

输出 hit@1 / hit@5 / hit@10 / MRR。当前词法路（lexical-only）为基线；向量路在 embedding 凭据可用后按同集复测，两种模式记录进 `evals/report.md`（M6）。

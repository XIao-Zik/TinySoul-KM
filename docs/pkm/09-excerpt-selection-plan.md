# 卡片摘录改进计划：结构感知选段替换头截断（09）

> **执行对象**：新会话。本文自包含，无需其他上下文。
> 项目根：`D:\ProgramData\RESUME\TinySoul-Agent-main\TinySoul-Agent-main`（下称 `<root>`）
> 分支：`pkm` ｜ 上游改动纪律：见 docs/pkm/00 §6（本计划**全部为新增文件 + 一处既有函数内部改写**，不碰白名单）

---

## 1. 背景与问题

每日反思的知识卡片（`tinysoul/plugins/knowledge/actions/card.py`）通过 `KnowledgeEngine.document_excerpt()` 给模型喂候选文档摘录。当前实现（`tinysoul/plugins/knowledge/engine.py:733`）：

```python
def document_excerpt(self, entry: KnowledgeIndexEntry, max_chars: int = 1200) -> str:
    text = self._store.read_document(entry.path, source=entry.source)
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text
```

**问题**：超过 1200 字符的文档做头部截断，不合理——
1. Markdown 是结构化文档，开头常是 frontmatter/引言，核心内容（表格、代码、结论）可能在任何位置，截掉的是"任意的 80%";
2. 切口内容盲，可能腰斩表格/代码块/结论；
3. 与检索管道不一致（设计文档 03 §5.1 已定义段落级切分 + 标题路径前缀，但从未实现）；
4. **截断误差传播**：annotations 写回用同一份摘录，长文档的 km_summary 只反映头部，污染下游检索。

**当初的合理性**：12 篇候选 × 1200 字符 ≈ 14K 字符的上下文预算，头截断是零成本确定性解法。**本计划保留预算，把"怎么花预算"变聪明。**

## 2. 目标与非目标

**目标**
- `document_excerpt` 对短文档（去 frontmatter 后 ≤ budget）行为不变：返回全文；
- 对长文档：按结构选段，**同样的字符预算装信息量最高的段落**，确定性、零 API 依赖、可离线验证；
- 函数签名不变（`document_excerpt(entry, max_chars=1200)`），调用方 `card.py:168` 零改动。

**非目标（本计划不做，防止范围蔓延）**
- 不做 embedding 预选（评测报告 §4：embedding API 余额问题未解决，本计划必须可离线验证；留作二期，选段器留好 scorer 接口即可）；
- 不动 card.py 的 prompt / schema / 校验逻辑；
- 不动检索 corpus、不动 MAX_DAILY_CANDIDATES=12、不加 low-confidence 代码过滤（各自是独立小任务）。

## 3. 设计

### 3.1 新增模块 `<root>/tinysoul/plugins/knowledge/excerpt.py`（纯函数，无 IO）

```python
@dataclass(frozen=True)
class Section:
    heading_path: tuple[str, ...]   # 如 ("背景", "动机")；无标题段落为 ()
    body: str                       # 该节正文（含节内子结构）
    position: int                   # 在文档中的顺序号
    score: float                    # 启发式得分

def split_sections(text: str) -> list[Section]: ...
def score_section(section: Section) -> float: ...   # 独立函数，便于二期换 embedding scorer
def build_excerpt(text: str, *, max_chars: int = 1200) -> str: ...
```

### 3.2 切分规则（split_sections）

1. 先用现成的 `split_frontmatter`（`ingest/obsidian.py:57`，engine.py 已 import）剥掉 frontmatter——标题/标签已由 card.py 的候选清单单独提供，frontmatter 不占预算；
2. 按 ATX 标题（`#`–`###`，行首 `#{1,3} `）切分，维护标题路径栈（进入更深一级 push，离开 pop）；
3. ** fenced code block 内的 `#` 行不是标题**：先标记围栏状态再判断（``` 或 ~~~ 开关）；
4. 无任何标题的长文档回退：按空行切段落组，heading_path 为 ()；
5. CRLF 容错（统一按 `\n` 处理后再输出原文换行）；空文档返回单个空节。

### 3.3 打分规则（score_section，全部确定性启发式）

| 信号 | 得分 |
|---|---|
| 有标题（heading_path 非空），H2 比H1/H3 略高 | +2 / +1.5 / +1 |
| 正文长度在 100–800 字符（信息密度甜区） | +2 |
| 含表格（`\|` 表头分隔行）或代码围栏 | +2 |
| 含列表（行首 `- `/`1. `） | +1 |
| 首节 / 末节（引言与结论位置） | +1 |
| 超长节（>1500 字符，得分惩罚，选段后仍可被预算截断） | -1 |

权重是初始值，目的只是"比头部截断好"，不追求最优——**文档里注明这是启发式 v1，消融留给评测**。

### 3.4 选段与拼接（build_excerpt）

```
1. sections = split_sections(text)（已去 frontmatter）
2. if 全文长度（去 frontmatter）<= max_chars: return 全文正文   # 短文档行为不变
3. 按 score 降序贪心选段，累计长度（含拼接开销）超过 max_chars 即停
4. 选中的 sections 按 position 升序重新排列后拼接：
   - 每节前插入标题路径行（如 "### 背景 / 动机"）；heading_path 为空则不加
   - 相邻两节在原文中不相邻时，插入一行 "…（中间省略 N 节）"
5. 拼接结果若仍超 max_chars（标题行开销），从已选中剔除得分最低的一节重拼（循环直到 ≤ 预算）
```

**关键不变量**：输出永不超 max_chars；选中节在文档中的原始顺序呈现（对 LLM 保持叙述连贯）；被省略的内容有明确标记（模型知道摘录不完整，这正是头截断没有的诚实性）。

### 3.5 engine 改动（唯一一处既有代码）

`engine.py:733` 的 `document_excerpt` 改为委托：

```python
def document_excerpt(self, entry: KnowledgeIndexEntry, max_chars: int = 1200) -> str:
    text = self._store.read_document(entry.path, source=entry.source)
    return build_excerpt(text, max_chars=max_chars)
```

`card.py` 不改（它用默认参数）。`annotations` 走同一份摘录，自动一起受益。

## 4. 测试计划

新增 `tests/km/test_excerpt.py`（风格对齐现有 test_card_executor.py：纯函数直测，无网络）：

1. `test_short_document_unchanged`：≤ 预算文档返回去 frontmatter 全文（回归保障）；
2. `test_tail_section_selected`：构造 5000 字符文档、关键事实放最后一个 H2 节 → 摘录包含该关键词（**头截断会失败的核心用例**）;
3. `test_budget_respected`：各种长度输入，`len(output) <= max_chars`；
4. `test_selected_sections_in_document_order`：得分乱序时输出仍按原文顺序；
5. `test_omission_marker_present`：有省略时输出含省略标记；
6. `test_code_fence_not_split`：长代码块作为整体选入或整体排除，且块内 `#` 注释不误判为标题；
7. `test_headingless_fallback`：无标题长文档按段落组切分仍可用；
8. `test_deterministic`：同输入两次调用输出相同；
9. `test_frontmatter_excluded`：frontmatter 不出现在摘录、不计预算。

扩展 `tests/km/test_card_executor.py`：
10. `test_card_prompt_contains_tail_fact`：长文档尾节关键词出现在 LLM 收到的候选块中（端到端串起 card.py:168 → engine → excerpt）。

**回归门槛**：`pytest tests/ -x` 全绿（含架构约束测试 `test_architecture.py`——新模块只被 knowledge 插件引用，不应破坏依赖方向约束）。

## 5. 验收与评测

1. 微基准（写进 `docs/pkm/08-execution-record.md`）：合成 20 篇 3000–8000 字符文档、每篇关键事实随机放尾节，断言摘录捕获率 100%（头截断基线 ≈ 0%）；
2. Day-1 端到端重跑：`tinysoul start --root my-pkm` 反思出卡 → 卡片引用校验仍 100% 通过、annotations 正常写回；
3. 在 08 执行文档登记：改动文件清单 + 微基准数字 + "启发式 v1，embedding scorer 为二期"。

## 6. 提交拆分（沿用 `feat(km):` 纪律）

1. `feat(km): excerpt 模块——结构感知选段（split/score/build 纯函数）` + 单测 1–8
2. `feat(km): document_excerpt 委托 build_excerpt，卡片摘录替换头截断` + 测试 9–10
3. `docs(km): 08 执行记录登记摘录改进与微基准`

## 7. 执行顺序 Checklist

- [ ] 1. 新建 `tinysoul/plugins/knowledge/excerpt.py`：Section/split_sections（含围栏状态机、frontmatter 剥离）
- [ ] 2. score_section + build_excerpt（贪心选段 + 原序拼接 + 预算循环剔除）
- [ ] 3. tests/km/test_excerpt.py 测试 1–8 全绿
- [ ] 4. engine.document_excerpt 改委托（engine.py:733 一处）
- [ ] 5. test_excerpt.py 测试 9 + test_card_executor.py 测试 10
- [ ] 6. `pytest tests/ -x` 全绿
- [ ] 7. 微基准脚本跑数 → 登记 08 执行文档 → 三次结构化提交

## 8. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 选段器把重要节打分过低 | 省略标记让模型知道摘录不完整；启发式 v1 偏保守（表格/代码/列表都加分）；二期 embedding scorer 只需替换 score_section |
| 拼接后超预算 | 步骤 5 的循环剔除兜底，测试 3 覆盖 |
| 卡片质量回归 | 引用校验/去重等护栏不变；测试 10 保证尾节内容可达模型 |
| 回滚 | 改动集中在 engine.py 一处委托 + 新增文件；revert 单 commit 即回到头截断行为 |

"""文档模块通用转换工具：编码解码、Q/A 文本解析（不含业务逻辑）。"""


def decode_text(name: str, content: bytes) -> str:
    """把文件字节内容解码为 UTF-8 文本，失败给出可读错误。"""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"文件 {name} 不是有效的 UTF-8 文本") from exc


def parse_qa_text(text: str, source_name: str) -> list[tuple[str, str]]:
    """把 Q/A 文本解析为 (问题, 答案) 列表，一个问答对 = 一条记录 = 一个向量索引单元。

    规则：
    - Q:/A: 开头分别为问题行与答案行，支持半角/全角冒号；
    - # 开头的行是注释（.md 中视为标题），跳过；
    - 问答对之间的空行忽略；答案可跨多行（答案内部的空行会保留）；
    - 格式错误（答案缺问题、问题缺答案、Q 后不是 A）直接抛 ValueError，避免静默丢数据。
    """
    lines = text.splitlines()
    pairs: list[tuple[str, str]] = []
    current_q: str | None = None
    current_a: list[str] = []

    def flush() -> None:
        nonlocal current_q, current_a
        if current_q is None:
            return
        if not current_a:
            raise ValueError(f"{source_name}：问题「{current_q}」后面缺少 A: 答案")
        pairs.append((current_q, "\n".join(current_a)))
        current_q, current_a = None, []

    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            if current_q is not None and current_a:
                current_a.append(line)  # 答案内部的空行
            continue
        if line.startswith("#"):
            continue
        if line.startswith(("Q:", "Q：")):
            flush()
            current_q = line[2:].strip()
            if not current_q:
                raise ValueError(f"{source_name} 第 {lineno} 行：Q 的问题内容为空")
        elif line.startswith(("A:", "A：")):
            if current_q is None:
                raise ValueError(f"{source_name} 第 {lineno} 行：A 答案没有对应的 Q 问题")
            current_a = [line[2:].strip()]
        elif current_q is not None:
            if current_a:
                current_a.append(line)  # 答案续行
            else:
                raise ValueError(f"{source_name} 第 {lineno} 行：问题「{current_q}」之后必须是 A 答案")
        else:
            raise ValueError(f"{source_name} 第 {lineno} 行：无法识别的行，应为 Q:/A: 开头或 # 注释")

    flush()
    return pairs
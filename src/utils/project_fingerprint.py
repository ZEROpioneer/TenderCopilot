"""项目指纹提取工具（用于智能追踪：从标题/内容提取项目编号或名称）"""
import re
import hashlib
from typing import List, Tuple


def extract_project_refs_from_title(title: str) -> List[str]:
    """从公告标题提取可能关联的项目标识（用于更正/流标/废标/变更类公告）

    常见格式：
    - XXX项目更正公告
    - 关于XXX的更正公告
    - XXX项目流标公告
    - 项目编号：XXX 的废标公告
    - XXX竞争性谈判变更公告
    """
    if not title or not isinstance(title, str):
        return []
    title = title.strip()
    refs = []

    # 项目编号格式：字母数字-数字-字母数字 等
    code_patterns = [
        r'项目编号[：:\s]*([A-Za-z0-9\-]+)',
        r'编号[：:\s]*([A-Za-z0-9\-]{6,})',
        r'([A-Za-z0-9]{2,}-\d+-[A-Za-z0-9\-]+)',  # 如 2024-XXX-001
    ]
    for pat in code_patterns:
        for m in re.finditer(pat, title):
            refs.append(m.group(1).strip())

    # 项目名称格式：XXX项目 / 关于XXX的
    suffix_patterns = [
        r'(.+?)(?:项目)?(?:更正|流标|废标|变更)公告',
        r'关于[《「]?(.+?)[》」]?(?:的)?(?:更正|流标|废标|变更)',
        r'(.+?)项目(?:的)?(?:流标|废标)',
    ]
    for pat in suffix_patterns:
        for m in re.finditer(pat, title):
            name = m.group(1).strip()
            if len(name) >= 2 and name not in refs:
                refs.append(name)

    return list(dict.fromkeys(refs))


def normalize_for_fingerprint(s: str) -> str:
    """清洗字符串用于指纹计算"""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r'\s+', '', s.strip())


def make_fingerprint(s: str) -> str:
    """对清洗后的字符串生成 SHA256 指纹"""
    norm = normalize_for_fingerprint(s)
    if not norm:
        return ""
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()


def extract_project_refs_from_content(content: str) -> List[Tuple[str, str]]:
    """从公告内容提取项目编号和名称（用于招标公告保存到 interested_projects）

    Returns:
        [(project_code, project_name), ...]  可能多组，通常一组
    """
    if not content or not isinstance(content, str):
        return []
    refs = []

    # 项目编号
    code_m = re.search(r'项目编号[：:\s]*([A-Za-z0-9\-]{4,})', content)
    if code_m:
        code = code_m.group(1).strip()
        # 尝试项目名称（常在编号附近）
        name_m = re.search(r'项目名称[：:\s]*([^\n\r]{2,}?)(?:\n|$|。)', content)
        name = name_m.group(1).strip() if name_m else ""
        refs.append((code, name or code))

    # 无编号时尝试从标题或首段提取项目名
    if not refs:
        name_m = re.search(r'项目名称[：:\s]*([^\n\r]{2,}?)(?:\n|$|。)', content)
        if name_m:
            refs.append(("", name_m.group(1).strip()))

    return refs

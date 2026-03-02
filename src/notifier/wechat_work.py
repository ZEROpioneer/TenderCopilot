"""企业微信通知 - 按项目安全分段，避免 Markdown 语法破损"""

import time
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import requests
from loguru import logger

if TYPE_CHECKING:
    from src.schema import TenderItem


def get_byte_len(text: str) -> int:
    """精准计算 UTF-8 字节长度（企微限制 4096 字节）。"""
    return len(text.encode("utf-8"))


# 企微 markdown.content 限制 4096 字节，留出余量给标题前缀和换行符
MAX_BYTES = 3800
# 首条消息含 header，需为 send() 中的 prefix 预留空间（约 50 字节）
MAX_FIRST_MESSAGE_BYTES = 4046
# 单项目最大字节数，防止超长项目导致死循环或发送失败
MAX_SINGLE_PROJECT_BYTES = 3000
# 摘要最大展示字符数（防止超长摘要爆破）
MAX_SUMMARY_CHARS = 150


class WechatWorkNotifier:
    """企业微信机器人通知"""

    def __init__(self, config):
        self.webhook_url = config["wechat_work"].get("webhook_url", "")
        self.enabled = config["wechat_work"].get("enabled", False)
        self.mention_users = config["wechat_work"].get("mention_users", [])

    def send(
        self,
        content: str,
        projects: Optional[List["TenderItem"]] = None,
    ) -> bool:
        """发送 Markdown 消息。

        当 projects 非空时，使用「按项目安全分段」策略，确保 Markdown 结构完整。
        否则回退为单条发送（仅当 content 较短时）。
        """
        if not self.enabled or not self.webhook_url:
            logger.warning("⚠️ 企业微信通知未启用或未配置 webhook_url")
            return False

        if projects and len(projects) > 0:
            chunks = self._build_chunks_by_project(projects)
        else:
            chunks = self._fallback_chunk(content)

        if not chunks:
            logger.warning("⚠️ 空内容，跳过企业微信通知发送")
            return False

        total = len(chunks)
        logger.info(f"📤 正在发送企业微信通知，共 {total} 条消息（按项目分段）...")

        WECHAT_MAX_BYTES = 4096
        all_success = True
        for idx, chunk in enumerate(chunks, start=1):
            prefix = f"【第 {idx}/{total} 条】\n\n" if total > 1 else ""
            body = prefix + chunk
            if get_byte_len(body) > WECHAT_MAX_BYTES:
                logger.warning(
                    f"⚠️ 第 {idx} 条消息超 {WECHAT_MAX_BYTES} 字节，强制截断"
                )
                body = prefix + self._truncate_to_bytes(
                    chunk, WECHAT_MAX_BYTES - get_byte_len(prefix)
                )

            data = {
                "msgtype": "markdown",
                "markdown": {"content": body},
            }

            try:
                response = requests.post(
                    self.webhook_url, json=data, timeout=10
                )
                response.raise_for_status()

                result = response.json()
                errcode = result.get("errcode", -1)
                errmsg = result.get("errmsg", "未知")
                if errcode != 0:
                    logger.error(
                        f"企微推送失败，错误码: {errcode}, 错误信息: {errmsg} [第 {idx}/{total} 条]"
                    )
                    all_success = False
                else:
                    logger.success(f"✅ 企业微信通知第 {idx}/{total} 条发送成功")
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"❌ 企业微信通知第 {idx}/{total} 条请求异常: {e}"
                )
                all_success = False
            except ValueError as e:
                logger.error(
                    f"❌ 企业微信通知第 {idx}/{total} 条响应解析失败: {e}"
                )
                all_success = False
            finally:
                time.sleep(1.5)

        return all_success

    def _format_project_md(self, item: "TenderItem", index: int) -> str:
        """为单个项目生成完整 Markdown 文本（企微友好，永不截断语法）。
        强制限制摘要与评分明细长度，确保单项目字节数不超过 MAX_SINGLE_PROJECT_BYTES。
        """
        feas = getattr(item, "feasibility", None) or {}
        loc = (getattr(item, "location", "") or "未知").strip()
        title = (getattr(item, "title", "") or "未知项目").strip()

        header = f"### {index}. [{loc}] {title}"
        lines = [header + "\n"]

        budget = (
            getattr(item, "budget_info", "") or getattr(item, "budget", "") or ""
        )
        lines.append(f"💰 预算: {(budget or '').strip() or '未公布'}")

        summary = (
            getattr(item, "project_summary", "") or getattr(item, "summary", "") or ""
        )
        summary = (summary or "").strip() or "未知"
        if len(summary) > MAX_SUMMARY_CHARS:
            summary = summary[:MAX_SUMMARY_CHARS] + "..."
        lines.append(f"🎯 摘要: {summary}")

        conf = getattr(item, "confidentiality_req", "") or ""
        conf = (conf or "").strip() or "未知"
        if len(conf) > MAX_SUMMARY_CHARS:
            conf = conf[:MAX_SUMMARY_CHARS] + "..."
        lines.append(f"🛑 资质: {conf}")

        doc_dl = (
            getattr(item, "doc_deadline", "")
            or getattr(item, "deadline", "")
            or ""
        )
        lines.append(f"⏰ 报名截止: {(doc_dl or '').strip() or '未知'}")

        bid_dl = getattr(item, "bid_deadline", "") or ""
        lines.append(f"⏳ 开标时间: {(bid_dl or '').strip() or '未知'}")

        has_att = getattr(item, "has_attachments", False) or (item.get("has_attachments") if hasattr(item, "get") else False)
        lines.append("📎 附件: 有 (请登录军采网查看/下载)" if has_att else "📎 附件: 无")

        # 真实总分来自 feasibility 动态规则引擎，ai_score 仅作兜底
        total_score = feas.get("total")
        if total_score is None:
            total_score = getattr(item, "ai_score", 0) or 0
        score_line = f"🤖 评分: {float(total_score):.1f}/100"
        lines.append(score_line)

        url = getattr(item, "url", "") or ""
        if url:
            lines.append(f"🔗 [查看原文]({url})")

        lines.append("")
        md = "\n".join(lines)
        # 最终保险：若仍超 3000 字节，强制截断
        if get_byte_len(md) > MAX_SINGLE_PROJECT_BYTES:
            md = self._truncate_to_bytes(md, MAX_SINGLE_PROJECT_BYTES)
        return md

    def _truncate_to_bytes(self, text: str, max_bytes: int) -> str:
        """按 UTF-8 字节数截断，避免在字符中间切断。"""
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        while max_bytes > 0:
            try:
                return encoded[:max_bytes].decode("utf-8") + "..."
            except UnicodeDecodeError:
                max_bytes -= 1
        return "..."

    def _build_chunks_by_project(
        self, projects: List["TenderItem"]
    ) -> List[str]:
        """按项目循环拼装，使用 UTF-8 字节级精准称重，生成安全分段列表。"""
        chunks: List[str] = []
        current_chunk = ""
        index = 0

        # 按评分倒序，与报告顺序一致
        sorted_projects = sorted(
            projects,
            key=lambda x: (getattr(x, "feasibility", None) or {}).get("total", 0),
            reverse=True,
        )

        for p in sorted_projects:
            index += 1
            project_md = self._format_project_md(p, index)

            if not current_chunk:
                current_chunk = project_md
                continue

            # 字节级称重：拼接后若超 MAX_BYTES，则归档当前 chunk
            candidate = current_chunk + "\n" + project_md
            if get_byte_len(candidate) > MAX_BYTES:
                chunks.append(current_chunk)
                current_chunk = project_md
            else:
                current_chunk = candidate

        if current_chunk:
            chunks.append(current_chunk)

        if not chunks:
            return []

        header = (
            f"# 🎯 招标项目日报 - {datetime.now().strftime('%Y年%m月%d日')}\n\n"
            f"> 共 {len(projects)} 个项目\n\n---\n\n"
        )
        # 首 chunk 加 header 后需在 4096 限制内（为 prefix 预留空间）
        first_with_header = header + chunks[0]
        if get_byte_len(first_with_header) > MAX_FIRST_MESSAGE_BYTES:
            logger.warning(
                f"⚠️ 首条消息含 header 后超 {MAX_FIRST_MESSAGE_BYTES} 字节，将截断项目内容"
            )
            first_with_header = self._truncate_to_bytes(
                first_with_header, MAX_FIRST_MESSAGE_BYTES
            )
        chunks[0] = first_with_header
        return chunks

    def _fallback_chunk(self, content: str) -> List[str]:
        """无 projects 时的回退：单条发送（仅当字节数在限制内时）。"""
        if not content or not content.strip():
            return []
        content = content.strip()
        if get_byte_len(content) <= MAX_BYTES:
            return [content]
        logger.warning(
            f"⚠️ 报告过长({get_byte_len(content)} 字节)且无项目列表，仅发送前{MAX_BYTES}字节"
        )
        return [self._truncate_to_bytes(content, MAX_BYTES)]

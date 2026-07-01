from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import formatdate, make_msgid
from functools import partial

from app.config import settings
from app.infrastructure.log.logging_config import get_logger

logger = get_logger(__name__)


def _sender_address() -> Address:
    """Build an RFC 5322 / RFC 2047 compliant From address."""
    local_part, separator, domain = settings.SMTP_USERNAME.rpartition("@")
    if not separator or not local_part or not domain:
        raise ValueError("SMTP_USERNAME must be a valid email address")
    return Address(
        display_name=settings.EMAIL_FROM_NAME,
        username=local_part,
        domain=domain,
    )


def _build_message(
    to_addr: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> EmailMessage:
    """Construct a standards-compliant multipart email."""
    sender = _sender_address()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.domain)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def _send_sync(to_addr: str, subject: str, text_body: str, html_body: str) -> None:
    """Run in thread-pool executor — blocking SMTP call."""
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as smtp:
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        msg = _build_message(to_addr, subject, text_body, html_body)
        refused = smtp.send_message(
            msg,
            from_addr=settings.SMTP_USERNAME,
            to_addrs=[to_addr],
        )
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


async def send_email(to_addr: str, subject: str, text_body: str, html_body: str) -> None:
    """Send an email asynchronously via thread-pool."""
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping email to %s", to_addr)
        return
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        partial(_send_sync, to_addr, subject, text_body, html_body),
    )


async def send_verification_code(to_addr: str, code: str) -> None:
    """Send an email verification code."""
    subject = f"【{settings.EMAIL_FROM_NAME}】邮箱验证码"
    text_body = (
        f"您正在注册 PPT 智能生成系统。验证码：{code}。"
        "验证码 10 分钟内有效，请勿泄露给他人。"
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
      <h2 style="color:#B45309;margin-bottom:8px;">邮箱验证</h2>
      <p style="color:#374151;margin-bottom:16px;">您正在注册 <strong>PPT 智能生成系统</strong>，请使用以下验证码完成邮箱验证：</p>
      <div style="background:#FEF3C7;border:1px solid #F59E0B;border-radius:8px;padding:20px;text-align:center;margin:16px 0;">
        <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#92400E;">{code}</span>
      </div>
      <p style="color:#6B7280;font-size:13px;">验证码 10 分钟内有效，请勿泄露给他人。</p>
    </div>
    """
    await send_email(to_addr, subject, text_body, html_body)


async def send_password_reset_code(to_addr: str, code: str) -> None:
    """Send a password reset code."""
    subject = f"【{settings.EMAIL_FROM_NAME}】密码重置验证码"
    text_body = (
        f"您正在重置 PPT 智能生成系统账户密码。验证码：{code}。"
        "验证码 10 分钟内有效，若非本人操作请忽略。"
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
      <h2 style="color:#B45309;margin-bottom:8px;">密码重置</h2>
      <p style="color:#374151;margin-bottom:16px;">您正在重置 <strong>PPT 智能生成系统</strong> 账户密码，请使用以下验证码：</p>
      <div style="background:#FEF3C7;border:1px solid #F59E0B;border-radius:8px;padding:20px;text-align:center;margin:16px 0;">
        <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#92400E;">{code}</span>
      </div>
      <p style="color:#6B7280;font-size:13px;">验证码 10 分钟内有效，若非本人操作请忽略。</p>
    </div>
    """
    await send_email(to_addr, subject, text_body, html_body)


async def send_bind_email_code(to_addr: str, code: str) -> None:
    """Send a verification code when binding or changing an email address."""
    subject = f"【{settings.EMAIL_FROM_NAME}】绑定邮箱验证码"
    text_body = (
        f"您正在绑定或修改 PPT 智能生成系统的邮箱地址。验证码：{code}。"
        "验证码 10 分钟内有效，若非本人操作请忽略。"
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
      <h2 style="color:#B45309;margin-bottom:8px;">绑定或修改邮箱</h2>
      <p style="color:#374151;margin-bottom:16px;">您正在绑定或修改 <strong>PPT 智能生成系统</strong> 的邮箱地址，请使用以下验证码完成验证：</p>
      <div style="background:#FEF3C7;border:1px solid #F59E0B;border-radius:8px;padding:20px;text-align:center;margin:16px 0;">
        <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#92400E;">{code}</span>
      </div>
      <p style="color:#6B7280;font-size:13px;">验证码 10 分钟内有效，若非本人操作请忽略。</p>
    </div>
    """
    await send_email(to_addr, subject, text_body, html_body)

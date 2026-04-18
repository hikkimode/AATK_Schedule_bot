from __future__ import annotations

import html
import logging
import sys
import traceback
from typing import Any

from aiogram import Bot
from aiogram.types import Update
from aiogram.types.error_event import ErrorEvent
from loguru import logger as loguru_logger
from pydantic import ValidationError


class ExcelParseError(Exception):
    def __init__(self, message: str, row: int | None = None, column: str | None = None):
        self.row = row
        self.column = column
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.args[0]]
        if self.row:
            parts.append("строка " + str(self.row))
        if self.column:
            parts.append("колонка " + str(self.column))
        return " | ".join(parts)


class DatabaseIntegrityError(Exception):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.details = details or {}
        super().__init__(message)


def format_validation_error(error: ValidationError) -> str:
    messages = []
    for err in error.errors():
        loc = err.get("loc", [])
        if len(loc) >= 2:
            row = loc[0] if isinstance(loc[0], int) else "?"
            field = loc[1] if len(loc) > 1 else loc[0]
            msg = "Строкa " + str(row + 2) + ", поле '" + str(field) + "': " + str(err.get("msg", ""))
            messages.append(msg)
        else:
            joined = ".".join(str(x) for x in loc)
            msg = "Поле '" + joined + "': " + str(err.get("msg", ""))
            messages.append(msg)
    return "\n".join(messages)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    loguru_logger.remove()

    stdout_fmt = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    file_fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"

    loguru_logger.add(
        sys.stdout,
        format=stdout_fmt,
        level="INFO",
        colorize=True,
    )

    loguru_logger.add(
        "logs/bot.log",
        rotation="10 MB",
        retention="10 days",
        compression="zip",
        format=file_fmt,
        level="DEBUG",
        encoding="utf-8",
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def setup_exception_handlers(bot: Bot, admin_ids: set[int]):
    from loguru import logger

    async def global_error_handler(event: ErrorEvent) -> bool:
        # Extract update and exception from ErrorEvent
        update = event.update
        exception = event.exception
        
        user_id = None
        if update.message:
            user_id = update.message.from_user.id if update.message.from_user else None
        elif update.callback_query:
            user_id = update.callback_query.from_user.id if update.callback_query.from_user else None

        user_message = "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
        admin_message = None

        if isinstance(exception, ExcelParseError):
            user_message = "❌ Ошибка в Excel: " + str(exception)
            admin_message = "Excel Parse Error\nUser: " + str(user_id) + "\nError: " + str(exception)

        elif isinstance(exception, ValidationError):
            formatted = format_validation_error(exception)
            user_message = "❌ Ошибка в данных Excel:\n" + formatted[:500]
            admin_message = "Validation Error\nUser: " + str(user_id) + "\nDetails:\n" + formatted

        elif isinstance(exception, DatabaseIntegrityError):
            user_message = "❌ Ошибка базы данных. Проверьте уникальность записей."
            admin_message = "DB Integrity Error\nUser: " + str(user_id) + "\n" + str(exception) + "\nDetails: " + str(exception.details)

        elif isinstance(exception, ValueError):
            user_message = "❌ " + str(exception)

        else:
            tb = traceback.format_exc()
            logger.exception("Unhandled exception")
            # Escape HTML characters in traceback to prevent broken messages
            safe_tb = html.escape(tb[-2000:])
            admin_message = (
                f"🚨 <b>UNHANDLED ERROR</b>\n"
                f"<b>User:</b> {user_id}\n"
                f"<b>Type:</b> {type(exception).__name__}\n"
                f"<b>Message:</b> {html.escape(str(exception))}\n\n"
                f"<b>Traceback:</b>\n<pre>{safe_tb}</pre>"
            )

        try:
            if update.message:
                await update.message.answer(user_message)
            elif update.callback_query:
                await update.callback_query.answer(user_message[:200], show_alert=True)
        except Exception as e:
            logger.error("Failed to send error message: " + str(e))

        if admin_message:
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        admin_id, 
                        admin_message[:4000], 
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error("Failed to notify admin " + str(admin_id) + ": " + str(e))

        return True

    return global_error_handler

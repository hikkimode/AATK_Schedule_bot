"""
Admin handlers for advanced features including AI OCR for schedule parsing.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, PhotoSize
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from locales import get_text
from models import ScheduleV2
from schemas.lesson import LessonImportSchema
from services.ocr_service import OCRResult, OCRService, ParsedScheduleItem


router = Router()

# FSM States for OCR workflow
class OCRStates(StatesGroup):
    waiting_for_photo = State()
    confirm_parsed_data = State()


# Storage key for parsed OCR data in FSM
OCR_DATA_KEY = "ocr_parsed_data"
OCR_MESSAGE_KEY = "ocr_preview_message_id"


def _admin_ocr_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for OCR confirmation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить и сохранить", callback_data="ocr_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="ocr_cancel"),
            ]
        ]
    )


@router.message(Command("ocr"), F.chat.type == "private")
async def cmd_ocr(message: Message, state: FSMContext, role: str, **kwargs) -> None:
    """Start OCR workflow - ask user to send a photo."""
    if role not in {"teacher", "superadmin"}:
        await message.answer("❌ Эта команда доступна только администраторам.")
        return
    
    await state.set_state(OCRStates.waiting_for_photo)
    await message.answer(
        "📸 <b>ИИ-распознавание расписания</b>\n\n"
        "Отправьте фото листка с заменами в расписании.\n"
        "ИИ попытается распознать группы, предметы, преподавателей и кабинеты.\n\n"
        "<i>Убедитесь, что текст на фото читаемый.</i>",
        parse_mode="HTML"
    )


@router.message(OCRStates.waiting_for_photo, F.photo)
async def process_ocr_photo(
    message: Message,
    state: FSMContext,
    role: str,
    session: AsyncSession,
    bot: Bot,
    **kwargs
) -> None:
    """Process photo for OCR and show preview."""
    if not message.photo:
        return
    
    if role not in {"teacher", "superadmin"}:
        await message.answer("❌ Доступ запрещен.")
        await state.clear()
        return
    
    # Send loading message
    loading_msg = await message.answer("🔍 ИИ анализирует расписание...")
    
    try:
        # Get the largest photo
        photo: PhotoSize = message.photo[-1]
        
        # Download photo
        file_info = await bot.get_file(photo.file_id)
        if not file_info.file_path:
            raise ValueError("Could not get file path")
        
        # Download to memory
        photo_bytes = await bot.download_file(file_info.file_path)
        if not photo_bytes:
            raise ValueError("Could not download photo")
        
        image_bytes = photo_bytes.read()
        
        # Initialize OCR service
        ocr_service = OCRService()
        
        # Process image
        result: OCRResult = await ocr_service.process_image(image_bytes)
        
        # Delete loading message
        await loading_msg.delete()
        
        if not result.success or not result.items:
            error_msg = result.error_message or "Не удалось распознать расписание"
            await message.answer(
                f"❌ <b>Ошибка распознавания</b>\n\n{error_msg}\n\n"
                f"<i>Попробуйте:</i>\n"
                f"• Отправить более четкое фото\n"
                f"• Убедиться, что текст хорошо виден\n"
                f"• Использовать фото с хорошим освещением",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Format preview
        preview_text = ocr_service.format_preview(result.items)
        
        # Send preview with confirmation buttons
        preview_msg = await message.answer(
            preview_text,
            parse_mode="HTML",
            reply_markup=_admin_ocr_keyboard()
        )
        
        # Store data in FSM
        # Convert items to dicts for JSON serialization
        items_data = []
        for item in result.items:
            item_dict: dict[str, Any] = {
                "group_name": item.group_name,
                "subject": item.subject,
                "teacher": item.teacher,
                "room": item.room,
                "lesson_number": item.lesson_number,
                "day": item.day,
            }
            # Add times if available
            if item.lesson_number and item.lesson_number in ocr_service.LESSON_TIMES:
                start, end = ocr_service.LESSON_TIMES[item.lesson_number]
                item_dict["start_time"] = start
                item_dict["end_time"] = end
            items_data.append(item_dict)
        
        await state.update_data({
            OCR_DATA_KEY: items_data,
            OCR_MESSAGE_KEY: preview_msg.message_id,
        })
        await state.set_state(OCRStates.confirm_parsed_data)
        
    except Exception as e:
        logger.exception(f"OCR processing error: {e}")
        await loading_msg.edit_text(
            f"❌ <b>Ошибка обработки</b>\n\n"
            f"Не удалось обработать фото: {str(e)[:200]}\n\n"
            f"<i>Попробуйте позже или обратитесь к разработчику.</i>",
            parse_mode="HTML"
        )
        await state.clear()


@router.message(OCRStates.waiting_for_photo)
async def ocr_wrong_input(message: Message, state: FSMContext) -> None:
    """Handle non-photo input during OCR state."""
    await message.answer(
        "❌ Пожалуйста, отправьте фото с расписанием.\n"
        "Или отмените операцию командой /cancel"
    )


@router.callback_query(OCRStates.confirm_parsed_data, F.data == "ocr_confirm")
async def ocr_confirm_save(
    callback: CallbackQuery,
    state: FSMContext,
    role: str,
    session: AsyncSession,
    bot: Bot,
    **kwargs
) -> None:
    """Save parsed OCR data to database as drafts."""
    if not callback.from_user:
        return
    
    if role not in {"teacher", "superadmin"}:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    # Get stored data from FSM
    state_data = await state.get_data()
    items_data: list[dict[str, Any]] = state_data.get(OCR_DATA_KEY, [])
    
    if not items_data:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        await state.clear()
        return
    
    await callback.answer("💾 Сохранение...")
    
    try:
        # Prepare data for ScheduleV2 (grouped by group+day)
        grouped_data: dict[tuple[str, str], list[dict[str, Any]]] = {}
        errors: list[str] = []
        
        for idx, item in enumerate(items_data):
            g_name = item.get("group_name")
            day = item.get("day")
            if not g_name or not day:
                errors.append(f"Запись {idx+1}: не указана группа или день")
                continue
            
            lesson_num = item.get("lesson_number", 1)
            lesson_times = OCRService.LESSON_TIMES.get(lesson_num, ("", ""))
            
            lesson_entry = {
                "num": lesson_num,
                "name": item.get("subject"),
                "teacher": item.get("teacher"),
                "room": item.get("room"),
                "time_start": item.get("start_time") or lesson_times[0],
                "time_end": item.get("end_time") or lesson_times[1],
                "is_change": True,
                "is_published": False,
                "subgroup": 0,
            }
            
            key = (g_name, day)
            if key not in grouped_data:
                grouped_data[key] = []
            grouped_data[key].append(lesson_entry)
            
        if not grouped_data:
            await callback.message.edit_text(
                f"❌ <b>Ошибка сохранения</b>\n\n"
                f"Нет валидных данных для сохранения:\n" + "\n".join(errors[:5]),
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Update or create ScheduleV2 records
        for (g_name, day), new_lessons in grouped_data.items():
            # Get existing row
            stmt = select(ScheduleV2).where(
                ScheduleV2.group_name == g_name,
                ScheduleV2.day == day
            )
            res = await session.execute(stmt)
            sched = res.scalar_one_or_none()
            
            if sched:
                # Update lessons list (merge by lesson number)
                lessons_dict = {l["num"]: l for l in sched.lessons}
                for nl in new_lessons:
                    lessons_dict[nl["num"]] = nl
                # Sort by lesson number
                sched.lessons = sorted(lessons_dict.values(), key=lambda x: x["num"])
            else:
                # Create new row
                sched = ScheduleV2(
                    group_name=g_name,
                    day=day,
                    lessons=sorted(new_lessons, key=lambda x: x["num"])
                )
                session.add(sched)
        
        await session.commit()
        
        # Build success message
        success_lines = [
            "✅ <b>Замены сохранены как черновики</b>",
            "",
            f"📊 Групп/дней обновлено: {len(grouped_data)}",
            f"📝 Всего записей: {sum(len(l) for l in grouped_data.values())}",
        ]
        
        if errors:
            success_lines.append(f"\n⚠️ Пропущено с ошибками: {len(errors)}")
        
        success_lines.append("\n📲 Перейдите в веб-панель для публикации.")
        
        await callback.message.edit_text(
            "\n".join(success_lines),
            parse_mode="HTML"
        )
        
        await state.clear()
        
        logger.info(
            f"OCR data saved by user {callback.from_user.id}: "
            f"{len(schedule_data)} items for {len(affected_groups)} groups"
        )
        
    except Exception as e:
        logger.exception(f"OCR save error: {e}")
        await session.rollback()
        await callback.message.answer(
            f"❌ <b>Ошибка сохранения</b>\n\n"
            f"Не удалось сохранить данные: {str(e)[:200]}\n\n"
            f"<i>Попробуйте еще раз или обратитесь к разработчику.</i>",
            parse_mode="HTML"
        )
    finally:
        await state.clear()


@router.callback_query(OCRStates.confirm_parsed_data, F.data == "ocr_cancel")
async def ocr_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Cancel OCR workflow."""
    data = await state.get_data()
    preview_message_id: int | None = data.get(OCR_MESSAGE_KEY)
    
    await callback.answer("❌ Отменено")
    
    # Delete preview message
    try:
        if preview_message_id:
            await bot.delete_message(callback.message.chat.id, preview_message_id)
    except Exception:
        pass
    
    await callback.message.answer(
        "❌ Распознанные данные отменены.\n"
        "Отправьте /ocr для новой попытки."
    )
    await state.clear()


@router.callback_query(F.data == "ocr_cancel")
@router.callback_query(F.data == "ocr_confirm")
async def ocr_expired_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle callbacks when session expired."""
    current_state = await state.get_state()
    if current_state != OCRStates.confirm_parsed_data.state:
        await callback.answer("⚠️ Сессия истекла. Начните заново с /ocr", show_alert=True)
        await state.clear()

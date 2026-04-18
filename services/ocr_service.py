"""
OCR Service using Google Gemini AI for automatic schedule parsing from photos.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
from loguru import logger
from pydantic import BaseModel, Field, ValidationError


class ParsedScheduleItem(BaseModel):
    """Single parsed schedule item from OCR."""
    group_name: str | None = Field(None, description="Название группы (например, АиВО-11)")
    subject: str | None = Field(None, description="Название предмета")
    teacher: str | None = Field(None, description="ФИО преподавателя")
    room: str | None = Field(None, description="Номер кабинета/аудитории")
    lesson_number: int | None = Field(None, ge=1, le=10, description="Номер пары (1-10)")
    day: str | None = Field(None, description="День недели (Пн, Вт, Ср, Чт, Пт, Сб)")


@dataclass
class OCRResult:
    """Result of OCR processing."""
    success: bool
    items: list[ParsedScheduleItem]
    raw_response: str
    error_message: str | None = None


class OCRService:
    """Service for extracting schedule data from images using Gemini AI."""
    
    # Lesson times mapping for auto-filling
    LESSON_TIMES: dict[int, tuple[str, str]] = {
        1: ("08:30", "09:50"),
        2: ("10:00", "11:20"),
        3: ("11:30", "12:50"),
        4: ("13:00", "14:20"),
        5: ("14:30", "15:50"),
        6: ("16:00", "17:20"),
    }
    
    # Supported days
    DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    
    SYSTEM_PROMPT = """Ты — эксперт по расписаниям колледжа. На фото — замены в расписании.

Твоя задача:
1. Найди все группы, упомянутые на фото
2. Для каждой группы определи: предмет, преподавателя, кабинет, номер пары, день недели
3. Верни результат СТРОГО в формате JSON массива объектов

Формат ответа (одна строка JSON, без markdown):
[{"group_name": "АиВО-11", "subject": "Математика", "teacher": "Иванов И.И.", "room": "305", "lesson_number": 3, "day": "Пн"}]

Правила:
- Если данные не найдены, используй null для строковых полей
- lesson_number должен быть числом от 1 до 10
- day может быть: Пн, Вт, Ср, Чт, Пт, Сб
- Если день не указан явно, определи по контексту или используй null
- Если номер пары не указан явно, посмотри на время (08:30-09:50 = 1 пара и т.д.)
- НЕ используй markdown разметку (не оборачивай в ```json)
- Верни только JSON, без дополнительного текста"""
    
    def __init__(self, api_key: str | None = None) -> None:
        """Initialize OCR service with Gemini API key."""
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self._api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in environment or pass to constructor.")
        
        genai.configure(api_key=self._api_key)
        self._model = genai.GenerativeModel("gemini-1.5-flash")
        logger.info("OCRService initialized with gemini-1.5-flash")
    
    async def process_image(self, image_bytes: bytes) -> OCRResult:
        """Process image and extract schedule data.
        
        Args:
            image_bytes: Raw image bytes (JPEG, PNG, etc.)
            
        Returns:
            OCRResult with parsed items or error information
        """
        try:
            # Create image part for Gemini
            image_part = {"mime_type": "image/jpeg", "data": image_bytes}
            
            # Send to Gemini
            response = await self._model.generate_content_async(
                [self.SYSTEM_PROMPT, image_part],
                generation_config={
                    "temperature": 0.1,  # Low temperature for consistent output
                    "max_output_tokens": 2048,
                }
            )
            
            raw_text = response.text.strip()
            logger.debug(f"Gemini raw response: {raw_text[:500]}...")
            
            # Extract JSON from response (handle various formats)
            json_str = self._extract_json(raw_text)
            if not json_str:
                return OCRResult(
                    success=False,
                    items=[],
                    raw_response=raw_text,
                    error_message="Не удалось найти JSON в ответе ИИ. Попробуйте отправить более четкое фото."
                )
            
            # Parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}, text: {json_str[:200]}")
                return OCRResult(
                    success=False,
                    items=[],
                    raw_response=raw_text,
                    error_message=f"ИИ вернул невалидный JSON: {e}"
                )
            
            # Ensure data is a list
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                return OCRResult(
                    success=False,
                    items=[],
                    raw_response=raw_text,
                    error_message="ИИ вернул неожиданный формат данных (ожидался массив)"
                )
            
            # Validate each item with Pydantic
            valid_items: list[ParsedScheduleItem] = []
            validation_errors: list[str] = []
            
            for idx, item_data in enumerate(data):
                if not isinstance(item_data, dict):
                    validation_errors.append(f"Элемент {idx}: не является объектом")
                    continue
                
                try:
                    # Clean up data before validation
                    cleaned = self._clean_data(item_data)
                    item = ParsedScheduleItem.model_validate(cleaned)
                    
                    # Add lesson times if lesson_number is present
                    if item.lesson_number and item.lesson_number in self.LESSON_TIMES:
                        # Store times in raw_text for compatibility with bulk import
                        start_time, end_time = self.LESSON_TIMES[item.lesson_number]
                        # We'll add this metadata for the handler to use
                        item._start_time = start_time  # type: ignore
                        item._end_time = end_time  # type: ignore
                    
                    valid_items.append(item)
                except ValidationError as e:
                    field_errors = ", ".join([f"{err['loc']}: {err['msg']}" for err in e.errors()])
                    validation_errors.append(f"Элемент {idx}: {field_errors}")
                except Exception as e:
                    validation_errors.append(f"Элемент {idx}: {e}")
            
            if not valid_items and validation_errors:
                return OCRResult(
                    success=False,
                    items=[],
                    raw_response=raw_text,
                    error_message=f"Все элементы не прошли валидацию: {'; '.join(validation_errors[:3])}"
                )
            
            return OCRResult(
                success=True,
                items=valid_items,
                raw_response=raw_text,
                error_message=None
            )
            
        except Exception as e:
            logger.exception(f"OCR processing failed: {e}")
            return OCRResult(
                success=False,
                items=[],
                raw_response="",
                error_message=f"Ошибка при обработке изображения: {str(e)}"
            )
    
    def _extract_json(self, text: str) -> str | None:
        """Extract JSON string from text, handling markdown code blocks."""
        # Try to find JSON in markdown code blocks
        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        match = re.search(code_block_pattern, text)
        if match:
            return match.group(1).strip()
        
        # Try to find JSON array/object directly
        # Look for [...] or {...}
        json_pattern = r'(\[[\s\S]*\]|\{[\s\S]*\})'
        match = re.search(json_pattern, text)
        if match:
            return match.group(1).strip()
        
        # If text starts with [ or {, assume it's JSON
        text = text.strip()
        if text.startswith('[') or text.startswith('{'):
            return text
        
        return None
    
    def _clean_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Clean and normalize OCR data before validation."""
        cleaned: dict[str, Any] = {}
        
        for key, value in data.items():
            if value is None:
                cleaned[key] = None
                continue
            
            # Convert to string and strip
            str_value = str(value).strip()
            
            # Handle empty strings as null
            if str_value == "" or str_value.lower() == "null":
                cleaned[key] = None
                continue
            
            # Clean up lesson_number
            if key == "lesson_number":
                try:
                    # Handle "1 пара" -> 1
                    num_str = re.search(r'\d+', str_value)
                    if num_str:
                        cleaned[key] = int(num_str.group())
                    else:
                        cleaned[key] = int(float(str_value))
                except (ValueError, TypeError):
                    cleaned[key] = None
                continue
            
            # Normalize day names
            if key == "day":
                day_mapping = {
                    "понедельник": "Пн", "пн": "Пн", "monday": "Пн",
                    "вторник": "Вт", "вт": "Вт", "tuesday": "Вт",
                    "среда": "Ср", "ср": "Ср", "wednesday": "Ср",
                    "четверг": "Чт", "чт": "Чт", "thursday": "Чт",
                    "пятница": "Пт", "пт": "Пт", "friday": "Пт",
                    "суббота": "Сб", "сб": "Сб", "saturday": "Сб",
                }
                cleaned[key] = day_mapping.get(str_value.lower(), str_value)
                continue
            
            cleaned[key] = str_value
        
        return cleaned
    
    def format_preview(self, items: list[ParsedScheduleItem]) -> str:
        """Format parsed items for user preview."""
        if not items:
            return "❌ Не найдено данных для отображения"
        
        lines = [
            "🔍 <b>Распознанное расписание замен</b>",
            f"📊 Найдено записей: {len(items)}",
            "",
        ]
        
        # Group by group_name for better display
        by_group: dict[str, list[ParsedScheduleItem]] = {}
        for item in items:
            group = item.group_name or "Без группы"
            if group not in by_group:
                by_group[group] = []
            by_group[group].append(item)
        
        for group_name, group_items in sorted(by_group.items()):
            lines.append(f"\n👥 <b>{group_name}</b>")
            
            # Sort by day then lesson number
            sorted_items = sorted(
                group_items,
                key=lambda x: (self.DAYS.index(x.day) if x.day in self.DAYS else 99, x.lesson_number or 99)
            )
            
            for item in sorted_items:
                day = item.day or "?"
                num = item.lesson_number or "?"
                subject = item.subject or "—"
                teacher = item.teacher or "—"
                room = item.room or "—"
                
                times = ""
                if item.lesson_number and item.lesson_number in self.LESSON_TIMES:
                    start, end = self.LESSON_TIMES[item.lesson_number]
                    times = f" ({start}-{end})"
                
                lines.append(f"  📅 {day}, {num}-я пара{times}")
                lines.append(f"     📘 {subject}")
                if item.teacher:
                    lines.append(f"     👤 {teacher}")
                if item.room:
                    lines.append(f"     🚪 {room}")
        
        lines.append("")
        lines.append("<i>Проверьте данные перед сохранением.</i>")
        
        return "\n".join(lines)

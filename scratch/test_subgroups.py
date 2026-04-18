import asyncio
import re
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from services.audit_service import ScheduleService
from models import Base, ScheduleV2
from schemas.schedule import LessonItem
import json

async def test_subgroup_logic():
    # 1. Test Regex
    subjects = [
        "Математика (1 подгр.)",
        "Физика(2подгр)",
        "Информатика (1 подгруппа)",
        "Английский 2 п.",
        "История (1)",
        "Физкультура"
    ]
    
    pattern = r"\(?\s*([12])\s*(?:подгр|гр|п)[а-яё]*\.?\s*\)?"
    
    print("--- Regex Testing ---")
    for s in subjects:
        match = re.search(pattern, s, re.IGNORECASE)
        subgroup = 0
        clean_name = s
        if match:
            subgroup = int(match.group(1))
            clean_name = re.sub(pattern, "", s, flags=re.IGNORECASE).strip()
        else:
            match_simple = re.search(r"\(\s*([12])\s*\)", s)
            if match_simple:
                subgroup = int(match_simple.group(1))
                clean_name = re.sub(r"\(\s*[12]\s*\)", "", s).strip()
        
        print(f"Original: '{s}' -> Subgroup: {subgroup}, Clean: '{clean_name}'")

    # 2. Test Filtering Logic
    print("\n--- Filtering Logic Testing ---")
    lessons_data = [
        {"num": 1, "name": "Общая пара", "subgroup": 0, "is_change": False},
        {"num": 2, "name": "Пара 1 подгруппы", "subgroup": 1, "is_change": False},
        {"num": 2, "name": "Пара 2 подгруппы", "subgroup": 2, "is_change": False},
        {"num": 3, "name": "Еще общая", "subgroup": 0, "is_change": False},
    ]
    
    lessons = [LessonItem.model_validate(item) for item in lessons_data]
    
    def filter_lessons(ls, sg):
        if sg == 0: return ls
        return [l for l in ls if l.subgroup == 0 or l.subgroup == sg]

    sg0 = filter_lessons(lessons, 0)
    print(f"Subgroup 0 (All) sees: {[l.name for l in sg0]}")
    
    sg1 = filter_lessons(lessons, 1)
    print(f"Subgroup 1 sees: {[l.name for l in sg1]}")
    
    sg2 = filter_lessons(lessons, 2)
    print(f"Subgroup 2 sees: {[l.name for l in sg2]}")

if __name__ == "__main__":
    asyncio.run(test_subgroup_logic())

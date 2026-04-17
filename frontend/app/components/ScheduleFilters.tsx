"use client";

import { useMemo, useState } from "react";

interface ScheduleChange {
  id: number;
  group_name: string | null;
  day: string | null;
  lesson_number: number | null;
  subject: string | null;
  teacher: string | null;
  room: string | null;
  start_time: string | null;
  end_time: string | null;
  raw_text: string | null;
}

interface ScheduleFiltersProps {
  changes: ScheduleChange[];
  children: (filteredChanges: ScheduleChange[]) => React.ReactNode;
}

const DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

// Search icon component
const SearchIcon = ({ className }: { className?: string }) => (
  <svg
    className={className}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

export default function ScheduleFilters({ changes, children }: ScheduleFiltersProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const filteredChanges = useMemo(() => {
    return changes.filter((change) => {
      // Filter by search query (group_name or subject, case-insensitive)
      const matchesSearch =
        !searchQuery ||
        (change.group_name?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false) ||
        (change.subject?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false);

      // Filter by selected day
      const matchesDay =
        !selectedDay ||
        (change.day?.toLowerCase().startsWith(selectedDay.toLowerCase()) ?? false);

      return matchesSearch && matchesDay;
    });
  }, [changes, searchQuery, selectedDay]);

  return (
    <div className="flex flex-col gap-4">
      {/* Search input with icon */}
      <div className="relative">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-tg-hint" />
        <input
          type="text"
          placeholder="Поиск по группе или предмету..."
          value={searchQuery}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setSearchQuery(e.target.value)
          }
          className="w-full pl-10 pr-4 py-3 rounded-xl border text-sm outline-none focus:ring-2 focus:ring-tg-link transition-all bg-tg-secondary text-tg-text border-tg-hint placeholder:text-tg-hint"
        />
      </div>

      {/* Day filter chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {DAYS.map((day) => (
          <button
            key={day}
            onClick={() => setSelectedDay(selectedDay === day ? null : day)}
            className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all border ${
              selectedDay === day
                ? "bg-tg-button text-tg-bg border-tg-button"
                : "bg-tg-secondary text-tg-text border-tg-hint hover:border-tg-link"
            }`}
          >
            {day}
          </button>
        ))}
      </div>

      {/* Results count */}
      <div className="text-sm text-tg-hint">
        Найдено: {filteredChanges.length} из {changes.length}
      </div>

      {/* Render filtered children */}
      {children(filteredChanges)}
    </div>
  );
}

"use client";

import { useMemo } from "react";
import toast from "react-hot-toast";

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
  is_published?: boolean;
}

interface PublishPanelProps {
  changes: ScheduleChange[];
  initData: string;
  onPublishSuccess: () => void;
}

// Publish icon
const PublishIcon = ({ className }: { className?: string }) => (
  <svg
    className={className}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
);

export default function PublishPanel({
  changes,
  initData,
  onPublishSuccess,
}: PublishPanelProps) {
  const draftCount = useMemo(() => {
    return changes.filter((c) => c.is_published === false).length;
  }, [changes]);

  const hasDrafts = draftCount > 0;

  const handlePublishAll = async () => {
    if (!initData) {
      toast.error("Ошибка авторизации");
      return;
    }

    const toastId = toast.loading("Публикация изменений...");

    try {
      const res = await fetch(
        "https://aatk-schedule-bot.onrender.com/schedule/publish-all",
        {
          method: "POST",
          headers: {
            Authorization: `tma ${initData}`,
            "Content-Type": "application/json",
          },
        }
      );

      if (!res.ok) {
        if (res.status === 403) {
          throw new Error("Доступ запрещен: требуются права администратора");
        }
        throw new Error(`Ошибка: ${res.status}`);
      }

      const data = await res.json();
      toast.success(
        `Опубликовано ${data.published_count || draftCount} изменений`,
        { id: toastId }
      );
      onPublishSuccess();
    } catch (err) {
      console.error("Publish error:", err);
      const message =
        err instanceof Error ? err.message : "Ошибка при публикации";
      toast.error(message, { id: toastId });
    }
  };

  if (!hasDrafts) {
    return null;
  }

  return (
    <div
      className={`fixed bottom-0 left-0 right-0 z-50 p-4 transition-all duration-300 ease-out transform ${
        hasDrafts ? "translate-y-0 opacity-100" : "translate-y-full opacity-0"
      }`}
    >
      <div className="bg-tg-secondary border border-tg-hint rounded-2xl shadow-lg p-4 max-w-md mx-auto">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1">
            <p className="text-sm text-tg-text font-medium">
              У вас {draftCount} неопубликованных{" "}
              {draftCount === 1
                ? "изменение"
                : draftCount < 5
                ? "изменения"
                : "изменений"}
            </p>
            <p className="text-xs text-tg-hint mt-1">
              Изменения видны только администраторам
            </p>
          </div>
          <button
            onClick={handlePublishAll}
            className="flex items-center gap-2 px-4 py-2.5 bg-tg-button text-white text-sm font-medium rounded-xl hover:opacity-90 active:scale-95 transition-all shadow-lg whitespace-nowrap"
          >
            <PublishIcon className="h-4 w-4" />
            Опубликовать для всех
          </button>
        </div>
      </div>
    </div>
  );
}

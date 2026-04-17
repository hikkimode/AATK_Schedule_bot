"use client";

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
}

const API_BASE_URL = "https://aatk-schedule-bot.onrender.com";

export function useScheduleActions(
  initData: string,
  isAdmin: boolean,
  fetchData: () => Promise<void>,
  setError: (error: string | null) => void
) {
  const getAuthHeaders = (): Record<string, string> => {
    if (!initData) return {} as Record<string, string>;
    return {
      Authorization: `tma ${initData}`,
      "Content-Type": "application/json",
    };
  };

  const handleDelete = async (id: number) => {
    if (!isAdmin) {
      setError("Только администраторы могут удалять записи");
      toast.error("Нет прав для удаления");
      return;
    }

    if (!window.confirm("Вы уверены, что хотите удалить эту замену?")) return;

    const toastId = toast.loading("Удаление...");

    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        if (res.status === 403) {
          throw new Error("Доступ запрещен: требуются права администратора");
        }
        throw new Error(`Ошибка: ${res.status}`);
      }

      await fetchData();
      toast.success("Замена удалена", { id: toastId });
    } catch (err) {
      console.error("Delete error:", err);
      const message = err instanceof Error ? err.message : "Ошибка при удалении";
      toast.error(message, { id: toastId });
      setError(message);
    }
  };

  const handleClearAll = async () => {
    if (!isAdmin) {
      setError("Только администраторы могут очищать замены");
      toast.error("Нет прав для очистки");
      return;
    }

    if (
      !window.confirm(
        "Вы уверены, что хотите удалить ВСЕ замены? Это действие нельзя отменить!"
      )
    )
      return;

    const toastId = toast.loading("Очистка...");

    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes/clear-all`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        if (res.status === 403) {
          throw new Error("Доступ запрещен: требуются права администратора");
        }
        throw new Error(`Ошибка: ${res.status}`);
      }

      await fetchData();
      toast.success("Все замены очищены", { id: toastId });
    } catch (err) {
      console.error("Clear all error:", err);
      const message = err instanceof Error ? err.message : "Ошибка при очистке";
      toast.error(message, { id: toastId });
      setError(message);
    }
  };

  const handleAdd = async (newChange: Partial<ScheduleChange>) => {
    if (!isAdmin) {
      setError("Только администраторы могут добавлять записи");
      toast.error("Нет прав для добавления");
      return false;
    }

    const toastId = toast.loading("Создание...");

    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(newChange),
      });

      if (!res.ok) {
        if (res.status === 403) {
          throw new Error("Доступ запрещен: требуются права администратора");
        }
        throw new Error(`Ошибка: ${res.status}`);
      }

      await fetchData();
      toast.success("Замена создана", { id: toastId });
      return true;
    } catch (err) {
      console.error("Create error:", err);
      const message = err instanceof Error ? err.message : "Ошибка при создании";
      toast.error(message, { id: toastId });
      setError(message);
      return false;
    }
  };

  const handleUpdate = async (id: number, editForm: Partial<ScheduleChange>) => {
    if (!isAdmin) {
      setError("Только администраторы могут редактировать записи");
      toast.error("Нет прав для редактирования");
      return false;
    }

    const toastId = toast.loading("Сохранение...");

    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes/${id}`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify(editForm),
      });

      if (!res.ok) {
        if (res.status === 403) {
          throw new Error("Доступ запрещен: требуются права администратора");
        }
        throw new Error(`Ошибка: ${res.status}`);
      }

      await fetchData();
      toast.success("Изменения сохранены", { id: toastId });
      return true;
    } catch (err) {
      console.error("Update error:", err);
      const message = err instanceof Error ? err.message : "Ошибка при сохранении";
      toast.error(message, { id: toastId });
      setError(message);
      return false;
    }
  };

  return {
    handleDelete,
    handleClearAll,
    handleAdd,
    handleUpdate,
  };
}

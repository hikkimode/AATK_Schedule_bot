"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import toast from "react-hot-toast";

// Telegram WebApp types
declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string;
        HapticFeedback: {
          impactOccurred: (style: "light" | "medium" | "heavy") => void;
          notificationOccurred: (type: "error" | "success" | "warning") => void;
        };
        colorScheme: "light" | "dark";
        onEvent: (event: string, handler: () => void) => void;
        offEvent: (event: string, handler: () => void) => void;
      };
    };
  }
}

// Icon Props Interface
interface IconProps {
  className?: string;
  style?: React.CSSProperties;
}

// SVG Icons
const RefreshCw = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
    <path d="M16 21h5v-5" />
  </svg>
);

const Users = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const UserCheck = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <polyline points="16 11 18 13 22 9" />
  </svg>
);

const Pencil = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
  </svg>
);

const Trash2 = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <line x1="10" y1="11" x2="10" y2="17" />
    <line x1="14" y1="11" x2="14" y2="17" />
  </svg>
);

const Plus = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const AlertTriangle = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const Clock = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

const SearchIcon = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

const BookOpen = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const PublishIcon = ({ className, style }: IconProps) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
);

const API_BASE_URL = "https://aatk-schedule-bot.onrender.com";

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

const DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

// Safe Haptic feedback helper with API existence checks
const triggerHaptic = (type: "light" | "medium" | "heavy" | "success" | "error") => {
  const haptic = window.Telegram?.WebApp?.HapticFeedback;
  if (!haptic) return; // Silent return if API unavailable (desktop, old clients)

  try {
    if (type === "light" || type === "medium" || type === "heavy") {
      haptic.impactOccurred(type);
    } else if (type === "success" || type === "error") {
      haptic.notificationOccurred(type);
    }
  } catch {
    // Ignore any haptic errors
  }
};

export default function Home() {
  const [isLoading, setIsLoading] = useState(true);
  const [changes, setChanges] = useState<ScheduleChange[]>([]);
  const [userCount, setUserCount] = useState<number>(0);
  const [activeCount, setActiveCount] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [initData, setInitData] = useState<string>("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [isInTelegram, setIsInTelegram] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  
  // Loading states for actions
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState<number | null>(null); // stores the id being deleted
  const [isPublishing, setIsPublishing] = useState(false);
  
  // Modal states
  const [showModal, setShowModal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState({
    group_name: "",
    subject: "",
    day: "",
    lesson_number: 1,
    teacher: "",
    room: "",
  });

  const getAuthHeaders = useCallback((): Record<string, string> => {
    if (!initData) return {};
    return {
      Authorization: `tma ${initData}`,
      "Content-Type": "application/json",
    };
  }, [initData]);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const changesRes = await fetch(`${API_BASE_URL}/schedule/changes`, {
        headers: getAuthHeaders(),
      });
      const statsRes = await fetch(`${API_BASE_URL}/bot/stats`, {
        headers: getAuthHeaders(),
      });

      if (!changesRes.ok || !statsRes.ok) {
        throw new Error(`HTTP error! status: ${changesRes.status}`);
      }

      const changesData: ScheduleChange[] = await changesRes.json();
      const statsData = await statsRes.json();

      setChanges(changesData);
      setUserCount(statsData.total_users);
      setActiveCount(statsData.active_users);
    } catch (err) {
      console.error("Fetch error:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setIsLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    if (typeof window !== "undefined" && window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      setInitData(tg.initData);
      setIsInTelegram(true);
      
      // Check admin status from initData
      try {
        const params = new URLSearchParams(tg.initData);
        const userJson = params.get("user");
        if (userJson) {
          const user = JSON.parse(userJson);
          setIsAdmin([123456789, 987654321].includes(user.id));
        }
      } catch {
        setIsAdmin(false);
      }
    } else {
      setIsInTelegram(false);
    }
  }, []);

  useEffect(() => {
    if (initData) {
      fetchData();
    }
  }, [initData, fetchData]);

  const filteredChanges = useMemo(() => {
    return changes.filter((change) => {
      const matchesSearch =
        !searchQuery ||
        (change.group_name?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false) ||
        (change.subject?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false);

      const matchesDay =
        !selectedDay ||
        (change.day?.toLowerCase().startsWith(selectedDay.toLowerCase()) ?? false);

      return matchesSearch && matchesDay;
    });
  }, [changes, searchQuery, selectedDay]);

  const draftCount = useMemo(() => {
    return changes.filter((c) => c.is_published === false).length;
  }, [changes]);

  const handleDelete = async (id: number) => {
    triggerHaptic("medium");
    if (!window.confirm("Удалить эту замену?")) return;

    setIsDeleting(id);
    const toastId = toast.loading("Удаление...");
    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        // Parse detailed error for 422
        if (res.status === 422) {
          const errorData = await res.json();
          const detail = errorData.detail;
          if (Array.isArray(detail)) {
            const messages = detail.map((err: { loc?: string[]; msg?: string }) => {
              const field = err.loc?.slice(-1)[0] || "поле";
              const fieldNames: Record<string, string> = {
                group_name: "Группа",
                subject: "Название предмета",
                day: "День недели",
                lesson_number: "Номер пары",
                teacher: "Преподаватель",
                room: "Кабинет",
              };
              return `Ошибка в поле '${fieldNames[field] || field}': ${err.msg}`;
            });
            throw new Error(messages.join("\n"));
          }
          throw new Error(detail || "Ошибка валидации");
        }
        throw new Error(`Ошибка сервера: ${res.status}`);
      }

      triggerHaptic("success");
      await fetchData();
      toast.success("Замена удалена", { id: toastId });
    } catch (err) {
      triggerHaptic("error");
      const message = err instanceof Error ? err.message : "Ошибка при удалении";
      toast.error(message, { id: toastId, duration: 5000 });
    } finally {
      setIsDeleting(null);
    }
  };

  const handlePublishAll = async () => {
    triggerHaptic("medium");
    setIsPublishing(true);
    const toastId = toast.loading("Публикация...");
    try {
      const res = await fetch(`${API_BASE_URL}/schedule/publish-all`, {
        method: "POST",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `Ошибка сервера: ${res.status}`);
      }

      const data = await res.json();
      triggerHaptic("success");
      await fetchData();
      toast.success(`Опубликовано ${data.published_count} замен`, { id: toastId });
    } catch (err) {
      triggerHaptic("error");
      const message = err instanceof Error ? err.message : "Ошибка публикации";
      toast.error(message, { id: toastId, duration: 5000 });
    } finally {
      setIsPublishing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    triggerHaptic("medium");
    
    if (isSubmitting) return; // Prevent double submission
    setIsSubmitting(true);

    const toastId = toast.loading(isEditing ? "Сохранение..." : "Создание...");
    try {
      const url = isEditing
        ? `${API_BASE_URL}/schedule/changes/${editingId}`
        : `${API_BASE_URL}/schedule/changes`;
      const method = isEditing ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: getAuthHeaders(),
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        // Parse detailed validation errors from FastAPI
        if (res.status === 422) {
          const errorData = await res.json();
          const detail = errorData.detail;
          
          if (Array.isArray(detail)) {
            // FastAPI validation error format: [{loc: ["body", "field"], msg: "...", type: "..."}]
            const messages = detail.map((err: { loc?: string[]; msg?: string }) => {
              const field = err.loc?.slice(-1)[0] || "поле";
              const fieldNames: Record<string, string> = {
                group_name: "Группа",
                subject: "Название предмета",
                day: "День недели",
                lesson_number: "Номер пары",
                teacher: "Преподаватель",
                room: "Кабинет",
              };
              return `Ошибка в поле '${fieldNames[field] || field}': ${err.msg}`;
            });
            throw new Error(messages.join("\n"));
          } else if (typeof detail === "string") {
            throw new Error(detail);
          }
        }
        throw new Error(`Ошибка сервера: ${res.status}`);
      }

      triggerHaptic("success");
      await fetchData();
      toast.success(isEditing ? "Изменения сохранены" : "Замена создана", { id: toastId });
      
      setShowModal(false);
      setIsEditing(false);
      setEditingId(null);
      setFormData({ group_name: "", subject: "", day: "", lesson_number: 1, teacher: "", room: "" });
    } catch (err) {
      triggerHaptic("error");
      const message = err instanceof Error ? err.message : "Ошибка при сохранении";
      toast.error(message, { id: toastId, duration: 5000 });
    } finally {
      setIsSubmitting(false);
    }
  };

  const openEditModal = (change: ScheduleChange) => {
    triggerHaptic("light");
    setIsEditing(true);
    setEditingId(change.id);
    setFormData({
      group_name: change.group_name || "",
      subject: change.subject || "",
      day: change.day || "",
      lesson_number: change.lesson_number || 1,
      teacher: change.teacher || "",
      room: change.room || "",
    });
    setShowModal(true);
  };

  const openAddModal = () => {
    triggerHaptic("light");
    setIsEditing(false);
    setEditingId(null);
    setFormData({ group_name: "", subject: "", day: "", lesson_number: 1, teacher: "", room: "" });
    setShowModal(true);
  };

  if (!isInTelegram) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ backgroundColor: "var(--tg-theme-bg-color)" }}>
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 mx-auto mb-4" style={{ color: "var(--tg-theme-hint-color)" }} />
          <p className="text-lg font-medium" style={{ color: "var(--tg-theme-text-color)" }}>
            Приложение доступно только в Telegram
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-32" style={{ backgroundColor: "var(--tg-theme-bg-color)" }}>
      {/* Safe area padding for iPhone */}
      <div className="h-[env(safe-area-inset-top)]" />
      
      {/* Sticky Header */}
      <header className="sticky top-0 z-40 backdrop-blur-xl border-b" style={{ 
        backgroundColor: "var(--tg-theme-bg-color)", 
        borderColor: "rgba(var(--tg-theme-hint-color), 0.2)" 
      }}>
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold" style={{ color: "var(--tg-theme-text-color)" }}>
                Расписание ААТК
              </h1>
              <p className="text-xs" style={{ color: "var(--tg-theme-hint-color)" }}>
                {isAdmin ? "Администратор" : "Просмотр"}
              </p>
            </div>
            <button 
              onClick={() => { triggerHaptic("light"); fetchData(); }}
              className="p-2 rounded-full active:scale-95 transition-transform"
              style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)" }}
            >
              <RefreshCw className="w-5 h-5" style={{ color: "var(--tg-theme-text-color)" }} />
            </button>
          </div>
        </div>
      </header>

      <main className="px-4 pt-4 space-y-4">
        {/* Stats Cards - Horizontal Scroll */}
        <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
          <div 
            className="flex-shrink-0 rounded-2xl p-4 min-w-[140px]"
            style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)" }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Users className="w-4 h-4" style={{ color: "var(--tg-theme-hint-color)" }} />
              <span className="text-xs" style={{ color: "var(--tg-theme-hint-color)" }}>Пользователи</span>
            </div>
            <p className="text-2xl font-bold" style={{ color: "var(--tg-theme-text-color)" }}>{userCount}</p>
          </div>
          <div 
            className="flex-shrink-0 rounded-2xl p-4 min-w-[140px]"
            style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)" }}
          >
            <div className="flex items-center gap-2 mb-2">
              <UserCheck className="w-4 h-4" style={{ color: "var(--tg-theme-hint-color)" }} />
              <span className="text-xs" style={{ color: "var(--tg-theme-hint-color)" }}>Активные</span>
            </div>
            <p className="text-2xl font-bold" style={{ color: "var(--tg-theme-text-color)" }}>{activeCount}</p>
          </div>
          <div 
            className="flex-shrink-0 rounded-2xl p-4 min-w-[140px]"
            style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)" }}
          >
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4" style={{ color: "var(--tg-theme-hint-color)" }} />
              <span className="text-xs" style={{ color: "var(--tg-theme-hint-color)" }}>Замены</span>
            </div>
            <p className="text-2xl font-bold" style={{ color: "var(--tg-theme-text-color)" }}>{changes.length}</p>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: "var(--tg-theme-hint-color)" }} />
          <input
            type="text"
            placeholder="Поиск по группе или предмету..."
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-3 rounded-2xl text-sm outline-none transition-all"
            style={{ 
              backgroundColor: "var(--tg-theme-secondary-bg-color)",
              color: "var(--tg-theme-text-color)"
            }}
          />
        </div>

        {/* Day Filter Chips */}
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
          {DAYS.map((day) => (
            <button
              key={day}
              onClick={() => { if (navigator.vibrate) navigator.vibrate(50); setSelectedDay(selectedDay === day ? null : day); }}
              className="px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all"
              style={{
                backgroundColor: selectedDay === day ? "var(--tg-theme-button-color)" : "var(--tg-theme-secondary-bg-color)",
                color: selectedDay === day ? "white" : "var(--tg-theme-text-color)"
              }}
            >
              {day}
            </button>
          ))}
        </div>

        {/* Results Count */}
        <p className="text-xs" style={{ color: "var(--tg-theme-hint-color)" }}>
          Найдено: {filteredChanges.length} из {changes.length}
        </p>

        {/* Changes List - Card Based */}
        <div className="space-y-3">
          {isLoading ? (
            // Skeleton loading
            Array.from({ length: 5 }).map((_, i) => (
              <div 
                key={i} 
                className="rounded-2xl p-4 animate-pulse"
                style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)" }}
              >
                <div className="flex items-center gap-3">
                  <div className="h-4 w-20 rounded" style={{ backgroundColor: "var(--tg-theme-hint-color)" }} />
                  <div className="h-4 flex-1 rounded" style={{ backgroundColor: "var(--tg-theme-hint-color)" }} />
                  <div className="h-4 w-16 rounded" style={{ backgroundColor: "var(--tg-theme-hint-color)" }} />
                </div>
              </div>
            ))
          ) : filteredChanges.length === 0 ? (
            // Empty State
            <div className="py-12 text-center">
              <BookOpen className="w-16 h-16 mx-auto mb-4 animate-bounce" style={{ color: "var(--tg-theme-hint-color)" }} />
              <p className="text-base font-medium" style={{ color: "var(--tg-theme-hint-color)" }}>
                Нет замен в расписании
              </p>
              <p className="text-sm mt-1" style={{ color: "var(--tg-theme-hint-color)" }}>
                Добавьте новую замену или измените фильтры
              </p>
            </div>
          ) : (
            filteredChanges.map((change) => (
              <div
                key={change.id}
                className="relative rounded-2xl p-4 transition-all active:scale-[0.98]"
                style={{ 
                  backgroundColor: "var(--tg-theme-secondary-bg-color)",
                  opacity: change.is_published === false ? 0.9 : 1
                }}
              >
                {/* Draft Badge */}
                {change.is_published === false && (
                  <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded-full text-xs" style={{ backgroundColor: "var(--tg-theme-button-color)", color: "white" }}>
                    <Clock className="w-3 h-3" />
                    Черновик
                  </div>
                )}

                {/* Card Header */}
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold text-base" style={{ color: "var(--tg-theme-text-color)" }}>
                    {change.group_name}
                  </span>
                  <span 
                    className="px-3 py-1 rounded-full text-sm font-medium"
                    style={{ 
                      backgroundColor: "rgba(var(--tg-theme-button-color), 0.2)", 
                      color: "var(--tg-theme-button-color)" 
                    }}
                  >
                    {change.lesson_number} пара
                  </span>
                </div>

                {/* Card Body */}
                <div className="mb-4">
                  <p className="text-lg font-semibold mb-1" style={{ color: "var(--tg-theme-text-color)" }}>
                    {change.subject}
                  </p>
                  <p className="text-sm" style={{ color: "var(--tg-theme-hint-color)" }}>
                    {change.teacher}{change.teacher && change.room ? " • " : ""}{change.room}
                  </p>
                </div>

                {/* Card Footer - Actions */}
                {isAdmin && (
                  <div className="flex items-center gap-2 pt-3 border-t" style={{ borderColor: "rgba(var(--tg-theme-hint-color), 0.2)" }}>
                    <button
                      onClick={() => openEditModal(change)}
                      className="flex items-center justify-center w-11 h-11 rounded-xl active:scale-95 transition-transform"
                      style={{ backgroundColor: "var(--tg-theme-bg-color)" }}
                    >
                      <Pencil className="w-5 h-5" style={{ color: "var(--tg-theme-text-color)" }} />
                    </button>
                    <button
                      onClick={() => handleDelete(change.id)}
                      disabled={isDeleting === change.id}
                      className="flex items-center justify-center w-11 h-11 rounded-xl active:scale-95 transition-transform disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{ backgroundColor: "rgba(239, 68, 68, 0.1)" }}
                    >
                      {isDeleting === change.id ? (
                        <div className="w-5 h-5 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Trash2 className="w-5 h-5" style={{ color: "#ef4444" }} />
                      )}
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </main>

      {/* Floating Action Button - Add */}
      {isAdmin && (
        <button
          onClick={openAddModal}
          className="fixed bottom-24 right-4 w-14 h-14 rounded-full shadow-lg flex items-center justify-center active:scale-95 transition-transform z-30"
          style={{ backgroundColor: "var(--tg-theme-button-color)" }}
        >
          <Plus className="w-6 h-6 text-white" />
        </button>
      )}

      {/* Publish Panel - Fixed Bottom */}
      {isAdmin && draftCount > 0 && (
        <div className="fixed bottom-0 left-0 right-0 p-4 z-50" style={{ paddingBottom: "max(16px, env(safe-area-inset-bottom))" }}>
          <div 
            className="rounded-2xl shadow-lg p-4"
            style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)" }}
          >
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--tg-theme-text-color)" }}>
                  {draftCount} неопубликованных {draftCount === 1 ? "замена" : draftCount < 5 ? "замены" : "замен"}
                </p>
                <p className="text-xs" style={{ color: "var(--tg-theme-hint-color)" }}>
                  Видны только администраторам
                </p>
              </div>
              <button
                onClick={handlePublishAll}
                disabled={isPublishing}
                className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium active:scale-95 transition-transform disabled:opacity-70 disabled:cursor-not-allowed"
                style={{ backgroundColor: "var(--tg-theme-button-color)", color: "white" }}
              >
                {isPublishing ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <PublishIcon className="w-4 h-4" />
                )}
                {isPublishing ? "Публикация..." : "Опубликовать"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ backgroundColor: "rgba(0, 0, 0, 0.5)" }}>
          <div 
            className="w-full max-w-md rounded-2xl p-4 max-h-[90vh] overflow-y-auto"
            style={{ backgroundColor: "var(--tg-theme-bg-color)" }}
          >
            <h2 className="text-lg font-bold mb-4" style={{ color: "var(--tg-theme-text-color)" }}>
              {isEditing ? "Редактировать замену" : "Новая замена"}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                type="text"
                placeholder="Группа"
                value={formData.group_name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, group_name: e.target.value })}
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)", color: "var(--tg-theme-text-color)" }}
                required
              />
              <input
                type="text"
                placeholder="Предмет"
                value={formData.subject}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, subject: e.target.value })}
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)", color: "var(--tg-theme-text-color)" }}
                required
              />
              <input
                type="text"
                placeholder="День (например: Понедельник)"
                value={formData.day}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, day: e.target.value })}
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)", color: "var(--tg-theme-text-color)" }}
                required
              />
              <input
                type="number"
                placeholder="Номер пары"
                value={formData.lesson_number}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, lesson_number: parseInt(e.target.value) })}
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)", color: "var(--tg-theme-text-color)" }}
                min="1"
                max="10"
                required
              />
              <input
                type="text"
                placeholder="Преподаватель"
                value={formData.teacher}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, teacher: e.target.value })}
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)", color: "var(--tg-theme-text-color)" }}
              />
              <input
                type="text"
                placeholder="Кабинет"
                value={formData.room}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, room: e.target.value })}
                className="w-full px-4 py-3 rounded-xl text-sm outline-none"
                style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)", color: "var(--tg-theme-text-color)" }}
              />
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => { triggerHaptic("light"); setShowModal(false); }}
                  disabled={isSubmitting}
                  className="flex-1 py-3 rounded-xl text-sm font-medium disabled:opacity-50"
                  style={{ backgroundColor: "var(--tg-theme-secondary-bg-color)", color: "var(--tg-theme-text-color)" }}
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 py-3 rounded-xl text-sm font-medium text-white disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  style={{ backgroundColor: "var(--tg-theme-button-color)" }}
                >
                  {isSubmitting && (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  )}
                  {isSubmitting ? (isEditing ? "Сохранение..." : "Создание...") : (isEditing ? "Сохранить" : "Создать")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

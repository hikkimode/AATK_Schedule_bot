"use client";

import { useEffect, useState, useCallback } from "react";

// Icons as simple SVG components
const RefreshCw = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
    <path d="M16 21h5v-5" />
  </svg>
);

const Users = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const UserCheck = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <polyline points="16 11 18 13 22 9" />
  </svg>
);

const Pencil = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
  </svg>
);

const Trash2 = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <line x1="10" y1="11" x2="10" y2="17" />
    <line x1="14" y1="11" x2="14" y2="17" />
  </svg>
);

const Plus = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const AlertTriangle = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const X = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const Check = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

declare global {
  interface Window {
    Telegram?: {
      WebApp: any;
    };
  }
}

interface BotStats {
  total_users: number;
  active_users: number;
}

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

// Simple Button component
function Button({
  children,
  onClick,
  disabled,
  className,
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`px-3 py-2 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      {children}
    </button>
  );
}

// Simple Card component
function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border ${className}`}>
      {children}
    </div>
  );
}

function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`p-4 ${className}`}>{children}</div>;
}

function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={`font-semibold ${className}`}>{children}</h3>;
}

function CardContent({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`p-4 pt-0 ${className}`}>{children}</div>;
}

// Simple Input component
function Input({
  id,
  type = "text",
  value,
  onChange,
  className,
  placeholder,
  min,
  max,
}: {
  id?: string;
  type?: string;
  value: string | number;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  className?: string;
  placeholder?: string;
  min?: number;
  max?: number;
}) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      min={min}
      max={max}
      className={`px-3 py-2 rounded-md border outline-none focus:ring-2 focus:ring-blue-500 ${className}`}
    />
  );
}

// Simple Label component
function Label({ htmlFor, children, className }: { htmlFor?: string; children: React.ReactNode; className?: string }) {
  return (
    <label htmlFor={htmlFor} className={`text-sm font-medium ${className}`}>
      {children}
    </label>
  );
}

// Simple Badge component
function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}

// Simple Skeleton loader
function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded ${className}`} />
  );
}

export default function Home() {
  const [userName, setUserName] = useState<string>("");
  const [userId, setUserId] = useState<number | null>(null);
  const [initData, setInitData] = useState<string>("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [isInTelegram, setIsInTelegram] = useState(true);
  const [stats, setStats] = useState<BotStats | null>(null);
  const [changes, setChanges] = useState<ScheduleChange[]>([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingChanges, setLoadingChanges] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<ScheduleChange>>({});
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newChange, setNewChange] = useState<Partial<ScheduleChange>>({
    group_name: "",
    subject: "",
    day: "",
    lesson_number: 1,
    teacher: "",
    room: "",
  });

  // List of admin IDs (should match config.superadmin_ids in backend)
  const ADMIN_IDS = [7748463140];

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (!window.Telegram?.WebApp) {
        setIsInTelegram(false);
        return;
      }

      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();

      // Store initData for API calls
      setInitData(tg.initData || "");

      const user = tg.initDataUnsafe?.user;
      if (user) {
        const fullName = [user.first_name, user.last_name]
          .filter(Boolean)
          .join(" ");
        setUserName(fullName);
        setUserId(user.id);
        setIsAdmin(ADMIN_IDS.includes(user.id));
      }
    }
  }, []);

  const getAuthHeaders = (): Record<string, string> => {
    if (!initData) return {} as Record<string, string>;
    return {
      "Authorization": `tma ${initData}`,
      "Content-Type": "application/json",
    };
  };

  const fetchData = useCallback(async () => {
    setLoadingStats(true);
    setLoadingChanges(true);
    setError(null);

    try {
      const headers = getAuthHeaders();
      const [statsRes, changesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/bot/stats`, { headers }),
        fetch(`${API_BASE_URL}/schedule/changes`, { headers }),
      ]);

      if (!statsRes.ok) {
        throw new Error("Failed to fetch stats: " + statsRes.status);
      }
      if (!changesRes.ok) {
        throw new Error("Failed to fetch changes: " + changesRes.status);
      }

      const statsData: BotStats = await statsRes.json();
      const changesData: ScheduleChange[] = await changesRes.json();

      setStats(statsData);
      setChanges(changesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoadingStats(false);
      setLoadingChanges(false);
    }
  }, [initData]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDelete = async (id: number) => {
    if (!isAdmin) {
      setError("Только администраторы могут удалять записи");
      return;
    }
    if (!window.confirm("Вы уверены, что хотите удалить эту замену?")) return;

    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        if (res.status === 403) throw new Error("Доступ запрещен: требуются права администратора");
        throw new Error("Failed to delete: " + res.status);
      }
      await fetchData();
    } catch (err) {
      console.error("Delete error:", err);
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const handleClearAll = async () => {
    if (!isAdmin) {
      setError("Только администраторы могут очищать замены");
      return;
    }
    if (!window.confirm("Вы уверены, что хотите удалить ВСЕ замены? Это действие нельзя отменить!")) return;

    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes/clear-all`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        if (res.status === 403) throw new Error("Доступ запрещен: требуются права администратора");
        throw new Error("Failed to clear all: " + res.status);
      }
      await fetchData();
    } catch (err) {
      console.error("Clear all error:", err);
      setError(err instanceof Error ? err.message : "Clear all failed");
    }
  };

  const handleEditStart = (change: ScheduleChange) => {
    setEditingId(change.id);
    setEditForm({ ...change });
  };

  const handleEditSave = async (id: number) => {
    if (!isAdmin) {
      setError("Только администраторы могут редактировать записи");
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes/${id}`, {
        method: "PATCH",
        headers: getAuthHeaders(),
        body: JSON.stringify(editForm),
      });
      if (!res.ok) {
        if (res.status === 403) throw new Error("Доступ запрещен: требуются права администратора");
        throw new Error("Failed to update: " + res.status);
      }
      setEditingId(null);
      await fetchData();
    } catch (err) {
      console.error("Update error:", err);
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const handleAdd = async () => {
    if (!isAdmin) {
      setError("Только администраторы могут добавлять записи");
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/schedule/changes`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(newChange),
      });
      if (!res.ok) {
        if (res.status === 403) throw new Error("Доступ запрещен: требуются права администратора");
        throw new Error("Failed to create: " + res.status);
      }
      setIsAddDialogOpen(false);
      setNewChange({
        group_name: "",
        subject: "",
        day: "",
        lesson_number: 1,
        teacher: "",
        room: "",
      });
      await fetchData();
    } catch (err) {
      console.error("Create error:", err);
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  if (!isInTelegram) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 bg-[#0f0f0f]">
        <Card className="bg-[#1a1a1a] border-[#2d2d2d] max-w-md w-full">
          <CardHeader>
            <CardTitle className="text-xl font-semibold text-white text-center">
              Доступ ограничен
            </CardTitle>
          </CardHeader>
          <CardContent className="text-center">
            <p className="text-gray-400 mb-4">
              Это приложение работает только внутри Telegram WebApp.
            </p>
            <p className="text-gray-500 text-sm">
              Пожалуйста, откройте бота через Telegram.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-full p-4 gap-4 bg-[#0f0f0f]">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">
          Привет, {userName || "Гость"}! 👋
        </h1>
        <Button
          onClick={fetchData}
          disabled={loadingStats || loadingChanges}
          className="border border-[#2d2d2d] bg-[#1a1a1a] hover:bg-[#2d2d2d] text-white text-sm"
        >
          <RefreshCw
            className={`h-4 w-4 mr-2 ${
              loadingStats || loadingChanges ? "animate-spin" : ""
            }`}
          />
          Обновить
        </Button>
      </header>

      {error && (
        <Card className="bg-red-950/50 border-red-900">
          <CardContent className="py-3">
            <p className="text-red-400 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Card className="bg-[#1a1a1a] border-[#2d2d2d]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400 flex items-center gap-2">
              <Users className="h-4 w-4" />
              Всего пользователей
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingStats ? (
              <Skeleton className="h-8 w-16 bg-[#2d2d2d]" />
            ) : (
              <p className="text-2xl font-bold text-white">
                {stats?.total_users.toLocaleString() || "0"}
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="bg-[#1a1a1a] border-[#2d2d2d]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-400 flex items-center gap-2">
              <UserCheck className="h-4 w-4" />
              Активные
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingStats ? (
              <Skeleton className="h-8 w-16 bg-[#2d2d2d]" />
            ) : (
              <p className="text-2xl font-bold text-green-400">
                {stats?.active_users.toLocaleString() || "0"}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="bg-[#1a1a1a] border-[#2d2d2d] flex-1">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg font-semibold text-white">
            Изменения расписания
          </CardTitle>
          <div className="flex gap-2">
            {isAdmin && (
              <Button
                onClick={() => setIsAddDialogOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm"
              >
                <Plus className="h-4 w-4 mr-1" />
                Добавить
              </Button>
            )}

            {isAdmin && (
              <Button
                onClick={handleClearAll}
                className="bg-red-600/80 hover:bg-red-700 text-white text-sm"
              >
                <AlertTriangle className="h-4 w-4 mr-1" />
                Очистить неделю
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#2d2d2d]">
                  <th className="text-left p-3 text-gray-400 font-medium">Группа</th>
                  <th className="text-left p-3 text-gray-400 font-medium">Предмет</th>
                  <th className="text-left p-3 text-gray-400 font-medium">Пара</th>
                  <th className="text-left p-3 text-gray-400 font-medium">День</th>
                  <th className="text-left p-3 text-gray-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {loadingChanges ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-[#2d2d2d]">
                      <td className="p-3"><Skeleton className="h-4 w-24 bg-[#2d2d2d]" /></td>
                      <td className="p-3"><Skeleton className="h-4 w-32 bg-[#2d2d2d]" /></td>
                      <td className="p-3"><Skeleton className="h-4 w-12 bg-[#2d2d2d]" /></td>
                      <td className="p-3"><Skeleton className="h-4 w-20 bg-[#2d2d2d]" /></td>
                      <td className="p-3"><Skeleton className="h-4 w-20 bg-[#2d2d2d]" /></td>
                    </tr>
                  ))
                ) : changes.length === 0 ? (
                  <tr className="border-b border-[#2d2d2d]">
                    <td colSpan={5} className="text-center text-gray-500 py-8">
                      Нет изменений в расписании
                    </td>
                  </tr>
                ) : (
                  changes.map((change) => (
                    <tr key={change.id} className="border-b border-[#2d2d2d] hover:bg-[#252525]">
                      <td className="p-3 font-medium text-white">
                        {editingId === change.id ? (
                          <Input
                            value={editForm.group_name || ""}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              setEditForm({ ...editForm, group_name: e.target.value })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8 text-sm"
                          />
                        ) : (
                          <Badge className="bg-blue-950/50 text-blue-300 border border-blue-900">
                            {change.group_name || "—"}
                          </Badge>
                        )}
                      </td>
                      <td className="p-3 text-gray-300">
                        {editingId === change.id ? (
                          <Input
                            value={editForm.subject || ""}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              setEditForm({ ...editForm, subject: e.target.value })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8 text-sm"
                          />
                        ) : (
                          change.subject || "—"
                        )}
                      </td>
                      <td className="p-3 text-white">
                        {editingId === change.id ? (
                          <Input
                            type="number"
                            min={1}
                            max={10}
                            value={editForm.lesson_number || 1}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              setEditForm({ ...editForm, lesson_number: parseInt(e.target.value) || 1 })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8 w-16 text-sm"
                          />
                        ) : (
                          <Badge className="border border-[#2d2d2d] text-gray-300">
                            {change.lesson_number || "—"}
                          </Badge>
                        )}
                      </td>
                      <td className="p-3 text-gray-400 text-sm">
                        {editingId === change.id ? (
                          <Input
                            value={editForm.day || ""}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              setEditForm({ ...editForm, day: e.target.value })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8 text-sm"
                          />
                        ) : (
                          change.day || "—"
                        )}
                      </td>
                      <td className="p-3">
                        <div className="flex gap-2">
                          {editingId === change.id ? (
                            <>
                              <Button
                                onClick={() => handleEditSave(change.id)}
                                className="h-8 w-8 p-0 text-green-400 hover:text-green-300 hover:bg-green-950/30 bg-transparent border-0"
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button
                                onClick={() => setEditingId(null)}
                                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-300 hover:bg-gray-800 bg-transparent border-0"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                onClick={() => handleEditStart(change)}
                                className="h-8 w-8 p-0 text-blue-400 hover:text-blue-300 hover:bg-blue-950/30 bg-transparent border-0"
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              {isAdmin && (
                                <Button
                                  onClick={() => handleDelete(change.id)}
                                  className="h-8 w-8 p-0 text-red-400 hover:text-red-300 hover:bg-red-950/30 bg-transparent border-0"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Modal Dialog */}
      {isAddDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-[#1a1a1a] border border-[#2d2d2d] rounded-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b border-[#2d2d2d] flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Добавить новую замену</h2>
              <Button
                onClick={() => setIsAddDialogOpen(false)}
                className="h-8 w-8 p-0 text-gray-400 hover:text-white bg-transparent border-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="p-4 grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="group" className="text-gray-300">Группа</Label>
                <Input
                  id="group"
                  value={newChange.group_name || ""}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setNewChange({ ...newChange, group_name: e.target.value })
                  }
                  className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                  placeholder="Например: ИС-101"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="subject" className="text-gray-300">Предмет</Label>
                <Input
                  id="subject"
                  value={newChange.subject || ""}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setNewChange({ ...newChange, subject: e.target.value })
                  }
                  className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                  placeholder="Например: Математика"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="day" className="text-gray-300">День</Label>
                  <Input
                    id="day"
                    value={newChange.day || ""}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNewChange({ ...newChange, day: e.target.value })
                    }
                    className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                    placeholder="Понедельник"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="lesson" className="text-gray-300">Пара №</Label>
                  <Input
                    id="lesson"
                    type="number"
                    min={1}
                    max={10}
                    value={newChange.lesson_number || 1}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNewChange({ ...newChange, lesson_number: parseInt(e.target.value) || 1 })
                    }
                    className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="teacher" className="text-gray-300">Преподаватель</Label>
                <Input
                  id="teacher"
                  value={newChange.teacher || ""}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setNewChange({ ...newChange, teacher: e.target.value })
                  }
                  className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                  placeholder="Иванов И.И."
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="room" className="text-gray-300">Аудитория</Label>
                <Input
                  id="room"
                  value={newChange.room || ""}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setNewChange({ ...newChange, room: e.target.value })
                  }
                  className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                  placeholder="305"
                />
              </div>
              <Button
                onClick={handleAdd}
                className="bg-green-600 hover:bg-green-700 text-white mt-2"
              >
                Сохранить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

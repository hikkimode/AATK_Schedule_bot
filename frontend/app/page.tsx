"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { RefreshCw, Users, UserCheck, Pencil, Trash2, Plus, AlertTriangle } from "lucide-react";

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

interface TelegramWebApp {
  ready: () => void;
  expand: () => void;
  initDataUnsafe: {
    user?: TelegramUser;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
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
  const ADMIN_IDS = [123456789]; // Replace with actual admin IDs

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

  const getAuthHeaders = () => {
    if (!initData) return {};
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
    <div className="flex flex-col min-h-full p-4 gap-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">
          Привет, {userName || "Гость"}! 👋
        </h1>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchData}
          disabled={loadingStats || loadingChanges}
          className="border-[#2d2d2d] bg-[#1a1a1a] hover:bg-[#2d2d2d] text-white"
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
              <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
                <DialogTrigger asChild>
                  <Button
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Добавить
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-[#1a1a1a] border-[#2d2d2d] text-white">
                  <DialogHeader>
                    <DialogTitle>Добавить новую замену</DialogTitle>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                      <Label htmlFor="group">Группа</Label>
                      <Input
                        id="group"
                        value={newChange.group_name || ""}
                        onChange={(e) =>
                          setNewChange({ ...newChange, group_name: e.target.value })
                        }
                        className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                        placeholder="Например: ИС-101"
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="subject">Предмет</Label>
                      <Input
                        id="subject"
                        value={newChange.subject || ""}
                        onChange={(e) =>
                          setNewChange({ ...newChange, subject: e.target.value })
                        }
                        className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                        placeholder="Например: Математика"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="grid gap-2">
                        <Label htmlFor="day">День</Label>
                        <Input
                          id="day"
                          value={newChange.day || ""}
                          onChange={(e) =>
                            setNewChange({ ...newChange, day: e.target.value })
                          }
                          className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                          placeholder="Понедельник"
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="lesson">Пара №</Label>
                        <Input
                          id="lesson"
                          type="number"
                          min={1}
                          max={10}
                          value={newChange.lesson_number || 1}
                          onChange={(e) =>
                            setNewChange({
                              ...newChange,
                              lesson_number: parseInt(e.target.value) || 1,
                            })
                          }
                          className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                        />
                      </div>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="teacher">Преподаватель</Label>
                      <Input
                        id="teacher"
                        value={newChange.teacher || ""}
                        onChange={(e) =>
                          setNewChange({ ...newChange, teacher: e.target.value })
                        }
                        className="bg-[#2d2d2d] border-[#3d3d3d] text-white"
                        placeholder="Иванов И.И."
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="room">Аудитория</Label>
                      <Input
                        id="room"
                        value={newChange.room || ""}
                        onChange={(e) =>
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
                </DialogContent>
              </Dialog>
            )}

            {isAdmin && (
              <Button
                size="sm"
                variant="destructive"
                onClick={handleClearAll}
                className="bg-red-600/80 hover:bg-red-700 text-white"
              >
                <AlertTriangle className="h-4 w-4 mr-1" />
                Очистить неделю
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-[#2d2d2d] hover:bg-transparent">
                  <TableHead className="text-gray-400">Группа</TableHead>
                  <TableHead className="text-gray-400">Предмет</TableHead>
                  <TableHead className="text-gray-400">Пара</TableHead>
                  <TableHead className="text-gray-400">День</TableHead>
                  <TableHead className="text-gray-400">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loadingChanges ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i} className="border-[#2d2d2d]">
                      <TableCell>
                        <Skeleton className="h-4 w-24 bg-[#2d2d2d]" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-32 bg-[#2d2d2d]" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-12 bg-[#2d2d2d]" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-20 bg-[#2d2d2d]" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-20 bg-[#2d2d2d]" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : changes.length === 0 ? (
                  <TableRow className="border-[#2d2d2d]">
                    <TableCell
                      colSpan={5}
                      className="text-center text-gray-500 py-8"
                    >
                      Нет изменений в расписании
                    </TableCell>
                  </TableRow>
                ) : (
                  changes.map((change) => (
                    <TableRow
                      key={change.id}
                      className="border-[#2d2d2d] hover:bg-[#252525]"
                    >
                      <TableCell className="font-medium text-white">
                        {editingId === change.id ? (
                          <Input
                            value={editForm.group_name || ""}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                group_name: e.target.value,
                              })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8"
                          />
                        ) : (
                          <Badge
                            variant="secondary"
                            className="bg-blue-950/50 text-blue-300 border-blue-900"
                          >
                            {change.group_name || "—"}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-gray-300">
                        {editingId === change.id ? (
                          <Input
                            value={editForm.subject || ""}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                subject: e.target.value,
                              })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8"
                          />
                        ) : (
                          change.subject || "—"
                        )}
                      </TableCell>
                      <TableCell className="text-white">
                        {editingId === change.id ? (
                          <Input
                            type="number"
                            min={1}
                            max={10}
                            value={editForm.lesson_number || 1}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                lesson_number: parseInt(e.target.value) || 1,
                              })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8 w-16"
                          />
                        ) : (
                          <Badge
                            variant="outline"
                            className="border-[#2d2d2d] text-gray-300"
                          >
                            {change.lesson_number || "—"}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-gray-400 text-sm">
                        {editingId === change.id ? (
                          <Input
                            value={editForm.day || ""}
                            onChange={(e) =>
                              setEditForm({ ...editForm, day: e.target.value })
                            }
                            className="bg-[#2d2d2d] border-[#3d3d3d] text-white h-8"
                          />
                        ) : (
                          change.day || "—"
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          {editingId === change.id ? (
                            <>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleEditSave(change.id)}
                                className="h-8 w-8 p-0 text-green-400 hover:text-green-300 hover:bg-green-950/30"
                              >
                                ✓
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setEditingId(null)}
                                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-300 hover:bg-gray-800"
                              >
                                ✕
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleEditStart(change)}
                                className="h-8 w-8 p-0 text-blue-400 hover:text-blue-300 hover:bg-blue-950/30"
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              {isAdmin && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleDelete(change.id)}
                                  className="h-8 w-8 p-0 text-red-400 hover:text-red-300 hover:bg-red-950/30"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              )}
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

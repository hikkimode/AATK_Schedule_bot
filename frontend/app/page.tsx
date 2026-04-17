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
import { RefreshCw, Users, UserCheck } from "lucide-react";

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
  const [stats, setStats] = useState<BotStats | null>(null);
  const [changes, setChanges] = useState<ScheduleChange[]>([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingChanges, setLoadingChanges] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();

      const user = tg.initDataUnsafe?.user;
      if (user) {
        const fullName = [user.first_name, user.last_name]
          .filter(Boolean)
          .join(" ");
        setUserName(fullName);
      }
    }
  }, []);

  const fetchData = useCallback(async () => {
    setLoadingStats(true);
    setLoadingChanges(true);
    setError(null);

    try {
      const [statsRes, changesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/bot/stats`),
        fetch(`${API_BASE_URL}/schedule/changes`),
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
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-white">
            Изменения расписания
          </CardTitle>
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
                    </TableRow>
                  ))
                ) : changes.length === 0 ? (
                  <TableRow className="border-[#2d2d2d]">
                    <TableCell
                      colSpan={4}
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
                        <Badge
                          variant="secondary"
                          className="bg-blue-950/50 text-blue-300 border-blue-900"
                        >
                          {change.group_name || "—"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-gray-300">
                        {change.subject || "—"}
                      </TableCell>
                      <TableCell className="text-white">
                        <Badge
                          variant="outline"
                          className="border-[#2d2d2d] text-gray-300"
                        >
                          {change.lesson_number || "—"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-gray-400 text-sm">
                        {change.day || "—"}
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

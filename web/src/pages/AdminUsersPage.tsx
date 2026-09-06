import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { getAuthState } from "@/lib/auth";
import {
  ApiError, listAdminUsers, revokeAdminUserSessions, updateAdminUser,
  type AdminUser, type UserRole,
} from "@/services";

const roleLabels: Record<UserRole, string> = {
  student: "学生",
  teacher: "教师",
  admin: "管理员",
};

export function AdminUsersPage() {
  const currentUserId = getAuthState()?.id;
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [submittedSearch, setSubmittedSearch] = useState("");
  const [role, setRole] = useState<UserRole | "">("");
  const [active, setActive] = useState<"" | "true" | "false">("");
  const [cursor, setCursor] = useState<string>();
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string>();
  const [message, setMessage] = useState<{ error: boolean; text: string }>();

  const load = useCallback(async () => {
    setLoading(true);
    setMessage(undefined);
    try {
      const page = await listAdminUsers({
        cursor,
        role: role || undefined,
        is_active: active ? active === "true" : undefined,
        search: submittedSearch || undefined,
        limit: 25,
      });
      setUsers(page.users);
      setNextCursor(page.next_cursor);
    } catch (error) {
      setMessage({ error: true, text: error instanceof ApiError ? error.message : "无法加载用户列表" });
    } finally {
      setLoading(false);
    }
  }, [active, cursor, role, submittedSearch]);

  useEffect(() => { void load(); }, [load]);

  const mutate = async (
    user: AdminUser,
    change: Partial<Pick<AdminUser, "role" | "is_active">>,
  ) => {
    setPendingId(user.id);
    setMessage(undefined);
    try {
      const updated = await updateAdminUser(user.id, change);
      setUsers((items) => items.map((item) => (item.id === user.id ? updated : item)));
      setMessage({ error: false, text: "用户权限已更新，原有登录会话已失效" });
    } catch (error) {
      setMessage({ error: true, text: error instanceof ApiError ? error.message : "更新失败" });
    } finally {
      setPendingId(undefined);
    }
  };

  const revoke = async (user: AdminUser) => {
    setPendingId(user.id);
    setMessage(undefined);
    try {
      const result = await revokeAdminUserSessions(user.id);
      setUsers((items) => items.map((item) => (
        item.id === user.id ? { ...item, session_count: 0 } : item
      )));
      setMessage({ error: false, text: `已撤销 ${result.revoked} 个会话` });
    } catch (error) {
      setMessage({ error: true, text: error instanceof ApiError ? error.message : "会话撤销失败" });
    } finally {
      setPendingId(undefined);
    }
  };

  return (
    <div className="flex flex-col gap-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <ShieldCheck aria-hidden="true" /> 用户与权限
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            管理角色、账号状态和服务端登录会话；所有变更均写入审计日志。
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw aria-hidden="true" /> 刷新
        </Button>
      </div>

      <form
        className="flex flex-wrap gap-2"
        aria-label="筛选用户"
        onSubmit={(event) => {
          event.preventDefault();
          const nextSearch = search.trim();
          if (cursor === undefined && submittedSearch === nextSearch) void load();
          else {
            setCursor(undefined);
            setSubmittedSearch(nextSearch);
          }
        }}
      >
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" aria-hidden="true" />
          <Input aria-label="搜索邮箱或昵称" className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
        <select aria-label="角色筛选" className="rounded-md border bg-background px-3 text-sm" value={role} onChange={(event) => { setRole(event.target.value as UserRole | ""); setCursor(undefined); }}>
          <option value="">全部角色</option>
          {Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select aria-label="账号状态筛选" className="rounded-md border bg-background px-3 text-sm" value={active} onChange={(event) => { setActive(event.target.value as typeof active); setCursor(undefined); }}>
          <option value="">全部状态</option><option value="true">启用</option><option value="false">停用</option>
        </select>
        <Button type="submit">查询</Button>
      </form>

      {message && <p role="status" className={message.error ? "text-sm text-destructive" : "text-sm text-emerald-700"}>{message.text}</p>}

      <div className="rounded-lg border bg-card">
        <Table aria-label="用户列表">
          <TableHeader><TableRow>
            <TableHead>用户</TableHead><TableHead>角色</TableHead><TableHead>状态</TableHead>
            <TableHead>有效会话</TableHead><TableHead className="text-right">操作</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {!loading && users.length === 0 && <TableRow><TableCell colSpan={5} className="py-10 text-center text-muted-foreground">没有匹配的用户</TableCell></TableRow>}
            {users.map((user) => {
              const isSelf = user.id === currentUserId;
              const pending = pendingId === user.id;
              return <TableRow key={user.id}>
                <TableCell>
                  <div className="font-medium">{user.nickname} {isSelf && <Badge variant="outline">当前账号</Badge>}</div>
                  <div className="text-xs text-muted-foreground">{user.email}</div>
                </TableCell>
                <TableCell>
                  <select aria-label={`修改 ${user.email} 的角色`} className="rounded-md border bg-background px-2 py-1" value={user.role} disabled={pending || isSelf} onChange={(event) => void mutate(user, { role: event.target.value as UserRole })}>
                    {Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </TableCell>
                <TableCell><Badge variant={user.is_active ? "outline" : "secondary"}>{user.is_active ? "启用" : "停用"}</Badge></TableCell>
                <TableCell>{user.session_count}</TableCell>
                <TableCell className="text-right"><div className="flex justify-end gap-2">
                  <Button size="sm" variant="outline" disabled={pending || isSelf} onClick={() => void mutate(user, { is_active: !user.is_active })}>{user.is_active ? "停用" : "启用"}</Button>
                  <Button size="sm" variant="outline" disabled={pending || user.session_count === 0} onClick={() => void revoke(user)}>撤销会话</Button>
                </div></TableCell>
              </TableRow>;
            })}
          </TableBody>
        </Table>
        {loading && <p role="status" className="p-8 text-center text-sm text-muted-foreground">正在加载用户…</p>}
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" disabled={!cursor || loading} onClick={() => setCursor(undefined)}>返回首页</Button>
        <Button variant="outline" disabled={!nextCursor || loading} onClick={() => setCursor(nextCursor ?? undefined)}>下一页</Button>
      </div>
    </div>
  );
}

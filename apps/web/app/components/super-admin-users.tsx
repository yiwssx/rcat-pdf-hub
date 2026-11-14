"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { NativeSelect } from "../../components/ui/native-select";
import {
  disableInstitutionalUser, listInstitutionalUsers, setInstitutionalUserRole,
  type InstitutionalUser, type InstitutionalUserRole,
} from "../../lib/api";

const ROLE_NAMES: Record<InstitutionalUserRole, string> = {
  super_admin: "Super Admin",
  admin: "Admin",
  operator: "Operator",
  viewer: "Viewer",
};

export function SuperAdminUsers({ auth }: { auth: string }) {
  const [users, setUsers] = useState<InstitutionalUser[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<InstitutionalUserRole>("admin");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const items = await listInstitutionalUsers(auth);
    setUsers(items);
  }

  useEffect(() => {
    let active = true;
    void listInstitutionalUsers(auth).then(items => {
      if (active) setUsers(items);
    }).catch(() => {
      if (active) setError("ไม่สามารถโหลดทะเบียนผู้ใช้ได้ กรุณาตรวจสอบสิทธิ์ Super Admin");
    });
    return () => { active = false; };
  }, [auth]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const target = email.trim().toLowerCase();
    if (!/^[a-z0-9][a-z0-9._%+-]*@rcat\.ac\.th$/.test(target)) {
      setError("ต้องเป็นอีเมล @rcat.ac.th ที่ถูกต้อง");
      return;
    }
    if (role === "super_admin" &&
        !window.confirm("ยืนยันการแต่งตั้ง Super Admin? ต้องเป็นบัญชี Google ที่ยืนยันตัวตนแล้ว")) return;
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const updated = await setInstitutionalUserRole(target, role, auth);
      await refresh();
      setStatus("บันทึกสิทธิ์ " + ROLE_NAMES[updated.role] + " สำหรับ " + updated.email + " แล้ว");
      setEmail("");
    } catch {
      setError("บันทึกไม่สำเร็จ บัญชี Super Admin ต้องเข้าสู่ระบบและผูก Google Subject ID ก่อน");
    } finally {
      setBusy(false);
    }
  }

  async function disable(user: InstitutionalUser) {
    if (busy || !window.confirm("ยืนยันระงับบัญชี " + user.email + "? ผู้ใช้จะถูกปฏิเสธตั้งแต่คำขอถัดไป")) return;
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await disableInstitutionalUser(user.email, auth);
      await refresh();
      setStatus("ระงับบัญชี " + user.email + " แล้ว");
    } catch {
      setError("ระงับบัญชีไม่สำเร็จ ตรวจสอบว่าไม่ใช่บัญชีของตนเองหรือ Super Admin คนสุดท้าย");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="v3AdminSection space-y-5" aria-label="จัดการผู้ใช้และบทบาท">
      <div>
        <h2>ผู้ใช้และสิทธิ์</h2>
        <p className="text-sm text-muted-foreground">เฉพาะ Super Admin เท่านั้นที่แต่งตั้ง เปลี่ยนบทบาท หรือระงับบัญชีได้ สิทธิ์มีผลเมื่อส่งคำขอครั้งถัดไป</p>
      </div>
      <form onSubmit={submit} className="grid gap-3 rounded-xl border border-border p-4 md:grid-cols-[minmax(0,1fr)_180px_auto] md:items-end">
        <label className="grid gap-1 text-sm font-medium">
          อีเมล Google Workspace
          <Input type="email" value={email} onChange={event => setEmail(event.target.value)}
            placeholder="user@rcat.ac.th" required autoComplete="off" maxLength={254} />
        </label>
        <label className="grid gap-1 text-sm font-medium">
          บทบาท
          <NativeSelect value={role} onChange={event => setRole(event.target.value as InstitutionalUserRole)}>
            <option value="admin">Admin</option>
            <option value="operator">Operator</option>
            <option value="viewer">Viewer</option>
            <option value="super_admin">Super Admin (ต้องเคยเข้าสู่ระบบ)</option>
          </NativeSelect>
        </label>
        <Button type="submit" disabled={busy}>{busy ? "กำลังบันทึก..." : "บันทึกสิทธิ์"}</Button>
      </form>
      {status && <p role="status" className="text-sm text-green-700">{status}</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[600px] text-left text-sm">
          <thead className="bg-muted/60 text-muted-foreground">
            <tr><th className="px-4 py-3">บัญชี</th><th className="px-4 py-3">บทบาท</th>
              <th className="px-4 py-3">การยืนยัน</th><th className="px-4 py-3">สถานะ</th>
              <th className="px-4 py-3">จัดการ</th></tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.email} className="border-t border-border">
                <td className="px-4 py-3 break-all">{user.email}</td>
                <td className="px-4 py-3 font-medium">{ROLE_NAMES[user.role]}</td>
                <td className="px-4 py-3">{user.linked ? "ผูก Google Subject แล้ว" : "รอเข้าสู่ระบบครั้งแรก"}</td>
                <td className="px-4 py-3">{user.active ? "ใช้งาน" : "ระงับ"}</td>
                <td className="px-4 py-3">
                  {user.active ? (
                    <Button type="button" variant="outline" size="sm" disabled={busy}
                      onClick={() => void disable(user)}>ระงับสิทธิ์</Button>
                  ) : <span className="text-muted-foreground">กำหนดบทบาทใหม่เพื่อเปิดใช้งาน</span>}
                </td>
              </tr>
            ))}
            {users.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">ไม่มีข้อมูลผู้ใช้</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">ระบบใช้ Google Subject ID เป็นหลักในการผูกสิทธิ์ ไม่ใช่ชื่อที่แสดง และ Admin ไม่มีสิทธิ์อ่านเอกสารส่วนตัวของผู้ใช้อื่นโดยอัตโนมัติ</p>
    </section>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import { getAuthConfig, getMe, localAdminLogin, logoutSession, SESSION_AUTH } from "../../lib/api";
import { BrandGlyph } from "./tool-icons";

export function LocalAdminLogin() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("เข้าสู่ระบบด้วยบัญชีผู้ดูแลภายใน");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const config = await getAuthConfig();
        if (!live) return;
        setEnabled(config.local_admin.enabled);
        try {
          const me = await getMe(SESSION_AUTH);
          if (live && me.is_admin) window.location.replace("/admin");
        } catch {
          // Login form remains available.
        }
      } catch {
        if (live) {
          setEnabled(false);
          setMessage("ไม่สามารถอ่านการตั้งค่า authentication ได้");
        }
      }
    })();
    return () => { live = false; };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true);
    try {
      const me = await localAdminLogin(username.trim(), password);
      if (!me.is_admin) throw new Error("บัญชีนี้ไม่ได้รับสิทธิ์ผู้ดูแล");
      window.location.replace("/admin");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "เข้าสู่ระบบไม่สำเร็จ");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  async function clearSession() {
    setBusy(true);
    try {
      await logoutSession();
      setMessage("ล้าง session เดิมแล้ว กรุณาเข้าสู่ระบบผู้ดูแล");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="v3LoginPage">
      <form className="v3LoginCard v3AdminLoginCard" onSubmit={submit}>
        <span className="v3BrandMark large"><BrandGlyph/></span>
        <div>
          <span className="v3Kicker">ADMIN CONSOLE</span>
          <h1>ผู้ดูแล RCAT PDF Hub</h1>
          <p>บัญชี Local Admin ใช้เฉพาะการดูแลระบบ และสร้าง session แบบ HttpOnly โดยไม่ส่ง Service API Key เข้า browser</p>
        </div>

        {enabled === false ? (
          <div className="v3InfoBox">
            Local Admin ยังไม่ได้เปิดใช้ ให้สร้าง password hash ด้วย <code>make local-admin-hash</code> แล้วกำหนด <code>PDFHUB_LOCAL_ADMIN_PASSWORD_HASH</code> ในไฟล์ .env
          </div>
        ) : (
          <div className="v3LoginFields">
            <label className="v3Field">ชื่อผู้ใช้
              <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" disabled={busy || enabled === null}/>
            </label>
            <label className="v3Field">รหัสผ่าน
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" disabled={busy || enabled === null}/>
            </label>
            <button className="v3PrimaryAction" type="submit" disabled={busy || enabled !== true || !username.trim() || !password}>
              {busy ? "กำลังตรวจสอบ…" : "เข้าสู่ Admin Console"}
            </button>
          </div>
        )}

        <small className="v3LoginMessage">{message}</small>
        <div className="v3AdminLoginLinks">
          <a href="/">← กลับ Workspace</a>
          <button type="button" onClick={() => void clearSession()} disabled={busy}>ล้าง session ปัจจุบัน</button>
        </div>
      </form>
    </main>
  );
}

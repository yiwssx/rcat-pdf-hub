"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

type Operation = "unlock-pdf" | "protect-pdf";

function ownedPdf(file: UploadedFile, actor: string): boolean {
  return file.source_system === actor
    && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 16 * 1024 * 1024
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}

function has(me: AuthMe | null, scope: string): boolean {
  return Boolean(me && (me.scopes.includes(scope) || me.scopes.includes("*")));
}

export function StagedPdfAccessClient({
  requestedFileId, requestedOperation, unlockEnabled, protectEnabled,
}: {
  requestedFileId?: string;
  requestedOperation?: string;
  unlockEnabled: boolean;
  protectEnabled: boolean;
}) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [operation, setOperation] = useState<Operation>(
    requestedOperation === "protect-pdf" && protectEnabled ? "protect-pdf"
      : unlockEnabled ? "unlock-pdf" : "protect-pdf",
  );
  // Secrets only live in transient controlled inputs, never in job params,
  // URLs, localStorage, analytics, console output or successful job details.
  const [password, setPassword] = useState("");
  const [userPassword, setUserPassword] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [confirmUser, setConfirmUser] = useState("");
  const [confirmOwner, setConfirmOwner] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  function clearSecrets() {
    setPassword("");
    setUserPassword("");
    setOwnerPassword("");
    setConfirmUser("");
    setConfirmOwner("");
  }

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const me = await getMe(SESSION_AUTH);
        if (!active) return;
        setIdentity(me);
        if (!has(me, "files:read")) return;
        const mine = (await listFiles(SESSION_AUTH)).filter((f) => ownedPdf(f, me.name));
        if (!active) return;
        setFiles(mine);
        setSelectedId(mine.find((f) => f.id === requestedFileId)?.id ?? mine[0]?.id ?? "");
      } catch {
        if (active) setError("ไม่สามารถตรวจสอบบัญชีและไฟล์ได้ กรุณาเข้าสู่ระบบใหม่");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [requestedFileId]);

  const selected = useMemo(() => files.find((f) => f.id === selectedId), [files, selectedId]);
  const enabled = operation === "unlock-pdf" ? unlockEnabled : protectEnabled;
  const allowed = has(identity, "files:read") && has(identity, "jobs:read")
    && has(identity, operation === "unlock-pdf" ? "pdf:unlock" : "pdf:protect");
  const validPasswords = operation === "unlock-pdf"
    ? password.length >= 1 && password.length <= 256
    : userPassword.length >= 1 && ownerPassword.length >= 1
      && userPassword.length <= 256 && ownerPassword.length <= 256
      && userPassword !== ownerPassword
      && userPassword === confirmUser && ownerPassword === confirmOwner;
  const canSubmit = enabled && allowed && Boolean(selected) && !busy && validPasswords;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || !identity || !selected || !ownedPdf(selected, identity.name)) return;
    const payload = operation === "unlock-pdf"
      ? { file_id: selected.id, password }
      : { file_id: selected.id, user_password: userPassword, owner_password: ownerPassword };
    // Clear as soon as the request body has been formed.
    clearSecrets();
    setError("");
    setJob(null);
    setBusy(true);
    try {
      setJob(await createJob(operation, payload, SESSION_AUTH));
    } catch {
      // Never echo sensitive input or raw server response into the UI.
      setError("ส่งคำขอไม่สำเร็จ โปรดตรวจสอบรหัสผ่าน สิทธิ์บัญชี หรือบริการรับงาน");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="t90DocumentStage">
      <header className="t90DocumentStageHeader">
        <a href="/">← Workspace</a>
        <span>RCAT PDF Hub · M08/M09 / STAGING ONLY</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">PDF ACCESS · ONE-TIME PASSWORD HANDOFF</p>
        <h1>ปลดล็อก / เข้ารหัส PDF</h1>
        <p role="note" className="t90DocumentStageNotice">
          ใช้กับไฟล์ของตนเองหรือที่ได้รับอนุญาตเท่านั้น
          รหัสผ่านจะส่งผ่าน HTTPS ไปยังบริการรับงานแบบใช้ครั้งเดียว ไม่บันทึกรหัสผ่านในประวัติงาน
          และไม่สามารถกู้รหัสผ่านที่ลืมได้
        </p>
        {loading ? <p role="status">กำลังตรวจสอบสิทธิ์และรายการไฟล์…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="access-source">PDF ของฉัน</label>
              <NativeSelect id="access-source" value={selectedId} disabled={!files.length || busy}
                onChange={(event) => { setSelectedId(event.target.value); clearSecrets(); setJob(null); }} required>
                {!files.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
                {files.map((f) => <option key={f.id} value={f.id}>{f.original_name}</option>)}
              </NativeSelect>
            </div>
            <fieldset className="t90DocumentStageFieldset">
              <legend>เลือกเครื่องมือ</legend>
              {unlockEnabled && (
                <label><input type="radio" name="access-operation" checked={operation === "unlock-pdf"}
                  onChange={() => { setOperation("unlock-pdf"); clearSecrets(); setJob(null); }}
                  disabled={busy} />ปลดล็อก PDF ด้วยรหัสผ่านที่ได้รับอนุญาต</label>
              )}
              {protectEnabled && (
                <label><input type="radio" name="access-operation" checked={operation === "protect-pdf"}
                  onChange={() => { setOperation("protect-pdf"); clearSecrets(); setJob(null); }}
                  disabled={busy} />เข้ารหัส PDF ด้วย AES-256</label>
              )}
            </fieldset>
            {operation === "unlock-pdf" ? (
              <div className="t90DocumentStageField">
                <label htmlFor="unlock-secret">รหัสผ่าน PDF ที่ต้องการปลดล็อก</label>
                <Input id="unlock-secret" type="password" autoComplete="off"
                  maxLength={256} value={password}
                  onChange={(event) => setPassword(event.target.value)} required disabled={busy} />
              </div>
            ) : (
              <>
                <p>รหัสผ่านเปิดเอกสารและรหัสผ่านเจ้าของต้องแตกต่างกัน</p>
                {([
                  ["user", "รหัสผ่านเปิด PDF", userPassword, setUserPassword],
                  ["confirm-user", "ยืนยันรหัสผ่านเปิด PDF", confirmUser, setConfirmUser],
                  ["owner", "รหัสผ่านเจ้าของ PDF", ownerPassword, setOwnerPassword],
                  ["confirm-owner", "ยืนยันรหัสผ่านเจ้าของ PDF", confirmOwner, setConfirmOwner],
                ] as const).map(([id, title, value, setter]) => (
                  <div key={id} className="t90DocumentStageField">
                    <label htmlFor={"m09-" + id}>{title}</label>
                    <Input id={"m09-" + id} type="password" autoComplete="new-password"
                      maxLength={256} value={value}
                      onChange={(event) => setter(event.target.value)} required disabled={busy}/>
                  </div>
                ))}
                {userPassword && userPassword === ownerPassword && (
                  <p role="alert" className="t90DocumentStageError">ห้ามใช้รหัสผ่านทั้งสองชุดซ้ำกัน</p>
                )}
              </>
            )}
            {identity && !allowed && (
              <p role="alert" className="t90DocumentStageError">บัญชีนี้ไม่มีสิทธิ์เรียกใช้ {operation}</p>
            )}
            {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
            <Button className="t90DocumentStageSubmit" type="submit" disabled={!canSubmit}>
              {busy ? "กำลังส่งงาน…" : operation === "unlock-pdf" ? "ปลดล็อก PDF" : "เข้ารหัส PDF"}
            </Button>
          </form>
        )}
        {job && (
          <div className="t90DocumentStageResult" role="status">
            <strong>รับงานแล้ว · {job.operation}</strong>
            <span>รหัสงาน: {job.id}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูสถานะงานและดาวน์โหลดไฟล์</a>
          </div>
        )}
      </section>
    </main>
  );
}

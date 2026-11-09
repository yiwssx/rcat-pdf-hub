"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

function valid(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 16 * 1024 * 1024
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}
function scope(me: AuthMe | null, value: string): boolean {
  return Boolean(me && (me.scopes.includes(value) || me.scopes.includes("*")));
}

export function StagedRepairClient({ requestedFileId }: { requestedFileId?: string }) {
  const [me, setMe] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [fileId, setFileId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const chosen = files.find((item) => item.id === fileId);
  const canWork = scope(me, "files:read") && scope(me, "jobs:read")
    && scope(me, "pdf:convert");

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const identity = await getMe(SESSION_AUTH);
        if (!live) return;
        setMe(identity);
        if (!scope(identity, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH)).filter((item) => valid(item, identity.name));
        if (!live) return;
        setFiles(owned);
        setFileId(owned.find((item) => item.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (live) setError("ไม่สามารถตรวจสอบสิทธิ์และรายการ PDF ได้");
      } finally {
        if (live) setLoading(false);
      }
    }
    void load();
    return () => { live = false; };
  }, [requestedFileId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen || !me || !valid(chosen, me.name) || !canWork || busy) return;
    setBusy(true);
    setError("");
    setJob(null);
    try {
      setJob(await createJob("advanced/repair-structure", { file_id: chosen.id }, SESSION_AUTH));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถเริ่มงานซ่อมโครงสร้าง PDF ได้");
    } finally {
      setBusy(false);
    }
  }

  return <main className="t90DocumentStage">
    <header className="t90DocumentStageHeader">
      <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
      <span>RCAT PDF HUB · M32 · ENGINEERING STAGING</span>
    </header>
    <section className="t90DocumentStageCard">
      <p className="t90DocumentStageKicker">M32 · QPDF STRUCTURAL REPAIR</p>
      <h1>ซ่อมโครงสร้าง PDF</h1>
      <p>สร้าง PDF ฉบับใหม่โดยซ่อมโครงสร้างออบเจ็กต์และ Cross-reference เท่าที่ qpdf กู้คืนได้</p>
      <p className="t90DocumentStageNotice" role="note">
        ไม่สามารถกู้หน้าหรือข้อความที่สูญหายถาวร ไม่ถอดรหัสเอกสาร ไม่รับรองการซ่อม PDF ที่เสียหายทุกชนิด
        และไม่รับรองลายเซ็นดิจิทัลหรือแบบฟอร์มที่โต้ตอบได้
        หากต้นฉบับเสียหายรุนแรงระบบจะรายงานข้อผิดพลาดแทนการสร้างไฟล์ปลอม
      </p>
      {loading ? <p role="status">กำลังตรวจสอบบัญชี…</p> : (
        <form onSubmit={(event) => { void submit(event); }}>
          <div className="t90DocumentStageField">
            <label htmlFor="m32-file">PDF ของบัญชีนี้</label>
            <select id="m32-file" aria-label="PDF ของบัญชีนี้"
              value={fileId} onChange={(event) => { setFileId(event.target.value); setJob(null); }}
              disabled={busy || !files.length} required>
              {!files.length && <option value="">ไม่มี PDF</option>}
              {files.map((item) =>
                <option value={item.id} key={item.id}>{item.original_name}</option>)}
            </select>
          </div>
          {me && !canWork && <p role="alert">ต้องมีสิทธิ์ files:read, jobs:read และ pdf:convert</p>}
          {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
          <button className="t90DocumentStageSubmit" type="submit"
            disabled={!chosen || !canWork || busy}>
            {busy ? "กำลังสร้างงาน…" : "ซ่อมโครงสร้าง PDF"}
          </button>
        </form>
      )}
      {job && <div className="t90DocumentStageResult" role="status">
        <strong>รับงาน M32 แล้ว</strong>
        <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
        <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูผลและดาวน์โหลด</a>
      </div>}
    </section>
  </main>;
}

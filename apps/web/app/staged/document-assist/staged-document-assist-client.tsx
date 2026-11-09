"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

type Mode = "summary" | "evidence";

function isMine(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner
    && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 12 * 1024 * 1024
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}
function has(me: AuthMe | null, scope: string) {
  return Boolean(me && (me.scopes.includes(scope) || me.scopes.includes("*")));
}

export function StagedDocumentAssistClient({
  requestedFileId, requestedTool,
}: {
  requestedFileId?: string; requestedTool?: string;
}) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [fileId, setFileId] = useState("");
  const [mode, setMode] = useState<Mode>(requestedTool === "evidence" ? "evidence" : "summary");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    let live = true;
    async function init() {
      try {
        const me = await getMe(SESSION_AUTH);
        if (!live) return;
        setIdentity(me);
        if (!has(me, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH)).filter((item) => isMine(item, me.name));
        if (!live) return;
        setFiles(owned);
        setFileId(owned.find((item) => item.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (live) setError("ตรวจสอบสิทธิ์หรือรายการไฟล์ไม่สำเร็จ กรุณาเข้าสู่ระบบใหม่");
      } finally {
        if (live) setLoading(false);
      }
    }
    void init();
    return () => { live = false; };
  }, [requestedFileId]);

  const selected = useMemo(() => files.find((item) => item.id === fileId), [files, fileId]);
  const allowed = has(identity, "files:read") && has(identity, "jobs:read")
    && has(identity, "pdf:extract-text");
  const canSubmit = Boolean(selected) && allowed && !busy
    && (mode === "summary" || (question.trim().length >= 3 && question.trim().length <= 250));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || !selected || !identity || !isMine(selected, identity.name)) return;
    setError("");
    setJob(null);
    setBusy(true);
    try {
      const result = await createJob(
        "document-assist/" + mode,
        mode === "summary" ? { file_id: selected.id } : { file_id: selected.id, question: question.trim() },
        SESSION_AUTH,
      );
      setJob(result);
    } catch {
      setError("ไม่สามารถส่งงานได้ กรุณาตรวจสอบสิทธิ์และไฟล์ที่เลือก");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="t90DocumentStage">
      <header className="t90DocumentStageHeader">
        <a href="/">← Workspace</a>
        <span>RCAT PDF Hub · M03/M06 / STAGING ONLY</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">SOURCE-GROUNDED DOCUMENT TOOLS</p>
        <h1>สรุปและค้นหลักฐานใน PDF</h1>
        <p role="note" className="t90DocumentStageNotice">
          เวอร์ชันนี้สรุปโดยคัดข้อความจากต้นฉบับและค้นส่วนที่ตรงกับคำถาม พร้อมระบุเลขหน้า
          ยังไม่ใช่แชต AI หรือการแปลความหมาย และไม่สร้างข้อความหรือคำตอบที่ไม่มีในต้นฉบับ
          ไฟล์สแกนต้องทำ OCR ก่อน
        </p>
        {loading ? <p role="status">กำลังโหลด PDF ของบัญชี…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="assist-source">PDF ของฉัน</label>
              <select id="assist-source" value={fileId} required disabled={!files.length || busy}
                onChange={(event) => { setFileId(event.target.value); setJob(null); }}>
                {!files.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
                {files.map((item) =>
                  <option key={item.id} value={item.id}>{item.original_name}</option>)}
              </select>
            </div>
            <fieldset className="t90DocumentStageFieldset">
              <legend>เลือกการประมวลผล</legend>
              <label>
                <input type="radio" name="assist-mode" checked={mode === "summary"}
                  onChange={() => { setMode("summary"); setJob(null); }} disabled={busy}/>
                สรุปข้อความสำคัญแบบ Extractive (M03)
              </label>
              <label>
                <input type="radio" name="assist-mode" checked={mode === "evidence"}
                  onChange={() => { setMode("evidence"); setJob(null); }} disabled={busy}/>
                ค้นหลักฐานตามคำถาม (M06)
              </label>
            </fieldset>
            {mode === "evidence" && (
              <div className="t90DocumentStageField">
                <label htmlFor="assist-question">คำถามหรือข้อความที่ต้องการค้นหา (3–250 ตัวอักษร)</label>
                <input id="assist-question" type="text" value={question} minLength={3} maxLength={250}
                  onChange={(event) => setQuestion(event.target.value)} disabled={busy}
                  placeholder="เช่น สรุปข้อกำหนดการใช้บริการ" required />
              </div>
            )}
            {!allowed && identity && <p role="alert" className="t90DocumentStageError">
              บัญชีนี้ยังไม่มีสิทธิ์ files:read, jobs:read และ pdf:extract-text ครบถ้วน
            </p>}
            {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
            <button className="t90DocumentStageSubmit" type="submit" disabled={!canSubmit}>
              {busy ? "กำลังสร้างงาน…" : mode === "summary" ? "สร้างสรุปจากต้นฉบับ" : "ค้นหลักฐานใน PDF"}
            </button>
          </form>
        )}
        {job && (
          <div className="t90DocumentStageResult" role="status">
            <strong>ส่งงานสำเร็จ · {mode === "summary" ? "Extractive summary" : "Evidence search"}</strong>
            <span>รหัสงาน: {job.id}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูผลข้อความ UTF-8 และดาวน์โหลด</a>
          </div>
        )}
      </section>
    </main>
  );
}

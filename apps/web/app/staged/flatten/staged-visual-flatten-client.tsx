"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  createJob, getMe, getPageInfo, listFiles, SESSION_AUTH,
  type AuthMe, type UploadedFile, type Job,
} from "../../../lib/api";

function eligible(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 12 * 1024 * 1024
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}
function granted(me: AuthMe | null, name: string): boolean {
  return Boolean(me && (me.scopes.includes(name) || me.scopes.includes("*")));
}

export function StagedVisualFlattenClient({ requestedFileId }: { requestedFileId?: string }) {
  const [me, setMe] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [fileId, setFileId] = useState("");
  const [pages, setPages] = useState(0);
  const [pageError, setPageError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const chosen = files.find((file) => file.id === fileId);
  const allowed = granted(me, "files:read") && granted(me, "jobs:read") && granted(me, "pdf:convert");

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const identity = await getMe(SESSION_AUTH);
        if (!live) return;
        setMe(identity);
        if (!granted(identity, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH)).filter((file) => eligible(file, identity.name));
        if (!live) return;
        setFiles(owned);
        setFileId(owned.find((file) => file.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (live) setError("ไม่สามารถตรวจสอบบัญชีและรายการไฟล์ได้ กรุณาเข้าสู่ระบบ");
      } finally {
        if (live) setLoading(false);
      }
    }
    void load();
    return () => { live = false; };
  }, [requestedFileId]);

  useEffect(() => {
    if (!chosen || !granted(me, "files:read")) return;
    let live = true;
    setPages(0);
    setPageError("");
    void getPageInfo(chosen.id, SESSION_AUTH).then((result) => {
      if (!live) return;
      if (result.file_id !== chosen.id || !Number.isSafeInteger(result.pages)
          || result.pages < 1 || result.pages > 25) {
        setPageError("M24 รองรับเอกสารไม่เกิน 25 หน้า");
      } else setPages(result.pages);
    }).catch(() => {
      if (live) setPageError("ไม่สามารถตรวจสอบจำนวนหน้าได้");
    });
    return () => { live = false; };
  }, [chosen, me]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen || !me || !eligible(chosen, me.name) || !allowed
        || pages < 1 || pages > 25 || submitting) return;
    setSubmitting(true);
    setError("");
    setJob(null);
    try {
      setJob(await createJob("advanced/flatten-visual", { file_id: chosen.id }, SESSION_AUTH));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถเริ่มงาน Flatten ได้");
    } finally {
      setSubmitting(false);
    }
  }

  return <main className="t90DocumentStage">
    <header className="t90DocumentStageHeader">
      <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
      <span>RCAT PDF HUB · M24 / ENGINEERING STAGING</span>
    </header>
    <section className="t90DocumentStageCard">
      <p className="t90DocumentStageKicker">M24 · VISUAL PDF FLATTEN</p>
      <h1>Flatten PDF แบบภาพ</h1>
      <p>แปลงหน้าที่มองเห็นให้เป็น PDF ฉบับใหม่แบบภาพ ไม่แก้ไฟล์ต้นฉบับ</p>
      <p className="t90DocumentStageNotice" role="note">
        ผลลัพธ์ไม่สามารถค้นหาหรือเลือกข้อความเดิมได้ ไม่รักษาฟิลด์ฟอร์มแบบแก้ไขได้
        ไม่รักษาลายเซ็นดิจิทัลและข้อมูล Accessibility และไม่ใช่การลบข้อมูลแบบ Redaction
        รองรับเฉพาะ PDF ไม่เข้ารหัส ไม่หมุนหรือ Crop และไม่เกิน 25 หน้า
      </p>
      {loading ? <p role="status">กำลังตรวจสอบเอกสาร…</p> : (
        <form onSubmit={(event) => { void submit(event); }}>
          <div className="t90DocumentStageField">
            <label htmlFor="m24-file">PDF ที่เป็นของบัญชีนี้</label>
            <select id="m24-file" aria-label="PDF ที่เป็นของบัญชีนี้"
              value={fileId} onChange={(event) => { setFileId(event.target.value); setJob(null); }}
              disabled={submitting || !files.length} required>
              {!files.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
              {files.map((file) =>
                <option key={file.id} value={file.id}>{file.original_name}</option>)}
            </select>
          </div>
          {chosen && <p>จำนวนหน้า: {pages || "กำลังตรวจสอบ"}</p>}
          {me && !allowed && <p role="alert">ต้องมีสิทธิ์ files:read, jobs:read และ pdf:convert</p>}
          {pageError && <p role="alert" className="t90DocumentStageError">{pageError}</p>}
          {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
          <button type="submit" className="t90DocumentStageSubmit"
            disabled={!chosen || !allowed || pages < 1 || Boolean(pageError) || submitting}>
            {submitting ? "กำลังสร้างงาน…" : "สร้าง PDF แบบภาพ"}
          </button>
        </form>
      )}
      {job && <div className="t90DocumentStageResult" role="status" aria-live="polite">
        <strong>สร้างงาน Flatten แล้ว</strong>
        <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
        <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูผลและดาวน์โหลด</a>
      </div>}
    </section>
  </main>;
}

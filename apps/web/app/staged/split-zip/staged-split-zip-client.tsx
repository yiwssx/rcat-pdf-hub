"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createJob, getMe, getPageInfo, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

const MAX_SOURCE_BYTES = 16 * 1024 * 1024;
const PAGES_PATTERN = /^(?:[1-9][0-9]{0,5}|z)(?:-(?:[1-9][0-9]{0,5}|z))?(?:,(?:[1-9][0-9]{0,5}|z)(?:-(?:[1-9][0-9]{0,5}|z))?)*$/;

function ownedPdf(item: UploadedFile, owner: string): boolean {
  return item.source_system === owner && item.content_type === "application/pdf"
    && item.original_name.toLowerCase().endsWith(".pdf")
    && item.size >= 24 && item.size <= MAX_SOURCE_BYTES
    && (!item.expires_at || (Number.isFinite(Date.parse(item.expires_at))
      && Date.parse(item.expires_at) > Date.now()));
}

function hasScope(me: AuthMe | null, scope: string): boolean {
  return Boolean(me && (me.scopes.includes("*") || me.scopes.includes(scope)));
}

export function StagedSplitZipClient({ requestedFileId }: { requestedFileId?: string }) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [pages, setPages] = useState("1");
  const [pageCount, setPageCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  const chosen = useMemo(() => files.find((file) => file.id === selectedId), [files, selectedId]);
  const canRead = hasScope(identity, "files:read");
  const canSubmit = hasScope(identity, "pdf:split") && canRead && hasScope(identity, "jobs:read");

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const me = await getMe(SESSION_AUTH);
        if (!live) return;
        setIdentity(me);
        if (!hasScope(me, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH)).filter((file) => ownedPdf(file, me.name));
        if (!live) return;
        setFiles(owned);
        setSelectedId(owned.find((file) => file.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (live) setError("ตรวจสอบบัญชีหรือรายการ PDF ไม่สำเร็จ กรุณาเข้าสู่ระบบก่อน");
      } finally {
        if (live) setLoading(false);
      }
    }
    void load();
    return () => { live = false; };
  }, [requestedFileId]);

  useEffect(() => {
    if (!chosen || !canRead) return;
    let live = true;
    setPageCount(null);
    void getPageInfo(chosen.id, SESSION_AUTH).then((info) => {
      if (!live) return;
      if (info.file_id !== chosen.id || !Number.isInteger(info.pages)
          || info.pages < 1 || info.pages > 200) {
        setError("M07 รองรับ PDF ที่มีจำนวนหน้าไม่เกิน 200 หน้า");
        return;
      }
      setPageCount(info.pages);
    }).catch(() => {
      if (live) setError("อ่านจำนวนหน้าไม่ได้ หรือไฟล์หมดอายุแล้ว");
    });
    return () => { live = false; };
  }, [chosen, canRead]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !canSubmit || !identity || !chosen || pageCount === null) return;
    if (!ownedPdf(chosen, identity.name)) {
      setError("ไฟล์ไม่ใช่ PDF ของบัญชีนี้หรือหมดอายุ");
      return;
    }
    const expression = pages.trim();
    if (!expression || expression.length > 256 || !PAGES_PATTERN.test(expression)) {
      setError("ระบุหน้า เช่น 1,3-5 หรือ 1-z โดยไม่เว้นวรรค");
      return;
    }
    // The backend is authoritative for page bounds, duplicates and 80-part limit.
    // No client-side parser can weaken that validation.
    setSubmitting(true);
    setJob(null);
    setError("");
    try {
      const submitted = await createJob("split-to-zip", {
        file_id: chosen.id, pages: expression,
      }, SESSION_AUTH);
      setJob(submitted);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "สร้างงาน M07 ไม่สำเร็จ");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="t90DocumentStage">
      <header className="t90DocumentStageHeader">
        <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
        <span>RCAT PDF Hub · M07 / STAGING ONLY</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">MANAGE PDF · M07</p>
        <h1>แยกหน้า PDF เป็น ZIP</h1>
        <p>เลือกหน้าจาก PDF แล้วส่งออกเป็นไฟล์ PDF หน้าละหนึ่งไฟล์ภายใน ZIP
          โดยไม่เปลี่ยนแปลงไฟล์ต้นฉบับ</p>
        <p role="note" className="t90DocumentStageNotice">
          รองรับไฟล์ PDF ไม่เกิน 16 MiB / 200 หน้า และส่งออกได้ไม่เกิน 80 หน้า
          ไม่รองรับ PDF ที่เข้ารหัส มีลายเซ็นดิจิทัล แบบฟอร์ม หรือคำอธิบายประกอบ
        </p>
        {loading ? <p role="status">กำลังตรวจสอบบัญชีและไฟล์…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="m07-file">PDF ของฉัน</label>
              <select id="m07-file" value={selectedId}
                onChange={(event) => {
                  setSelectedId(event.target.value);
                  setPages("1");
                  setPageCount(null);
                  setJob(null);
                  setError("");
                }} disabled={!files.length || submitting} required>
                {!files.length && <option value="">ไม่มี PDF ที่รองรับ</option>}
                {files.map((file) => <option key={file.id} value={file.id}>{file.original_name}</option>)}
              </select>
            </div>
            {chosen && <p role="status">จำนวนหน้า: {pageCount ?? "กำลังอ่าน…"} หน้า</p>}
            <div className="t90DocumentStageField">
              <label htmlFor="m07-pages">หน้าที่จะแยก</label>
              <input id="m07-pages" type="text" autoComplete="off" value={pages}
                maxLength={256} placeholder="1,3-5 หรือ 1-z"
                onChange={(event) => { setPages(event.target.value); setJob(null); }}
                disabled={submitting || !chosen} required />
              <small>ใช้ z แทนหน้าสุดท้าย เช่น 1-z; เลือกหน้าไม่ซ้ำกัน</small>
            </div>
            {identity && !hasScope(identity, "pdf:split") &&
              <p role="alert">บัญชีนี้ไม่มีสิทธิ์ pdf:split</p>}
            {identity && !canRead && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ files:read</p>}
            {identity && !hasScope(identity, "jobs:read") &&
              <p role="alert">บัญชีนี้ไม่มีสิทธิ์ jobs:read</p>}
            {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
            <button type="submit" className="t90DocumentStageSubmit"
              disabled={!canSubmit || !chosen || pageCount === null || submitting}>
              {submitting ? "กำลังสร้างงาน…" : "แยก PDF เป็น ZIP"}
            </button>
          </form>
        )}
        {job && (
          <div className="t90DocumentStageResult" role="status" aria-live="polite">
            <strong>สร้างงานแยก PDF แล้ว</strong>
            <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>
              ดูผลงาน ดาวน์โหลด ZIP และ PDF รายหน้า
            </a>
          </div>
        )}
      </section>
    </main>
  );
}

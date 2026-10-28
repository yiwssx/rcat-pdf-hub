"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

const FIELDS = ["title", "author", "subject", "keywords"] as const;
type MetadataField = (typeof FIELDS)[number];
type Operation = "edit-metadata" | "remove-metadata" | "extract-text";

const FIELD_NAMES: Record<MetadataField, string> = {
  title: "ชื่อเรื่อง (Title)",
  author: "ผู้สร้าง (Author)",
  subject: "หัวข้อ (Subject)",
  keywords: "คำสำคัญ (Keywords)",
};

const OPERATION_NAMES: Record<Operation, string> = {
  "edit-metadata": "แก้ไขข้อมูลเอกสาร",
  "remove-metadata": "ลบ Info และ XMP ที่รองรับ",
  "extract-text": "ส่งออกข้อความที่ค้นหาได้",
};

function validPdf(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner
    && file.content_type.toLowerCase() === "application/pdf"
    && file.size > 0
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at)) && Date.parse(file.expires_at) > Date.now()));
}

export function StagedDocumentDataClient({ requestedFileId }: { requestedFileId?: string }) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [operation, setOperation] = useState<Operation>("extract-text");
  const [enabled, setEnabled] = useState<Record<MetadataField, boolean>>({
    title: false, author: false, subject: false, keywords: false,
  });
  const [values, setValues] = useState<Record<MetadataField, string>>({
    title: "", author: "", subject: "", keywords: "",
  });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState<Job | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        // Session bootstrap must finish before the authenticated files request.
        const me = await getMe(SESSION_AUTH);
        const owned = (await listFiles(SESSION_AUTH)).filter((file) => validPdf(file, me.name));
        if (!active) return;
        setIdentity(me);
        setFiles(owned);
        setSelectedId(owned.find((file) => file.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
        setError("");
      } catch {
        if (active) setError("ไม่สามารถตรวจสอบสิทธิ์และรายการไฟล์ได้ โปรดเข้าสู่ระบบที่หน้าหลักก่อน");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [requestedFileId]);

  const requiredScope = operation === "extract-text" ? "pdf:extract-text" : "pdf:metadata";
  const hasScope = Boolean(identity && (identity.scopes.includes("*") || identity.scopes.includes(requiredScope)));
  const hasJobScope = Boolean(identity && (identity.scopes.includes("*") || identity.scopes.includes("jobs:read")));
  const hasFileScope = Boolean(identity && (identity.scopes.includes("*") || identity.scopes.includes("files:read")));
  const chosen = useMemo(() => files.find((file) => file.id === selectedId), [files, selectedId]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !chosen || !identity || !hasScope || !hasJobScope || !hasFileScope) return;
    if (!validPdf(chosen, identity.name)) {
      setError("ไฟล์ไม่ใช่ PDF ที่ยืนยันแล้ว หรือไฟล์หมดอายุ กรุณาเลือกไฟล์ใหม่");
      return;
    }
    const payload: { file_id: string; changes?: Partial<Record<MetadataField, string | null>> } = {
      file_id: chosen.id,
    };
    if (operation === "edit-metadata") {
      const changes: Partial<Record<MetadataField, string | null>> = {};
      for (const field of FIELDS) {
        if (!enabled[field]) continue;
        const value = values[field];
        if (value.length > 512 || /[\u0000-\u001f\u007f]/.test(value)) {
          setError("ข้อมูล Metadata ต้องมีความยาวไม่เกิน 512 อักขระ และไม่มีอักขระควบคุม");
          return;
        }
        changes[field] = value === "" ? null : value;
      }
      if (Object.keys(changes).length === 0) {
        setError("กรุณาเลือกอย่างน้อยหนึ่งฟิลด์ที่ต้องการแก้ไข");
        return;
      }
      payload.changes = changes;
    }
    setError("");
    setSubmitted(null);
    setSubmitting(true);
    try {
      // The server remains the authority for file ownership, MIME, expiry,
      // scopes and runtime activation. No client-supplied actor identity.
      const job = await createJob("document-data/" + operation, payload, SESSION_AUTH);
      setSubmitted(job);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถสร้างงานได้");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="t90DocumentStage">
      <header className="t90DocumentStageHeader">
        <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
        <span>RCAT PDF Hub · T90-1.4c / STAGING ONLY</span>
      </header>

      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">DOCUMENT DATA · CONTROLLED PREVIEW</p>
        <h1>จัดการข้อมูลและข้อความใน PDF</h1>
        <p>ทดลองการแก้ไข Metadata, ลบ Info/XMP และดึงข้อความจากชั้นข้อความของ PDF โดยเก็บไฟล์ต้นฉบับไว้</p>
        <p className="t90DocumentStageNotice" role="note">
          การลบ Metadata ไม่ใช่การลบข้อมูลส่วนบุคคลทั้งหมดหรือการ Redact PDF
          และการดึงข้อความไม่ใช่ OCR — เอกสารที่เป็นภาพสแกนต้องใช้เครื่องมือ OCR แยกต่างหาก
        </p>

        {loading ? <p role="status">กำลังตรวจสอบบัญชีและไฟล์ที่มีสิทธิ์…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="t90-document-file">PDF ที่อัปโหลดแล้ว (เฉพาะไฟล์ของบัญชีนี้)</label>
              <select id="t90-document-file" value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setSubmitted(null); }} disabled={!files.length || submitting} required>
                {!files.length && <option value="">ไม่มี PDF ที่เข้าถึงได้</option>}
                {files.map((file) => <option key={file.id} value={file.id}>{file.original_name}</option>)}
              </select>
            </div>
            <fieldset className="t90DocumentStageFieldset">
              <legend>เลือกการดำเนินการ</legend>
              {(["edit-metadata", "remove-metadata", "extract-text"] as const).map((item) => (
                <label key={item}>
                  <input type="radio" name="t90-operation" value={item} checked={operation === item}
                    onChange={() => { setOperation(item); setSubmitted(null); setError(""); }} disabled={submitting} />
                  {OPERATION_NAMES[item]}
                </label>
              ))}
            </fieldset>

            {operation === "edit-metadata" && (
              <fieldset className="t90DocumentStageFieldset">
                <legend>ฟิลด์ที่ต้องการแก้ไข</legend>
                <p>เลือกฟิลด์ก่อนกรอกค่า หากเลือกแล้วเว้นว่าง ระบบจะลบฟิลด์นั้น</p>
                {FIELDS.map((field) => (
                  <div className="t90DocumentStageMetadata" key={field}>
                    <label>
                      <input type="checkbox" checked={enabled[field]} disabled={submitting}
                        onChange={(event) => setEnabled((old) => ({ ...old, [field]: event.target.checked }))} />
                      {FIELD_NAMES[field]}
                    </label>
                    <input aria-label={"ค่า " + FIELD_NAMES[field]} value={values[field]} maxLength={512}
                      onChange={(event) => setValues((old) => ({ ...old, [field]: event.target.value }))}
                      disabled={submitting || !enabled[field]} placeholder="เว้นว่างเพื่อลบฟิลด์" />
                  </div>
                ))}
              </fieldset>
            )}

            {!hasScope && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ {requiredScope}</p>}
            {!hasJobScope && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ jobs:read</p>}
            {!hasFileScope && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ files:read</p>}
            {error && <p className="t90DocumentStageError" role="alert">{error} <a href="/">กลับหน้าแรก</a></p>}
            <button type="submit" className="t90DocumentStageSubmit"
              disabled={submitting || !chosen || !hasScope || !hasJobScope || !hasFileScope}>
              {submitting ? "กำลังสร้างงาน…" : "สร้างงานทดลอง"}
            </button>
          </form>
        )}

        {submitted && (
          <div className="t90DocumentStageResult" role="status" aria-live="polite">
            <strong>รับงาน {OPERATION_NAMES[submitted.operation as Operation] ?? submitted.operation} แล้ว</strong>
            <span>รหัสงาน: {submitted.id} · สถานะ: {submitted.status}</span>
            <a href={"/jobs/" + encodeURIComponent(submitted.id) + "/result"}>เปิดดูผลและดาวน์โหลดจากหน้าผลงาน</a>
          </div>
        )}
      </section>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  createJob, getMe, listFiles, uploadFile, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";
import { STAGED_FROM_PDF_FORMATS } from "./catalog";

function validOwnedPdf(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner
    && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size > 0
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}

function hasScope(identity: AuthMe | null, scope: string): boolean {
  return Boolean(identity && (identity.scopes.includes("*") || identity.scopes.includes(scope)));
}

export function StagedFromPdfClient({
  requestedFileId, requestedToolId,
}: {
  requestedFileId?: string;
  requestedToolId?: string;
}) {
  const firstTool = STAGED_FROM_PDF_FORMATS.find((item) => item.id === requestedToolId)
    ?? STAGED_FROM_PDF_FORMATS[0];
  const [toolId, setToolId] = useState(firstTool.id);
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [candidate, setCandidate] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  const selectedTool = STAGED_FROM_PDF_FORMATS.find((item) => item.id === toolId) ?? firstTool;
  const owned = files.filter((file) => identity && validOwnedPdf(file, identity.name));
  const selectedFile = owned.find((file) => file.id === selectedId);
  const canUpload = hasScope(identity, "files:write");
  const canReadResults = hasScope(identity, "files:read") && hasScope(identity, "jobs:read");
  const allowed = hasScope(identity, selectedTool.requiredScope);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        const me = await getMe(SESSION_AUTH);
        const records = (await listFiles(SESSION_AUTH))
          .filter((file) => validOwnedPdf(file, me.name));
        if (!active) return;
        setIdentity(me);
        setFiles(records);
        setSelectedId(records.find((file) => file.id === requestedFileId)?.id ?? "");
        setError("");
      } catch {
        if (active) setError("กรุณาเข้าสู่ระบบด้วยบัญชีที่ได้รับสิทธิ์ก่อนใช้งาน");
      } finally {
        if (active) setLoading(false);
      }
    }
    void bootstrap();
    return () => { active = false; };
  }, [requestedFileId]);

  async function upload() {
    if (!candidate || !identity || !canUpload || uploading || submitting) return;
    if (!candidate.name.toLowerCase().endsWith(".pdf") || candidate.size === 0) {
      setError("โปรดเลือกไฟล์ PDF จริงที่มีข้อมูล");
      return;
    }
    setUploading(true);
    setJob(null);
    setError("");
    try {
      const stored = await uploadFile(candidate, SESSION_AUTH);
      if (!validOwnedPdf(stored, identity.name)) {
        setError("ไฟล์ที่อัปโหลดไม่ผ่านการตรวจชนิด PDF หรือไม่ใช่ไฟล์ของบัญชีนี้");
        return;
      }
      setFiles((previous) => [stored, ...previous.filter((item) => item.id !== stored.id)]);
      setSelectedId(stored.id);
      setCandidate(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถอัปโหลด PDF ได้");
    } finally {
      setUploading(false);
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!identity || !selectedFile || !allowed || !canReadResults || loading
      || uploading || submitting || !validOwnedPdf(selectedFile, identity.name)) return;
    setSubmitting(true);
    setJob(null);
    setError("");
    try {
      // No arbitrary operation, actor, output type, URL or worker params.
      // Backend independently checks actual PDF signature, owner, expiry,
      // MIME, limits, type-specific scope and default-OFF flags.
      const result = await createJob(
        "from-pdf/" + selectedTool.route, { file_id: selectedFile.id }, SESSION_AUTH,
      );
      setJob(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถส่งออก PDF ได้");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="t90DocumentStage t90ExportStage">
      <header className="t90DocumentStageHeader">
        <a href="/" aria-label="กลับหน้าหลัก">← Workspace</a>
        <span>RCAT PDF HUB · T90-3 · ENGINEERING STAGING</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">SHARED PDF EXPORT WORKFLOW</p>
        <h1>แปลง PDF เป็นไฟล์อื่น</h1>
        <p>เลือกผลลัพธ์จากตัวแปลงที่มี Backend พร้อมแล้ว ใช้การอัปโหลด คิวงาน และดาวน์โหลดร่วมกับระบบเดิม</p>
        <p className="t90DocumentStageNotice" role="note">
          ฟีเจอร์นี้ยังไม่เปิดใช้งาน Production และไม่ได้รับรองความเที่ยงตรงของทุกเอกสาร
          ตัวเลือก Word/PPT/Excel หมายถึง DOCX/PPTX/XLSX ตามลำดับ ส่วน MOBI ไม่มี Engine ที่ยอมรับได้และไม่แสดงให้เลือก
        </p>

        {loading ? <p role="status">กำลังตรวจสอบบัญชีและไฟล์ PDF …</p> : (
          <>
            <div className="t90DocumentStageField">
              <label htmlFor="t90-export-format">รูปแบบไฟล์ผลลัพธ์</label>
              <select id="t90-export-format" value={toolId}
                onChange={(event) => {
                  if (!STAGED_FROM_PDF_FORMATS.some((t) => t.id === event.target.value)) return;
                  setToolId(event.target.value);
                  setJob(null);
                  setError("");
                }} disabled={submitting || uploading}>
                {STAGED_FROM_PDF_FORMATS.map((t) => (
                  <option key={t.id} value={t.id}>{t.id} · {t.label} → {t.fileKind}</option>
                ))}
              </select>
            </div>
            <p className="t90ExportLimit" role="note">ขอบเขต: {selectedTool.limitation}</p>
            <div className="t90DocumentStageField">
              <label htmlFor="t90-export-upload">อัปโหลด PDF ต้นฉบับ</label>
              <input id="t90-export-upload" type="file" accept=".pdf,application/pdf"
                disabled={uploading || submitting || !canUpload}
                onChange={(event) => setCandidate(event.target.files?.[0] ?? null)} />
              <button type="button" className="t90DocumentStageSubmit"
                disabled={!candidate || !canUpload || uploading || submitting}
                onClick={() => { void upload(); }}>
                {uploading ? "กำลังอัปโหลด…" : "อัปโหลด PDF"}
              </button>
            </div>
            <form onSubmit={(event) => { void submit(event); }}>
              <div className="t90DocumentStageField">
                <label htmlFor="t90-export-file">ไฟล์ PDF ของบัญชีนี้</label>
                <select id="t90-export-file" value={selectedFile?.id ?? ""}
                  onChange={(event) => { setSelectedId(event.target.value); setJob(null); }}
                  disabled={submitting || uploading || !owned.length} required>
                  <option value="">เลือกไฟล์ที่ต้องการแปลง</option>
                  {owned.map((f) => <option key={f.id} value={f.id}>{f.original_name}</option>)}
                </select>
              </div>
              {!canUpload && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ files:write</p>}
              {!allowed && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ {selectedTool.requiredScope}</p>}
              {!canReadResults && identity && <p role="alert">ต้องมีสิทธิ์ files:read และ jobs:read</p>}
              {error && <p className="t90DocumentStageError" role="alert">{error}</p>}
              <button type="submit" className="t90DocumentStageSubmit"
                disabled={!selectedFile || !allowed || !canReadResults || uploading || submitting}>
                {submitting ? "กำลังสร้างงาน…" : "แปลง PDF"}
              </button>
            </form>
          </>
        )}
        {job && (
          <div className="t90DocumentStageResult" role="status" aria-live="polite">
            <strong>ส่งงานออกไฟล์แล้ว</strong>
            <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>
              ดูผลลัพธ์และดาวน์โหลด
            </a>
          </div>
        )}
        <p className="t90ExportFooter">ตัวเลือกทั้งหมดใช้ค่า Parameter มาตรฐานที่ตรวจสอบแล้วจาก Backend; ไม่มีการส่งค่าตามอำเภอใจ</p>
      </section>
    </main>
  );
}

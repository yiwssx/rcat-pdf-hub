"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createJob, getMe, listFiles, uploadFile, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

type Geometry = { page: number; x: number; y: number; width: number; height: number };

function activeOwned(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner && file.size > 0
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}

function isPdf(file: UploadedFile): boolean {
  return file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 16 * 1024 * 1024;
}

function isImage(file: UploadedFile): boolean {
  const name = file.original_name.toLowerCase();
  return ((file.content_type === "image/png" && name.endsWith(".png"))
    || (file.content_type === "image/jpeg" && (name.endsWith(".jpg") || name.endsWith(".jpeg"))))
    && file.size <= 8 * 1024 * 1024;
}

function granted(me: AuthMe | null, scope: string) {
  return Boolean(me && (me.scopes.includes(scope) || me.scopes.includes("*")));
}

export function StagedImageOverlayClient({ requestedFileId }: { requestedFileId?: string }) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [pdfId, setPdfId] = useState("");
  const [imageId, setImageId] = useState("");
  const [candidate, setCandidate] = useState<File | null>(null);
  const [geometry, setGeometry] = useState<Geometry>({
    page: 1, x: 30, y: 30, width: 120, height: 80,
  });
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  const mine = useMemo(() => files.filter((file) =>
    identity && activeOwned(file, identity.name)), [files, identity]);
  const pdfs = mine.filter(isPdf);
  const images = mine.filter(isImage);
  const selectedPdf = pdfs.find((file) => file.id === pdfId);
  const selectedImage = images.find((file) => file.id === imageId);
  const canUpload = granted(identity, "files:write");
  const canWork = granted(identity, "pdf:stamp")
    && granted(identity, "files:read") && granted(identity, "jobs:read");

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        const me = await getMe(SESSION_AUTH);
        const stored = (await listFiles(SESSION_AUTH))
          .filter((file) => activeOwned(file, me.name));
        if (!active) return;
        setIdentity(me);
        setFiles(stored);
        const initial = stored.find((file) => file.id === requestedFileId && isPdf(file));
        setPdfId(initial?.id ?? "");
      } catch {
        if (active) setError("ต้องเข้าสู่ระบบด้วยบัญชีที่มีสิทธิ์ก่อนใช้งาน");
      } finally {
        if (active) setLoading(false);
      }
    }
    void bootstrap();
    return () => { active = false; };
  }, [requestedFileId]);

  function changeGeometry(key: keyof Geometry, value: string) {
    setGeometry((old) => ({ ...old, [key]: Number(value) }));
    setJob(null);
  }

  async function upload() {
    if (!candidate || !identity || !canUpload || uploading || submitting) return;
    if (!/\.(pdf|png|jpe?g)$/i.test(candidate.name) || candidate.size === 0) {
      setError("รองรับเฉพาะ PDF และภาพ PNG/JPEG");
      return;
    }
    setUploading(true);
    setError("");
    setJob(null);
    try {
      const stored = await uploadFile(candidate, SESSION_AUTH);
      if (!activeOwned(stored, identity.name) || (!isPdf(stored) && !isImage(stored))) {
        setError("ไฟล์ที่รับไว้ไม่ตรงกับชนิดไฟล์และเจ้าของที่ได้รับอนุญาต");
        return;
      }
      setFiles((previous) => [stored, ...previous.filter((file) => file.id !== stored.id)]);
      if (isPdf(stored)) setPdfId(stored.id);
      else setImageId(stored.id);
      setCandidate(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถอัปโหลดได้");
    } finally {
      setUploading(false);
    }
  }

  function validGeometry(): boolean {
    const { page, x, y, width, height } = geometry;
    return Number.isInteger(page) && page >= 1 && page <= 80
      && [x, y, width, height].every(Number.isFinite)
      && x >= 0 && x <= 4000 && y >= 0 && y <= 4000
      && width >= 8 && width <= 2000 && height >= 8 && height <= 2000;
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || uploading || submitting || !canWork || !identity || !selectedPdf
      || !selectedImage || !validGeometry() || pdfId === imageId) return;
    setSubmitting(true);
    setError("");
    setJob(null);
    try {
      const created = await createJob("advanced/add-image", {
        file_id: selectedPdf.id, image_file_id: selectedImage.id, ...geometry,
      }, SESSION_AUTH);
      setJob(created);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถเพิ่มภาพได้");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="t90DocumentStage t90ImageOverlay">
      <header className="t90DocumentStageHeader">
        <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
        <span>RCAT PDF HUB · M23 · ENGINEERING STAGING</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">M23 · ADD IMAGE TO PDF</p>
        <h1>เพิ่มรูปภาพลงใน PDF</h1>
        <p>วางภาพ JPEG/PNG ลงบนหน้าของ PDF ด้วยพิกัดและขนาดที่กำหนด โดยไม่เปลี่ยนต้นฉบับ</p>
        <p className="t90DocumentStageNotice" role="note">
          ใช้กับ PDF ธรรมดาที่ยังไม่เข้ารหัส ไม่มีลายเซ็น ไม่มี Annotation และไม่หมุนหน้าเท่านั้น
          การวางภาพไม่ใช่การ Redact หรือการลบเนื้อหาที่อยู่ใต้ภาพ และยังไม่เปิดให้ใช้ใน Production
        </p>
        {loading ? <p role="status">กำลังตรวจสอบไฟล์และบัญชี…</p> : (
          <>
            <div className="t90DocumentStageField">
              <label htmlFor="m23-upload">อัปโหลด PDF หรือรูปภาพ</label>
              <input id="m23-upload" type="file" accept=".pdf,.png,.jpg,.jpeg"
                disabled={!canUpload || uploading || submitting}
                onChange={(event) => setCandidate(event.target.files?.[0] ?? null)} />
              <button className="t90DocumentStageSubmit" type="button"
                onClick={() => { void upload(); }}
                disabled={!candidate || !canUpload || uploading || submitting}>
                {uploading ? "กำลังอัปโหลด…" : "อัปโหลด"}
              </button>
            </div>
            <form onSubmit={(event) => { void submit(event); }}>
              <div className="t90DocumentStageField">
                <label htmlFor="m23-pdf">PDF ต้นฉบับที่เป็นของบัญชีนี้</label>
                <select id="m23-pdf" value={pdfId} required
                  onChange={(event) => { setPdfId(event.target.value); setJob(null); }}
                  disabled={submitting || uploading || !pdfs.length}>
                  <option value="">เลือก PDF</option>
                  {pdfs.map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}
                </select>
              </div>
              <div className="t90DocumentStageField">
                <label htmlFor="m23-image">ภาพ JPEG/PNG ของบัญชีนี้</label>
                <select id="m23-image" value={imageId} required
                  onChange={(event) => { setImageId(event.target.value); setJob(null); }}
                  disabled={submitting || uploading || !images.length}>
                  <option value="">เลือกรูปภาพ</option>
                  {images.map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}
                </select>
              </div>
              <fieldset className="t90DocumentStageFieldset">
                <legend>ตำแหน่งและขนาดใน PDF points (จุดกำเนิดล่างซ้าย)</legend>
                <div className="m23Geometry">
                  {([
                    ["page", "หน้าที่ต้องการวาง", 1, 80, 1],
                    ["x", "พิกัด X", 0, 4000, 1],
                    ["y", "พิกัด Y", 0, 4000, 1],
                    ["width", "ความกว้าง", 8, 2000, 1],
                    ["height", "ความสูง", 8, 2000, 1],
                  ] as const).map(([key, label, min, max, step]) => (
                    <label key={key} htmlFor={"m23-" + key}>
                      {label}
                      <input type="number" id={"m23-" + key}
                        min={min} max={max} step={step} required
                        value={geometry[key]}
                        onChange={(event) => changeGeometry(key, event.target.value)}
                        disabled={submitting || uploading} />
                    </label>
                  ))}
                </div>
              </fieldset>
              {!canWork && identity && <p role="alert">ต้องมีสิทธิ์ pdf:stamp, files:read และ jobs:read</p>}
              {!canUpload && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ files:write</p>}
              {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
              <button type="submit" className="t90DocumentStageSubmit"
                disabled={!selectedPdf || !selectedImage || !canWork
                  || !validGeometry() || uploading || submitting}>
                {submitting ? "กำลังสร้างงาน…" : "เพิ่มรูปภาพลงใน PDF"}
              </button>
            </form>
          </>
        )}
        {job && (
          <div className="t90DocumentStageResult" role="status" aria-live="polite">
            <strong>รับงานเพิ่มภาพแล้ว</strong>
            <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>
              ดูผลและดาวน์โหลด PDF
            </a>
          </div>
        )}
      </section>
    </main>
  );
}

"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

function active(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner && file.size > 0
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}
function pdf(file: UploadedFile): boolean {
  return file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 16 * 1024 * 1024;
}
function image(file: UploadedFile): boolean {
  const name = file.original_name.toLowerCase();
  return ((file.content_type === "image/png" && name.endsWith(".png"))
    || (file.content_type === "image/jpeg" && /\.(jpg|jpeg)$/.test(name)))
    && file.size <= 8 * 1024 * 1024;
}
function granted(me: AuthMe | null, key: string): boolean {
  return Boolean(me && (me.scopes.includes(key) || me.scopes.includes("*")));
}

export function StagedImageWatermarkClient({ requestedFileId }: { requestedFileId?: string }) {
  const [me, setMe] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [pdfId, setPdfId] = useState("");
  const [imageId, setImageId] = useState("");
  const [relativeWidth, setRelativeWidth] = useState(0.30);
  const [opacity, setOpacity] = useState(0.20);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const pdfs = files.filter(pdf);
  const images = files.filter(image);
  const chosenPdf = pdfs.find((file) => file.id === pdfId);
  const chosenImage = images.find((file) => file.id === imageId);
  const canWork = granted(me, "files:read") && granted(me, "jobs:read")
    && granted(me, "pdf:watermark");

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const identity = await getMe(SESSION_AUTH);
        if (!live) return;
        setMe(identity);
        if (!granted(identity, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH)).filter((file) => active(file, identity.name));
        if (!live) return;
        setFiles(owned);
        setPdfId(owned.find((file) => file.id === requestedFileId && pdf(file))?.id ?? "");
      } catch {
        if (live) setError("ตรวจสอบบัญชีและรายการไฟล์ไม่สำเร็จ");
      } finally {
        if (live) setLoading(false);
      }
    }
    void load();
    return () => { live = false; };
  }, [requestedFileId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!me || !canWork || !chosenPdf || !chosenImage || busy
        || !active(chosenPdf, me.name) || !active(chosenImage, me.name)
        || pdfId === imageId) return;
    if (!Number.isFinite(relativeWidth) || relativeWidth < .1 || relativeWidth > .8
        || !Number.isFinite(opacity) || opacity < .05 || opacity > .7) {
      setError("สัดส่วนภาพหรือความโปร่งใสอยู่นอกขอบเขต");
      return;
    }
    setBusy(true);
    setError("");
    setJob(null);
    try {
      setJob(await createJob("advanced/image-watermark", {
        file_id: chosenPdf.id, image_file_id: chosenImage.id,
        relative_width: relativeWidth, opacity,
      }, SESSION_AUTH));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "สร้างงานลายน้ำภาพไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  return <main className="t90DocumentStage m21ImageWatermark">
    <header className="t90DocumentStageHeader">
      <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
      <span>RCAT PDF HUB · M21 / ENGINEERING STAGING</span>
    </header>
    <section className="t90DocumentStageCard">
      <p className="t90DocumentStageKicker">M21 · REPEATED IMAGE WATERMARK</p>
      <h1>ใส่ลายน้ำรูปภาพลงทุกหน้า PDF</h1>
      <p>เลือก PNG/JPEG เพื่อวางกลางทุกหน้า PDF ด้วยความโปร่งใสและขนาดที่กำหนด</p>
      <p className="t90DocumentStageNotice" role="note">
        เป็นการวางภาพทับหน้าเอกสาร ไม่ใช่ลายเซ็นดิจิทัลหรือการป้องกันการแก้ไข
        รองรับเอกสารทั่วไปที่ไม่เข้ารหัส ไม่มีลายเซ็น ฟอร์ม หรือ Annotation ที่ซับซ้อน
      </p>
      {loading ? <p role="status">กำลังตรวจสอบบัญชี…</p> : (
        <form onSubmit={(event) => { void submit(event); }}>
          <div className="m21ImageWatermarkFields">
            <label>PDF ต้นฉบับของฉัน
              <select aria-label="PDF ต้นฉบับของฉัน" value={pdfId}
                onChange={(event) => { setPdfId(event.target.value); setJob(null); }}
                disabled={busy || !pdfs.length} required>
                <option value="">เลือก PDF</option>
                {pdfs.map((file) => <option key={file.id} value={file.id}>{file.original_name}</option>)}
              </select>
            </label>
            <label>รูป PNG/JPEG ของฉัน
              <select aria-label="รูป PNG/JPEG ของฉัน" value={imageId}
                onChange={(event) => { setImageId(event.target.value); setJob(null); }}
                disabled={busy || !images.length} required>
                <option value="">เลือกรูปภาพ</option>
                {images.map((file) => <option key={file.id} value={file.id}>{file.original_name}</option>)}
              </select>
            </label>
            <label>ความกว้างเทียบหน้ากระดาษ (0.10–0.80)
              <input aria-label="สัดส่วนภาพลายน้ำ" type="number" min=".1" max=".8" step=".05"
                value={relativeWidth} onChange={(event) => setRelativeWidth(Number(event.target.value))}
                disabled={busy} required />
            </label>
            <label>ความทึบ (0.05–0.70)
              <input aria-label="ความทึบลายน้ำ" type="number" min=".05" max=".7" step=".05"
                value={opacity} onChange={(event) => setOpacity(Number(event.target.value))}
                disabled={busy} required />
            </label>
          </div>
          {me && !canWork && <p role="alert">ต้องมีสิทธิ์ files:read, jobs:read และ pdf:watermark</p>}
          {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
          <button className="t90DocumentStageSubmit" type="submit"
            disabled={!chosenPdf || !chosenImage || !canWork || busy}>
            {busy ? "กำลังสร้างงาน…" : "เพิ่มลายน้ำรูปภาพ"}
          </button>
        </form>
      )}
      {job && <div className="t90DocumentStageResult" role="status">
        <strong>รับงานลายน้ำรูปภาพแล้ว</strong>
        <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
        <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูผลและดาวน์โหลด</a>
      </div>}
    </section>
  </main>;
}

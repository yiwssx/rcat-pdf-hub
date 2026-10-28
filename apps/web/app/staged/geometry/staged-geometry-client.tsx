"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

type GeometryOperation = "crop-pdf" | "resize-pdf";
const NAMES: Record<GeometryOperation, string> = {
  "crop-pdf": "ครอบตัดหน้ากระดาษ (CropBox)",
  "resize-pdf": "เปลี่ยนขนาดหน้ากระดาษ (Resize)",
};
const FIELDS = ["left", "bottom", "right", "top", "width", "height"] as const;
type NumberField = (typeof FIELDS)[number];
const LABELS: Record<NumberField, string> = {
  left: "ซ้าย (Left)", bottom: "ล่าง (Bottom)",
  right: "ขวา (Right)", top: "บน (Top)",
  width: "ความกว้าง (Width)", height: "ความสูง (Height)",
};

function validPdf(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner && file.content_type === "application/pdf"
    && file.size > 0
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at)) && Date.parse(file.expires_at) > Date.now()));
}

export function StagedGeometryClient({ requestedFileId }: { requestedFileId?: string }) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [fileId, setFileId] = useState("");
  const [operation, setOperation] = useState<GeometryOperation>("crop-pdf");
  const [values, setValues] = useState<Record<NumberField, string>>({
    left: "20", bottom: "20", right: "460", top: "700", width: "595", height: "842",
  });
  const [pages, setPages] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const me = await getMe(SESSION_AUTH);
        const owned = (await listFiles(SESSION_AUTH)).filter((file) => validPdf(file, me.name));
        if (!active) return;
        setIdentity(me);
        setFiles(owned);
        setFileId(owned.find((f) => f.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (active) setError("ไม่สามารถตรวจสอบสิทธิ์หรือไฟล์ได้ กรุณาเข้าสู่ระบบที่ Workspace");
      } finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, [requestedFileId]);

  const scope = operation === "crop-pdf" ? "pdf:crop" : "pdf:resize";
  const hasScope = Boolean(identity && (identity.scopes.includes(scope) || identity.scopes.includes("*")));
  const hasReads = Boolean(identity && (identity.scopes.includes("*")
    || (identity.scopes.includes("files:read") && identity.scopes.includes("jobs:read"))));
  const chosen = useMemo(() => files.find((file) => file.id === fileId), [files, fileId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !chosen || !identity || !hasScope || !hasReads) return;
    if (!validPdf(chosen, identity.name)) { setError("PDF นี้ไม่ใช่ไฟล์ที่มีสิทธิ์เข้าถึง"); return; }
    const keys: NumberField[] = operation === "crop-pdf"
      ? ["left", "bottom", "right", "top"] : ["width", "height"];
    const numbers: Record<string, number> = {};
    for (const key of keys) {
      const raw = values[key].trim();
      const value = Number(raw);
      if (!raw || !Number.isFinite(value) || value < (operation === "resize-pdf" ? 10 : -14400) || value > 14400) {
        setError("กรุณาระบุพิกัดหรือขนาดเป็นตัวเลข PDF points ที่ถูกต้อง"); return;
      }
      numbers[key] = value;
    }
    if (operation === "crop-pdf" && (
      numbers.right - numbers.left < 10 || numbers.top - numbers.bottom < 10 ||
      numbers.right - numbers.left > 14400 || numbers.top - numbers.bottom > 14400
    )) { setError("กรอบ Crop ต้องกว้างและสูงระหว่าง 10–14400 points"); return; }
    let selectedPages: number[] | null = null;
    if (operation === "crop-pdf" && pages.trim()) {
      const tokens = pages.split(",").map((part) => part.trim());
      selectedPages = tokens.map(Number);
      if (tokens.some((part) => !/^\d+$/.test(part))
        || !selectedPages.length || selectedPages.length > 1000
        || selectedPages.some((n) => !Number.isInteger(n) || n < 1 || n > 1000)
        || new Set(selectedPages).size !== selectedPages.length) {
        setError("ระบุหน้าเป็นหมายเลขไม่ซ้ำกัน เช่น 1,3,5 (ไม่รองรับช่วง 1-3)"); return;
      }
    }
    const payload = operation === "crop-pdf"
      ? { file_id: chosen.id, ...numbers, pages: selectedPages }
      : { file_id: chosen.id, ...numbers };
    setError("");
    setJob(null);
    setBusy(true);
    try { setJob(await createJob("geometry/" + operation, payload, SESSION_AUTH)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "สร้างงานไม่สำเร็จ"); }
    finally { setBusy(false); }
  }

  return (
    <main className="t90DocumentStage">
      <header className="t90DocumentStageHeader">
        <a href="/">← Workspace</a>
        <span>RCAT PDF Hub · T90-1.5 / STAGING ONLY</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">PDF GEOMETRY · CONTROLLED PREVIEW</p>
        <h1>ครอบตัดและเปลี่ยนขนาดหน้า PDF</h1>
        <p role="note" className="t90DocumentStageNotice">
          Crop ซ่อนเนื้อหานอกกรอบเท่านั้น ไม่ใช่การลบข้อมูล (Redaction)
          พิกัดอ้างอิงหน่วย PDF points โดยวัดจากมุมล่างซ้ายของหน้าที่ยังไม่หมุน
          ส่วน Resize ปรับขนาดแบบพอดีกับค่าที่ตั้งและอาจทำให้อัตราส่วนผิดเพี้ยน
        </p>
        {loading ? <p role="status">กำลังโหลดข้อมูลไฟล์…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="t90-geometry-file">PDF ที่อัปโหลดแล้ว (เฉพาะไฟล์ของบัญชีนี้)</label>
              <select id="t90-geometry-file" value={fileId} required disabled={busy || !files.length}
                onChange={(event) => { setFileId(event.target.value); setJob(null); }}>
                {!files.length && <option value="">ไม่มี PDF ที่เข้าถึงได้</option>}
                {files.map((file) => <option key={file.id} value={file.id}>{file.original_name}</option>)}
              </select>
            </div>
            <fieldset className="t90DocumentStageFieldset">
              <legend>เลือกเครื่องมือ</legend>
              {(["crop-pdf", "resize-pdf"] as const).map((item) => (
                <label key={item}>
                  <input type="radio" name="geometry-op" checked={operation === item}
                    onChange={() => { setOperation(item); setError(""); setJob(null); }} disabled={busy} />
                  {NAMES[item]}
                </label>
              ))}
            </fieldset>
            <div className="t90GeometryFields">
              {(operation === "crop-pdf"
                ? (["left", "bottom", "right", "top"] as const)
                : (["width", "height"] as const)
              ).map((key) => (
                <div className="t90DocumentStageField" key={key}>
                  <label htmlFor={"geometry-" + key}>{LABELS[key]} · pt</label>
                  <input id={"geometry-" + key} type="number" step="any" value={values[key]}
                    min={operation === "resize-pdf" ? 10 : -14400} max={14400}
                    onChange={(event) => setValues((old) => ({ ...old, [key]: event.target.value }))}
                    required disabled={busy} />
                </div>
              ))}
            </div>
            {operation === "crop-pdf" && (
              <div className="t90DocumentStageField">
                <label htmlFor="t90-geometry-pages">หน้าที่จะ Crop (เว้นว่าง = ทุกหน้า)</label>
                <input id="t90-geometry-pages" type="text" value={pages}
                  onChange={(event) => setPages(event.target.value)} disabled={busy}
                  placeholder="1,3,5" autoComplete="off" />
              </div>
            )}
            {!hasScope && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ {scope}</p>}
            {!hasReads && identity && <p role="alert">ต้องมีสิทธิ์ files:read และ jobs:read</p>}
            {error && <p className="t90DocumentStageError" role="alert">{error}</p>}
            <button type="submit" className="t90DocumentStageSubmit"
              disabled={busy || !chosen || !hasScope || !hasReads}>
              {busy ? "กำลังสร้างงาน…" : "สร้างงานทดลอง"}
            </button>
          </form>
        )}
        {job && (
          <div className="t90DocumentStageResult" role="status" aria-live="polite">
            <strong>รับงาน {NAMES[job.operation as GeometryOperation] ?? job.operation} แล้ว</strong>
            <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูผลและดาวน์โหลด PDF</a>
          </div>
        )}
      </section>
    </main>
  );
}

"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";

import { useEffect, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, uploadFile, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";
import { SignaturePad } from "./signature-pad";

type Placement = { page: number; x: number; y: number; width: number; height: number };
type Mode = "draw" | "upload";
const MAX_PDF = 16 * 1024 * 1024;
const MAX_IMAGE = 8 * 1024 * 1024;

function pdfOwned(item: UploadedFile, owner: string) {
  return item.source_system === owner
    && item.content_type === "application/pdf"
    && item.original_name.toLowerCase().endsWith(".pdf")
    && item.size >= 24 && item.size <= MAX_PDF
    && (!item.expires_at || (Number.isFinite(Date.parse(item.expires_at))
      && Date.parse(item.expires_at) > Date.now()));
}
function scoped(me: AuthMe | null, scope: string) {
  return Boolean(me && (me.scopes.includes(scope) || me.scopes.includes("*")));
}
function pngCandidate(file: File | null) {
  return Boolean(file && file.type === "image/png"
    && file.name.toLowerCase().endsWith(".png")
    && file.size >= 16 && file.size <= MAX_IMAGE);
}
function geometryValid(v: Placement) {
  return Number.isSafeInteger(v.page) && v.page >= 1 && v.page <= 80
    && [v.x, v.y, v.width, v.height].every(Number.isFinite)
    && v.x >= 0 && v.x <= 4000 && v.y >= 0 && v.y <= 4000
    && v.width >= 8 && v.width <= 2000 && v.height >= 8 && v.height <= 2000;
}

export function StagedVisualSignatureClient({
  requestedFileId,
}: { requestedFileId?: string }) {
  const [me, setMe] = useState<AuthMe | null>(null);
  const [pdfs, setPdfs] = useState<UploadedFile[]>([]);
  const [pdfId, setPdfId] = useState("");
  const [mode, setMode] = useState<Mode>("draw");
  const [blob, setBlob] = useState<Blob | null>(null);
  const [candidate, setCandidate] = useState<File | null>(null);
  const [placement, setPlacement] = useState<Placement>({
    page: 1, x: 50, y: 45, width: 180, height: 55,
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    let live = true;
    async function initialize() {
      try {
        const identity = await getMe(SESSION_AUTH);
        if (!live) return;
        setMe(identity);
        if (!scoped(identity, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH))
          .filter((file) => pdfOwned(file, identity.name));
        if (!live) return;
        setPdfs(owned);
        setPdfId(owned.find((file) => file.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (live) setError("กรุณาเข้าสู่ระบบและตรวจสอบรายการ PDF ที่มีสิทธิ์");
      } finally {
        if (live) setLoading(false);
      }
    }
    void initialize();
    return () => { live = false; };
  }, [requestedFileId]);

  const selected = pdfs.find((item) => item.id === pdfId);
  const allowed = scoped(me, "files:read") && scoped(me, "files:write")
    && scoped(me, "jobs:read") && scoped(me, "pdf:stamp");
  const imageReady = mode === "draw" ? Boolean(blob && blob.size >= 16 && blob.size <= MAX_IMAGE)
    : pngCandidate(candidate);
  const ready = allowed && Boolean(selected) && imageReady
    && geometryValid(placement) && !busy && !loading;

  function changeMode(next: Mode) {
    setMode(next);
    setBlob(null);
    setCandidate(null);
    setJob(null);
  }
  function updatePosition(key: keyof Placement, value: string) {
    setPlacement((before) => ({ ...before, [key]: Number(value) }));
    setJob(null);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready || !me || !selected || !pdfOwned(selected, me.name)) return;
    setBusy(true);
    setError("");
    setJob(null);
    try {
      const image = mode === "draw"
        ? new File([blob!], "visual-signature.png", { type: "image/png" })
        : candidate!;
      const uploaded = await uploadFile(image, SESSION_AUTH);
      if (uploaded.source_system !== me.name
          || uploaded.content_type !== "image/png"
          || !uploaded.original_name.toLowerCase().endsWith(".png")
          || uploaded.size < 16 || uploaded.size > MAX_IMAGE) {
        throw new Error("Uploaded image metadata not trusted");
      }
      // Real M23 image-overlay endpoint and Worker; no duplicate PDF engine.
      const submitted = await createJob("advanced/add-image", {
        file_id: selected.id, image_file_id: uploaded.id, ...placement,
      }, SESSION_AUTH);
      setJob(submitted);
    } catch {
      setError("บันทึกลายเซ็นหรือสร้างงาน PDF ไม่สำเร็จ ภาพที่อัปโหลดแล้วอาจยังอยู่ในคลังไฟล์ตามนโยบายการเก็บรักษา");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="t90DocumentStage m12VisualSignature">
      <header className="t90DocumentStageHeader">
        <a href="/">← Workspace</a>
        <span>RCAT PDF Hub · M12 / VISUAL SIGNATURE · STAGING ONLY</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">VISUAL SIGNATURE · REUSES M23 ENGINE</p>
        <h1>ลงลายเซ็นภาพบน PDF</h1>
        <p>วาดลายเซ็นด้วยนิ้วหรือเมาส์ หรืออัปโหลด PNG แล้ววางบนหน้าเอกสาร</p>
        <p className="t90DocumentStageNotice" role="note">
          เป็นลายเซ็นอิเล็กทรอนิกส์แบบภาพ ไม่ใช่ลายเซ็นดิจิทัลที่มีใบรับรอง
          ไม่ยืนยันตัวบุคคล ไม่สร้างการรับรองทางคริปโตกราฟี และไม่ใช่การ Redact
          ภาพลายเซ็นจะถูกเก็บในคลังไฟล์ของบัญชีตามระยะเวลาของระบบ
        </p>
        {loading ? <p role="status">กำลังตรวจสอบบัญชีและ PDF…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="m12-source">PDF ของฉัน</label>
              <NativeSelect id="m12-source" value={pdfId} required disabled={!pdfs.length || busy}
                onChange={(event) => { setPdfId(event.target.value); setJob(null); }}>
                {!pdfs.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
                {pdfs.map((item) => <option key={item.id} value={item.id}>{item.original_name}</option>)}
              </NativeSelect>
            </div>
            <fieldset className="t90DocumentStageFieldset">
              <legend>รูปแบบลายเซ็น</legend>
              <label>
                <input type="radio" name="m12-method" checked={mode === "draw"}
                  onChange={() => changeMode("draw")} disabled={busy} />
                วาดลายเซ็น
              </label>
              <label>
                <input type="radio" name="m12-method" checked={mode === "upload"}
                  onChange={() => changeMode("upload")} disabled={busy} />
                ใช้ภาพลายเซ็น PNG
              </label>
            </fieldset>
            {mode === "draw" ? (
              <SignaturePad disabled={busy} onImage={(next) => { setBlob(next); setJob(null); }} />
            ) : (
              <div className="t90DocumentStageField">
                <label htmlFor="m12-upload">ลายเซ็น PNG (ไม่เกิน 8 MB)</label>
                <input id="m12-upload" type="file" accept="image/png,.png"
                  className="m12SignatureFile" disabled={busy}
                  onChange={(event) => { setCandidate(event.target.files?.[0] ?? null); setJob(null); }} />
              </div>
            )}
            <fieldset className="t90DocumentStageFieldset">
              <legend>ตำแหน่งลายเซ็น (PDF points มุมล่างซ้าย)</legend>
              <div className="m12SignatureGeometry">
                {([
                  ["page", "หน้า", 1, 80],
                  ["x", "X", 0, 4000],
                  ["y", "Y", 0, 4000],
                  ["width", "กว้าง", 8, 2000],
                  ["height", "สูง", 8, 2000],
                ] as const).map(([key, label, min, max]) => (
                  <label key={key} htmlFor={"m12-" + key}>
                    {label}
                    <Input id={"m12-" + key} type="number" min={min} max={max}
                      step={1} value={placement[key]} required disabled={busy}
                      onChange={(event) => updatePosition(key, event.target.value)} />
                  </label>
                ))}
              </div>
            </fieldset>
            {!allowed && me && <p role="alert" className="t90DocumentStageError">
              ต้องมีสิทธิ์ files:read, files:write, jobs:read และ pdf:stamp
            </p>}
            {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
            <Button className="t90DocumentStageSubmit" type="submit" disabled={!ready}>
              {busy ? "กำลังอัปโหลดและสร้างงาน…" : "วางลายเซ็นลง PDF"}
            </Button>
          </form>
        )}
        {job && (
          <div className="t90DocumentStageResult" role="status">
            <strong>รับงานลายเซ็นภาพแล้ว</strong>
            <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูงานและดาวน์โหลด PDF</a>
          </div>
        )}
      </section>
    </main>
  );
}

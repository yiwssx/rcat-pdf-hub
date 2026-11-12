"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";

import { useEffect, useState, type FormEvent } from "react";
import {
  createJob, getMe, getPageInfo, listFiles, SESSION_AUTH,
  type AuthMe, type UploadedFile, type Job,
} from "../../../lib/api";

type Tool = "M25" | "M26" | "M29";
type Mode = "annotation" | "highlight" | "whiteout";
const MODES: Record<Tool, { mode: Mode; title: string; about: string }> = {
  M25: { mode: "annotation", title: "เพิ่ม Annotation", about: "เพิ่ม FreeText annotation จริงใน PDF (ASCII เท่านั้น)" },
  M26: { mode: "highlight", title: "ไฮไลต์ PDF", about: "เพิ่ม Highlight annotation ตามสี่เหลี่ยมที่เลือก ไม่ค้นหาคำให้อัตโนมัติ" },
  M29: { mode: "whiteout", title: "ปิดทับข้อความ/รูปภาพ", about: "ปิดทับด้วยสีขาวเฉพาะที่มองเห็น เนื้อหาเดิมยังคงอยู่: ไม่ใช่ Secure Redaction" },
};

function valid(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner
    && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 16 * 1024 * 1024
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}
function scope(me: AuthMe | null, name: string) {
  return Boolean(me && (me.scopes.includes(name) || me.scopes.includes("*")));
}

export function StagedPdfMarkupClient({
  requestedFileId, requestedToolId,
}: { requestedFileId?: string; requestedToolId?: string }) {
  const [tool, setTool] = useState<Tool>(
    requestedToolId === "M26" || requestedToolId === "M29" ? requestedToolId : "M25",
  );
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [fileId, setFileId] = useState("");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [x, setX] = useState(36);
  const [y, setY] = useState(36);
  const [width, setWidth] = useState(180);
  const [height, setHeight] = useState(60);
  const [text, setText] = useState("Review note");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const chosen = files.find((item) => item.id === fileId);
  const canWork = scope(identity, "files:read") && scope(identity, "jobs:read")
    && scope(identity, "pdf:stamp");

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const me = await getMe(SESSION_AUTH);
        if (!live) return;
        setIdentity(me);
        if (!scope(me, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH)).filter((item) => valid(item, me.name));
        if (!live) return;
        setFiles(owned);
        setFileId(owned.find((item) => item.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (live) setError("ตรวจสอบบัญชีและรายการ PDF ไม่สำเร็จ");
      } finally {
        if (live) setLoading(false);
      }
    }
    void load();
    return () => { live = false; };
  }, [requestedFileId]);

  useEffect(() => {
    if (!chosen || !scope(identity, "files:read")) return;
    let live = true;
    setTotal(0);
    setError("");
    void getPageInfo(chosen.id, SESSION_AUTH).then((info) => {
      if (!live) return;
      if (info.file_id !== chosen.id || !Number.isSafeInteger(info.pages)
          || info.pages < 1 || info.pages > 80) {
        setError("เครื่องมือนี้รองรับ PDF สูงสุด 80 หน้า");
      } else setTotal(info.pages);
    }).catch(() => { if (live) setError("อ่านจำนวนหน้าไม่สำเร็จ"); });
    return () => { live = false; };
  }, [chosen, identity]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosen || !identity || !canWork || busy || !total || !valid(chosen, identity.name)) return;
    if (!Number.isInteger(page) || page < 1 || page > total
      || page > 80 || ![x, y, width, height].every(Number.isFinite)
      || x < 0 || y < 0 || x > 4000 || y > 4000
      || width < 8 || width > 1500 || height < 8 || height > 1500) {
      setError("หมายเลขหน้าหรือกรอบสี่เหลี่ยมอยู่นอกขอบเขต");
      return;
    }
    if (tool === "M25" && (!text.trim() || text.length > 120
      || !/^[\x20-\x7e]+$/.test(text))) {
      setError("Annotation รองรับข้อความ ASCII ที่พิมพ์ได้ไม่เกิน 120 ตัวอักษร");
      return;
    }
    setBusy(true);
    setError("");
    setJob(null);
    try {
      setJob(await createJob("advanced/markup", {
        file_id: chosen.id, mode: MODES[tool].mode, page,
        x, y, width, height, text: tool === "M25" ? text : "",
      }, SESSION_AUTH));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "สร้างงาน PDF Markup ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  return <main className="t90DocumentStage t90Markup">
    <header className="t90DocumentStageHeader">
      <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
      <span>RCAT PDF HUB · M25/M26/M29 · ENGINEERING STAGING</span>
    </header>
    <section className="t90DocumentStageCard">
      <p className="t90DocumentStageKicker">PDF MARKUP · OWNER ONLY</p>
      <h1>เพิ่มหมายเหตุ ไฮไลต์ และปิดทับ PDF</h1>
      <p className="t90DocumentStageNotice" role="note">
        M25/M26 สร้าง PDF Annotation จริง ส่วน M29 เป็นการปิดทับทางภาพเท่านั้น
        ข้อความที่ถูกปิดทับยังสามารถคัดลอกหรือกู้คืนได้ ไม่เหมาะสำหรับปกปิดข้อมูลลับ
        ไม่รองรับเอกสารลงลายเซ็น ฟอร์มที่โต้ตอบได้ หน้า Crop/หมุน หรือ Annotation เดิม
      </p>
      {loading ? <p role="status">กำลังตรวจสอบบัญชี…</p> : (
        <form onSubmit={(event) => { void submit(event); }}>
          <div className="markupFields">
            <label>เครื่องมือ
              <NativeSelect aria-label="เครื่องมือ PDF Markup" value={tool}
                onChange={(event) => { setTool(event.target.value as Tool); setJob(null); }}
                disabled={busy}>
                {Object.entries(MODES).map(([id, info]) =>
                  <option key={id} value={id}>{id} · {info.title}</option>)}
              </NativeSelect>
            </label>
            <label>PDF ต้นฉบับของฉัน
              <NativeSelect aria-label="PDF ต้นฉบับของฉัน" value={fileId}
                onChange={(event) => { setFileId(event.target.value); setPage(1); setJob(null); }}
                disabled={!files.length || busy}>
                {!files.length && <option value="">ไม่มี PDF</option>}
                {files.map((item) =>
                  <option key={item.id} value={item.id}>{item.original_name}</option>)}
              </NativeSelect>
            </label>
            <label>หน้าที่ต้องการ (จาก {total || "…"} หน้า)
              <Input aria-label="หน้า PDF" type="number" min={1} max={total || 80} value={page}
                onChange={(event) => setPage(Number(event.target.value))} disabled={busy} required />
            </label>
            {([
              ["x", "พิกัด X", x, setX, 0, 4000],
              ["y", "พิกัด Y", y, setY, 0, 4000],
              ["width", "ความกว้าง", width, setWidth, 8, 1500],
              ["height", "ความสูง", height, setHeight, 8, 1500],
            ] as const).map(([key, label, value, setter, min, max]) =>
              <label key={key}>{label} (PDF points)
                <Input aria-label={label} type="number" min={min} max={max} value={value}
                  onChange={(event) => setter(Number(event.target.value))}
                  disabled={busy} required />
              </label>)}
            {tool === "M25" && <label className="full">ข้อความ Annotation (ASCII)
              <Textarea aria-label="ข้อความ Annotation" value={text} maxLength={120}
                onChange={(event) => setText(event.target.value)} disabled={busy} required />
            </label>}
          </div>
          <p>{MODES[tool].about}</p>
          {identity && !canWork && <p role="alert">ต้องมีสิทธิ์ files:read, jobs:read และ pdf:stamp</p>}
          {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
          <Button type="submit" className="t90DocumentStageSubmit"
            disabled={busy || !chosen || !canWork || !total}>
            {busy ? "กำลังสร้างงาน…" : MODES[tool].title}
          </Button>
        </form>
      )}
      {job && <div className="t90DocumentStageResult" role="status">
        <strong>รับงาน {tool} แล้ว</strong>
        <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
        <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูผลและดาวน์โหลด</a>
      </div>}
    </section>
  </main>;
}

"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createJob, getMe, getPageInfo, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

export type ManageId = "M14" | "M15" | "M16" | "M18" | "M22" | "M30" | "M31" | "M33";
type ToolInfo = {
  id: ManageId; title: string; scope: string; path: string; description: string;
};
const TOOLS: readonly ToolInfo[] = [
  { id:"M14", title:"ลบหน้า PDF", scope:"pdf:split", path:"manage-pages/delete", description:"ลบหน้าที่เลือก โดยยังเหลือหน้าอื่นใน PDF" },
  { id:"M15", title:"จัดเรียงหน้า PDF", scope:"pdf:split", path:"manage-pages/reorder", description:"ระบุลำดับหน้าใหม่แบบครบทุกหน้า ไม่ทำซ้ำและไม่ข้าม" },
  { id:"M16", title:"ดึงหน้าจาก PDF", scope:"pdf:split", path:"extract-pages", description:"ส่งออกเฉพาะหน้าที่เลือก เป็น PDF เดียวหรือ ZIP เฉพาะเมื่อ Backend อนุญาต" },
  { id:"M18", title:"ดึงรูปภาพฝังใน PDF", scope:"pdf:extract-images", path:"extract-images", description:"ดึงภาพที่ฝังในไฟล์เป็น ZIP ไม่ใช่การจับภาพทุกหน้า" },
  { id:"M22", title:"เพิ่มข้อความลง PDF", scope:"pdf:stamp", path:"advanced/add-text", description:"เพิ่มข้อความ ASCII บนหน้าหนึ่งตำแหน่ง ไม่ใช่โปรแกรมแก้ไขข้อความเดิม" },
  { id:"M30", title:"แปลง PDF เป็นขาวดำ", scope:"pdf:grayscale", path:"grayscale-pdf", description:"สร้าง PDF สีเทาฉบับใหม่จากต้นฉบับ" },
  { id:"M31", title:"หัวกระดาษและท้ายกระดาษ", scope:"pdf:header-footer", path:"header-and-footer", description:"เพิ่มข้อความหัว/ท้ายหน้า PDF (เฉพาะรูปแบบที่ Backend รองรับ)" },
  { id:"M33", title:"กรอกแบบฟอร์ม PDF", scope:"pdf:convert", path:"advanced/fill-pdf-form", description:"กรอกฟิลด์ข้อความ AcroForm ที่มีอยู่แล้ว ไม่ใช่การสร้างฟิลด์หรือลายเซ็น" },
];

const PAGE_RANGE = /^(?:[1-9][0-9]{0,5}|z)(?:-(?:[1-9][0-9]{0,5}|z))?(?:,(?:[1-9][0-9]{0,5}|z)(?:-(?:[1-9][0-9]{0,5}|z))?)*$/;

function eligiblePdf(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= 16 * 1024 * 1024
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}

function hasScope(me: AuthMe | null, scope: string): boolean {
  return Boolean(me && (me.scopes.includes(scope) || me.scopes.includes("*")));
}

function parseList(source: string, total: number): number[] {
  const pieces = source.split(",").map((v) => v.trim());
  if (!total || total > 120 || !pieces.length || pieces.length > 120
    || pieces.some((v) => !/^[1-9][0-9]{0,2}$/.test(v))) {
    throw new Error("ระบุเลขหน้าคั่นด้วยจุลภาค และไฟล์ไม่เกิน 120 หน้า");
  }
  const numbers = pieces.map(Number);
  if (new Set(numbers).size !== numbers.length || numbers.some((v) => v > total)) {
    throw new Error("หมายเลขหน้าต้องไม่ซ้ำและไม่เกินจำนวนหน้าจริง");
  }
  return numbers;
}

function validRange(raw: string): boolean {
  return raw.length >= 1 && raw.length <= 256 && PAGE_RANGE.test(raw)
    && raw.split(/[,-]/).every((piece) => piece === "z" || Number(piece) <= 100_000);
}

function parseFields(raw: string): Record<string, string> {
  const result: Record<string, string> = Object.create(null);
  const lines = raw.trim().split(/\r?\n/);
  if (!raw.trim() || lines.length > 30) throw new Error("ระบุฟิลด์ระหว่าง 1–30 รายการ");
  for (const line of lines) {
    const pivot = line.indexOf("=");
    const key = pivot < 0 ? "" : line.slice(0, pivot).trim();
    const value = pivot < 0 ? "" : line.slice(pivot + 1);
    if (!key || key.length > 128 || value.length > 512
      || /[\x00-\x1f\x7f]/.test(key)
      || /[\x00-\x08\x0b-\x1f\x7f]/.test(value)
      || Object.prototype.hasOwnProperty.call(result, key)) {
      throw new Error("ฟิลด์แบบฟอร์มต้องเป็น ชื่อฟิลด์=ข้อความ และไม่ซ้ำกัน");
    }
    result[key] = value;
  }
  return result;
}

export function StagedManageClient({
  requestedFileId, requestedToolId, enabledToolIds, allowMultiOutput,
}: {
  requestedFileId?: string; requestedToolId?: string; enabledToolIds: readonly ManageId[]; allowMultiOutput: boolean;
}) {
  const available = useMemo(
    () => TOOLS.filter((item) => enabledToolIds.includes(item.id)),
    [enabledToolIds],
  );
  const [toolId, setToolId] = useState<ManageId>(
    available.find((item) => item.id === requestedToolId)?.id ?? available[0]?.id ?? "M14",
  );
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [fileId, setFileId] = useState("");
  const [total, setTotal] = useState(0);
  const [pageError, setPageError] = useState("");
  const [pages, setPages] = useState("1");
  const [pageList, setPageList] = useState("1");
  const [format, setFormat] = useState<"pdf" | "zip">("pdf");
  const [overlayText, setOverlayText] = useState("Internal Document");
  const [overlayPage, setOverlayPage] = useState(1);
  const [x, setX] = useState(36);
  const [y, setY] = useState(36);
  const [fontSize, setFontSize] = useState(12);
  const [header, setHeader] = useState("");
  const [footer, setFooter] = useState("Page {page}");
  const [margin, setMargin] = useState(30);
  const [align, setAlign] = useState<"left" | "center" | "right">("center");
  const [updates, setUpdates] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  const tool = available.find((item) => item.id === toolId);
  const chosen = files.find((item) => item.id === fileId);
  const canWork = Boolean(tool && identity && hasScope(identity, tool.scope)
    && hasScope(identity, "files:read") && hasScope(identity, "jobs:read"));

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const me = await getMe(SESSION_AUTH);
        if (!active) return;
        setIdentity(me);
        if (!hasScope(me, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH))
          .filter((item) => eligiblePdf(item, me.name));
        if (!active) return;
        setFiles(owned);
        setFileId(owned.find((item) => item.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (active) setError("ตรวจสอบบัญชีและรายการเอกสารไม่สำเร็จ กรุณาเข้าสู่ระบบ");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [requestedFileId]);

  useEffect(() => {
    if (!chosen || !identity || !hasScope(identity, "files:read")) return;
    let active = true;
    setTotal(0);
    setPageError("");
    void getPageInfo(chosen.id, SESSION_AUTH).then((info) => {
      if (!active) return;
      if (info.file_id !== chosen.id || !Number.isSafeInteger(info.pages)
        || info.pages < 1 || info.pages > 5000) {
        setPageError("ไม่สามารถยืนยันจำนวนหน้าของ PDF ได้");
      } else setTotal(info.pages);
    }).catch(() => {
      if (active) setPageError("อ่านจำนวนหน้าของ PDF ไม่สำเร็จ");
    });
    return () => { active = false; };
  }, [chosen, identity]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!tool || !identity || !chosen || !canWork || busy
      || !eligiblePdf(chosen, identity.name) || !total) return;
    setJob(null);
    setError("");
    let payload: Record<string, unknown> = { file_id: chosen.id };
    try {
      switch (tool.id) {
        case "M16":
          if (!validRange(pages)) throw new Error("รูปแบบช่วงหน้าไม่ถูกต้อง เช่น 1,3-5 หรือ 1-z");
          if (total > 200) throw new Error("เครื่องมือชุดนี้รองรับ PDF ไม่เกิน 200 หน้า");
          payload = { ...payload, pages };
          if (tool.id === "M16") {
            if (format === "zip" && !allowMultiOutput) throw new Error("ยังไม่ได้เปิด Multi-output สำหรับ ZIP");
            payload.format = format;
          }
          break;
        case "M14":
        case "M15": {
          const numbers = parseList(pageList, total);
          if (tool.id === "M14" && numbers.length >= total) {
            throw new Error("การลบต้องเหลืออย่างน้อยหนึ่งหน้า");
          }
          if (tool.id === "M15" && (numbers.length !== total
            || numbers.some((value) => value > total))) {
            throw new Error("การจัดเรียงต้องระบุเลขหน้าทุกหน้าอย่างละหนึ่งครั้ง");
          }
          payload = { ...payload, [tool.id === "M14" ? "pages" : "order"]: numbers };
          break;
        }
        case "M22":
          if (!overlayText.trim() || overlayText.length > 120
            || !/^[\x20-\x7e]+$/.test(overlayText)) {
            throw new Error("M22 รองรับข้อความ ASCII ที่พิมพ์ได้เท่านั้น ไม่รองรับภาษาไทย");
          }
          if (!Number.isInteger(overlayPage) || overlayPage < 1
            || overlayPage > Math.min(total, 80)
            || ![x, y].every((value) => Number.isFinite(value) && value >= 0 && value <= 4000)
            || !Number.isInteger(fontSize) || fontSize < 8 || fontSize > 24) {
            throw new Error("เลขหน้า ตำแหน่ง หรือขนาดตัวอักษรอยู่นอกขอบเขต");
          }
          payload = { ...payload, page: overlayPage, x, y, font_size: fontSize, text: overlayText };
          break;
        case "M31":
          if (!header.trim() && !footer.trim()) {
            throw new Error("กรุณากรอกข้อความหัวหรือท้ายกระดาษ");
          }
          if (header.length > 256 || footer.length > 256 || /[\x00-\x08\x0b-\x1f]/.test(header + footer)
            || !Number.isInteger(fontSize) || fontSize < 8 || fontSize > 24
            || !Number.isInteger(margin) || margin < 12 || margin > 144) {
            throw new Error("ข้อความ หัว/ท้ายหน้า หรือขนาดอยู่นอกขอบเขต");
          }
          payload = {
            ...payload, header, footer, font_size: fontSize,
            margin, header_align: align, footer_align: align,
          };
          break;
        case "M33":
          payload = { ...payload, updates: parseFields(updates) };
          break;
        case "M18":
        case "M30":
          break;
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ข้อมูลไม่ถูกต้อง");
      return;
    }
    setBusy(true);
    try {
      setJob(await createJob(tool.path, payload, SESSION_AUTH));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถสร้างงาน PDF ได้");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="t90DocumentStage t90Manage">
      <header className="t90DocumentStageHeader">
        <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
        <span>RCAT PDF HUB · MANAGE PDF / ENGINEERING STAGING</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">MANAGE PDF · SOURCE WORKFLOW</p>
        <h1>จัดการและปรับแต่งเอกสาร PDF</h1>
        <p className="t90ManageOptionNote" role="note">
          เปิดได้เฉพาะ Backend ที่ได้รับการอนุญาตแยกแล้วเท่านั้น
          ทุกการดำเนินการสร้างผลลัพธ์ใหม่ ไม่แก้ไฟล์ต้นฉบับ และยังไม่ได้รับรองใช้งาน Production
        </p>
        {loading ? <p role="status">กำลังตรวจสอบบัญชีและไฟล์…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90ManageOptions">
              <label>เครื่องมือที่เปิดในสภาพแวดล้อมนี้
                <NativeSelect aria-label="เครื่องมือ Manage PDF" value={tool?.id ?? ""}
                  onChange={(event) => {
                    setToolId(event.target.value as ManageId); setJob(null); setError("");
                  }} disabled={!available.length || busy}>
                  {!available.length && <option value="">ไม่มีเครื่องมือที่อนุญาต</option>}
                  {available.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.title}</option>)}
                </NativeSelect>
              </label>
              <label>PDF ต้นฉบับ (เฉพาะของฉัน)
                <NativeSelect aria-label="PDF ต้นฉบับ (เฉพาะของฉัน)" value={fileId}
                  onChange={(event) => { setFileId(event.target.value); setJob(null); }}
                  disabled={!files.length || busy}>
                  {!files.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
                  {files.map((item) =>
                    <option key={item.id} value={item.id}>{item.original_name}</option>)}
                </NativeSelect>
              </label>
              <label>จำนวนหน้าต้นฉบับ
                <Input aria-label="จำนวนหน้าต้นฉบับ" value={total || "ยังไม่ทราบ"} readOnly />
              </label>
            </div>
            {tool && <p className="t90ManageHints">{tool.description}</p>}
            {tool && (tool.id === "M16") && (
              <div className="t90ManageFields">
                <label className="wide">ช่วงหน้าที่ต้องการ เช่น 1,3-5 หรือ 1-z
                  <Input aria-label="ช่วงหน้า PDF" value={pages} maxLength={256}
                    onChange={(event) => { setPages(event.target.value); setJob(null); }}
                    disabled={busy} required />
                </label>
                {tool.id === "M16" && <label>ชนิดผลลัพธ์
                  <NativeSelect aria-label="ชนิดผลลัพธ์" value={format}
                    onChange={(event) => setFormat(event.target.value as "pdf" | "zip")}>
                    <option value="pdf">PDF เดียว</option>
                    <option value="zip" disabled={!allowMultiOutput}>PDF แยกหน้าใน ZIP (ต้องเปิด Multi-output)</option>
                  </NativeSelect>
                </label>}
              </div>
            )}
            {tool && (tool.id === "M14" || tool.id === "M15") && (
              <div className="t90ManageFields">
                <label className="wide">
                  {tool.id === "M14" ? "หน้าที่จะลบ (เช่น 2,4)" : "ลำดับหน้าใหม่ทุกหน้า (เช่น 3,1,2)"}
                  <Input aria-label="รายการหมายเลขหน้า" value={pageList}
                    onChange={(event) => { setPageList(event.target.value); setJob(null); }}
                    disabled={busy} required />
                </label>
              </div>
            )}
            {tool?.id === "M22" && (
              <div className="t90ManageFields">
                <label className="wide">ข้อความ ASCII เท่านั้น
                  <Input aria-label="ข้อความที่จะเพิ่ม" maxLength={120} value={overlayText}
                    onChange={(event) => setOverlayText(event.target.value)} disabled={busy} required />
                </label>
                <label>หน้าที่จะเพิ่มข้อความ
                  <Input type="number" min={1} max={Math.min(80, total || 80)} value={overlayPage}
                    onChange={(event) => setOverlayPage(Number(event.target.value))} disabled={busy} required />
                </label>
                <label>พิกัด X (points)
                  <Input aria-label="พิกัด X" type="number" min={0} max={4000} value={x}
                    onChange={(event) => setX(Number(event.target.value))} disabled={busy} required />
                </label>
                <label>พิกัด Y (points)
                  <Input aria-label="พิกัด Y" type="number" min={0} max={4000} value={y}
                    onChange={(event) => setY(Number(event.target.value))} disabled={busy} required />
                </label>
              </div>
            )}
            {tool?.id === "M31" && (
              <div className="t90ManageFields">
                <label className="wide">ข้อความหัวกระดาษ
                  <Input aria-label="ข้อความหัวกระดาษ" maxLength={256} value={header}
                    onChange={(event) => setHeader(event.target.value)} disabled={busy} />
                </label>
                <label className="wide">ข้อความท้ายกระดาษ
                  <Input aria-label="ข้อความท้ายกระดาษ" maxLength={256} value={footer}
                    onChange={(event) => setFooter(event.target.value)} disabled={busy} />
                </label>
                <label>ระยะขอบ (points)
                  <Input aria-label="ระยะขอบ" type="number" min={12} max={144} value={margin}
                    onChange={(event) => setMargin(Number(event.target.value))} disabled={busy} required />
                </label>
                <label>ตำแหน่งข้อความ
                  <NativeSelect aria-label="ตำแหน่งข้อความ" value={align}
                    onChange={(event) => setAlign(event.target.value as "left" | "center" | "right")}
                    disabled={busy}>
                    <option value="left">ซ้าย</option><option value="center">กลาง</option>
                    <option value="right">ขวา</option>
                  </NativeSelect>
                </label>
              </div>
            )}
            {tool && (tool.id === "M22" || tool.id === "M31") && (
              <div className="t90ManageFields">
                <label>ขนาดตัวอักษร 8–24
                  <Input aria-label="ขนาดตัวอักษร" type="number" min={8} max={24} value={fontSize}
                    onChange={(event) => setFontSize(Number(event.target.value))} disabled={busy} required />
                </label>
              </div>
            )}
            {tool?.id === "M33" && (
              <div className="t90ManageFields">
                <label className="wide">กรอกฟิลด์ AcroForm: ชื่อฟิลด์=ค่า (บรรทัดละรายการ)
                  <Textarea aria-label="ฟิลด์ AcroForm" value={updates} maxLength={15000}
                    onChange={(event) => setUpdates(event.target.value)} disabled={busy}
                    placeholder={"student_name=Example\nstudent_id=123"} required />
                </label>
              </div>
            )}
            {!hasScope(identity, "files:read") && identity && <p role="alert">ไม่มีสิทธิ์ files:read</p>}
            {tool && !hasScope(identity, tool.scope) && identity &&
              <p role="alert">ไม่มีสิทธิ์ {tool.scope}</p>}
            {tool && !hasScope(identity, "jobs:read") && identity &&
              <p role="alert">ไม่มีสิทธิ์ jobs:read</p>}
            {pageError && <p role="alert" className="t90DocumentStageError">{pageError}</p>}
            {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
            {!available.length && <p role="status">Backend ของเครื่องมือกลุ่มนี้ยังปิดอยู่</p>}
            <Button type="submit" className="t90DocumentStageSubmit"
              disabled={busy || !chosen || !total || !tool || !canWork || Boolean(pageError)}>
              {busy ? "กำลังสร้างงาน…" : "เริ่มดำเนินการ"}
            </Button>
          </form>
        )}
        {job && <div className="t90DocumentStageResult" role="status" aria-live="polite">
          <strong>รับงาน {tool?.id ?? "PDF"} แล้ว</strong>
          <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
          <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>
            เปิดหน้าผลงานและดาวน์โหลด
          </a>
        </div>}
      </section>
    </main>
  );
}

"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

type Lang = "en" | "th";
const MAX_FILE_BYTES = 8 * 1024 * 1024;
function owned(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner
    && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= MAX_FILE_BYTES
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}
function has(me: AuthMe | null, scope: string): boolean {
  return Boolean(me && (me.scopes.includes(scope) || me.scopes.includes("*")));
}

export function StagedTranslationClient({ requestedFileId }: { requestedFileId?: string }) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [fileId, setFileId] = useState("");
  const [sourceLang, setSourceLang] = useState<Lang>("en");
  const [targetLang, setTargetLang] = useState<Lang>("th");
  const [format, setFormat] = useState<"pdf" | "text">("pdf");
  const [layout, setLayout] = useState<"translated" | "bilingual">("translated");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const me = await getMe(SESSION_AUTH);
        if (!alive) return;
        setIdentity(me);
        if (!has(me, "files:read")) return;
        const found = (await listFiles(SESSION_AUTH)).filter((f) => owned(f, me.name));
        if (!alive) return;
        setFiles(found);
        setFileId(found.find((f) => f.id === requestedFileId)?.id ?? found[0]?.id ?? "");
      } catch {
        if (alive) setError("ตรวจสอบบัญชีหรือรายการ PDF ไม่สำเร็จ");
      } finally {
        if (alive) setLoading(false);
      }
    }
    void load();
    return () => { alive = false; };
  }, [requestedFileId]);

  const selected = useMemo(() => files.find((f) => f.id === fileId), [files, fileId]);
  const allowed = has(identity, "files:read") && has(identity, "jobs:read")
    && has(identity, "pdf:extract-text");
  const ready = allowed && Boolean(selected) && sourceLang !== targetLang && !busy;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready || !selected || !identity || !owned(selected, identity.name)) return;
    setBusy(true);
    setError("");
    setJob(null);
    try {
      setJob(await createJob("translation/" + (format === "pdf" ? "pdf" : "text"), {
        file_id: selected.id, source_language: sourceLang, target_language: targetLang,
        ...(format === "pdf" && layout === "bilingual" ? { layout: "bilingual" } : {}),
      }, SESSION_AUTH));
    } catch {
      setError("ส่งงานแปลภาษาไม่สำเร็จ กรุณาตรวจสอบสิทธิ์และบริการแปลภาษาภายใน");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="t90DocumentStage">
      <header className="t90DocumentStageHeader">
        <a href="/">← Workspace</a>
        <span>RCAT PDF Hub · M05 / LIMITED STAGING</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">ON-PREMISE MACHINE TRANSLATION</p>
        <h1>แปลข้อความจาก PDF</h1>
        <p role="note" className="t90DocumentStageNotice">
          รองรับภาษาอังกฤษและไทย เฉพาะ PDF ที่เลือกข้อความได้
          เลือกผลลัพธ์ PDF ที่จัดหน้าใหม่ด้วยฟอนต์ภาษาไทย หรือ TXT UTF-8 ได้
          โดยมีหมายเลขหน้าต้นฉบับประกอบ สามารถเลือกรูปแบบ PDF สองภาษาเพื่อเทียบต้นฉบับกับคำแปลได้
          แต่ PDF ใหม่ไม่คง Layout เดิม
          ต้องมีระบบแปลภาษาที่รันภายในและได้รับอนุมัติก่อนใช้งาน
          ไฟล์สแกนต้อง OCR ก่อน และคำแปลควรตรวจทานก่อนนำไปใช้จริง
        </p>
        {loading ? <p role="status">กำลังโหลด PDF ของบัญชี…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="m05-source">PDF ของฉัน</label>
              <select id="m05-source" value={fileId} required disabled={!files.length || busy}
                onChange={(event) => { setFileId(event.target.value); setJob(null); }}>
                {!files.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
                {files.map((f) => <option key={f.id} value={f.id}>{f.original_name}</option>)}
              </select>
            </div>
            <div className="t90DocumentStageField">
              <label htmlFor="m05-from">ภาษาต้นฉบับ</label>
              <select id="m05-from" value={sourceLang} disabled={busy} onChange={(event) => {
                const next = event.target.value as Lang;
                setSourceLang(next); setTargetLang(next === "en" ? "th" : "en"); setJob(null);
              }}>
                <option value="en">English</option>
                <option value="th">ไทย</option>
              </select>
            </div>
            <div className="t90DocumentStageField">
              <label htmlFor="m05-to">ภาษาเป้าหมาย</label>
              <select id="m05-to" value={targetLang} disabled={busy} onChange={(event) => {
                setTargetLang(event.target.value as Lang); setJob(null);
              }}>
                <option value="th">ไทย</option>
                <option value="en">English</option>
              </select>
            </div>
            <div className="t90DocumentStageField">
              <label htmlFor="m05-format">รูปแบบผลลัพธ์</label>
              <select id="m05-format" value={format} disabled={busy}
                onChange={(event) => { setFormat(event.target.value as "pdf" | "text"); setJob(null); }}>
                <option value="pdf">PDF ฉบับแปล (จัดหน้าใหม่)</option>
                <option value="text">TXT ข้อความแปล</option>
              </select>
            </div>
            {format === "pdf" && (
              <div className="t90DocumentStageField">
                <label htmlFor="m05-layout">รูปแบบหน้า PDF</label>
                <select id="m05-layout" value={layout} disabled={busy}
                  onChange={(event) => { setLayout(event.target.value as "translated" | "bilingual"); setJob(null); }}>
                  <option value="translated">คำแปลอย่างเดียว (จัดหน้าใหม่)</option>
                  <option value="bilingual">สองภาษา: ข้อความต้นฉบับและคำแปลสำหรับตรวจทาน</option>
                </select>
              </div>
            )}
            {!allowed && identity && <p role="alert" className="t90DocumentStageError">
              ต้องมีสิทธิ์ files:read, jobs:read และ pdf:extract-text
            </p>}
            {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
            <button type="submit" className="t90DocumentStageSubmit" disabled={!ready}>
              {busy ? "กำลังสร้างงาน…" : "แปลข้อความ PDF ภายในระบบ"}
            </button>
          </form>
        )}
        {job && (
          <div role="status" className="t90DocumentStageResult">
            <strong>รับงานแปลภาษาแล้ว</strong>
            <span>รหัสงาน: {job.id}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>
              {"ดูผลและดาวน์โหลด " + (format === "pdf" ? "PDF ฉบับแปล" : "TXT")}
            </a>
          </div>
        )}
      </section>
    </main>
  );
}

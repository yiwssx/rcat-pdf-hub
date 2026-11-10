"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createJob, getMe, listFiles, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";

const MAX_FILE_BYTES = 12 * 1024 * 1024;
const TEXT = /^[\x20-\x7e\u0e01-\u0e2e\u0e30\u0e32\u0e40-\u0e44\u0e50-\u0e59]+$/;

function ownedPdf(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner
    && file.content_type === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size >= 24 && file.size <= MAX_FILE_BYTES
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}
function hasScope(me: AuthMe | null, scope: string): boolean {
  return Boolean(me && (me.scopes.includes(scope) || me.scopes.includes("*")));
}
function validReplacement(oldText: string, newText: string): boolean {
  return oldText.length >= 3 && oldText.length <= 96
    && oldText.length === newText.length && oldText !== newText
    && oldText.split(" ").length === newText.split(" ").length
    && Boolean(oldText.trim() && newText.trim())
    && TEXT.test(oldText) && TEXT.test(newText);
}

export function StagedPdfTextEditorClient({ requestedFileId }: { requestedFileId?: string }) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [page, setPage] = useState(1);
  const [oldText, setOldText] = useState("");
  const [newText, setNewText] = useState("");
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
        if (!hasScope(me, "files:read")) return;
        const owned = (await listFiles(SESSION_AUTH)).filter((item) => ownedPdf(item, me.name));
        if (!alive) return;
        setFiles(owned);
        setSelectedId(owned.find((item) => item.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (alive) setError("ไม่สามารถตรวจสอบสิทธิ์หรือไฟล์ได้ กรุณาเข้าสู่ระบบใหม่");
      } finally {
        if (alive) setLoading(false);
      }
    }
    void load();
    return () => { alive = false; };
  }, [requestedFileId]);

  const selected = useMemo(() => files.find((item) => item.id === selectedId), [files, selectedId]);
  const authorized = hasScope(identity, "pdf:stamp")
    && hasScope(identity, "files:read") && hasScope(identity, "jobs:read");
  const ready = authorized && Boolean(selected)
    && !busy && Number.isSafeInteger(page) && page >= 1 && page <= 80
    && validReplacement(oldText, newText);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready || !selected || !identity || !ownedPdf(selected, identity.name)) return;
    setBusy(true);
    setError("");
    setJob(null);
    try {
      setJob(await createJob("advanced/edit-existing-text", {
        file_id: selected.id, page, old_text: oldText, new_text: newText,
      }, SESSION_AUTH));
    } catch {
      setError("ไม่สามารถแก้ไขข้อความได้ ไม่พบข้อความตำแหน่งเดียวที่แก้ไขได้อย่างปลอดภัย หรือฟอนต์ฝังไม่มีหลักฐาน glyph/Mapping ครบถ้วน");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="t90DocumentStage m01Editor">
      <header className="t90DocumentStageHeader">
        <a href="/">← Workspace</a>
        <span>RCAT PDF Hub · M01 / LIMITED STAGING</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">REAL TEXT OBJECT REPLACEMENT · LIMITED</p>
        <h1>แก้ไขข้อความเดิมใน PDF</h1>
        <p>แทนที่ข้อความที่มีอยู่จริงใน PDF โดยแก้คำสั่งแสดงข้อความ ไม่ใช่วางข้อความทับ</p>
        <p className="t90DocumentStageNotice" role="note">
          รองรับข้อความ ASCII ใน Courier, Helvetica, Times และฟอนต์ TrueType ที่ฝังอยู่บางชนิด รวมถึงพยัญชนะไทย สระแบบไม่ซ้อนตำแหน่งบางตัว และเลขไทยใน TrueType ที่มี ToUnicode แบบหนึ่งไบต์
          (ต้องพิสูจน์ได้ว่าตัวอักษรใหม่เคยแสดงด้วยฟอนต์เดียวกันในหน้านั้น)
          รองรับข้อความแบ่งช่วงภายใน TJ เดียว หรือ Tj สองคำสั่งที่ติดกันโดยไม่มีคำสั่งคั่น โดยต้องคงจำนวนตัวอักษรและช่องว่างเดิม
          ข้อความเดิมต้องปรากฏครั้งเดียว ภาษาไทยรองรับ ก–ฮ, ะ, า, เ–ไ และ ๐–๙ ใน Tj เดียวและ glyph ที่มีอยู่แล้ว ไม่รองรับสระบน–ล่าง สระผสม วรรณยุกต์ ฟอนต์ CID และข้อความข้ามคำสั่งที่เปลี่ยนสถานะ
          ไม่รองรับไฟล์สแกน ลายเซ็น แบบฟอร์ม หรือการ Redact
          ผลลัพธ์เป็นไฟล์สำเนาและยังไม่ได้เปิดใช้ Production
        </p>
        {loading ? <p role="status">กำลังตรวจสอบบัญชีและ PDF ของฉัน…</p> : (
          <form onSubmit={(event) => { void submit(event); }}>
            <div className="t90DocumentStageField">
              <label htmlFor="m01-source">PDF ของฉัน</label>
              <select id="m01-source" value={selectedId} disabled={!files.length || busy}
                onChange={(event) => { setSelectedId(event.target.value); setJob(null); }}
                required>
                {!files.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
                {files.map((item) =>
                  <option key={item.id} value={item.id}>{item.original_name}</option>)}
              </select>
            </div>
            <div className="m01Fields">
              <div className="t90DocumentStageField">
                <label htmlFor="m01-page">หน้า PDF (1–80)</label>
                <input id="m01-page" aria-label="หน้า PDF" type="number" min={1} max={80}
                  value={page} onChange={(event) => {
                    setPage(Number(event.target.value)); setJob(null);
                  }} disabled={busy} required/>
              </div>
              <div className="t90DocumentStageField">
                <label htmlFor="m01-existing">ข้อความเดิมที่ต้องการแก้ไข</label>
                <input id="m01-existing" type="text" maxLength={96} value={oldText}
                  onChange={(event) => { setOldText(event.target.value); setJob(null); }}
                  placeholder="ORIGINAL" disabled={busy} required />
              </div>
              <div className="t90DocumentStageField">
                <label htmlFor="m01-replacement">ข้อความใหม่ (จำนวนตัวอักษรเท่ากัน)</label>
                <input id="m01-replacement" type="text" maxLength={96} value={newText}
                  onChange={(event) => { setNewText(event.target.value); setJob(null); }}
                  placeholder="REVISED!" disabled={busy} required />
              </div>
            </div>
            <p className="m01Counter" aria-live="polite">
              จำนวนตัวอักษร: เดิม {oldText.length} / ใหม่ {newText.length}
            </p>
            {!authorized && identity && (
              <p role="alert" className="t90DocumentStageError">
                ต้องมีสิทธิ์ files:read, jobs:read และ pdf:stamp
              </p>
            )}
            {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
            <button className="t90DocumentStageSubmit" type="submit" disabled={!ready}>
              {busy ? "กำลังสร้างงาน…" : "แก้ไขข้อความเดิมใน PDF"}
            </button>
          </form>
        )}
        {job && (
          <div role="status" className="t90DocumentStageResult">
            <strong>รับงานแก้ไข PDF แล้ว</strong>
            <span>รหัสงาน: {job.id} · สถานะ: {job.status}</span>
            <a href={"/jobs/" + encodeURIComponent(job.id) + "/result"}>ดูผลและดาวน์โหลด PDF</a>
          </div>
        )}
      </section>
    </main>
  );
}

"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  createJob,
  fetchDownload,
  fetchPreview,
  Job,
  listFiles,
  listJobs,
  uploadFile,
  UploadedFile,
} from "../../lib/api";
import { AdminPanel } from "./admin-panel";

type Tab = "tools" | "admin";

const positionOptions = [
  ["center", "กลาง"],
  ["top-left", "บนซ้าย"], ["top-center", "บนกลาง"], ["top-right", "บนขวา"],
  ["bottom-left", "ล่างซ้าย"], ["bottom-center", "ล่างกลาง"], ["bottom-right", "ล่างขวา"],
] as const;

export function PdfHubConsole() {
  const [tab, setTab] = useState<Tab>("tools");
  const [apiKey, setApiKey] = useState("");
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("พร้อมใช้งาน");
  const [targetId, setTargetId] = useState("");
  const [stampId, setStampId] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewPage, setPreviewPage] = useState(1);

  const [splitPages, setSplitPages] = useState("1-3");
  const [rotateDegrees, setRotateDegrees] = useState(90);
  const [rotatePages, setRotatePages] = useState("1-z");
  const [watermarkText, setWatermarkText] = useState("เอกสารภายใน");
  const [watermarkOpacity, setWatermarkOpacity] = useState(0.18);
  const [watermarkRotation, setWatermarkRotation] = useState(45);
  const [watermarkFontSize, setWatermarkFontSize] = useState(48);
  const [watermarkPosition, setWatermarkPosition] = useState("center");
  const [pageFormat, setPageFormat] = useState("หน้า {page} / {total}");
  const [pageStart, setPageStart] = useState(1);
  const [pagePosition, setPagePosition] = useState("bottom-center");
  const [stampPosition, setStampPosition] = useState("bottom-right");
  const [stampScale, setStampScale] = useState(0.2);

  const target = useMemo(() => files.find((file) => file.id === targetId) || null, [files, targetId]);
  const activeJobs = useMemo(() => jobs.some((job) => job.status === "queued" || job.status === "running"), [jobs]);

  useEffect(() => {
    if (!apiKey || !activeJobs) return;
    const timer = window.setInterval(async () => {
      try {
        setJobs(await listJobs(apiKey));
      } catch {
        // Keep the console usable if one background poll fails.
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [apiKey, activeJobs]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  async function loadWorkspace() {
    if (!apiKey) return;
    setBusy(true);
    try {
      const [fileRows, jobRows] = await Promise.all([listFiles(apiKey), listJobs(apiKey)]);
      setFiles(fileRows);
      setJobs(jobRows);
      if (!targetId && fileRows[0]) setTargetId(fileRows[0].id);
      setMessage("โหลด workspace แล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "โหลด workspace ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function onFiles(list: FileList | null) {
    if (!list?.length || !apiKey) return;
    setBusy(true);
    setMessage("กำลังอัปโหลด...");
    try {
      const uploaded: UploadedFile[] = [];
      for (const file of Array.from(list)) uploaded.push(await uploadFile(file, apiKey));
      setFiles((old) => [...uploaded, ...old.filter((item) => !uploaded.some((fresh) => fresh.id === item.id))]);
      if (uploaded[0]) setTargetId(uploaded[0].id);
      setMessage(`อัปโหลดแล้ว ${uploaded.length} ไฟล์`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "อัปโหลดไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function submit(operation: string, payload: object) {
    if (!apiKey) return;
    setBusy(true);
    try {
      const job = await createJob(operation, payload, apiKey);
      setJobs((old) => [job, ...old]);
      setMessage(`ส่งงาน ${operation} แล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ทำรายการไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function run(operation: string) {
    if (!targetId && operation !== "merge") {
      setMessage("เลือกไฟล์เป้าหมายก่อน");
      return;
    }
    switch (operation) {
      case "merge":
        if (files.length < 2) return setMessage("Merge ต้องมีอย่างน้อย 2 ไฟล์ในรายการ");
        return submit("merge", { file_ids: files.map((file) => file.id) });
      case "split":
        return submit("split", { file_id: targetId, pages: splitPages });
      case "rotate":
        return submit("rotate", { file_id: targetId, degrees: rotateDegrees, pages: rotatePages });
      case "ocr":
        return submit("ocr", { file_id: targetId, languages: "tha+eng", deskew: true, rotate_pages: true });
      case "compress":
        return submit("compress", { file_id: targetId });
      case "pdfa":
        return submit("pdfa", { file_id: targetId, languages: "tha+eng", deskew: false, rotate_pages: false });
      case "office-to-pdf":
        return submit("office-to-pdf", { file_id: targetId });
      case "watermark":
        return submit("watermark", {
          file_id: targetId,
          text: watermarkText,
          font_size: watermarkFontSize,
          opacity: watermarkOpacity,
          rotation: watermarkRotation,
          position: watermarkPosition,
          margin: 36,
        });
      case "page-numbers":
        return submit("page-numbers", {
          file_id: targetId,
          format: pageFormat,
          start_number: pageStart,
          font_size: 10,
          position: pagePosition,
          margin: 24,
        });
      case "stamp":
        if (!stampId) return setMessage("เลือกไฟล์ PDF ที่จะใช้เป็นตราประทับก่อน");
        return submit("stamp", { file_id: targetId, stamp_file_id: stampId, position: stampPosition, scale: stampScale, margin: 24 });
      default:
        setMessage("Unknown operation");
    }
  }

  async function refreshJobs() {
    if (!apiKey) return;
    try {
      setJobs(await listJobs(apiKey));
      setMessage("อัปเดตสถานะแล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "อ่านสถานะไม่สำเร็จ");
    }
  }

  async function download(fileId: string) {
    if (!apiKey) return;
    try {
      const blob = await fetchDownload(fileId, apiKey);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `pdfhub-${fileId}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ดาวน์โหลดไม่สำเร็จ");
    }
  }

  async function preview() {
    if (!apiKey || !targetId) return;
    try {
      setMessage("กำลังสร้าง Preview...");
      const blob = await fetchPreview(targetId, apiKey, previewPage, 900);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
      setMessage(`Preview หน้า ${previewPage} พร้อมแล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Preview ไม่สำเร็จ");
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <span className="eyebrow">RCAT • SELF-HOSTED • CENTRAL PDF INFRASTRUCTURE</span>
          <h1>PDF Hub</h1>
          <p>ประมวลผล PDF, OCR ไทย, Office conversion, watermark, page number, stamp และควบคุม service quota จากศูนย์กลางเดียว</p>
        </div>
        <div className="status"><span className="statusDot" />{message}</div>
      </header>

      <nav className="tabs" aria-label="PDF Hub sections">
        <button className={tab === "tools" ? "active" : ""} onClick={() => setTab("tools")}>PDF Console</button>
        <button className={tab === "admin" ? "active" : ""} onClick={() => setTab("admin")}>Admin</button>
      </nav>

      <section className="panel auth">
        <label>API Key</label>
        <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="pdfh_... หรือ Bootstrap Admin Key" autoComplete="off" />
        <button className="secondary" onClick={loadWorkspace} disabled={!apiKey || busy}>เชื่อมต่อ</button>
        <small>คีย์อยู่เฉพาะใน memory ของ browser tab นี้ ไม่บันทึกลง localStorage</small>
      </section>

      {tab === "admin" ? <AdminPanel apiKey={apiKey} /> : (
        <>
          <section className="workspaceGrid">
            <div className="panel drop">
              <input id="files" type="file" multiple onChange={(e) => onFiles(e.target.files)} disabled={!apiKey || busy} />
              <label htmlFor="files">
                <span className="dropIcon">＋</span>
                <strong>เพิ่มไฟล์เข้า Workspace</strong>
                <span>PDF, Word, Excel, PowerPoint และเอกสาร LibreOffice</span>
              </label>
            </div>

            <div className="panel targetPanel">
              <div className="panelTitle"><h2>ไฟล์เป้าหมาย</h2><span>{files.length} files</span></div>
              <select value={targetId} onChange={(e) => { setTargetId(e.target.value); setPreviewUrl(null); }}>
                <option value="">— เลือกไฟล์ —</option>
                {files.map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}
              </select>
              {target && <div className="fileMeta"><strong>{target.original_name}</strong><span>{(target.size / 1024 / 1024).toFixed(2)} MB • {target.content_type}</span><code>{target.id}</code></div>}
              <div className="previewControls"><label>หน้า<input type="number" min="1" value={previewPage} onChange={(e) => setPreviewPage(Math.max(1, Number(e.target.value)))} /></label><button className="secondary" onClick={preview} disabled={!targetId}>Preview PDF</button></div>
            </div>
          </section>

          {previewUrl && (
            <section className="panel previewPanel">
              <div className="panelTitle"><h2>Preview</h2><button className="ghost" onClick={() => setPreviewUrl(null)}>ปิด</button></div>
              <div className="previewCanvas"><Image src={previewUrl} alt={`Preview page ${previewPage}`} width={900} height={1200} unoptimized /></div>
            </section>
          )}

          <section className="panel">
            <div className="panelTitle"><h2>Quick Tools</h2><span>Async queue</span></div>
            <div className="tools">
              <button disabled={busy || files.length < 2} onClick={() => run("merge")}><strong>รวม PDF</strong><small>รวมทุกไฟล์ใน workspace ตามลำดับ</small></button>
              <button disabled={busy || !targetId} onClick={() => run("ocr")}><strong>OCR ไทย + อังกฤษ</strong><small>Tesseract tha+eng + deskew</small></button>
              <button disabled={busy || !targetId} onClick={() => run("compress")}><strong>บีบอัด PDF</strong><small>Ghostscript /ebook profile</small></button>
              <button disabled={busy || !targetId} onClick={() => run("pdfa")}><strong>PDF/A-2</strong><small>เอกสารเก็บถาวร</small></button>
              <button disabled={busy || !targetId} onClick={() => run("office-to-pdf")}><strong>Office → PDF</strong><small>Gotenberg / LibreOffice</small></button>
            </div>
          </section>

          <section className="grid two advancedGrid">
            <div className="panel toolConfig">
              <div className="panelTitle"><h2>Split & Rotate</h2><span>qpdf</span></div>
              <label>หน้าที่ต้องการแยก<input value={splitPages} onChange={(e) => setSplitPages(e.target.value)} placeholder="1-3,5,8-z" /></label>
              <button className="primary" onClick={() => run("split")} disabled={busy || !targetId}>แยก/เลือกหน้า</button>
              <div className="separator" />
              <div className="inlineFields">
                <label>หมุน<select value={rotateDegrees} onChange={(e) => setRotateDegrees(Number(e.target.value))}><option value={90}>+90°</option><option value={180}>180°</option><option value={270}>+270°</option><option value={-90}>-90°</option></select></label>
                <label>หน้า<input value={rotatePages} onChange={(e) => setRotatePages(e.target.value)} /></label>
              </div>
              <button className="secondary" onClick={() => run("rotate")} disabled={busy || !targetId}>หมุนหน้า</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>Watermark</h2><span>รองรับภาษาไทย</span></div>
              <label>ข้อความ<input value={watermarkText} onChange={(e) => setWatermarkText(e.target.value)} /></label>
              <div className="inlineFields three">
                <label>ขนาด<input type="number" min="8" max="160" value={watermarkFontSize} onChange={(e) => setWatermarkFontSize(Number(e.target.value))} /></label>
                <label>Opacity<input type="number" min="0.02" max="1" step="0.05" value={watermarkOpacity} onChange={(e) => setWatermarkOpacity(Number(e.target.value))} /></label>
                <label>องศา<input type="number" min="-180" max="180" value={watermarkRotation} onChange={(e) => setWatermarkRotation(Number(e.target.value))} /></label>
              </div>
              <label>ตำแหน่ง<select value={watermarkPosition} onChange={(e) => setWatermarkPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
              <button className="primary" onClick={() => run("watermark")} disabled={busy || !targetId || !watermarkText}>ใส่ Watermark</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>Page Number</h2><span>{"{page} {total}"}</span></div>
              <label>รูปแบบ<input value={pageFormat} onChange={(e) => setPageFormat(e.target.value)} /></label>
              <div className="inlineFields">
                <label>เริ่มที่<input type="number" min="0" value={pageStart} onChange={(e) => setPageStart(Number(e.target.value))} /></label>
                <label>ตำแหน่ง<select value={pagePosition} onChange={(e) => setPagePosition(e.target.value)}>{positionOptions.filter(([value]) => value !== "center").map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
              </div>
              <button className="primary" onClick={() => run("page-numbers")} disabled={busy || !targetId}>ใส่เลขหน้า</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>PDF Stamp</h2><span>overlay PDF หน้าแรก</span></div>
              <label>ไฟล์ตราประทับ<select value={stampId} onChange={(e) => setStampId(e.target.value)}><option value="">— เลือก PDF Stamp —</option>{files.filter((file) => file.id !== targetId).map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select></label>
              <div className="inlineFields">
                <label>ตำแหน่ง<select value={stampPosition} onChange={(e) => setStampPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                <label>สเกล<input type="number" min="0.03" max="0.8" step="0.05" value={stampScale} onChange={(e) => setStampScale(Number(e.target.value))} /></label>
              </div>
              <button className="primary" onClick={() => run("stamp")} disabled={busy || !targetId || !stampId}>ประทับ PDF</button>
            </div>
          </section>

          <section className="grid two">
            <div className="panel">
              <div className="panelTitle"><h2>ไฟล์ล่าสุด</h2><button className="ghost" onClick={loadWorkspace}>Refresh</button></div>
              <div className="list fileList">
                {files.length === 0 && <p className="muted">เชื่อมต่อหรืออัปโหลดไฟล์ก่อน</p>}
                {files.slice(0, 30).map((file) => (
                  <button className={`fileRow ${targetId === file.id ? "selected" : ""}`} key={file.id} onClick={() => setTargetId(file.id)}>
                    <div><strong>{file.original_name}</strong><small>{(file.size / 1024 / 1024).toFixed(2)} MB • {file.source_system}</small></div>
                    <code>{file.id.slice(0, 8)}</code>
                  </button>
                ))}
              </div>
            </div>

            <div className="panel">
              <div className="panelTitle"><h2>งานล่าสุด</h2><button className="ghost" onClick={refreshJobs}>Refresh</button></div>
              <div className="list">
                {jobs.length === 0 && <p className="muted">ยังไม่มีงาน</p>}
                {jobs.slice(0, 30).map((job) => (
                  <div className="jobRow" key={job.id}>
                    <div className="jobMain"><span className={`jobDot ${job.status}`} /><div><strong>{job.operation}</strong><small>{job.status} • {job.progress}%</small>{job.error && <small className="error">{job.error}</small>}</div></div>
                    {job.output_file_id ? <button className="download" onClick={() => download(job.output_file_id!)}>ดาวน์โหลด</button> : <code>{job.id.slice(0, 8)}</code>}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

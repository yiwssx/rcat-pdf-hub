"use client";

import { useMemo, useState } from "react";
import { createJob, Job, listJobs, uploadFile, UploadedFile } from "../lib/api";

export default function Home() {
  const [apiKey, setApiKey] = useState("");
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("พร้อมใช้งาน");
  const selectedIds = useMemo(() => files.map((f) => f.id), [files]);

  async function onFiles(list: FileList | null) {
    if (!list?.length || !apiKey) return;
    setBusy(true);
    setMessage("กำลังอัปโหลด...");
    try {
      const uploaded: UploadedFile[] = [];
      for (const file of Array.from(list)) uploaded.push(await uploadFile(file, apiKey));
      setFiles((old) => [...old, ...uploaded]);
      setMessage(`อัปโหลดแล้ว ${uploaded.length} ไฟล์`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "อัปโหลดไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function run(operation: string) {
    if (!apiKey || !files.length) return;
    setBusy(true);
    try {
      let job: Job;
      if (operation === "merge") {
        if (selectedIds.length < 2) throw new Error("Merge ต้องมีอย่างน้อย 2 ไฟล์");
        job = await createJob("merge", { file_ids: selectedIds }, apiKey);
      } else if (operation === "ocr") {
        job = await createJob("ocr", { file_id: selectedIds[0], languages: "tha+eng", deskew: true, rotate_pages: true }, apiKey);
      } else if (operation === "compress") {
        job = await createJob("compress", { file_id: selectedIds[0] }, apiKey);
      } else if (operation === "pdfa") {
        job = await createJob("pdfa", { file_id: selectedIds[0], languages: "tha+eng", deskew: false, rotate_pages: false }, apiKey);
      } else {
        throw new Error("Unknown operation");
      }
      setJobs((old) => [job, ...old]);
      setMessage(`ส่งงาน ${operation} แล้ว`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "ทำรายการไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function download(fileId: string) {
    if (!apiKey) return;
    try {
      const res = await fetch(`/api/v1/files/${fileId}/download`, { headers: { "X-API-Key": apiKey } });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pdfhub-${fileId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "ดาวน์โหลดไม่สำเร็จ");
    }
  }

  async function refreshJobs() {
    if (!apiKey) return;
    try {
      setJobs(await listJobs(apiKey));
      setMessage("อัปเดตสถานะแล้ว");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "อ่านสถานะไม่สำเร็จ");
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <span className="eyebrow">SELF-HOSTED • CENTRAL PDF INFRASTRUCTURE</span>
          <h1>PDF Hub</h1>
          <p>ศูนย์กลางรวม แยก บีบอัด OCR ภาษาไทย แปลง PDF/A และเชื่อมหลายระบบผ่าน API เดียว</p>
        </div>
        <div className="status">{message}</div>
      </header>

      <section className="panel auth">
        <label>API Key</label>
        <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="pdfh_... หรือ Bootstrap Admin Key" autoComplete="off" />
        <small>คีย์อยู่ในหน่วยความจำของ browser tab นี้เท่านั้น หน้าเว็บนี้ไม่บันทึกลง localStorage</small>
      </section>

      <section className="panel drop">
        <input id="files" type="file" multiple onChange={(e) => onFiles(e.target.files)} disabled={!apiKey || busy} />
        <label htmlFor="files">
          <strong>เลือกไฟล์เอกสาร</strong>
          <span>PDF สำหรับ merge/OCR/compress หรือ Office สำหรับ endpoint convert</span>
        </label>
      </section>

      <section className="tools">
        <button disabled={busy || files.length < 2} onClick={() => run("merge")}>รวม PDF</button>
        <button disabled={busy || files.length < 1} onClick={() => run("ocr")}>OCR ไทย + อังกฤษ</button>
        <button disabled={busy || files.length < 1} onClick={() => run("compress")}>บีบอัด PDF</button>
        <button disabled={busy || files.length < 1} onClick={() => run("pdfa")}>แปลง PDF/A-2</button>
      </section>

      <section className="grid">
        <div className="panel">
          <div className="panelTitle"><h2>ไฟล์ใน Session</h2><span>{files.length}</span></div>
          <div className="list">
            {files.length === 0 && <p className="muted">ยังไม่มีไฟล์</p>}
            {files.map((file) => (
              <div className="row" key={file.id}>
                <div><strong>{file.original_name}</strong><small>{(file.size / 1024 / 1024).toFixed(2)} MB</small></div>
                <code>{file.id.slice(0, 8)}</code>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panelTitle"><h2>งานล่าสุด</h2><button className="ghost" onClick={refreshJobs}>Refresh</button></div>
          <div className="list">
            {jobs.length === 0 && <p className="muted">กด Refresh เพื่อโหลดงานล่าสุด</p>}
            {jobs.map((job) => (
              <div className="row" key={job.id}>
                <div>
                  <strong>{job.operation}</strong>
                  <small>{job.status} • {job.progress}%</small>
                  {job.error && <small className="error">{job.error}</small>}
                </div>
                {job.output_file_id ? (
                  <button className="download" onClick={() => download(job.output_file_id!)}>ดาวน์โหลด</button>
                ) : <code>{job.id.slice(0, 8)}</code>}
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

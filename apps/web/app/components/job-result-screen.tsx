"use client";

import { useEffect, useState } from "react";
import { fetchDownload, FileLookupError, getFile, getJob, Job, JobLookupError, UploadedFile } from "../../lib/api";
import { TaskJourneyNav } from "./task-journey";

type ResultState = { job: Job; file: UploadedFile | null };
type Props = { jobId: string; auth: string };

function resultError(reason: unknown): string {
  if (reason instanceof JobLookupError || reason instanceof FileLookupError) {
    if (reason.status === 401) return "Session หมดอายุ กรุณาเข้าสู่ระบบใหม่";
    if (reason.status === 403) return "ไม่มีสิทธิ์เข้าถึงงานหรือไฟล์ผลลัพธ์นี้";
    if (reason.status === 404) return "ไม่พบงานหรือไฟล์ผลลัพธ์ อาจถูกลบแล้ว";
    if (reason.status === 410) return "ไฟล์ผลลัพธ์หมดอายุหรือไม่พร้อมใช้งานแล้ว";
  }
  return "ไม่สามารถโหลดข้อมูลผลลัพธ์ได้ กรุณาตรวจสอบการเชื่อมต่อและลองใหม่";
}

export function JobResultScreen({ jobId, auth }: Props) {
  const [data, setData] = useState<ResultState | null>(null);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const job = await getJob(jobId, auth);
        // A result is never exposed before authoritative job completion.
        const file = job.status === "completed" && job.output_file_id
          ? await getFile(job.output_file_id, auth)
          : null;
        if (!live) return;
        setData({ job, file });
        setError("");
      } catch (reason) {
        if (!live) return;
        setData(null);
        setError(resultError(reason));
      }
    };
    void load();
    return () => { live = false; };
  }, [jobId, auth, reload]);

  const expired = Boolean(data?.file?.expires_at && Date.parse(data.file.expires_at) <= Date.now());
  const ready = Boolean(data?.job.status === "completed" && data.file && !expired);

  async function download() {
    if (!data?.file || !ready || downloading) return;
    setDownloading(true);
    setError("");
    try {
      const blob = await fetchDownload(data.file.id, auth);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.file.original_name || `pdfhub-${data.file.id}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) {
      setError(resultError(reason));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main className="v3Main v3JobResult" aria-label="ผลลัพธ์งาน PDF">
      <section className="v3HomeTitle">
        <div><span className="v3Kicker">DOCUMENT RESULT</span><h1>ผลลัพธ์งาน PDF</h1><p>เข้าถึงผลลัพธ์ผ่าน Job ID ที่ตรวจสิทธิ์กับระบบแล้ว</p></div>
        <a className="v3TextLink" href={`/jobs/${encodeURIComponent(jobId)}`}>← สถานะงาน</a>
      </section>
      <TaskJourneyNav stage="result" kind="processing" />
      <section className="v3JobDetailCard" aria-live="polite">
        {!data && !error && <p role="status">กำลังตรวจสอบไฟล์ผลลัพธ์…</p>}
        {error && <div className="v3InfoBox" role="alert">{error}</div>}
        {data && <>
          <div className="v3SectionHead">
            <div><span className="v3Kicker">JOB</span><h2>{data.job.operation}</h2></div>
            <span className={`v3JobBadge ${data.job.status}`}>{data.job.status === "completed" ? "เสร็จสมบูรณ์" : "ยังไม่เสร็จ"}</span>
          </div>
          {data.job.status !== "completed" ? (
            <div className="v3InfoBox">งานนี้ยังไม่เสร็จหรือสิ้นสุดโดยไม่มีผลลัพธ์ <a href={`/jobs/${encodeURIComponent(jobId)}`}>กลับไปดูสถานะงาน</a></div>
          ) : !data.job.output_file_id ? (
            <div className="v3InfoBox">งานเสร็จแล้ว แต่ไม่มีไฟล์ผลลัพธ์ให้ดาวน์โหลด</div>
          ) : expired ? (
            <div className="v3InfoBox" role="status">ไฟล์ผลลัพธ์หมดอายุแล้ว กรุณาเริ่มงานใหม่หรือตรวจสอบการเก็บรักษาไฟล์</div>
          ) : data.file ? (<>
            <div className="v3TaskSummary"><strong>{data.file.original_name}</strong><small>{Math.max(1, Math.ceil(data.file.size / 1024))} KB • {data.file.content_type}</small></div>
            <div className="v3JobDetailActions">
              <button type="button" className="v3PrimaryAction" disabled={!ready || downloading} onClick={() => void download()}>
                {downloading ? "กำลังเตรียมดาวน์โหลด…" : "ดาวน์โหลดผลลัพธ์"}
              </button>
              <a className="v3TextLink" href="/files">คลังไฟล์ของฉัน</a>
            </div>
          </>) : null}
        </>}
        <button type="button" className="v3MiniButton" onClick={() => setReload((count) => count + 1)}>ตรวจสอบใหม่</button>
      </section>
    </main>
  );
}

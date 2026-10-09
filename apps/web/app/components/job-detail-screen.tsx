"use client";

import { useEffect, useState } from "react";
import { cancelJob, getJob, Job, JobLookupError, retryJob } from "../../lib/api";
import { TaskJourneyNav } from "./task-journey";

type Props = { jobId: string; auth: string };
const terminal = new Set(["completed", "failed", "cancelled"]);
const statusNames: Record<Job["status"], string> = {
  queued: "รอประมวลผล",
  running: "กำลังประมวลผล",
  completed: "ประมวลผลเสร็จแล้ว",
  failed: "ประมวลผลไม่สำเร็จ",
  cancelled: "ยกเลิกงานแล้ว",
};

function safeLookupMessage(error: unknown): string {
  if (error instanceof JobLookupError) {
    if (error.status === 401) return "Session หมดอายุ กรุณาเข้าสู่ระบบใหม่";
    if (error.status === 403) return "บัญชีนี้ไม่มีสิทธิ์ดูงานดังกล่าว";
    if (error.status === 404) return "ไม่พบงาน หรือประวัติงานถูกลบแล้ว";
    if (error.status === 410) return "ประวัติงานนี้ไม่พร้อมใช้งานแล้ว";
  }
  return "เชื่อมต่อสถานะงานไม่ได้ ตรวจสอบการเชื่อมต่อแล้วลองใหม่";
}

export function JobDetailScreen({ jobId, auth }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      try {
        const current = await getJob(jobId, auth);
        if (!live) return;
        setJob(current);
        setError("");
        if (!terminal.has(current.status)) {
          timer = setTimeout(() => { void refresh(); }, 2500);
        }
      } catch (failure) {
        if (!live) return;
        setJob(null);
        setError(safeLookupMessage(failure));
        // Authorization failures must not be retried indefinitely.
        if (!(failure instanceof JobLookupError && [401, 403, 404, 410].includes(failure.status))) {
          timer = setTimeout(() => { void refresh(); }, 5000);
        }
      }
    };
    void refresh();
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, [auth, jobId, reload]);

  async function act(action: "cancel" | "retry") {
    if (!job || busy) return;
    setBusy(true);
    try {
      const updated = action === "cancel" ? await cancelJob(job.id, auth) : await retryJob(job.id, auth);
      if (action === "retry") {
        window.location.assign(`/jobs/${encodeURIComponent(updated.id)}`);
        return;
      }
      setJob(updated);
      setReload((count) => count + 1);
    } catch {
      setError(action === "cancel"
        ? "ไม่สามารถยกเลิกงานได้ อาจเปลี่ยนสถานะไปแล้ว กรุณารีเฟรช"
        : "ไม่สามารถลองใหม่ได้ ตรวจสอบสิทธิ์และไฟล์ต้นฉบับ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="v3Main v3JobDetail" aria-label="รายละเอียดงานประมวลผล">
      <section className="v3HomeTitle">
        <div><span className="v3Kicker">JOB STATUS</span><h1>สถานะงาน PDF</h1><p>เปิดลิงก์นี้ซ้ำเพื่อดูสถานะล่าสุดจากระบบได้</p></div>
        <a className="v3TextLink" href="/">← เครื่องมือทั้งหมด</a>
      </section>
      <TaskJourneyNav stage={job?.status === "completed" ? "result" : "processing"} kind="processing" />
      <section className="v3JobDetailCard" aria-live="polite">
        {!job && !error && <p role="status">กำลังตรวจสอบงาน…</p>}
        {error && <div className="v3InfoBox" role="alert">{error}</div>}
        {job && <>
          <div className="v3SectionHead">
            <div><span className="v3Kicker">OPERATION</span><h2>{job.operation}</h2></div>
            <span className={`v3JobBadge ${job.status}`}>{statusNames[job.status]}</span>
          </div>
          <p><strong>เลขที่งาน:</strong> <code>{job.id}</code></p>
          <p><strong>ไฟล์ต้นฉบับ:</strong> {job.input_file_ids.length} รายการ</p>
          <p>{statusNames[job.status]}</p>
          {(job.status === "queued" || job.status === "running") && (
            <div className="v3JobProgress">
              <progress aria-label="ความคืบหน้างาน" max={100} value={Math.min(100, Math.max(0, job.progress))}/>
              <span>{job.progress}%</span>
              <small>ระบบจะตรวจสอบสถานะใหม่อัตโนมัติ</small>
            </div>
          )}
          {job.status === "completed" && <div className="v3InfoBox" role="status">
            ประมวลผลสำเร็จ {job.output_file_id ? "ระบบบันทึกไฟล์ผลลัพธ์แล้ว" : "ไม่มีไฟล์ผลลัพธ์จากงานนี้"}
          </div>}
          {job.status === "failed" && <div className="v3InfoBox" role="alert">
            งานนี้ไม่สำเร็จ สามารถลองส่งงานใหม่ได้หากไฟล์ต้นฉบับยังอยู่
          </div>}
          {job.status === "cancelled" && <div className="v3InfoBox">งานถูกยกเลิกแล้ว</div>}
          <div className="v3JobDetailActions">
            {(job.status === "queued" || job.status === "running") && <button type="button" className="v3SecondaryAction" disabled={busy} onClick={() => void act("cancel")}>ยกเลิกงาน</button>}
            {(job.status === "failed" || job.status === "cancelled") && <button type="button" className="v3PrimaryAction" disabled={busy} onClick={() => void act("retry")}>ลองประมวลผลใหม่</button>}
            {job.status === "completed" && job.output_file_id && <a className="v3PrimaryAction" href={`/jobs/${encodeURIComponent(job.id)}/result`}>ดูผลลัพธ์และดาวน์โหลด →</a>}
          </div>
        </>}
        <button type="button" className="v3MiniButton" onClick={() => setReload((count) => count + 1)}>รีเฟรชสถานะ</button>
      </section>
    </main>
  );
}

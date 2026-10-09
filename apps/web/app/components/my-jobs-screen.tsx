"use client";

import { useEffect, useState } from "react";
import { Job, listJobs } from "../../lib/api";

type StatusFilter = Job["status"] | "all";
const pageSize = 20;
const statusText: Record<Job["status"], string> = {
  queued: "รอประมวลผล",
  running: "กำลังประมวลผล",
  completed: "เสร็จแล้ว",
  failed: "ไม่สำเร็จ",
  cancelled: "ยกเลิกแล้ว",
};

export function MyJobsScreen({ auth }: { auth: string }) {
  const [status, setStatus] = useState<StatusFilter>("all");
  const [offset, setOffset] = useState(0);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const data = await listJobs(auth, {
          mine: true,
          limit: pageSize + 1,
          offset,
          status: status === "all" ? undefined : status,
        });
        if (!live) return;
        setJobs(data.slice(0, pageSize));
        setHasMore(data.length > pageSize);
        setError("");
        if (data.some((job) => job.status === "queued" || job.status === "running")) {
          timer = setTimeout(() => { void load(); }, 3000);
        }
      } catch {
        if (live) {
          setError("ไม่สามารถโหลดประวัติงานของบัญชีนี้ได้ กรุณาตรวจสอบการเชื่อมต่อ");
          setJobs([]);
          setHasMore(false);
        }
      } finally {
        if (live) setLoading(false);
      }
    };
    setLoading(true);
    void load();
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, [auth, status, offset, refreshKey]);

  return (
    <main className="v3Main" aria-label="งานของฉัน">
      <section className="v3HomeTitle">
        <div><span className="v3Kicker">MY JOBS</span><h1>งานของฉัน</h1><p>ติดตามงานที่กำลังทำและกลับมาดูงานเดิมได้ตลอดเวลาที่ประวัติยังอยู่</p></div>
        <a className="v3TextLink" href="/">← เครื่องมือทั้งหมด</a>
      </section>
      <section className="v3JobDetailCard v3JobsHistory">
        <div className="v3SectionHead">
          <div><span className="v3Kicker">HISTORY</span><h2>ประวัติงาน</h2></div>
          <button className="v3MiniButton" type="button" onClick={() => setRefreshKey((value) => value + 1)}>รีเฟรช</button>
        </div>
        <label className="v3Field">สถานะงาน
          <select aria-label="กรองสถานะงาน" value={status} onChange={(event) => { setStatus(event.target.value as StatusFilter); setOffset(0); }}>
            <option value="all">ทุกสถานะ</option>
            <option value="queued">รอประมวลผล</option>
            <option value="running">กำลังประมวลผล</option>
            <option value="completed">เสร็จแล้ว</option>
            <option value="failed">ไม่สำเร็จ</option>
            <option value="cancelled">ยกเลิกแล้ว</option>
          </select>
        </label>
        {loading && <p role="status">กำลังโหลดประวัติงาน…</p>}
        {error && <div className="v3InfoBox" role="alert">{error}</div>}
        {!loading && !error && jobs.length === 0 && <div className="v3EmptyMini">ไม่พบงานในสถานะนี้</div>}
        <div className="v3JobsHistoryList">
          {jobs.map((job) => (
            <article className="v3JobsHistoryRow" key={job.id}>
              <div><strong>{job.operation}</strong><small>Job {job.id}</small><small>ไฟล์ต้นฉบับ {job.input_file_ids.length} รายการ</small></div>
              <span className={`v3JobBadge ${job.status}`}>{statusText[job.status]}</span>
              <a className="v3TextLink" href={`/jobs/${encodeURIComponent(job.id)}`}>ดูสถานะ →</a>
              {job.status === "completed" && job.output_file_id &&
                <a className="v3TextLink" href={`/jobs/${encodeURIComponent(job.id)}/result`}>ผลลัพธ์</a>}
            </article>
          ))}
        </div>
        <nav className="v3LibraryPagination" aria-label="หน้าประวัติงาน">
          <button type="button" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>← ก่อนหน้า</button>
          <span>หน้า {Math.floor(offset / pageSize) + 1}</span>
          <button type="button" disabled={loading || !hasMore} onClick={() => setOffset(offset + pageSize)}>ถัดไป →</button>
        </nav>
      </section>
    </main>
  );
}

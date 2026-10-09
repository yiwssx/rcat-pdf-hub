"use client";

import { useEffect, useState } from "react";
import { AdminJobTriagePage, Job, listAdminJobTriage } from "../../lib/api";

const pageSize = 25;
type FilterStatus = Job["status"] | "all";
const labels: Record<Job["status"], string> = {
  queued: "รอประมวลผล",
  running: "กำลังประมวลผล",
  completed: "เสร็จแล้ว",
  failed: "ไม่สำเร็จ",
  cancelled: "ยกเลิกแล้ว",
};

export function AdminJobTriagePanel({ auth }: { auth: string }) {
  const [status, setStatus] = useState<FilterStatus>("all");
  const [operationDraft, setOperationDraft] = useState("");
  const [operation, setOperation] = useState("");
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [page, setPage] = useState<AdminJobTriagePage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const invalidOperation = operationDraft.length > 0 && !/^[a-z0-9-]{1,40}$/.test(operationDraft);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    setPage(null);
    void listAdminJobTriage(auth, {
      limit: pageSize,
      offset,
      status: status === "all" ? undefined : status,
      operation: operation || undefined,
    }).then((value) => {
      if (live) setPage(value);
    }).catch(() => {
      if (live) setError("ไม่สามารถอ่านรายการงานระดับผู้ดูแลได้ กรุณาตรวจสอบสิทธิ์และการบันทึก Audit");
    }).finally(() => {
      if (live) setLoading(false);
    });
    return () => { live = false; };
  }, [auth, status, operation, offset, reload]);

  function applyOperation() {
    if (invalidOperation) return;
    setOperation(operationDraft);
    setOffset(0);
  }

  return (
    <section className="v3AdminSection v3AdminJobTriage" aria-label="รายการงานสำหรับวิเคราะห์ปัญหา">
      <div className="v3SectionHead">
        <div><span className="v3Kicker">READ ONLY · AUDITED</span><h2>ตรวจสอบสถานะงาน</h2></div>
        <button type="button" className="v3MiniButton" disabled={loading} onClick={() => setReload((n) => n + 1)}>รีเฟรชรายการ</button>
      </div>
      <p>แสดงเฉพาะสถานะ ความคืบหน้า ประเภทงาน และเวลาประมวลผล ไม่แสดงชื่อผู้ใช้ เนื้อหาไฟล์ หรือข้อความข้อผิดพลาดดิบ</p>
      <div className="v3AdminTriageFilters">
        <label>สถานะงาน
          <select aria-label="กรองสถานะงานของระบบ" value={status} onChange={(event) => {
            setStatus(event.target.value as FilterStatus); setOffset(0);
          }}>
            <option value="all">ทุกสถานะ</option>
            {(["queued", "running", "completed", "failed", "cancelled"] as const).map((value) => (
              <option key={value} value={value}>{labels[value]}</option>
            ))}
          </select>
        </label>
        <form onSubmit={(event) => { event.preventDefault(); applyOperation(); }}>
          <label>ประเภทงาน
            <input aria-label="กรองประเภทงาน" value={operationDraft} maxLength={40}
              onChange={(event) => setOperationDraft(event.target.value.toLowerCase())}
              placeholder="เช่น compress, ocr" />
          </label>
          <button type="submit" disabled={invalidOperation || loading}>ใช้ตัวกรอง</button>
        </form>
      </div>
      {invalidOperation && <p role="status">ประเภทงานต้องเป็นตัวอักษรอังกฤษพิมพ์เล็ก ตัวเลข หรือขีดกลาง ไม่เกิน 40 ตัวอักษร</p>}
      {loading && <p role="status">กำลังโหลดรายการงานที่อนุญาต…</p>}
      {error && <div className="v3InfoBox" role="alert">{error}</div>}
      {!loading && !error && page?.items.length === 0 && <p>ไม่พบงานตามตัวกรองนี้</p>}
      {page && <div className="v3AdminTriageList">
        {page.items.map((job) => <article key={job.id} className="v3AdminTriageRow">
          <div><strong>{job.operation}</strong><small>Job ID: {job.id}</small>
            <small>สร้างเมื่อ {new Date(job.created_at).toLocaleString("th-TH")}</small></div>
          <span className={`v3JobBadge ${job.status}`}>{labels[job.status]}</span>
          <div><strong>{job.progress}%</strong><small>{job.failure_recorded ? "มีเหตุผิดพลาดบันทึกไว้" : "ไม่มีข้อมูลผิดพลาดที่บันทึกไว้"}</small></div>
        </article>)}
      </div>}
      <nav className="v3LibraryPagination" aria-label="หน้ารายการงานระดับผู้ดูแล">
        <button type="button" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>← ก่อนหน้า</button>
        <span>หน้า {Math.floor(offset / pageSize) + 1}</span>
        <button type="button" disabled={loading || !page?.has_more} onClick={() => setOffset(offset + pageSize)}>ถัดไป →</button>
      </nav>
      <p className="v3AdminTriageNote">การอ่านรายการนี้ถูกบันทึก Audit และไม่มีคำสั่ง Retry, Cancel หรือ Repair ในหน้านี้</p>
    </section>
  );
}

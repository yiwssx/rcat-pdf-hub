"use client";

import type { AdminStatus } from "../../lib/api";

type Issue = { id: string; title: string; detail: string; section: "jobs" | "storage" | "diagnostics" };
export function actionableAdminIssues(status: AdminStatus): Issue[] {
  const issues: Issue[] = [];
  if (!status.database_ok) issues.push({ id: "database", title: "Database ตอบสนองผิดปกติ", detail: "ตรวจการเชื่อมต่อและบันทึกเหตุการณ์ของบริการ", section: "diagnostics" });
  if (!status.redis_ok) issues.push({ id: "redis", title: "Redis / คิวงานไม่พร้อม", detail: "ตรวจการเชื่อมต่อคิวก่อนส่งงานใหม่", section: "diagnostics" });
  if (!status.storage_write_ok) issues.push({ id: "storage", title: "Storage เขียนข้อมูลไม่ได้", detail: "ตรวจสถานะพื้นที่จัดเก็บและเส้นทางข้อมูล", section: "storage" });
  if (status.queue_depth > 0 && status.workers === 0) issues.push({ id: "workers", title: "มีงานรอแต่ไม่มี Worker", detail: `มีงานรอ ${status.queue_depth} งาน ต้องตรวจ Worker และคิว`, section: "jobs" });
  const toolsDown = Object.entries(status.tools).filter(([, ready]) => !ready).map(([name]) => name);
  if (!status.gotenberg_ok) toolsDown.push("gotenberg");
  if (toolsDown.length) issues.push({ id: "tools", title: "เครื่องมือประมวลผลไม่พร้อม", detail: toolsDown.join(", "), section: "diagnostics" });
  if (status.disk.free <= 0) issues.push({ id: "disk", title: "ไม่มีพื้นที่ว่างในดิสก์", detail: "ตรวจพื้นที่จัดเก็บก่อนรับไฟล์เพิ่ม", section: "storage" });
  return issues;
}

export function AdminOverviewScreen({
  status, error, loading, onRefresh,
}: { status: AdminStatus | null; error: string; loading: boolean; onRefresh: () => void }) {
  const issues = status ? actionableAdminIssues(status) : [];
  return (
    <section className="v3AdminOverviewScreen" aria-label="ภาพรวมสถานะระบบ">
      <div className="v3SectionHead">
        <div><span className="v3Kicker">SERVICE HEALTH</span><h2>ภาพรวมการทำงาน</h2></div>
        <button type="button" className="v3MiniButton" onClick={onRefresh} disabled={loading}>ตรวจสถานะใหม่</button>
      </div>
      {loading && <p role="status">กำลังตรวจสอบข้อมูลสถานะล่าสุด…</p>}
      {error && <div role="alert" className="v3InfoBox">{error}</div>}
      {status && <>
        <div className="v3AdminOverview">
          <div className="v3AdminMetric"><span>FILES</span><strong>{status.files}</strong><small>{(status.pdfhub_bytes / 1024 ** 2).toFixed(1)} MB ใน PDF Hub</small></div>
          <div className="v3AdminMetric"><span>QUEUE</span><strong>{status.queue_depth}</strong><small>{status.workers} Worker</small></div>
          <div className="v3AdminMetric"><span>DISK FREE</span><strong>{(status.disk.free / 1024 ** 3).toFixed(1)} GB</strong><small>{status.data_dir}</small></div>
          <div className="v3AdminMetric"><span>SERVICES</span><strong>{status.database_ok && status.redis_ok ? "OK" : "WARN"}</strong><small>DB {status.database_ok ? "✓" : "×"} · Redis {status.redis_ok ? "✓" : "×"}</small></div>
        </div>
        <section className="v3AdminSection" aria-label="รายการตรวจสอบที่ควรดำเนินการ">
          <h2>สิ่งที่ควรตรวจสอบ</h2>
          {issues.length === 0 ? <p role="status">ไม่พบความผิดปกติจากข้อมูลสถานะที่ระบบตรวจสอบได้</p> : (
            <div className="v3AdminIssueList">
              {issues.map((issue) => <div className="v3AdminIssue" key={issue.id}>
                <div><strong>{issue.title}</strong><p>{issue.detail}</p></div>
                <a className="v3TextLink" href={`/admin?section=${issue.section}`}>ไปตรวจสอบ →</a>
              </div>)}
            </div>
          )}
          <p>รายการนี้เป็นการวินิจฉัยเบื้องต้นจาก Telemetry ปัจจุบัน ไม่ใช่คำสั่งซ่อมหรือการยืนยันว่าเหตุได้รับการแก้ไขแล้ว</p>
        </section>
        <div className="v3AdminQuickLinks">
          <a href="/admin?section=jobs">ดูงานและคิว →</a>
          <a href="/admin?section=storage">ดูพื้นที่จัดเก็บ →</a>
          <a href="/admin?section=diagnostics">ตรวจบริการและ Audit →</a>
          <a href="/admin?section=integrations">ตรวจการเชื่อมต่อ →</a>
        </div>
      </>}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { getAdminStorageHealth, type AdminStorageHealth } from "../../lib/api";

const issueLabels: Record<string, string> = {
  backend_mismatch: "รูปแบบ Storage ไม่ตรงกับ Metadata",
  invalid_stored_name: "ชื่อออบเจ็กต์จัดเก็บไม่ถูกต้อง",
  missing_object: "มี Metadata แต่หาไฟล์ไม่พบ",
  orphan_object: "มีออบเจ็กต์ที่ไม่มี Metadata อ้างอิง",
  size_mismatch: "ขนาดไฟล์จริงไม่ตรงกับ Metadata",
  duplicate_storage_name: "ชื่อไฟล์ซ้ำในพื้นที่จัดเก็บ",
};

export function AdminStorageHealthPanel({ auth }: { auth: string }) {
  const [snapshot, setSnapshot] = useState<AdminStorageHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function checkHealth() {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const result = await getAdminStorageHealth(auth);
      setSnapshot(result);
    } catch {
      setSnapshot(null);
      setError("ตรวจสอบ Storage ไม่สำเร็จ กรุณาตรวจสิทธิ์ผู้ดูแลและระบบ Audit แล้วลองใหม่");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Reconciliation can scan many files: it is intentionally user-triggered,
    // not background polled or performed on every Admin page load.
    setSnapshot(null);
    setError("");
  }, [auth]);

  return <section className="v3AdminSection" aria-label="ตรวจสอบความสอดคล้องของ Storage">
    <div className="v3SectionHead">
      <div><span className="v3Kicker">DRY RUN · AUDITED</span><h2>ตรวจสอบ Storage Reconciliation</h2></div>
      <button className="v3MiniButton" type="button" disabled={loading} onClick={() => void checkHealth()}>
        {loading ? "กำลังตรวจ…" : "ตรวจสอบความสอดคล้อง"}
      </button>
    </div>
    <p>ตรวจเปรียบเทียบฐานข้อมูลกับพื้นที่จัดเก็บตามคำสั่งเท่านั้น ไม่มีการซ่อม ย้าย หรือลบไฟล์ และไม่แสดงชื่อไฟล์หรือที่อยู่จัดเก็บ</p>
    {loading && <p role="status">กำลังตรวจสอบ Metadata และไฟล์จริง…</p>}
    {error && <p role="alert" className="v3InfoBox">{error}</p>}
    {snapshot && <div>
      <p role="status">{snapshot.healthy ? "ไม่พบรายการผิดปกติในขอบเขตที่ตรวจสอบ" : `พบรายการผิดปกติ ${snapshot.issue_count.toLocaleString("th-TH")} รายการ — ต้องตรวจสอบก่อนดำเนินการแก้ไข`}</p>
      <div className="v3AdminOverview">
        <div className="v3AdminMetric"><span>DATABASE</span><strong>{snapshot.database_records.toLocaleString("th-TH")}</strong><small>ไฟล์ใน Metadata</small></div>
        <div className="v3AdminMetric"><span>STORAGE</span><strong>{snapshot.storage_objects.toLocaleString("th-TH")}</strong><small>ไฟล์ในระบบจัดเก็บ ({snapshot.backend})</small></div>
        <div className="v3AdminMetric"><span>ISSUES</span><strong>{snapshot.issue_count.toLocaleString("th-TH")}</strong><small>{snapshot.dry_run ? "อ่านอย่างเดียว" : "สถานะไม่ทราบ"}</small></div>
      </div>
      {Object.keys(snapshot.category_counts).length > 0 && <ul className="v3AdminStorageCategories">
        {Object.entries(snapshot.category_counts).map(([category, count]) => <li key={category}>
          <span>{issueLabels[category] ?? "ปัญหาด้านพื้นที่จัดเก็บ"}</span><strong>{count.toLocaleString("th-TH")}</strong>
        </li>)}
      </ul>}
    </div>}
    {!snapshot && !loading && !error && <p>กด “ตรวจสอบความสอดคล้อง” เพื่อเริ่มการวิเคราะห์แบบอ่านอย่างเดียว</p>}
    <p className="v3AdminTriageNote">ผลการตรวจเป็น Snapshot ณ เวลาที่กดตรวจเท่านั้น และไม่มีคำสั่ง Repair โดยอัตโนมัติ</p>
  </section>;
}

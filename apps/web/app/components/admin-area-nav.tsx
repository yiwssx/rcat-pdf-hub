export const ADMIN_AREAS = [
  { id: "overview", label: "ภาพรวม", description: "สุขภาพและสถานะบริการ" },
  { id: "jobs", label: "งานประมวลผล", description: "คิวและสถานะงาน" },
  { id: "access", label: "สิทธิ์เข้าถึง", description: "บัญชี บทบาท และ Service Keys" },
  { id: "storage", label: "พื้นที่จัดเก็บ", description: "ความจุและการเก็บรักษา" },
  { id: "diagnostics", label: "วิเคราะห์ปัญหา", description: "สถานะเครื่องมือและ Audit" },
  { id: "integrations", label: "การเชื่อมต่อ", description: "Paperless, Webhook และระบบภายนอก" },
] as const;

export type AdminArea = (typeof ADMIN_AREAS)[number]["id"];

export function isAdminArea(value: string | undefined): value is AdminArea {
  return ADMIN_AREAS.some((area) => area.id === value);
}

export function AdminAreaNav({ active }: { active: AdminArea }) {
  return (
    <nav className="v3AdminAreaNav" aria-label="เมนูผู้ดูแลระบบ">
      {ADMIN_AREAS.map((area) => (
        <a key={area.id} href={`/admin?section=${area.id}`}
          aria-current={active === area.id ? "page" : undefined}>
          <strong>{area.label}</strong>
          <small>{area.description}</small>
        </a>
      ))}
    </nav>
  );
}

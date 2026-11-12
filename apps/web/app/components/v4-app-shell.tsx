"use client";

import Link from "next/link";

import { usePathname } from "next/navigation";
import {
  Activity, ChevronDown, Clock3, Files, FolderOpen,
  Home, LayoutGrid, LogOut, RefreshCw,
  ShieldCheck, Sparkles, Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { AuthMe, Job } from "../../lib/api";
import { BrandGlyph } from "./tool-icons";

type V4NavEntry = {
  href: string; label: string; icon: LucideIcon; adminOnly?: boolean;
};

const NAV: readonly V4NavEntry[] = [
  { href: "/", label: "ภาพรวม", icon: Home },
  { href: "/tools", label: "เครื่องมือ", icon: LayoutGrid },
  { href: "/files", label: "ไฟล์ของฉัน", icon: FolderOpen },
  { href: "/jobs", label: "งานประมวลผล", icon: Workflow },
  { href: "/admin", label: "ศูนย์ควบคุม", icon: ShieldCheck, adminOnly: true },
];

function activePath(path: string, href: string) {
  return href === "/" ? path === "/" : path === href || path.startsWith(href + "/");
}

export function V4AppShell({
  identity, message, jobs, onOpenJobs, onRefresh, onLogout,
}: {
  identity: AuthMe;
  message: string;
  jobs: Job[];
  onOpenJobs: () => void;
  onRefresh: () => void;
  onLogout: () => void;
}) {
  const pathname = usePathname();
  const activeJobs = jobs.filter(job => job.status === "queued" || job.status === "running").length;
  const links = NAV.filter(item => !item.adminOnly || identity.is_admin);
  const current = links.find(item => activePath(pathname, item.href)) ?? links[0];

  return (
    <>
      <aside className="v4Sidebar" aria-label="แถบเครื่องมือหลัก">
        <Link prefetch={false} className="v3Brand v4Brand" href="/" aria-label="RCAT PDF Hub">
          <span className="v3BrandMark"><BrandGlyph /></span>
          <span><strong>RCAT <em>PDF HUB</em></strong><small>Digital document studio</small></span>
        </Link>
        <div className="v4SidebarSectionLabel">WORKSPACE</div>
        <nav className="v4SidebarNav" aria-label="เมนูหลัก">
          {links.map(item => {
            const Icon = item.icon;
            return (
              <Link prefetch={false} key={item.href} href={item.href} aria-label={item.label} aria-current={activePath(pathname, item.href) ? "page" : undefined}
                className="v4NavLink">
                <Icon aria-hidden="true" size={19} strokeWidth={1.9} />
                <span>{item.label}</span>
                {item.href === "/jobs" && activeJobs > 0 && <span className="v4NavCount">{activeJobs}</span>}
              </Link>
            );
          })}
        </nav>
        <div className="v4SidebarBottom">
          <div className="v4SidebarHint">
            <Sparkles aria-hidden="true" size={18} />
            <div><strong>ทำงานอย่างเป็นขั้นตอน</strong><small>เลือกเครื่องมือและไฟล์ได้ตามงาน</small></div>
          </div>
          <div className="v4SidebarOrg"><span className="v4OrgMark">RC</span><span>RCAT PRIVATE WORKSPACE<small>สิทธิ์การใช้เครื่องมือตามบัญชี</small></span></div>
        </div>
      </aside>

      <header className="v4Topbar">
        <div className="v4TopbarTitle">
          <span className="v4TopbarEyebrow">RCAT / DOCUMENT WORKSPACE</span>
          <strong>{current.label}</strong>
        </div>
        <div className="v4TopbarActions">
          <span className="v3Status v4SyncStatus" role="status" title={message}>
            <span className="v4StatusDot" aria-hidden="true" />
            {message}
          </span>
          <button className="v3JobsButton v4TopButton" type="button" onClick={onOpenJobs} aria-label="งานล่าสุด">
            <Clock3 aria-hidden="true" size={18} />
            <span>งานล่าสุด</span>
            {activeJobs > 0 && <em>{activeJobs}</em>}
          </button>
          <details className="v3Account v4Account">
            <summary aria-label="เมนูบัญชี">
              <span className="v3Avatar">{(identity.display_name || identity.name || "U").slice(0, 1).toUpperCase()}</span>
              <span className="v3AccountName"><strong>{identity.display_name || identity.name}</strong><small>{identity.is_admin ? "ผู้ดูแลระบบ" : "ผู้ใช้งาน"}</small></span>
              <ChevronDown aria-hidden="true" size={14}/>
            </summary>
            <div className="v3AccountMenu">
              <div className="v3AccountMeta"><strong>{identity.display_name || identity.name}</strong><small>{identity.auth_source} · {identity.groups.join(", ") || "session"}</small></div>
              <Link prefetch={false} href="/files"><Files aria-hidden="true" size={16}/> ไฟล์ของฉัน</Link>
              <Link prefetch={false} href="/jobs"><Activity aria-hidden="true" size={16}/> ประวัติงาน</Link>
              {identity.is_admin && <Link prefetch={false} href="/admin"><ShieldCheck aria-hidden="true" size={16}/> ศูนย์ควบคุม</Link>}
              <button type="button" onClick={onRefresh}><RefreshCw aria-hidden="true" size={16}/> รีเฟรชข้อมูล</button>
              <button type="button" className="danger" onClick={onLogout}><LogOut aria-hidden="true" size={16}/> ออกจากระบบ</button>
            </div>
          </details>
        </div>
      </header>

      <nav className="v4MobileNav" aria-label="เมนูหลักบนมือถือ">
        {links.filter(item => !item.adminOnly).map(item => {
          const Icon = item.icon;
          return <Link prefetch={false} key={item.href} href={item.href} aria-current={activePath(pathname, item.href) ? "page" : undefined}>
            <Icon aria-hidden="true" size={21}/><span>{item.label}</span>
          </Link>;
        })}
      </nav>
    </>
  );
}

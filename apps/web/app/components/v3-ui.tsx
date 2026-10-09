"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { AuthMe, FileLibraryKind, FileLibraryOrder, FileLibraryPage, FileLibrarySort, Job, queryFileLibrary, UploadedFile } from "../../lib/api";
import { BrandGlyph, ToolIcon, ToolIconName } from "./tool-icons";

export type ToolDefinition = {
  id: string;
  title: string;
  description: string;
  icon: ToolIconName;
  tone: string;
  badge?: string;
};

function fileKind(file: UploadedFile) {
  if (file.content_type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf")) return "PDF";
  if (file.content_type.toLowerCase().startsWith("image/")) return "IMG";
  return "DOC";
}

function sizeLabel(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export function AppHeader({
  identity,
  message,
  jobs,
  onOpenJobs,
  onRefresh,
  onLogout,
}: {
  identity: AuthMe;
  message: string;
  jobs: Job[];
  onOpenJobs: () => void;
  onRefresh: () => void;
  onLogout: () => void;
}) {
  const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running").length;
  return (
    <header className="v3Header">
      <a className="v3Brand" href="/" aria-label="RCAT PDF Hub">
        <span className="v3BrandMark"><BrandGlyph/></span>
        <span><strong>RCAT PDF Hub</strong><small>Document Workspace</small></span>
      </a>

      <nav className="v3PrimaryNav" aria-label="เมนูหลัก">
        <a href="/">Workspace</a>
        <a href="/files">Files</a>
      </nav>

      <div className="v3HeaderActions">
        <span className="v3Status" title={message}><i/>{message}</span>
        <button className="v3JobsButton" type="button" onClick={onOpenJobs}>
          <span>◷</span>
          <strong>งานล่าสุด</strong>
          {(activeJobs > 0 || jobs.length > 0) && <em>{activeJobs || Math.min(jobs.length, 9)}</em>}
        </button>
        <details className="v3Account">
          <summary aria-label="เมนูบัญชี">
            <span className="v3Avatar">{(identity.display_name || identity.name || "U").slice(0, 1).toUpperCase()}</span>
            <span className="v3AccountName"><strong>{identity.display_name || identity.name}</strong><small>{identity.is_admin ? "ผู้ดูแลระบบ" : "ผู้ใช้งาน"}</small></span>
            <b>⌄</b>
          </summary>
          <div className="v3AccountMenu">
            <div className="v3AccountMeta"><strong>{identity.display_name || identity.name}</strong><small>{identity.auth_source} • {identity.groups.join(", ") || "session"}</small></div>
            <a href="/">Workspace</a>
            <a href="/files">ไฟล์ทั้งหมด</a>
            {identity.is_admin && <a href="/admin">Admin Console</a>}
            <button type="button" onClick={onRefresh}>รีเฟรชข้อมูล</button>
            <button type="button" className="danger" onClick={onLogout}>ออกจากระบบ</button>
          </div>
        </details>
      </div>
    </header>
  );
}

export function AdminIdentityPanel({ identity }: { identity: AuthMe }) {
  const roles = identity.roles.length ? identity.roles : ["—"];
  const scopes = identity.scopes.length ? identity.scopes : ["—"];
  const groups = identity.groups.length ? identity.groups : ["—"];

  return (
    <section className="v3EffectiveAccess" aria-labelledby="effective-access-title">
      <div className="v3SectionHead">
        <div>
          <span className="v3Kicker">EFFECTIVE ACCESS</span>
          <h2 id="effective-access-title">สิทธิ์ที่มีผลจริง</h2>
          <p>ข้อมูล identity และ authorization ที่ API ใช้ตัดสินสิทธิ์ของบัญชีนี้</p>
        </div>
      </div>
      <div className="v3EffectiveAccessGrid">
        <div className="v3EffectiveAccessItem">
          <span>IDENTITY</span>
          <strong>{identity.display_name || identity.name}</strong>
          <small>{identity.subject || identity.name}</small>
        </div>
        <div className="v3EffectiveAccessItem">
          <span>AUTH SOURCE</span>
          <strong>{identity.auth_source}</strong>
          <small>{groups.join(", ")}</small>
        </div>
        <div className="v3EffectiveAccessItem">
          <span>ROLE</span>
          <strong>{roles.join(", ")}</strong>
          <small>{identity.is_admin ? "administrator" : "human user"}</small>
        </div>
      </div>
      <div className="v3EffectiveScopes">
        <span>EFFECTIVE SCOPES</span>
        <div>{scopes.map((scope) => <code key={scope}>{scope}</code>)}</div>
      </div>
      <p className="v3EffectiveAccessNote">แสดงเฉพาะข้อมูลสิทธิ์ที่คำนวณแล้ว ไม่แสดง credential หรือข้อมูลลับของ session</p>
    </section>
  );
}

export function LoginScreen({
  enterprise,
  oidcUrl,
  returnTo = "/",
  ldapEnabled,
  ldapUser,
  ldapPassword,
  busy,
  message,
  setLdapUser,
  setLdapPassword,
  onLdap,
  onSession,
}: {
  enterprise: boolean;
  oidcUrl: string | null | undefined;
  returnTo?: string;
  ldapEnabled: boolean;
  ldapUser: string;
  ldapPassword: string;
  busy: boolean;
  message: string;
  setLdapUser: (value: string) => void;
  setLdapPassword: (value: string) => void;
  onLdap: () => void;
  onSession: () => void;
}) {
  return (
    <main className="v3LoginPage">
      <section className="v3LoginCard">
        <span className="v3BrandMark large"><BrandGlyph/></span>
        <div><span className="v3Kicker">RCAT PDF HUB</span><h1>เข้าสู่ Document Workspace</h1><p>{enterprise ? "ใช้บัญชีองค์กรของคุณเพื่อเข้าใช้งาน" : "ระบบนี้ใช้ session ภายใน ไม่ต้องกรอก API Key"}</p></div>
        {oidcUrl && <button className="v3PrimaryAction" onClick={() => { window.location.href = `${oidcUrl}?return_to=${encodeURIComponent(returnTo)}`; }}>เข้าสู่ระบบด้วย SSO</button>}
        {ldapEnabled && <div className="v3LoginFields">
          <label className="v3Field">ชื่อผู้ใช้<input value={ldapUser} onChange={(e) => setLdapUser(e.target.value)} autoComplete="username"/></label>
          <label className="v3Field">รหัสผ่าน<input type="password" value={ldapPassword} onChange={(e) => setLdapPassword(e.target.value)} autoComplete="current-password"/></label>
          <button className="v3PrimaryAction" onClick={onLdap} disabled={busy || !ldapUser || !ldapPassword}>LDAP Login</button>
        </div>}
        {!enterprise && <button className="v3PrimaryAction" onClick={onSession} disabled={busy}>{busy ? "กำลังเชื่อมต่อ…" : "เข้าใช้งาน"}</button>}
        <small className="v3LoginMessage">{message}</small>
      </section>
    </main>
  );
}

export function HomeScreen({
  files,
  tools,
  busy,
  onFiles,
  onSelectFile,
  onTool,
}: {
  files: UploadedFile[];
  tools: ToolDefinition[];
  busy: boolean;
  onFiles: (files: FileList | null) => void;
  onSelectFile: (id: string) => void;
  onTool: (tool: ToolDefinition) => void;
}) {
  return (
    <main className="v3Main" id="workspace">
      <section className="v3HomeTitle">
        <div><span className="v3Kicker">DOCUMENT WORKSPACE</span><h1>จัดการเอกสารของคุณ</h1><p>เพิ่มไฟล์ เลือกเครื่องมือ แล้วทำงานต่อในพื้นที่เดียว</p></div>
        <a className="v3TextLink" href="/files">ดูไฟล์ทั้งหมด →</a>
      </section>

      <section className="v3StartGrid">
        <div className="v3Dropzone" onDragOver={(event) => { event.preventDefault(); event.currentTarget.classList.add("isDragging"); }} onDragLeave={(event) => event.currentTarget.classList.remove("isDragging")} onDrop={(event) => { event.preventDefault(); event.currentTarget.classList.remove("isDragging"); onFiles(event.dataTransfer.files); }}>
          <input id="files" type="file" multiple disabled={busy} onChange={(e) => onFiles(e.target.files)}/>
          <label htmlFor="files">
            <span className="v3DropIcon">＋</span>
            <strong>วางไฟล์ หรือเลือกจากเครื่อง</strong>
            <p>PDF • Word • Excel • PowerPoint • รูปภาพ</p>
            <span className="v3UploadButton">เลือกไฟล์</span>
          </label>
        </div>

        <div className="v3RecentCard">
          <div className="v3SectionHead"><div><span className="v3Kicker">RECENT FILES</span><h2>ไฟล์ล่าสุด</h2></div><a href="/files">ทั้งหมด</a></div>
          <div className="v3RecentList">
            {files.length === 0 && <div className="v3EmptyMini"><span>◫</span><p>ยังไม่มีไฟล์ใน Workspace</p></div>}
            {files.slice(0, 5).map((file) => (
              <button type="button" className="v3RecentFile" key={file.id} onClick={() => onSelectFile(file.id)}>
                <span className={`v3FileBadge ${fileKind(file).toLowerCase()}`}>{fileKind(file)}</span>
                <span><strong>{file.original_name}</strong><small>{sizeLabel(file.size)} • {new Date(file.created_at).toLocaleDateString("th-TH")}</small></span>
                <b>›</b>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="v3ToolsBlock">
        <div className="v3SectionHead"><div><span className="v3Kicker">TOOLS</span><h2>เลือกงานที่ต้องการ</h2><p>สีของเครื่องมือยังคงเป็นเอกลักษณ์แบบลูกกวาด แต่โครงหน้าไม่แย่งความสนใจจากงานหลัก</p></div></div>
        <div className="v3ToolGrid">
          {tools.map((tool) => (
            <button type="button" className="v3ToolCard" data-tone={tool.tone} key={tool.id} onClick={() => onTool(tool)}>
              <span className="v3ToolCardIcon"><ToolIcon name={tool.icon}/></span>
              <span className="v3ToolCardText">{tool.badge && <em>{tool.badge}</em>}<strong>{tool.title}</strong><small>{tool.description}</small></span>
              <b>›</b>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

export function DocumentWorkspace({
  target,
  tools,
  activeTool,
  previewUrl,
  previewPage,
  busy,
  toolPanel,
  onBack,
  onTool,
  onPreview,
  onPreviewPage,
}: {
  target: UploadedFile;
  tools: ToolDefinition[];
  activeTool: string;
  previewUrl: string | null;
  previewPage: number;
  busy: boolean;
  toolPanel: React.ReactNode;
  onBack: () => void;
  onTool: (tool: ToolDefinition) => void;
  onPreview: () => void;
  onPreviewPage: (page: number) => void;
}) {
  const isPdf = fileKind(target) === "PDF";
  return (
    <main className="v3Main v3DocumentMode" id="workspace">
      <section className="v3DocumentBar" id="workspace-target">
        <button className="v3BackLink" type="button" onClick={onBack}>← กลับ</button>
        <span className={`v3FileBadge ${fileKind(target).toLowerCase()}`}>{fileKind(target)}</span>
        <div><strong>{target.original_name}</strong><small>{sizeLabel(target.size)} • {target.content_type}</small></div>
        <a className="v3TextLink" href="/files">เปลี่ยนไฟล์</a>
      </section>

      <section className="v3DocumentGrid">
        <div className="v3PreviewPane">
          <div className="v3PreviewToolbar">
            <div><span className="v3Kicker">PREVIEW</span><strong>{isPdf ? `หน้า ${previewPage}` : "ไฟล์ที่เลือก"}</strong></div>
            {isPdf && <div className="v3PreviewActions"><label>หน้า<input aria-label="หน้า Preview" type="number" min="1" value={previewPage} onChange={(e) => onPreviewPage(Math.max(1, Number(e.target.value)))}/></label><button type="button" onClick={onPreview} disabled={busy}>ดูตัวอย่าง PDF</button></div>}
          </div>
          <div className="v3PreviewStage">
            {previewUrl ? <Image src={previewUrl} alt={`Preview page ${previewPage}`} width={900} height={1200} unoptimized/> :
              <div className="v3PreviewPlaceholder">
                <span className={`v3BigFile ${fileKind(target).toLowerCase()}`}>{fileKind(target)}</span>
                <strong>{target.original_name}</strong>
                <p>{isPdf ? "กด “ดูตัวอย่าง PDF” เพื่อแสดงเอกสาร" : "เลือกเครื่องมือด้านขวาเพื่อเริ่มทำงานกับไฟล์นี้"}</p>
              </div>}
          </div>
        </div>

        <aside className="v3ActionPane">
          {activeTool ? toolPanel : <>
            <div className="v3ActionHead"><span className="v3Kicker">CHOOSE A TASK</span><h2>ทำอะไรกับไฟล์นี้?</h2><p>เลือกเครื่องมือ แล้วตั้งค่าโดยไม่ออกจาก Workspace</p></div>
            <div className="v3CompactTools">
              {tools.map((tool) => (
                <button type="button" className="v3CompactTool" data-tone={tool.tone} key={tool.id} onClick={() => onTool(tool)}>
                  <span><ToolIcon name={tool.icon}/></span><div><strong>{tool.title}</strong><small>{tool.description}</small></div><b>›</b>
                </button>
              ))}
            </div>
          </>}
        </aside>
      </section>
    </main>
  );
}

export function FilesScreen({
  auth,
  busy,
  refreshKey,
  onPageItems,
  onFiles,
  onSelectFile,
  onDownload,
  onDelete,
  onRetention,
}: {
  auth: string;
  busy: boolean;
  refreshKey: string;
  onPageItems: (files: UploadedFile[]) => void;
  onFiles: (files: FileList | null) => Promise<void>;
  onSelectFile: (file: UploadedFile) => void;
  onDownload: (id: string) => Promise<void>;
  onDelete: (ids: string[]) => Promise<void>;
  onRetention: (id: string, keep: boolean) => Promise<void>;
}) {
  const pageSize = 50;
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<FileLibraryKind>("all");
  const [sort, setSort] = useState<FileLibrarySort>("created_at");
  const [order, setOrder] = useState<FileLibraryOrder>("desc");
  const [includeExpired, setIncludeExpired] = useState(false);
  const [offset, setOffset] = useState(0);
  const [reloadToken, setReloadToken] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [page, setPage] = useState<FileLibraryPage>({
    items: [],
    total: 0,
    limit: pageSize,
    offset: 0,
    has_more: false,
  });

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void (async () => {
        setLoading(true);
        setLoadError("");
        try {
          const result = await queryFileLibrary(auth, {
            limit: pageSize,
            offset,
            q: query,
            kind,
            include_expired: includeExpired,
            sort,
            order,
          });
          if (cancelled) return;
          if (result.total > 0 && result.items.length === 0 && offset > 0) {
            setOffset(Math.max(0, offset - pageSize));
            return;
          }
          setPage(result);
          onPageItems(result.items);
          setSelected((old) => old.filter((id) => result.items.some((file) => file.id === id)));
        } catch (error) {
          if (!cancelled) {
            setLoadError(error instanceof Error ? error.message : "โหลดคลังไฟล์ไม่สำเร็จ");
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
    }, query.trim() ? 250 : 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [auth, includeExpired, kind, offset, onPageItems, order, query, refreshKey, reloadToken, sort]);

  const currentPage = page.total === 0 ? 0 : Math.floor(page.offset / page.limit) + 1;
  const totalPages = page.total === 0 ? 0 : Math.ceil(page.total / page.limit);

  function resetAnd(change: () => void) {
    setOffset(0);
    change();
  }

  async function mutate(action: () => Promise<void>) {
    await action();
    setReloadToken((value) => value + 1);
  }

  return (
    <main className="v3Main">
      <section className="v3FilesHead">
        <div><span className="v3Kicker">FILES</span><h1>ไฟล์ทั้งหมด</h1><p>{page.total} ไฟล์ใน Workspace</p></div>
        <div className="v3FilesActions">
          {selected.length > 0 && <><span>{selected.length} รายการ</span><button type="button" className="v3DangerButton" disabled={busy} onClick={() => void mutate(async () => { await onDelete(selected); setSelected([]); })}>ลบที่เลือก</button></>}
          <label className="v3InlineUpload"><input id="files" type="file" multiple disabled={busy} onChange={(event) => {
            const input = event.currentTarget;
            const list = input.files;
            void mutate(async () => {
              await onFiles(list);
              input.value = "";
              setOffset(0);
            });
          }}/>＋ เพิ่มไฟล์</label>
        </div>
      </section>

      <section className="v3LibraryToolbar" aria-label="ตัวกรองคลังไฟล์">
        <div className="v3Search"><span>⌕</span><input aria-label="ค้นหาชื่อไฟล์" value={query} onChange={(event) => resetAnd(() => setQuery(event.target.value))} placeholder="ค้นหาชื่อไฟล์…"/></div>
        <label>ประเภท
          <select aria-label="ประเภทไฟล์" value={kind} onChange={(event) => resetAnd(() => setKind(event.target.value as FileLibraryKind))}>
            <option value="all">ทั้งหมด</option>
            <option value="pdf">PDF</option>
            <option value="image">รูปภาพ</option>
            <option value="other">อื่น ๆ</option>
          </select>
        </label>
        <label>เรียงตาม
          <select aria-label="เรียงไฟล์ตาม" value={sort} onChange={(event) => resetAnd(() => setSort(event.target.value as FileLibrarySort))}>
            <option value="created_at">วันที่เพิ่ม</option>
            <option value="name">ชื่อไฟล์</option>
            <option value="size">ขนาด</option>
            <option value="expires_at">วันหมดอายุ</option>
          </select>
        </label>
        <label>ลำดับ
          <select aria-label="ลำดับการเรียง" value={order} onChange={(event) => resetAnd(() => setOrder(event.target.value as FileLibraryOrder))}>
            <option value="desc">มาก → น้อย</option>
            <option value="asc">น้อย → มาก</option>
          </select>
        </label>
        <label className="v3ExpiredToggle"><input type="checkbox" checked={includeExpired} onChange={(event) => resetAnd(() => setIncludeExpired(event.target.checked))}/> รวมไฟล์หมดอายุ</label>
      </section>

      <div className="v3LibraryStatus" role="status">
        <span>{loading ? "กำลังโหลด…" : loadError ? "โหลดข้อมูลไม่สำเร็จ" : page.total > 0 ? `แสดง ${page.offset + 1}–${page.offset + page.items.length} จาก ${page.total}` : "ไม่พบไฟล์"}</span>
        {loadError && <small>{loadError}</small>}
      </div>

      <section className="v3FileLibrary" aria-busy={loading}>
        {page.items.map((file) => <div key={file.id} className="v3LibraryRow">
          <label className="v3FileCheck" onClick={(event) => event.stopPropagation()}><input type="checkbox" checked={selected.includes(file.id)} onChange={(event) => setSelected((old) => event.target.checked ? [...old, file.id] : old.filter((id) => id !== file.id))}/></label>
          <button type="button" className="v3FileOpen" onClick={() => onSelectFile(file)}>
            <span className={`v3FileBadge ${fileKind(file).toLowerCase()}`}>{fileKind(file)}</span>
            <div><strong>{file.original_name}</strong><small>{file.content_type} • {file.expires_at ? `หมดอายุ ${new Date(file.expires_at).toLocaleString("th-TH")}` : "เก็บถาวร"}</small></div>
          </button>
          <span>{sizeLabel(file.size)}</span>
          <div className="v3FileRowActions">
            <button type="button" onClick={() => void onDownload(file.id)}>ดาวน์โหลด</button>
            <button type="button" onClick={() => void mutate(() => onRetention(file.id, Boolean(file.expires_at)))}>{file.expires_at ? "เก็บถาวร" : "ใช้ retention"}</button>
            <button type="button" className="danger" onClick={() => void mutate(() => onDelete([file.id]))}>ลบ</button>
          </div>
        </div>)}
        {!loading && page.items.length === 0 && <div className="v3LibraryEmpty"><span>◫</span><h2>ไม่พบไฟล์</h2><p>{query ? "ลองค้นหาด้วยคำอื่นหรือเปลี่ยนตัวกรอง" : "เพิ่มไฟล์เพื่อเริ่มใช้งาน"}</p></div>}
      </section>

      <nav className="v3LibraryPagination" aria-label="หน้าคลังไฟล์">
        <button type="button" disabled={loading || page.offset === 0} onClick={() => setOffset(Math.max(0, page.offset - page.limit))}>← ก่อนหน้า</button>
        <span>{page.total === 0 ? "0 รายการ" : `หน้า ${currentPage} จาก ${totalPages}`}</span>
        <button type="button" disabled={loading || !page.has_more} onClick={() => setOffset(page.offset + page.limit)}>ถัดไป →</button>
      </nav>
    </main>
  );
}

export function JobDrawer({
  open,
  jobs,
  files,
  onClose,
  onDownload,
  onCancel,
  onRetry,
  onClear,
}: {
  open: boolean;
  jobs: Job[];
  files: UploadedFile[];
  onClose: () => void;
  onDownload: (fileId: string) => void;
  onCancel: (jobId: string) => void;
  onRetry: (jobId: string) => void;
  onClear: () => void;
}) {
  if (!open) return null;
  return (
    <div className="v3DrawerLayer" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
      <aside className="v3JobDrawer" aria-label="งานล่าสุด">
        <header><div><span className="v3Kicker">RECENT JOBS</span><h2>งานล่าสุด</h2></div><div className="v3JobHeaderActions">{jobs.some((job) => ["completed", "failed", "cancelled"].includes(job.status)) && <button type="button" className="clear" onClick={onClear}>ล้างประวัติ</button>}<button type="button" onClick={onClose}>×</button></div></header>
        <div className="v3JobList">
          {jobs.length === 0 && <div className="v3DrawerEmpty"><span>◷</span><p>ยังไม่มีงานประมวลผล</p></div>}
          {jobs.map((job) => <article className="job v3JobItem" key={job.id}>
            <span className={`v3JobDot ${job.status}`}/>
            <div className="jobInfo"><strong>{job.operation}</strong><small>{job.input_file_ids.map((id) => files.find((file) => file.id === id)?.original_name || id.slice(0, 8)).join(" + ")}</small><small>{job.status === "running" ? `กำลังประมวลผล ${job.progress}%` : job.status === "completed" ? `เสร็จแล้ว${job.output_file_id ? ` • ${files.find((file) => file.id === job.output_file_id)?.original_name || "มีไฟล์ผลลัพธ์"}` : ""}` : job.status === "failed" ? "ไม่สำเร็จ" : job.status === "cancelled" ? "ยกเลิกแล้ว" : "รอประมวลผล"}</small>{job.error && <em>{job.error}</em>}</div>
            <span className={`v3JobBadge ${job.status}`}>{job.status === "cancelled" ? "ยกเลิก" : `${job.progress}%`}</span>
            <div className="v3JobActions">
              {(job.status === "queued" || job.status === "running") && <button type="button" className="danger" onClick={() => onCancel(job.id)}>ยกเลิก</button>}
              {(job.status === "failed" || job.status === "cancelled") && <button type="button" onClick={() => onRetry(job.id)}>ลองใหม่</button>}
              {job.output_file_id && <button type="button" className="downloadButton" onClick={() => onDownload(job.output_file_id!)}>ดาวน์โหลด</button>}
            </div>
          </article>)}
        </div>
      </aside>
    </div>
  );
}

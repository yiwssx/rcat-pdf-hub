"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import {
  archiveToPaperless,
  AdminStatus,
  bulkDeleteFiles,
  cancelJob,
  clearTerminalJobs,
  AuthConfig,
  AuthMe,
  createJob,
  createSignedDownload,
  deleteFile,
  fetchDownload,
  fetchPreview,
  getAdminStatus,
  getAuthConfig,
  getIntegrationStatus,
  getMe,
  IntegrationStatus,
  Job,
  ldapLogin,
  listFiles,
  listJobs,
  retryJob,
  logoutSession,
  SESSION_AUTH,
  setFileRetention,
  uploadFile,
  UploadedFile,
} from "../../lib/api";
import { createToolWorkspaceSettings } from "./tool-workspace-state";
import { findPdfTool, PDF_TOOLS } from "./tool-catalog";
import {
  AdminIdentityPanel,
  AppHeader,
  DocumentWorkspace,
  FilesScreen,
  HomeScreen,
  JobDrawer,
  LoginScreen,
  ToolDefinition,
} from "./v3-ui";

export type PdfHubView = "workspace" | "files" | "admin";

const AdminPanel = dynamic(
  () => import("./admin-panel").then((module) => module.AdminPanel),
  { loading: () => <div className="v3InfoBox" role="status">กำลังโหลดเครื่องมือผู้ดูแล…</div> },
);

const ToolWorkspace = dynamic(
  () => import("./tool-workspace").then((module) => module.ToolWorkspace),
  { loading: () => <div className="v3InfoBox" role="status">กำลังโหลดเครื่องมือ PDF…</div> },
);

const imageContentTypes = new Set(["image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"]);

const tools = PDF_TOOLS;

function isPdf(file: UploadedFile | null) {
  return Boolean(file && (file.content_type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf")));
}

export function PdfHubApp({ initialView = "workspace", initialTool, initialFileId }: { initialView?: PdfHubView; initialTool?: string; initialFileId?: string }) {
  const [auth, setAuth] = useState("");
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("พร้อมใช้งาน");
  const [targetId, setTargetId] = useState(initialFileId ?? "");
  const [activeTool, setActiveTool] = useState(initialTool ?? "");
  const [jobsOpen, setJobsOpen] = useState(false);
  const [adminStatus, setAdminStatus] = useState<AdminStatus | null>(null);
  const [ldapUser, setLdapUser] = useState("");
  const [ldapPassword, setLdapPassword] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [toolSettings, setToolSettings] = useState(createToolWorkspaceSettings);

  const routeTool = initialTool ? findPdfTool(initialTool) : undefined;
  const target = useMemo(() => files.find((file) => file.id === targetId) || null, [files, targetId]);
  const pdfFiles = useMemo(() => files.filter((file) => isPdf(file)), [files]);
  const imageFiles = useMemo(() => files.filter((file) => imageContentTypes.has(file.content_type.toLowerCase())), [files]);
  const targetIsPdf = isPdf(target);
  const activeJobs = useMemo(() => jobs.some((job) => job.status === "queued" || job.status === "running"), [jobs]);
  const enterpriseAuthEnabled = Boolean(authConfig?.oidc.enabled || authConfig?.ldap.enabled);

  function clearSignedToolResult() {
    setToolSettings((old) => (
      old.signedUrl === null && old.signedTargetId === null
        ? old
        : { ...old, signedUrl: null, signedTargetId: null }
    ));
  }

  async function loadWorkspace(authValue = auth) {
    if (!authValue) return;
    setBusy(true);
    try {
      const [fileRows, jobRows, status] = await Promise.all([
        initialView === "workspace" ? listFiles(authValue) : Promise.resolve([]),
        listJobs(authValue),
        getIntegrationStatus(authValue),
      ]);
      setFiles(fileRows);
      setJobs(jobRows);
      setIntegrations(status);
      setMessage("เชื่อมต่อ PDF Hub แล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "โหลด Workspace ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function connectSession() {
    setBusy(true);
    try {
      const me = await getMe(SESSION_AUTH);
      setIdentity(me);
      setAuth(SESSION_AUTH);
      await loadWorkspace(SESSION_AUTH);
    } catch (error) {
      setAuth("");
      setIdentity(null);
      setMessage(error instanceof Error ? error.message : "ไม่สามารถสร้าง Web Console session ได้");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const config = await getAuthConfig();
        if (!live) return;
        setAuthConfig(config);
        try {
          const me = await getMe(SESSION_AUTH);
          if (!live) return;
          setIdentity(me);
          setAuth(SESSION_AUTH);
          await loadWorkspace(SESSION_AUTH);
        } catch {
          setMessage("กรุณาเข้าสู่ระบบ");
        }
      } catch {
        if (live) setMessage("อ่านการตั้งค่า authentication ไม่สำเร็จ");
      }
    })();
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (initialView !== "admin" || !auth || !identity?.is_admin) return;
    void getAdminStatus(auth).then(setAdminStatus).catch(() => setAdminStatus(null));
  }, [initialView, auth, identity?.is_admin]);

  useEffect(() => {
    if (!auth || !activeJobs) return;
    const timer = window.setInterval(async () => {
      try {
        const jobRows = await listJobs(auth);
        setJobs(jobRows);
        if (
          initialView === "workspace"
          && !jobRows.some((job) => job.status === "queued" || job.status === "running")
        ) {
          setFiles(await listFiles(auth));
        }
      } catch {
        // A failed poll must not take the workspace down.
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [auth, activeJobs, initialView]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  async function loginLdap() {
    if (!ldapUser || !ldapPassword) return;
    setBusy(true);
    try {
      const me = await ldapLogin(ldapUser, ldapPassword);
      setIdentity(me);
      setAuth(SESSION_AUTH);
      setLdapPassword("");
      await loadWorkspace(SESSION_AUTH);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "LDAP login ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    try {
      if (auth === SESSION_AUTH) await logoutSession();
    } finally {
      setAuth("");
      setIdentity(null);
      setFiles([]);
      setJobs([]);
      setTargetId("");
      setActiveTool("");
      setJobsOpen(false);
      setMessage("ออกจากระบบแล้ว");
      window.location.href = "/";
    }
  }

  async function onFiles(list: FileList | null) {
    if (!list?.length || !auth) return;
    setBusy(true);
    setMessage("กำลังอัปโหลดและตรวจความปลอดภัย…");
    try {
      const uploaded: UploadedFile[] = [];
      for (const file of Array.from(list)) uploaded.push(await uploadFile(file, auth));
      setFiles((old) => [...uploaded, ...old.filter((item) => !uploaded.some((fresh) => fresh.id === item.id))]);
      if (uploaded[0]) {
        setTargetId(uploaded[0].id);
        setPreviewUrl(null);
        if (initialTool) setActiveTool(initialTool);
      }
      clearSignedToolResult();
      setMessage(`อัปโหลดแล้ว ${uploaded.length} ไฟล์`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "อัปโหลดไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  function selectFile(id: string) {
    setTargetId(id);
    setActiveTool(initialTool ?? "");
    setPreviewUrl(null);
    setPreviewPage(1);
    clearSignedToolResult();
  }

  function selectLibraryFile(file: UploadedFile) {
    setFiles((old) => [file, ...old.filter((item) => item.id !== file.id)]);
    selectFile(file.id);
  }

  function chooseTool(tool: ToolDefinition) {
    // Route intent is explicit and survives navigation. The optional file ID
    // comes only from a user-selected workspace file, never a fallback.
    const selectedFile = targetId ? `?file=${encodeURIComponent(targetId)}` : "";
    window.location.assign(`/tools/${encodeURIComponent(tool.id)}${selectedFile}`);
  }

  async function submit(operation: string, payload: object) {
    if (!auth) return;
    setBusy(true);
    try {
      const job = await createJob(operation, payload, auth);
      setJobs((old) => [job, ...old.filter((item) => item.id !== job.id)]);
      setActiveTool("");
      setJobsOpen(true);
      setMessage(`ส่งงาน ${operation} แล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ทำรายการไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function preview() {
    if (!auth || !targetId || !targetIsPdf) return;
    try {
      const blob = await fetchPreview(targetId, auth, previewPage, 900);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
      setMessage(`Preview หน้า ${previewPage} พร้อมแล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Preview ไม่สำเร็จ");
    }
  }

  async function download(fileId: string) {
    if (!auth) return;
    try {
      const blob = await fetchDownload(fileId, auth);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const metadata = files.find((file) => file.id === fileId);
      anchor.href = url;
      anchor.download = metadata?.original_name || `pdfhub-${fileId}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ดาวน์โหลดไม่สำเร็จ");
    }
  }

  async function createSignedLink(ttlSeconds: number): Promise<string | null> {
    if (!auth || !targetId) return null;
    setBusy(true);
    try {
      const result = await createSignedDownload(targetId, auth, ttlSeconds);
      setMessage("สร้างลิงก์ดาวน์โหลดแล้ว");
      return result.url;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "สร้างลิงก์ไม่สำเร็จ");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function deleteFiles(fileIds: string[]) {
    if (!auth || fileIds.length < 1) return;
    if (!window.confirm(`ยืนยันลบ ${fileIds.length} ไฟล์? การลบนี้ย้อนกลับไม่ได้`)) return;
    setBusy(true);
    try {
      if (fileIds.length === 1) await deleteFile(fileIds[0], auth);
      else await bulkDeleteFiles(fileIds, auth);
      setFiles((old) => old.filter((file) => !fileIds.includes(file.id)));
      if (fileIds.includes(targetId)) {
        setTargetId("");
        setActiveTool("");
        setPreviewUrl(null);
      }
      setMessage(`ลบไฟล์แล้ว ${fileIds.length} ไฟล์`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ลบไฟล์ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function updateRetention(fileId: string, keep: boolean) {
    if (!auth) return;
    setBusy(true);
    try {
      const updated = await setFileRetention(fileId, keep, auth);
      setFiles((old) => old.map((file) => file.id === updated.id ? updated : file));
      setMessage(keep ? "ตั้งไฟล์เป็นเก็บถาวรแล้ว" : "คืนไฟล์เข้าสู่ retention ปกติแล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "แก้ retention ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function clearJobHistory() {
    if (!auth) return;
    if (!window.confirm("ล้างประวัติงานที่เสร็จแล้ว/ล้มเหลว/ยกเลิกทั้งหมด? ไฟล์ผลลัพธ์จะไม่ถูกลบ")) return;
    try {
      const result = await clearTerminalJobs(auth);
      setJobs((old) => old.filter((job) => !["completed", "failed", "cancelled"].includes(job.status)));
      setMessage(`ล้างประวัติงานแล้ว ${result.deleted} รายการ`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ล้างประวัติงานไม่สำเร็จ");
    }
  }

  async function controlJob(jobId: string, action: "cancel" | "retry") {
    if (!auth) return;
    try {
      const updated = action === "cancel" ? await cancelJob(jobId, auth) : await retryJob(jobId, auth);
      setJobs((old) => [updated, ...old.filter((job) => job.id !== updated.id && (action !== "cancel" || job.id !== jobId))]);
      setMessage(action === "cancel" ? "ยกเลิกงานแล้ว" : "ส่งงานใหม่เข้าคิวแล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "จัดการงานไม่สำเร็จ");
    }
  }

  async function archive() {
    if (!auth || !targetId) return;
    setBusy(true);
    try {
      const result = await archiveToPaperless(targetId, auth);
      setActiveTool("");
      setMessage(`ส่งเข้าคลังแล้ว: ${result.external_id || result.status}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Archive ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  if (!auth || !identity) {
    return <LoginScreen
      enterprise={enterpriseAuthEnabled}
      oidcUrl={authConfig?.oidc.login_url}
      returnTo={routeTool ? `/tools/${routeTool.id}${initialFileId ? `?file=${encodeURIComponent(initialFileId)}` : ""}` : initialView === "admin" ? "/admin" : initialView === "files" ? "/files" : "/"}
      ldapEnabled={Boolean(authConfig?.ldap.enabled)}
      ldapUser={ldapUser}
      ldapPassword={ldapPassword}
      busy={busy}
      message={message}
      setLdapUser={setLdapUser}
      setLdapPassword={setLdapPassword}
      onLdap={() => void loginLdap()}
      onSession={() => void connectSession()}
    />;
  }

  const toolPanel = target ? (
    <ToolWorkspace
      tool={activeTool}
      auth={auth}
      target={target}
      pdfFiles={pdfFiles}
      imageFiles={imageFiles}
      targetIsPdf={targetIsPdf}
      busy={busy}
      integrations={integrations}
      settings={toolSettings}
      onSettingsChange={setToolSettings}
      onSubmit={submit}
      onCreateSignedLink={createSignedLink}
      onArchive={archive}
      onMessage={setMessage}
      onClose={() => routeTool ? window.location.assign("/") : setActiveTool("")}
    />
  ) : null;

  return (
    <div className="v3App">
      <AppHeader identity={identity} message={message} jobs={jobs} onOpenJobs={() => setJobsOpen(true)} onRefresh={() => void loadWorkspace()} onLogout={() => void logout()}/>

      {initialView === "admin" ? (
        <main className="v3Main v3AdminMain">
          <section className="v3HomeTitle">
            <div><span className="v3Kicker">ADMIN CONSOLE</span><h1>จัดการระบบ</h1><p>การตั้งค่าระบบถูกแยกจาก Workspace ของผู้ใช้แล้ว</p></div>
            <a className="v3TextLink" href="/">← กลับ Workspace</a>
          </section>
          {identity.is_admin ? <>
            <AdminIdentityPanel identity={identity}/>
            {adminStatus && <section className="v3AdminOverview"><div className="v3AdminMetric"><span>FILES</span><strong>{adminStatus.files}</strong><small>{(adminStatus.pdfhub_bytes / 1024 / 1024).toFixed(1)} MB ใน PDF Hub</small></div><div className="v3AdminMetric"><span>QUEUE</span><strong>{adminStatus.queue_depth}</strong><small>{adminStatus.workers} worker</small></div><div className="v3AdminMetric"><span>DISK FREE</span><strong>{(adminStatus.disk.free / 1024 / 1024 / 1024).toFixed(1)} GB</strong><small>{adminStatus.data_dir}</small></div><div className="v3AdminMetric"><span>SERVICES</span><strong>{adminStatus.database_ok && adminStatus.redis_ok ? "OK" : "WARN"}</strong><small>DB {adminStatus.database_ok ? "✓" : "×"} • Redis {adminStatus.redis_ok ? "✓" : "×"}</small></div></section>}
            {adminStatus && <section className="v3Diagnostics"><div className="v3SectionHead"><div><span className="v3Kicker">DIAGNOSTICS</span><h2>เครื่องมือประมวลผล</h2></div><button className="v3MiniButton" onClick={() => void getAdminStatus(auth).then(setAdminStatus)}>รีเฟรช</button></div><div className="v3DiagnosticGrid">{Object.entries({ ...adminStatus.tools, gotenberg: adminStatus.gotenberg_ok, storage: adminStatus.storage_write_ok }).map(([name, ok]) => <div key={name} className={ok ? "ok" : "bad"}><span>{ok ? "✓" : "×"}</span><strong>{name}</strong></div>)}</div></section>}
            {integrations && <section className="v3SystemStrip">
              <div><span>▰</span><p><strong>Storage</strong><small>{integrations.storage_backend.toUpperCase()}</small></p></div>
              <div><span>✓</span><p><strong>Malware scan</strong><small>{integrations.clamav_enabled ? "พร้อมใช้งาน" : "ไม่ได้เปิดใช้"}</small></p></div>
              <div><span>⌁</span><p><strong>Secure delivery</strong><small>Signed URL + webhook</small></p></div>
              <div><span>▣</span><p><strong>Archive</strong><small>{integrations.paperless_enabled ? "Paperless พร้อมใช้งาน" : "ไม่ได้เปิดใช้"}</small></p></div>
            </section>}
            <AdminPanel apiKey={auth}/>
          </> : <section className="v3AccessDenied"><span>🔐</span><h2>บัญชีนี้ไม่มีสิทธิ์ผู้ดูแล</h2><p>Admin Console จะแสดงเฉพาะ identity ที่ระบบกำหนดเป็นผู้ดูแลเท่านั้น</p><a href="/admin/login">เข้าสู่ระบบผู้ดูแล</a><a href="/">กลับ Workspace</a></section>}
        </main>
      ) : routeTool && !target ? (
        <main className="v3Main" id="workspace">
          <section className="v3HomeTitle">
            <div>
              <span className="v3Kicker">เลือกเครื่องมือ → เลือกไฟล์ → ตั้งค่า</span>
              <h1>{routeTool.title}</h1>
              <p>{routeTool.description} — เลือกไฟล์ที่ต้องการโดยตรง ระบบจะไม่เลือกไฟล์เดิมให้อัตโนมัติ</p>
            </div>
            <a className="v3TextLink" href="/">← เครื่องมือทั้งหมด</a>
          </section>
          <section className="v3StartGrid" aria-label="เลือกไฟล์สำหรับเครื่องมือ">
            <div className="v3Dropzone">
              <input id="files" type="file" multiple disabled={busy} onChange={(event) => void onFiles(event.target.files)}/>
              <label htmlFor="files">
                <span className="v3DropIcon">＋</span>
                <strong>อัปโหลดไฟล์สำหรับ {routeTool.title}</strong>
                <p>เลือกไฟล์จากเครื่องเพื่อเริ่มงานนี้</p>
                <span className="v3UploadButton">เลือกไฟล์</span>
              </label>
            </div>
            <div className="v3RecentCard">
              <div className="v3SectionHead">
                <div><span className="v3Kicker">MY FILES</span><h2>เลือกไฟล์ที่มีอยู่</h2></div>
                <a href="/files">ดูคลังไฟล์</a>
              </div>
              <div className="v3RecentList">
                {files.length === 0 && <p className="v3EmptyMini">ยังไม่มีไฟล์ใน Workspace</p>}
                {files.map((file) => (
                  <button className="v3RecentFile" key={file.id} type="button" onClick={() => { setTargetId(file.id); setActiveTool(routeTool.id); }}>
                    <span className="v3FileBadge">{isPdf(file) ? "PDF" : "FILE"}</span>
                    <span><strong>{file.original_name}</strong><small>{file.content_type}</small></span>
                    <b>›</b>
                  </button>
                ))}
              </div>
            </div>
          </section>
        </main>
      ) : target ? (
        <DocumentWorkspace
          target={target}
          tools={tools}
          activeTool={activeTool}
          previewUrl={previewUrl}
          previewPage={previewPage}
          busy={busy}
          toolPanel={toolPanel}
          onBack={() => { setTargetId(""); setActiveTool(initialTool ?? ""); setPreviewUrl(null); }}
          onTool={chooseTool}
          onPreview={() => void preview()}
          onPreviewPage={setPreviewPage}
        />
      ) : initialView === "files" ? (
        <FilesScreen
          auth={auth}
          busy={busy}
          refreshKey={`${activeJobs ? "active" : "idle"}:${jobs[0]?.id || ""}:${jobs[0]?.status || ""}`}
          onPageItems={setFiles}
          onFiles={onFiles}
          onSelectFile={selectLibraryFile}
          onDownload={download}
          onDelete={deleteFiles}
          onRetention={updateRetention}
        />
      ) : (
        <HomeScreen files={files} tools={tools} busy={busy} onFiles={(list) => void onFiles(list)} onSelectFile={selectFile} onTool={chooseTool}/>
      )}

      <JobDrawer open={jobsOpen} jobs={jobs} files={files} onClose={() => setJobsOpen(false)} onDownload={(fileId) => void download(fileId)} onCancel={(jobId) => void controlJob(jobId, "cancel")} onRetry={(jobId) => void controlJob(jobId, "retry")} onClear={() => void clearJobHistory()}/>
    </div>
  );
}

"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
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
  getFile,
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
import { JobDetailScreen } from "./job-detail-screen";
import { JobResultScreen } from "./job-result-screen";
import { MyJobsScreen } from "./my-jobs-screen";
import { FileDetailScreen } from "./file-detail-screen";
import { AdminAreaNav, type AdminArea } from "./admin-area-nav";
import { AdminOverviewScreen } from "./admin-overview-screen";
import { AdminJobTriagePanel } from "./admin-job-triage-panel";
import { AdminStorageHealthPanel } from "./admin-storage-health-panel";
import { findPdfTool, PDF_TOOLS } from "./tool-catalog";
import { ToolFileIntake } from "./tool-file-intake";
import { validateToolInputs, TOOL_INPUT_RULES } from "./tool-input-rules";
import { resolveTaskJourneyStage } from "./task-journey";
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

export type PdfHubView = "workspace" | "files" | "admin" | "job" | "result" | "jobs" | "file";

const AdminPanel = dynamic(
  () => import("./admin-panel").then((module) => module.AdminPanel),
  { loading: () => <div className="v3InfoBox" role="status">กำลังโหลดเครื่องมือผู้ดูแล…</div> },
);

const ToolWorkspace = dynamic(
  () => import("./tool-workspace").then((module) => module.ToolWorkspace),
  { loading: () => <div className="v3InfoBox" role="status">กำลังโหลดเครื่องมือ PDF…</div> },
);

const imageContentTypes = new Set(["image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"]);

const tools: ToolDefinition[] = [...PDF_TOOLS];

function isPdf(file: UploadedFile | null) {
  return Boolean(file && (file.content_type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf")));
}

export function PdfHubApp({ initialView = "workspace", initialTool, initialFileId, initialJobId, initialAdminArea = "overview" }: { initialView?: PdfHubView; initialTool?: string; initialFileId?: string; initialJobId?: string; initialAdminArea?: AdminArea }) {
  const [auth, setAuth] = useState("");
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("พร้อมใช้งาน");
  const [targetId, setTargetId] = useState(initialFileId ?? "");
  const [selectedInputIds, setSelectedInputIds] = useState<string[]>(initialFileId ? [initialFileId] : []);
  const [activeTool, setActiveTool] = useState(initialTool ?? "");
  const [jobsOpen, setJobsOpen] = useState(false);
  const submitInFlight = useRef(false);
  const [submitting, setSubmitting] = useState(false);
  const [lastSubmittedJobId, setLastSubmittedJobId] = useState<string | null>(null);
  const [adminStatus, setAdminStatus] = useState<AdminStatus | null>(null);
  const [adminStatusError, setAdminStatusError] = useState("");
  const [adminStatusLoading, setAdminStatusLoading] = useState(false);
  const [ldapUser, setLdapUser] = useState("");
  const [ldapPassword, setLdapPassword] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [toolSettings, setToolSettings] = useState(createToolWorkspaceSettings);

  const routeTool = initialTool ? findPdfTool(initialTool) : undefined;
  const target = useMemo(() => files.find((file) => file.id === targetId) || null, [files, targetId]);
  const reviewedFiles = selectedInputIds
    .map((id) => files.find((file) => file.id === id))
    .filter((file): file is UploadedFile => Boolean(file));
  const hasValidRouteInputs = !routeTool || (
    reviewedFiles.length === selectedInputIds.length
    && validateToolInputs(routeTool.id, reviewedFiles) === null
  );
  // A routed task may only see explicitly selected inputs. P7A.2 extends
  // this to reviewed multi-selection; do not submit unrelated library files.
  const pdfFiles = useMemo(
    () => files.filter((file) => isPdf(file) && (!initialTool || selectedInputIds.includes(file.id))),
    [files, initialTool, selectedInputIds],
  );
  const imageFiles = useMemo(() => {
    if (!initialTool) return files.filter((file) => imageContentTypes.has(file.content_type.toLowerCase()));
    // Image-to-PDF page order must follow the user's reviewed input order.
    return selectedInputIds
      .map((id) => files.find((file) => file.id === id))
      .filter((file): file is UploadedFile => Boolean(file && imageContentTypes.has(file.content_type.toLowerCase())));
  }, [files, initialTool, selectedInputIds]);
  const targetIsPdf = isPdf(target);
  const activeJobs = useMemo(() => jobs.some((job) => job.status === "queued" || job.status === "running"), [jobs]);
  const lastSubmittedJob = jobs.find((job) => job.id === lastSubmittedJobId) ?? null;
  const taskStage = resolveTaskJourneyStage(Boolean(target), submitting, lastSubmittedJob);
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
      const [fileRows, jobRows, status, requestedFile] = await Promise.all([
        initialView === "workspace" ? listFiles(authValue) : Promise.resolve([]),
        initialView === "jobs" ? listJobs(authValue, { mine: true }) : listJobs(authValue),
        getIntegrationStatus(authValue),
        // A selected file may be outside the first 2,000 library rows.
        initialView === "workspace" && initialFileId
          ? getFile(initialFileId, authValue).catch(() => null)
          : Promise.resolve(null),
      ]);
      setFiles(requestedFile
        ? [requestedFile, ...fileRows.filter((row) => row.id !== requestedFile.id)]
        : fileRows);
      setJobs(jobRows);
      setIntegrations(status);
      setMessage(initialView === "workspace" && initialFileId && !requestedFile && !fileRows.some((row) => row.id === initialFileId)
        ? "ไม่พบไฟล์ที่เลือกหรือไม่มีสิทธิ์ใช้งาน กรุณาเลือกไฟล์ใหม่"
        : "เชื่อมต่อ PDF Hub แล้ว");
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
    let live = true;
    setAdminStatusLoading(true);
    void getAdminStatus(auth).then((result) => {
      if (!live) return;
      setAdminStatus(result);
      setAdminStatusError("");
    }).catch(() => {
      if (!live) return;
      setAdminStatus(null);
      setAdminStatusError("อ่านสถานะระบบไม่ได้ กรุณาตรวจสอบการเชื่อมต่อและสิทธิ์เข้าถึง");
    }).finally(() => { if (live) setAdminStatusLoading(false); });
    return () => { live = false; };
  }, [initialView, auth, identity?.is_admin]);

  async function refreshAdminStatus() {
    if (!auth || !identity?.is_admin || adminStatusLoading) return;
    setAdminStatusLoading(true);
    try {
      setAdminStatus(await getAdminStatus(auth));
      setAdminStatusError("");
    } catch {
      setAdminStatus(null);
      setAdminStatusError("อ่านสถานะระบบไม่ได้ กรุณาตรวจสอบการเชื่อมต่อและสิทธิ์เข้าถึง");
    } finally {
      setAdminStatusLoading(false);
    }
  }

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
      setLastSubmittedJobId(null);
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
      if (initialTool) {
        // Uploads enter the same review screen as library selection.
        setSelectedInputIds(uploaded.map((file) => file.id));
        setTargetId("");
        setActiveTool(initialTool);
        setPreviewUrl(null);
      } else if (uploaded[0]) {
        if (initialView === "files") {
          window.location.assign(`/files/${encodeURIComponent(uploaded[0].id)}`);
          return;
        }
        setTargetId(uploaded[0].id);
        setPreviewUrl(null);
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
    window.location.assign(`/files/${encodeURIComponent(file.id)}`);
  }

  function confirmToolInputs(ids: string[]) {
    if (!initialTool) return;
    const chosen = ids.map((id) => files.find((file) => file.id === id));
    if (chosen.some((file) => !file)) {
      setMessage("ไฟล์ที่เลือกไม่อยู่ใน Workspace หรือไม่มีสิทธิ์เข้าถึง");
      return;
    }
    const error = validateToolInputs(initialTool, chosen as UploadedFile[]);
    if (error) {
      setMessage(error);
      return;
    }
    setSelectedInputIds(ids);
    setToolSettings((old) => ({
      ...old,
      mergeOrder: [...ids],
      stampId: initialTool === "pdf-stamp" ? ids[1] : old.stampId,
    }));
    setTargetId(ids[0]);
    setActiveTool(initialTool);
    setPreviewUrl(null);
    setMessage(`เลือกไฟล์แล้ว ${ids.length} รายการ`);
  }

  function chooseTool(tool: ToolDefinition) {
    if (routeTool?.id === tool.id) {
      setActiveTool(tool.id);
      return;
    }
    // Route intent is explicit and survives navigation. The optional file ID
    // comes only from a user-selected workspace file, never a fallback.
    const selectedFile = targetId ? `?file=${encodeURIComponent(targetId)}` : "";
    window.location.assign(`/tools/${encodeURIComponent(tool.id)}${selectedFile}`);
  }

  async function submit(operation: string, payload: object) {
    // A ref closes the gap between two synchronous clicks before React renders busy=true.
    if (!auth || submitInFlight.current) return;
    if (routeTool) {
      const args = payload as Record<string, unknown>;
      const used = [
        ...(Array.isArray(args.file_ids) ? args.file_ids : []),
        args.file_id,
        args.stamp_file_id,
      ].filter((id): id is string => typeof id === "string");
      if (!used.length || used.some((id) => !selectedInputIds.includes(id))) {
        setMessage("โปรดตรวจรายการไฟล์ก่อนส่งงาน — พบไฟล์ที่ไม่ได้เลือกไว้");
        return;
      }
    }
    submitInFlight.current = true;
    setSubmitting(true);
    setBusy(true);
    try {
      const job = await createJob(operation, payload, auth);
      setJobs((old) => [job, ...old.filter((item) => item.id !== job.id)]);
      setLastSubmittedJobId(job.id);
      setActiveTool("");
      if (routeTool) {
        window.location.assign(`/jobs/${encodeURIComponent(job.id)}`);
      } else {
        setJobsOpen(true);
      }
      setMessage(`ส่งงาน ${operation} แล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ทำรายการไม่สำเร็จ");
    } finally {
      submitInFlight.current = false;
      setSubmitting(false);
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
      returnTo={routeTool ? `/tools/${routeTool.id}${initialFileId ? `?file=${encodeURIComponent(initialFileId)}` : ""}` : (initialView === "job" || initialView === "result") && initialJobId ? `/jobs/${encodeURIComponent(initialJobId)}${initialView === "result" ? "/result" : ""}` : initialView === "admin" ? `/admin?section=${initialAdminArea}` : initialView === "files" ? "/files" : initialView === "file" && initialFileId ? `/files/${encodeURIComponent(initialFileId)}` : initialView === "jobs" ? "/jobs" : "/"}
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

      {initialView === "file" && initialFileId ? (
        <FileDetailScreen fileId={initialFileId} auth={auth} />
      ) : initialView === "jobs" ? (
        <MyJobsScreen auth={auth} />
      ) : initialView === "result" && initialJobId ? (
        <JobResultScreen jobId={initialJobId} auth={auth} />
      ) : initialView === "job" && initialJobId ? (
        <JobDetailScreen jobId={initialJobId} auth={auth} />
      ) : initialView === "admin" ? (
        <main className="v3Main v3AdminMain">
          <section className="v3HomeTitle">
            <div><span className="v3Kicker">ADMIN CONSOLE</span><h1>จัดการระบบ</h1><p>การตั้งค่าระบบถูกแยกจาก Workspace ของผู้ใช้แล้ว</p></div>
            <a className="v3TextLink" href="/">← กลับ Workspace</a>
          </section>
          {identity.is_admin ? <>
            <AdminAreaNav active={initialAdminArea} />
            {initialAdminArea === "overview" && <>
              <AdminIdentityPanel identity={identity}/>
              <AdminOverviewScreen
                status={adminStatus}
                loading={adminStatusLoading}
                error={adminStatusError}
                onRefresh={() => void refreshAdminStatus()}
              />
            </>}
            {initialAdminArea === "jobs" && <section className="v3AdminSection" aria-label="ข้อมูลคิวงานของระบบ">
              <h2>คิวและงานประมวลผล</h2>
              {adminStatus ? <>
                <div className="v3AdminOverview">
                  {(["queued", "running", "completed", "failed", "cancelled"] as const).map((status) => (
                    <div key={status} className="v3AdminMetric"><span>{status.toUpperCase()}</span><strong>{adminStatus.jobs[status] ?? 0}</strong><small>จำนวนงาน</small></div>
                  ))}
                </div>
                <p>คิวรอ {adminStatus.queue_depth} งาน · Worker {adminStatus.workers} ตัว</p>
              </> : <p role="status">กำลังโหลดข้อมูลคิวงาน…</p>}
              <AdminJobTriagePanel auth={auth} />
              <a className="v3TextLink" href="/jobs">งานของฉัน →</a>
            </section>}
            {initialAdminArea === "access" && <>
              <AdminIdentityPanel identity={identity}/>
              <AdminPanel apiKey={auth} area="access"/>
            </>}
            {initialAdminArea === "storage" && <section className="v3AdminSection" aria-label="สถานะพื้นที่จัดเก็บ">
              <h2>พื้นที่จัดเก็บและ Retention</h2>
              {adminStatus ? <>
                <div className="v3AdminOverview">
                  <div className="v3AdminMetric"><span>DISK FREE</span><strong>{(adminStatus.disk.free / 1024 ** 3).toFixed(1)} GB</strong><small>คงเหลือ</small></div>
                  <div className="v3AdminMetric"><span>PDF HUB USED</span><strong>{(adminStatus.pdfhub_bytes / 1024 ** 2).toFixed(1)} MB</strong><small>{adminStatus.files} ไฟล์</small></div>
                  <div className="v3AdminMetric"><span>RETENTION</span><strong>{adminStatus.retention_hours} ชม.</strong><small>ค่าเริ่มต้น</small></div>
                </div>
                <p>Storage backend: {adminStatus.storage_backend} · การเขียนข้อมูล: {adminStatus.storage_write_ok ? "พร้อม" : "มีปัญหา"}</p>
              </> : <p role="status">กำลังโหลดสถานะพื้นที่จัดเก็บ…</p>}
              <AdminStorageHealthPanel auth={auth} />
              <p>การตรวจความสอดคล้องเป็น Dry-run เท่านั้น ระบบยังไม่เปิดคำสั่งซ่อม ย้าย หรือลบข้อมูลข้ามบัญชีโดยอัตโนมัติ</p>
            </section>}
            {initialAdminArea === "diagnostics" && <>
              {adminStatus ? <section className="v3Diagnostics">
                <div className="v3SectionHead"><div><span className="v3Kicker">DIAGNOSTICS</span><h2>เครื่องมือประมวลผล</h2></div><button className="v3MiniButton" onClick={() => void refreshAdminStatus()}>รีเฟรช</button></div>
                <div className="v3DiagnosticGrid">{Object.entries({ ...adminStatus.tools, gotenberg: adminStatus.gotenberg_ok, storage: adminStatus.storage_write_ok }).map(([name, ok]) => <div key={name} className={ok ? "ok" : "bad"}><span>{ok ? "✓" : "×"}</span><strong>{name}</strong></div>)}</div>
              </section> : <p role="status">กำลังโหลด Diagnostic Status…</p>}
              <AdminPanel apiKey={auth} area="diagnostics"/>
            </>}
            {initialAdminArea === "integrations" && <>
              {integrations && <section className="v3SystemStrip">
                <div><span>▰</span><p><strong>Storage</strong><small>{integrations.storage_backend.toUpperCase()}</small></p></div>
                <div><span>✓</span><p><strong>Malware scan</strong><small>{integrations.clamav_enabled ? "พร้อมใช้งาน" : "ไม่ได้เปิดใช้"}</small></p></div>
                <div><span>⌁</span><p><strong>Secure delivery</strong><small>Signed URL + webhook</small></p></div>
                <div><span>▣</span><p><strong>Archive</strong><small>{integrations.paperless_enabled ? "Paperless พร้อมใช้งาน" : "ไม่ได้เปิดใช้"}</small></p></div>
              </section>}
              <AdminPanel apiKey={auth} area="integrations"/>
            </>}
          </> : <section className="v3AccessDenied"><span>🔐</span><h2>บัญชีนี้ไม่มีสิทธิ์ผู้ดูแล</h2><p>Admin Console จะแสดงเฉพาะ identity ที่ระบบกำหนดเป็นผู้ดูแลเท่านั้น</p><a href="/admin/login">เข้าสู่ระบบผู้ดูแล</a><a href="/">กลับ Workspace</a></section>}
        </main>
      ) : routeTool && (!target || !hasValidRouteInputs) ? (
        <ToolFileIntake
          tool={routeTool}
          files={files}
          selectedIds={selectedInputIds}
          busy={busy}
          onChange={setSelectedInputIds}
          onUpload={(list) => void onFiles(list)}
          onContinue={confirmToolInputs}
        />
      ) : target ? (
        <DocumentWorkspace
          target={target}
          tools={tools}
          activeTool={activeTool}
          previewUrl={previewUrl}
          previewPage={previewPage}
          busy={busy}
          toolPanel={toolPanel}
          taskJourney={routeTool ? { stage: taskStage, kind: TOOL_INPUT_RULES[routeTool.id].flow } : undefined}
          onBack={() => { setTargetId(""); setActiveTool(initialTool ?? ""); setLastSubmittedJobId(null); setPreviewUrl(null); }}
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

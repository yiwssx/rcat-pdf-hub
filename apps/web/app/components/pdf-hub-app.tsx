"use client";

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
import { AdminPanel } from "./admin-panel";
import { ToolPanel } from "./tool-panel";
import {
  AppHeader,
  DocumentWorkspace,
  FilesScreen,
  HomeScreen,
  JobDrawer,
  LoginScreen,
  ToolDefinition,
} from "./v3-ui";

export type PdfHubView = "workspace" | "files" | "admin";

const imageContentTypes = new Set(["image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"]);

const tools: ToolDefinition[] = [
  { id: "ocr", title: "สแกน / OCR", description: "อ่านข้อความไทย + อังกฤษจากเอกสาร", icon: "scan", tone: "rose", badge: "ยอดนิยม" },
  { id: "merge-pdf", title: "รวม PDF", description: "รวมหลายไฟล์เป็นเอกสารเดียว", icon: "merge", tone: "blue" },
  { id: "split-rotate", title: "จัดหน้า PDF", description: "เลือก แยก และหมุนหน้า", icon: "organize", tone: "violet" },
  { id: "compress", title: "ลดขนาด PDF", description: "บีบอัดไฟล์สำหรับส่งและจัดเก็บ", icon: "compress", tone: "amber" },
  { id: "pdf-to-images", title: "PDF → รูปภาพ", description: "ส่งออกหน้าเอกสารเป็น PNG/JPEG", icon: "image", tone: "red" },
  { id: "images-to-pdf", title: "รูปภาพ → PDF", description: "รวมรูปภาพหลายไฟล์เป็น PDF", icon: "imagePdf", tone: "cyan" },
  { id: "watermark", title: "ลายน้ำ", description: "เพิ่มข้อความลายน้ำภาษาไทย", icon: "watermark", tone: "pink" },
  { id: "page-numbers", title: "เลขหน้า", description: "ใส่เลขหน้าและกำหนดตำแหน่ง", icon: "numbers", tone: "indigo" },
  { id: "pdfa", title: "PDF/A-2", description: "แปลงเพื่อจัดเก็บระยะยาว", icon: "pdfa", tone: "green" },
  { id: "office-to-pdf", title: "Office → PDF", description: "แปลง Word, Excel และ PowerPoint", icon: "office", tone: "orange" },
  { id: "pdf-stamp", title: "ประทับ PDF", description: "วางตราประทับจาก PDF อีกไฟล์", icon: "stamp", tone: "purple" },
  { id: "signed-link", title: "ลิงก์ดาวน์โหลด", description: "สร้างลิงก์ชั่วคราวเพื่อแชร์ไฟล์", icon: "link", tone: "sky" },
  { id: "archive", title: "คลังเอกสาร", description: "ส่งเอกสารเข้า Paperless", icon: "archive", tone: "teal" },
];

function isPdf(file: UploadedFile | null) {
  return Boolean(file && (file.content_type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf")));
}

export function PdfHubApp({ initialView = "workspace" }: { initialView?: PdfHubView }) {
  const [auth, setAuth] = useState("");
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("พร้อมใช้งาน");
  const [targetId, setTargetId] = useState("");
  const [activeTool, setActiveTool] = useState("");
  const [pendingTool, setPendingTool] = useState("");
  const [jobsOpen, setJobsOpen] = useState(false);
  const [mergeOrder, setMergeOrder] = useState<string[]>([]);
  const [adminStatus, setAdminStatus] = useState<AdminStatus | null>(null);

  const [ldapUser, setLdapUser] = useState("");
  const [ldapPassword, setLdapPassword] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const [signedTtl, setSignedTtl] = useState(300);
  const [splitPages, setSplitPages] = useState("1-3");
  const [rotateDegrees, setRotateDegrees] = useState(90);
  const [rotatePages, setRotatePages] = useState("1-z");
  const [watermarkText, setWatermarkText] = useState("เอกสารภายใน");
  const [watermarkOpacity, setWatermarkOpacity] = useState(0.18);
  const [watermarkRotation, setWatermarkRotation] = useState(45);
  const [watermarkFontSize, setWatermarkFontSize] = useState(48);
  const [watermarkPosition, setWatermarkPosition] = useState("center");
  const [pageFormat, setPageFormat] = useState("หน้า {page} / {total}");
  const [pageStart, setPageStart] = useState(1);
  const [pagePosition, setPagePosition] = useState("bottom-center");
  const [stampId, setStampId] = useState("");
  const [stampPosition, setStampPosition] = useState("bottom-right");
  const [stampScale, setStampScale] = useState(0.2);
  const [imagePageSize, setImagePageSize] = useState("a4");
  const [imageFit, setImageFit] = useState("contain");
  const [imageDpi, setImageDpi] = useState(150);
  const [rasterFormat, setRasterFormat] = useState("png");
  const [rasterDpi, setRasterDpi] = useState(150);
  const [rasterFirstPage, setRasterFirstPage] = useState(1);
  const [rasterLastPage, setRasterLastPage] = useState("");

  const target = useMemo(() => files.find((file) => file.id === targetId) || null, [files, targetId]);
  const pdfFiles = useMemo(() => files.filter((file) => isPdf(file)), [files]);
  const imageFiles = useMemo(() => files.filter((file) => imageContentTypes.has(file.content_type.toLowerCase())), [files]);
  const targetIsPdf = isPdf(target);
  const activeJobs = useMemo(() => jobs.some((job) => job.status === "queued" || job.status === "running"), [jobs]);
  const enterpriseAuthEnabled = Boolean(authConfig?.oidc.enabled || authConfig?.ldap.enabled);

  async function loadWorkspace(authValue = auth) {
    if (!authValue) return;
    setBusy(true);
    try {
      const [fileRows, jobRows, status] = await Promise.all([
        listFiles(authValue),
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
    setMergeOrder((old) => {
      const available = pdfFiles.map((file) => file.id);
      const kept = old.filter((id) => available.includes(id));
      return kept.length > 0 ? kept : available;
    });
  }, [pdfFiles]);

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
        if (!jobRows.some((job) => job.status === "queued" || job.status === "running")) {
          setFiles(await listFiles(auth));
        }
      } catch {
        // A failed poll must not take the workspace down.
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [auth, activeJobs]);

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
        if (pendingTool) setActiveTool(pendingTool);
      }
      setPendingTool("");
      setSignedUrl(null);
      setMessage(`อัปโหลดแล้ว ${uploaded.length} ไฟล์`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "อัปโหลดไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  function selectFile(id: string) {
    setTargetId(id);
    setActiveTool("");
    setPreviewUrl(null);
    setPreviewPage(1);
    setSignedUrl(null);
  }

  function chooseTool(tool: ToolDefinition) {
    let candidate = target;
    const requiresPdf = !["images-to-pdf", "office-to-pdf", "signed-link"].includes(tool.id);

    if (tool.id === "merge-pdf") {
      candidate = candidate && isPdf(candidate) ? candidate : pdfFiles[0] || null;
      if (pdfFiles.length < 2) {
        setPendingTool(tool.id);
        setMessage("รวม PDF ต้องมี PDF อย่างน้อย 2 ไฟล์ — เพิ่มไฟล์ได้เลย");
        document.getElementById("files")?.click();
        return;
      }
    } else if (tool.id === "images-to-pdf") {
      candidate = candidate && imageContentTypes.has(candidate.content_type.toLowerCase()) ? candidate : imageFiles[0] || null;
      if (!candidate) {
        setPendingTool(tool.id);
        setMessage("เพิ่มรูปภาพอย่างน้อย 1 ไฟล์ก่อน");
        document.getElementById("files")?.click();
        return;
      }
    } else if (requiresPdf) {
      candidate = candidate && isPdf(candidate) ? candidate : pdfFiles[0] || null;
    } else {
      candidate = candidate || files[0] || null;
    }

    if (!candidate) {
      setPendingTool(tool.id);
      setMessage("เพิ่มหรือเลือกไฟล์ก่อนใช้เครื่องมือนี้");
      document.getElementById("files")?.click();
      return;
    }

    setTargetId(candidate.id);
    setActiveTool(tool.id);
    setPreviewUrl(null);
    setSignedUrl(null);
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

  async function run(operation: string) {
    if (!targetId && operation !== "merge" && operation !== "images-to-pdf") {
      setMessage("เลือกไฟล์ก่อน");
      return;
    }
    switch (operation) {
      case "merge":
        if (pdfFiles.length < 2) return setMessage("Merge ต้องมี PDF อย่างน้อย 2 ไฟล์");
        return submit("merge", { file_ids: mergeOrder.length ? mergeOrder : pdfFiles.map((file) => file.id) });
      case "images-to-pdf":
        if (imageFiles.length < 1) return setMessage("ต้องมีไฟล์ภาพอย่างน้อย 1 ไฟล์");
        return submit("images-to-pdf", { file_ids: imageFiles.map((file) => file.id), page_size: imagePageSize, fit: imageFit, margin: 18, dpi: imageDpi });
      case "pdf-to-images":
        if (!targetIsPdf) return setMessage("PDF → รูปภาพ ต้องเลือกไฟล์ PDF");
        return submit("pdf-to-images", { file_id: targetId, format: rasterFormat, dpi: rasterDpi, first_page: rasterFirstPage, last_page: rasterLastPage ? Number(rasterLastPage) : null });
      case "split":
        return submit("split", { file_id: targetId, pages: splitPages });
      case "rotate":
        return submit("rotate", { file_id: targetId, degrees: rotateDegrees, pages: rotatePages });
      case "ocr":
        return submit("ocr", { file_id: targetId, languages: "tha+eng", deskew: true, rotate_pages: true });
      case "compress":
        return submit("compress", { file_id: targetId });
      case "pdfa":
        return submit("pdfa", { file_id: targetId, languages: "tha+eng", deskew: false, rotate_pages: false });
      case "office-to-pdf":
        return submit("office-to-pdf", { file_id: targetId });
      case "watermark":
        return submit("watermark", { file_id: targetId, text: watermarkText, font_size: watermarkFontSize, opacity: watermarkOpacity, rotation: watermarkRotation, position: watermarkPosition, margin: 36 });
      case "page-numbers":
        return submit("page-numbers", { file_id: targetId, format: pageFormat, start_number: pageStart, font_size: 10, position: pagePosition, margin: 24 });
      case "stamp":
        if (!stampId) return setMessage("เลือกไฟล์ PDF ที่จะใช้เป็นตราประทับก่อน");
        return submit("stamp", { file_id: targetId, stamp_file_id: stampId, position: stampPosition, scale: stampScale, margin: 24 });
      default:
        setMessage("ไม่รู้จัก operation");
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

  async function makeSignedLink() {
    if (!auth || !targetId) return;
    setBusy(true);
    try {
      const result = await createSignedDownload(targetId, auth, signedTtl);
      setSignedUrl(result.url);
      setMessage("สร้างลิงก์ดาวน์โหลดแล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "สร้างลิงก์ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function copySignedLink() {
    if (!signedUrl) return;
    try {
      await navigator.clipboard.writeText(signedUrl);
      setMessage("คัดลอกลิงก์แล้ว");
    } catch {
      setMessage("คัดลอกอัตโนมัติไม่ได้");
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

  const toolPanel = target ? <ToolPanel
    tool={activeTool}
    auth={auth}
    target={target}
    pdfFiles={pdfFiles}
    imageFiles={imageFiles}
    targetIsPdf={targetIsPdf}
    busy={busy}
    integrations={integrations}
    signedUrl={signedUrl}
    signedTtl={signedTtl}
    splitPages={splitPages}
    rotateDegrees={rotateDegrees}
    rotatePages={rotatePages}
    watermarkText={watermarkText}
    watermarkOpacity={watermarkOpacity}
    watermarkRotation={watermarkRotation}
    watermarkFontSize={watermarkFontSize}
    watermarkPosition={watermarkPosition}
    pageFormat={pageFormat}
    pageStart={pageStart}
    pagePosition={pagePosition}
    stampId={stampId}
    stampPosition={stampPosition}
    stampScale={stampScale}
    imagePageSize={imagePageSize}
    imageFit={imageFit}
    imageDpi={imageDpi}
    rasterFormat={rasterFormat}
    rasterDpi={rasterDpi}
    rasterFirstPage={rasterFirstPage}
    rasterLastPage={rasterLastPage}
    mergeOrder={mergeOrder}
    setSignedTtl={setSignedTtl}
    setSplitPages={setSplitPages}
    setRotateDegrees={setRotateDegrees}
    setRotatePages={setRotatePages}
    setWatermarkText={setWatermarkText}
    setWatermarkOpacity={setWatermarkOpacity}
    setWatermarkRotation={setWatermarkRotation}
    setWatermarkFontSize={setWatermarkFontSize}
    setWatermarkPosition={setWatermarkPosition}
    setPageFormat={setPageFormat}
    setPageStart={setPageStart}
    setPagePosition={setPagePosition}
    setStampId={setStampId}
    setStampPosition={setStampPosition}
    setStampScale={setStampScale}
    setImagePageSize={setImagePageSize}
    setImageFit={setImageFit}
    setImageDpi={setImageDpi}
    setRasterFormat={setRasterFormat}
    setRasterDpi={setRasterDpi}
    setRasterFirstPage={setRasterFirstPage}
    setRasterLastPage={setRasterLastPage}
    setMergeOrder={setMergeOrder}
    onRun={(operation) => void run(operation)}
    onSignedLink={() => void makeSignedLink()}
    onCopySignedLink={() => void copySignedLink()}
    onArchive={() => void archive()}
    onOrganize={(pages) => void submit("organize", { file_id: targetId, pages })}
    onClose={() => setActiveTool("")}
  /> : null;

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
      ) : target ? (
        <DocumentWorkspace
          target={target}
          tools={tools}
          activeTool={activeTool}
          previewUrl={previewUrl}
          previewPage={previewPage}
          busy={busy}
          toolPanel={toolPanel}
          onBack={() => { setTargetId(""); setActiveTool(""); setPreviewUrl(null); }}
          onTool={chooseTool}
          onPreview={() => void preview()}
          onPreviewPage={setPreviewPage}
        />
      ) : initialView === "files" ? (
        <FilesScreen files={files} busy={busy} onFiles={(list) => void onFiles(list)} onSelectFile={selectFile} onDownload={(id) => void download(id)} onDelete={(ids) => void deleteFiles(ids)} onRetention={(id, keep) => void updateRetention(id, keep)}/>
      ) : (
        <HomeScreen files={files} tools={tools} busy={busy} onFiles={(list) => void onFiles(list)} onSelectFile={selectFile} onTool={chooseTool}/>
      )}

      <JobDrawer open={jobsOpen} jobs={jobs} files={files} onClose={() => setJobsOpen(false)} onDownload={(fileId) => void download(fileId)} onCancel={(jobId) => void controlJob(jobId, "cancel")} onRetry={(jobId) => void controlJob(jobId, "retry")} onClear={() => void clearJobHistory()}/>
    </div>
  );
}

"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  archiveToPaperless,
  AuthConfig,
  AuthMe,
  createJob,
  createSignedDownload,
  fetchDownload,
  fetchPreview,
  getAuthConfig,
  getIntegrationStatus,
  getMe,
  IntegrationStatus,
  Job,
  ldapLogin,
  listFiles,
  listJobs,
  logoutSession,
  SESSION_AUTH,
  uploadFile,
  UploadedFile,
} from "../../lib/api";
import { AdminPanel } from "./admin-panel";

type Tab = "tools" | "admin";

const positionOptions = [
  ["center", "กลาง"],
  ["top-left", "บนซ้าย"], ["top-center", "บนกลาง"], ["top-right", "บนขวา"],
  ["bottom-left", "ล่างซ้าย"], ["bottom-center", "ล่างกลาง"], ["bottom-right", "ล่างขวา"],
] as const;

const imageContentTypes = new Set(["image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"]);

export function PdfHubConsole() {
  const [tab, setTab] = useState<Tab>("tools");
  const [auth, setAuth] = useState("");
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null);
  const [ldapUser, setLdapUser] = useState("");
  const [ldapPassword, setLdapPassword] = useState("");

  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("พร้อมใช้งาน");
  const [targetId, setTargetId] = useState("");
  const [stampId, setStampId] = useState("");
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
  const imageFiles = useMemo(() => files.filter((file) => imageContentTypes.has(file.content_type.toLowerCase())), [files]);
  const pdfFiles = useMemo(() => files.filter((file) => file.content_type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf")), [files]);
  const activeJobs = useMemo(() => jobs.some((job) => job.status === "queued" || job.status === "running"), [jobs]);
  const authenticated = Boolean(auth);
  const targetIsPdf = Boolean(target && (target.content_type === "application/pdf" || target.original_name.toLowerCase().endsWith(".pdf")));

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
      if (!targetId && fileRows[0]) setTargetId(fileRows[0].id);
      setMessage("เชื่อมต่อ PDF Hub แล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "โหลด workspace ไม่สำเร็จ");
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
          // No SSO/LDAP cookie yet; service API key login remains available.
        }
      } catch {
        if (live) setMessage("อ่านการตั้งค่า authentication ไม่สำเร็จ");
      }
    })();
    return () => { live = false; };
    // Initial session discovery must run only once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!auth || !activeJobs) return;
    const timer = window.setInterval(async () => {
      try {
        const jobRows = await listJobs(auth);
        setJobs(jobRows);
        if (!jobRows.some((job) => job.status === "queued" || job.status === "running")) {
          const fileRows = await listFiles(auth);
          setFiles(fileRows);
          if (!targetId && fileRows[0]) setTargetId(fileRows[0].id);
        }
      } catch {
        // Keep the console usable if one background poll fails.
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [auth, activeJobs, targetId]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  async function connectApiKey() {
    const value = apiKeyDraft.trim();
    if (!value) return;
    setAuth(value);
    setIdentity(null);
    await loadWorkspace(value);
  }

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
      setIntegrations(null);
      setTargetId("");
      setSignedUrl(null);
      setMessage("ออกจากระบบแล้ว");
    }
  }

  async function onFiles(list: FileList | null) {
    if (!list?.length || !auth) return;
    setBusy(true);
    setMessage("กำลังอัปโหลดและตรวจความปลอดภัย...");
    try {
      const uploaded: UploadedFile[] = [];
      for (const file of Array.from(list)) uploaded.push(await uploadFile(file, auth));
      setFiles((old) => [...uploaded, ...old.filter((item) => !uploaded.some((fresh) => fresh.id === item.id))]);
      if (uploaded[0]) setTargetId(uploaded[0].id);
      setSignedUrl(null);
      setMessage(`อัปโหลดแล้ว ${uploaded.length} ไฟล์`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "อัปโหลดไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function submit(operation: string, payload: object) {
    if (!auth) return;
    setBusy(true);
    try {
      const job = await createJob(operation, payload, auth);
      setJobs((old) => [job, ...old]);
      setMessage(`ส่งงาน ${operation} แล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ทำรายการไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function run(operation: string) {
    if (!targetId && operation !== "merge" && operation !== "images-to-pdf") return setMessage("เลือกไฟล์เป้าหมายก่อน");
    switch (operation) {
      case "merge":
        if (pdfFiles.length < 2) return setMessage("Merge ต้องมี PDF อย่างน้อย 2 ไฟล์");
        return submit("merge", { file_ids: pdfFiles.map((file) => file.id) });
      case "images-to-pdf":
        if (imageFiles.length < 1) return setMessage("ต้องมีไฟล์ภาพอย่างน้อย 1 ไฟล์");
        return submit("images-to-pdf", {
          file_ids: imageFiles.map((file) => file.id),
          page_size: imagePageSize,
          fit: imageFit,
          margin: 18,
          dpi: imageDpi,
        });
      case "pdf-to-images":
        if (!targetIsPdf) return setMessage("PDF → Images ต้องเลือกไฟล์ PDF");
        return submit("pdf-to-images", {
          file_id: targetId,
          format: rasterFormat,
          dpi: rasterDpi,
          first_page: rasterFirstPage,
          last_page: rasterLastPage ? Number(rasterLastPage) : null,
        });
      case "split": return submit("split", { file_id: targetId, pages: splitPages });
      case "rotate": return submit("rotate", { file_id: targetId, degrees: rotateDegrees, pages: rotatePages });
      case "ocr": return submit("ocr", { file_id: targetId, languages: "tha+eng", deskew: true, rotate_pages: true });
      case "compress": return submit("compress", { file_id: targetId });
      case "pdfa": return submit("pdfa", { file_id: targetId, languages: "tha+eng", deskew: false, rotate_pages: false });
      case "office-to-pdf": return submit("office-to-pdf", { file_id: targetId });
      case "watermark": return submit("watermark", {
        file_id: targetId, text: watermarkText, font_size: watermarkFontSize,
        opacity: watermarkOpacity, rotation: watermarkRotation, position: watermarkPosition, margin: 36,
      });
      case "page-numbers": return submit("page-numbers", {
        file_id: targetId, format: pageFormat, start_number: pageStart,
        font_size: 10, position: pagePosition, margin: 24,
      });
      case "stamp":
        if (!stampId) return setMessage("เลือกไฟล์ PDF ที่จะใช้เป็นตราประทับก่อน");
        return submit("stamp", { file_id: targetId, stamp_file_id: stampId, position: stampPosition, scale: stampScale, margin: 24 });
      default: return setMessage("Unknown operation");
    }
  }

  async function preview() {
    if (!auth || !targetId) return;
    if (!targetIsPdf) return setMessage("Preview รองรับ PDF เท่านั้น");
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
      setMessage(`สร้าง signed URL ถึง ${new Date(result.expires_at).toLocaleTimeString("th-TH")} แล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "สร้าง signed URL ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function copySignedLink() {
    if (!signedUrl) return;
    try {
      await navigator.clipboard.writeText(signedUrl);
      setMessage("คัดลอก signed URL แล้ว");
    } catch {
      setMessage("เบราว์เซอร์ไม่อนุญาต clipboard — คัดลอกจากลิงก์ที่แสดงได้โดยตรง");
    }
  }

  async function archive() {
    if (!auth || !targetId) return;
    setBusy(true);
    try {
      const result = await archiveToPaperless(targetId, auth);
      setMessage(`ส่งเข้า Paperless แล้ว: ${result.external_id || result.status}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Archive ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <span className="eyebrow">RCAT • SELF-HOSTED • ENTERPRISE PDF INFRASTRUCTURE</span>
          <h1>PDF Hub</h1>
          <p>PDF + Image processing, OCR ไทย, secure delivery, SSO/LDAP, malware scanning, S3/NAS, observability และ document archive จากศูนย์กลางเดียว</p>
        </div>
        <div className="status"><span className="statusDot" />{message}</div>
      </header>

      <nav className="tabs" aria-label="PDF Hub sections">
        <button className={tab === "tools" ? "active" : ""} onClick={() => setTab("tools")}>PDF Console</button>
        <button className={tab === "admin" ? "active" : ""} onClick={() => setTab("admin")}>Admin</button>
      </nav>

      <section className="panel auth">
        {auth === SESSION_AUTH && identity ? (
          <>
            <div><strong>{identity.display_name || identity.name}</strong><small>{identity.auth_source} • {identity.groups.join(", ") || "authenticated"}</small></div>
            <button className="secondary" onClick={() => void loadWorkspace()} disabled={busy}>รีเฟรช</button>
            <button className="ghost" onClick={logout}>ออกจากระบบ</button>
          </>
        ) : (
          <>
            <label>Service API Key</label>
            <input type="password" value={apiKeyDraft} onChange={(e) => setApiKeyDraft(e.target.value)} placeholder="pdfh_... หรือ Bootstrap Admin Key" autoComplete="off" />
            <button className="secondary" onClick={connectApiKey} disabled={!apiKeyDraft || busy}>เชื่อมต่อ</button>
            {authConfig?.oidc.enabled && authConfig.oidc.login_url && (
              <button className="primary" onClick={() => { window.location.href = `${authConfig.oidc.login_url}?return_to=/`; }}>SSO Login</button>
            )}
          </>
        )}
        {authConfig?.ldap.enabled && auth !== SESSION_AUTH && (
          <div className="inlineFields three">
            <label>LDAP user<input value={ldapUser} onChange={(e) => setLdapUser(e.target.value)} autoComplete="username" /></label>
            <label>LDAP password<input type="password" value={ldapPassword} onChange={(e) => setLdapPassword(e.target.value)} autoComplete="current-password" /></label>
            <button className="secondary" onClick={loginLdap} disabled={!ldapUser || !ldapPassword || busy}>LDAP Login</button>
          </div>
        )}
        <small>API key อยู่เฉพาะใน memory ของ tab; SSO/LDAP ใช้ HttpOnly session cookie</small>
      </section>

      {authenticated && integrations && (
        <section className="panel">
          <div className="panelTitle"><h2>Platform</h2><span>Phase 4</span></div>
          <div className="tools">
            <div><strong>Storage</strong><small>{integrations.storage_backend.toUpperCase()}</small></div>
            <div><strong>Malware scan</strong><small>{integrations.clamav_enabled ? "ClamAV enabled" : "disabled"}</small></div>
            <div><strong>Secure delivery</strong><small>Signed URL + durable webhook</small></div>
            <div><strong>Archive</strong><small>{integrations.paperless_enabled ? "Paperless enabled" : "disabled"}</small></div>
          </div>
        </section>
      )}

      {tab === "admin" ? <AdminPanel apiKey={auth} /> : authenticated ? (
        <>
          <section className="workspaceGrid">
            <div className="panel drop">
              <input id="files" type="file" multiple onChange={(e) => void onFiles(e.target.files)} disabled={busy} />
              <label htmlFor="files"><span className="dropIcon">＋</span><strong>เพิ่มไฟล์เข้า Workspace</strong><span>PDF, รูปภาพ และเอกสาร Office/LibreOffice</span></label>
            </div>
            <div className="panel targetPanel">
              <div className="panelTitle"><h2>ไฟล์เป้าหมาย</h2><span>{files.length} files</span></div>
              <select value={targetId} onChange={(e) => { setTargetId(e.target.value); setPreviewUrl(null); setSignedUrl(null); }}>
                <option value="">— เลือกไฟล์ —</option>
                {files.map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}
              </select>
              {target && <div className="fileMeta"><strong>{target.original_name}</strong><span>{(target.size / 1024 / 1024).toFixed(2)} MB • {target.content_type}</span><code>{target.id}</code></div>}
              <div className="previewControls"><label>หน้า<input type="number" min="1" value={previewPage} onChange={(e) => setPreviewPage(Math.max(1, Number(e.target.value)))} /></label><button className="secondary" onClick={preview} disabled={!targetId || !targetIsPdf}>Preview PDF</button></div>
              <div className="inlineFields"><label>Signed URL TTL (sec)<input type="number" min="30" max="3600" value={signedTtl} onChange={(e) => setSignedTtl(Math.max(30, Number(e.target.value)))} /></label><button className="secondary" onClick={makeSignedLink} disabled={!targetId || busy}>สร้าง Signed URL</button></div>
              {signedUrl && <div className="secretBox"><strong>Short-lived download URL</strong><code>{signedUrl}</code><div className="rowActions"><a className="ghost" href={signedUrl} target="_blank" rel="noreferrer">เปิด</a><button className="ghost" onClick={copySignedLink}>คัดลอก</button></div></div>}
            </div>
          </section>

          {previewUrl && <section className="panel previewPanel"><div className="panelTitle"><h2>Preview</h2><button className="ghost" onClick={() => setPreviewUrl(null)}>ปิด</button></div><div className="previewCanvas"><Image src={previewUrl} alt={`Preview page ${previewPage}`} width={900} height={1200} unoptimized /></div></section>}

          <section className="panel">
            <div className="panelTitle"><h2>Quick Tools</h2><span>Async queue</span></div>
            <div className="tools">
              <button disabled={busy || pdfFiles.length < 2} onClick={() => void run("merge")}><strong>รวม PDF</strong><small>รวม PDF ทั้ง workspace</small></button>
              <button disabled={busy || imageFiles.length < 1} onClick={() => void run("images-to-pdf")}><strong>Images → PDF</strong><small>{imageFiles.length} images • batch</small></button>
              <button disabled={busy || !targetIsPdf} onClick={() => void run("pdf-to-images")}><strong>PDF → Images</strong><small>PNG/JPEG ZIP</small></button>
              <button disabled={busy || !targetIsPdf} onClick={() => void run("ocr")}><strong>OCR ไทย + อังกฤษ</strong><small>Tesseract tha+eng</small></button>
              <button disabled={busy || !targetIsPdf} onClick={() => void run("compress")}><strong>บีบอัด PDF</strong><small>Ghostscript</small></button>
              <button disabled={busy || !targetIsPdf} onClick={() => void run("pdfa")}><strong>PDF/A-2</strong><small>เอกสารเก็บถาวร</small></button>
              <button disabled={busy || !targetId} onClick={() => void run("office-to-pdf")}><strong>Office → PDF</strong><small>Gotenberg / LibreOffice</small></button>
              {integrations?.paperless_enabled && <button disabled={busy || !targetIsPdf} onClick={archive}><strong>Archive</strong><small>ส่งเข้า Paperless-ngx</small></button>}
            </div>
          </section>

          <section className="grid two advancedGrid">
            <div className="panel toolConfig">
              <div className="panelTitle"><h2>Image → PDF</h2><span>Pillow + ReportLab</span></div>
              <div className="inlineFields three">
                <label>Page<select value={imagePageSize} onChange={(e) => setImagePageSize(e.target.value)}><option value="auto">Auto</option><option value="a4">A4</option><option value="letter">Letter</option></select></label>
                <label>Fit<select value={imageFit} onChange={(e) => setImageFit(e.target.value)}><option value="contain">Contain</option><option value="cover">Cover</option></select></label>
                <label>DPI<input type="number" min="72" max="600" value={imageDpi} onChange={(e) => setImageDpi(Number(e.target.value))} /></label>
              </div>
              <small>{imageFiles.length} image files ใน workspace จะถูกเรียงตามรายการไฟล์</small>
              <button className="primary" onClick={() => void run("images-to-pdf")} disabled={busy || imageFiles.length < 1}>สร้าง PDF จากภาพ</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>PDF → Images</h2><span>Poppler ZIP</span></div>
              <div className="inlineFields three">
                <label>Format<select value={rasterFormat} onChange={(e) => setRasterFormat(e.target.value)}><option value="png">PNG</option><option value="jpeg">JPEG</option></select></label>
                <label>DPI<input type="number" min="72" max="600" value={rasterDpi} onChange={(e) => setRasterDpi(Number(e.target.value))} /></label>
                <label>หน้าแรก<input type="number" min="1" value={rasterFirstPage} onChange={(e) => setRasterFirstPage(Math.max(1, Number(e.target.value)))} /></label>
              </div>
              <label>หน้าสุดท้าย (เว้นว่าง = ต่อจากหน้าแรกได้สูงสุด 200 หน้า/งาน)<input type="number" min={rasterFirstPage} value={rasterLastPage} onChange={(e) => setRasterLastPage(e.target.value)} /></label>
              <button className="primary" onClick={() => void run("pdf-to-images")} disabled={busy || !targetIsPdf}>แปลง PDF เป็น ZIP รูปภาพ</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>Split & Rotate</h2><span>qpdf</span></div>
              <label>หน้าที่ต้องการแยก<input value={splitPages} onChange={(e) => setSplitPages(e.target.value)} /></label>
              <button className="primary" onClick={() => void run("split")} disabled={busy || !targetIsPdf}>แยก/เลือกหน้า</button>
              <div className="separator" />
              <div className="inlineFields"><label>หมุน<select value={rotateDegrees} onChange={(e) => setRotateDegrees(Number(e.target.value))}><option value={90}>+90°</option><option value={180}>180°</option><option value={270}>+270°</option><option value={-90}>-90°</option></select></label><label>หน้า<input value={rotatePages} onChange={(e) => setRotatePages(e.target.value)} /></label></div>
              <button className="secondary" onClick={() => void run("rotate")} disabled={busy || !targetIsPdf}>หมุนหน้า</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>Watermark</h2><span>รองรับภาษาไทย</span></div>
              <label>ข้อความ<input value={watermarkText} onChange={(e) => setWatermarkText(e.target.value)} /></label>
              <div className="inlineFields three"><label>ขนาด<input type="number" value={watermarkFontSize} onChange={(e) => setWatermarkFontSize(Number(e.target.value))} /></label><label>Opacity<input type="number" min="0.02" max="1" step="0.01" value={watermarkOpacity} onChange={(e) => setWatermarkOpacity(Number(e.target.value))} /></label><label>หมุน<input type="number" value={watermarkRotation} onChange={(e) => setWatermarkRotation(Number(e.target.value))} /></label></div>
              <label>ตำแหน่ง<select value={watermarkPosition} onChange={(e) => setWatermarkPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
              <button className="primary" onClick={() => void run("watermark")} disabled={busy || !targetIsPdf}>ใส่ Watermark</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>Page Numbers</h2><span>pypdf</span></div>
              <label>Format<input value={pageFormat} onChange={(e) => setPageFormat(e.target.value)} /></label>
              <div className="inlineFields"><label>เริ่มเลข<input type="number" min="0" value={pageStart} onChange={(e) => setPageStart(Number(e.target.value))} /></label><label>ตำแหน่ง<select value={pagePosition} onChange={(e) => setPagePosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label></div>
              <button className="primary" onClick={() => void run("page-numbers")} disabled={busy || !targetIsPdf}>ใส่เลขหน้า</button>
            </div>

            <div className="panel toolConfig">
              <div className="panelTitle"><h2>PDF Stamp</h2><span>overlay</span></div>
              <label>ไฟล์ Stamp<select value={stampId} onChange={(e) => setStampId(e.target.value)}><option value="">— เลือก PDF —</option>{pdfFiles.filter((file) => file.id !== targetId).map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select></label>
              <div className="inlineFields"><label>ตำแหน่ง<select value={stampPosition} onChange={(e) => setStampPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>Scale<input type="number" min="0.03" max="0.8" step="0.01" value={stampScale} onChange={(e) => setStampScale(Number(e.target.value))} /></label></div>
              <button className="primary" onClick={() => void run("stamp")} disabled={busy || !targetIsPdf || !stampId}>ประทับ PDF</button>
            </div>
          </section>

          <section className="panel">
            <div className="panelTitle"><h2>Jobs</h2><button className="ghost" onClick={() => void loadWorkspace()} disabled={busy}>Refresh</button></div>
            <div className="jobList">{jobs.length ? jobs.map((job) => <div className="job" key={job.id}><div><strong>{job.operation}</strong><code>{job.id}</code></div><span className={`badge ${job.status}`}>{job.status} • {job.progress}%</span>{job.output_file_id && <button className="ghost" onClick={() => void download(job.output_file_id!)}>ดาวน์โหลด</button>}{job.error && <small>{job.error}</small>}</div>) : <p className="muted">ยังไม่มีงาน</p>}</div>
          </section>
        </>
      ) : <section className="panel"><h2>เลือกวิธีเข้าสู่ระบบ</h2><p>ใช้ Service API Key, OIDC SSO หรือ LDAP ตามที่ผู้ดูแลเปิดใช้งาน</p></section>}
    </main>
  );
}

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
type ToolIconName = "scan" | "merge" | "organize" | "split" | "compress" | "image" | "imagePdf" | "watermark" | "numbers" | "archive" | "office" | "stamp" | "link" | "pdfa";

const positionOptions = [
  ["center", "กลาง"],
  ["top-left", "บนซ้าย"], ["top-center", "บนกลาง"], ["top-right", "บนขวา"],
  ["bottom-left", "ล่างซ้าย"], ["bottom-center", "ล่างกลาง"], ["bottom-right", "ล่างขวา"],
] as const;

const imageContentTypes = new Set(["image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"]);

function ToolIcon({ name }: { name: ToolIconName }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.9, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {name === "scan" && <><path {...common} d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"/><path {...common} d="M7 13c2.8-3.7 7.2-3.7 10 0M8.5 15.5h7"/></>}
      {name === "merge" && <><rect {...common} x="4" y="5" width="9" height="12" rx="2"/><rect {...common} x="11" y="7" width="9" height="12" rx="2"/></>}
      {name === "organize" && <><rect {...common} x="4" y="4" width="6" height="6" rx="1.5"/><rect {...common} x="14" y="4" width="6" height="6" rx="1.5"/><rect {...common} x="4" y="14" width="6" height="6" rx="1.5"/><rect {...common} x="14" y="14" width="6" height="6" rx="1.5"/></>}
      {name === "split" && <><rect {...common} x="4" y="5" width="6" height="14" rx="2"/><rect {...common} x="14" y="5" width="6" height="14" rx="2"/><path {...common} d="M12 4v16"/></>}
      {name === "compress" && <><path {...common} d="M8 3v5H3M16 3v5h5M8 21v-5H3M16 21v-5h5"/><path {...common} d="m3 8 5-5M21 8l-5-5M3 16l5 5M21 16l-5 5"/></>}
      {name === "image" && <><rect {...common} x="3" y="4" width="18" height="16" rx="2.5"/><circle {...common} cx="8.2" cy="9" r="1.5"/><path {...common} d="m5 17 4.5-4.5 3.2 3.2 2.2-2.2L19 17"/></>}
      {name === "imagePdf" && <><rect {...common} x="3" y="5" width="9" height="12" rx="2"/><path {...common} d="m5 14 2.2-2.5L10 14"/><rect {...common} x="12" y="7" width="9" height="12" rx="2"/><path {...common} d="M14.5 11h4M14.5 14h4M14.5 17h2.5"/></>}
      {name === "watermark" && <path {...common} d="M12 3s5 6.1 5 10a5 5 0 0 1-10 0c0-3.9 5-10 5-10Z"/>}
      {name === "numbers" && <><rect {...common} x="5" y="3" width="14" height="18" rx="2"/><path {...common} d="M8 8h1M8 12h1M8 16h1M12 8h4M12 12h4M12 16h4"/></>}
      {name === "archive" && <><path {...common} d="M4 8h16v12H4zM3 4h18v4H3z"/><path {...common} d="M9 12h6"/></>}
      {name === "office" && <><path {...common} d="M6 3h8l4 4v14H6z"/><path {...common} d="M14 3v5h5M9 13h6M9 16h6"/></>}
      {name === "stamp" && <><path {...common} d="M8 4h8v5c0 2.2 2 3 3 4v3H5v-3c1-1 3-1.8 3-4V4Z"/><path {...common} d="M5 19h14"/></>}
      {name === "link" && <><path {...common} d="M10 13a4.5 4.5 0 0 0 6.5.2l2-2a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2"/><path {...common} d="M14 11a4.5 4.5 0 0 0-6.5-.2l-2 2a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"/></>}
      {name === "pdfa" && <><path {...common} d="M6 3h8l4 4v14H6z"/><path {...common} d="M14 3v5h5M9 16l3-6 3 6M10 14h4"/></>}
    </svg>
  );
}

function BrandGlyph() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path d="M13 7h15l8 8v25H13a4 4 0 0 1-4-4V11a4 4 0 0 1 4-4Z" fill="currentColor" opacity=".18"/>
      <path d="M28 7v9h8" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round"/>
      <path d="M16 24h13M16 30h10" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
    </svg>
  );
}

export function PdfHubApp() {
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
      const [fileRows, jobRows, status] = await Promise.all([listFiles(authValue), listJobs(authValue), getIntegrationStatus(authValue)]);
      setFiles(fileRows); setJobs(jobRows); setIntegrations(status);
      if (!targetId && fileRows[0]) setTargetId(fileRows[0].id);
      setMessage("เชื่อมต่อ PDF Hub แล้ว");
    } catch (error) { setMessage(error instanceof Error ? error.message : "โหลด workspace ไม่สำเร็จ"); }
    finally { setBusy(false); }
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
          setIdentity(me); setAuth(SESSION_AUTH); await loadWorkspace(SESSION_AUTH);
        } catch { /* No session yet. */ }
      } catch { if (live) setMessage("อ่านการตั้งค่า authentication ไม่สำเร็จ"); }
    })();
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!auth || !activeJobs) return;
    const timer = window.setInterval(async () => {
      try {
        const jobRows = await listJobs(auth); setJobs(jobRows);
        if (!jobRows.some((job) => job.status === "queued" || job.status === "running")) {
          const fileRows = await listFiles(auth); setFiles(fileRows);
          if (!targetId && fileRows[0]) setTargetId(fileRows[0].id);
        }
      } catch { /* Keep UI usable if a poll fails. */ }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [auth, activeJobs, targetId]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  async function connectApiKey() { const value = apiKeyDraft.trim(); if (!value) return; setAuth(value); setIdentity(null); await loadWorkspace(value); }
  async function loginLdap() { if (!ldapUser || !ldapPassword) return; setBusy(true); try { const me = await ldapLogin(ldapUser, ldapPassword); setIdentity(me); setAuth(SESSION_AUTH); setLdapPassword(""); await loadWorkspace(SESSION_AUTH); } catch (error) { setMessage(error instanceof Error ? error.message : "LDAP login ไม่สำเร็จ"); } finally { setBusy(false); } }
  async function logout() { try { if (auth === SESSION_AUTH) await logoutSession(); } finally { setAuth(""); setIdentity(null); setFiles([]); setJobs([]); setIntegrations(null); setTargetId(""); setSignedUrl(null); setMessage("ออกจากระบบแล้ว"); } }

  async function onFiles(list: FileList | null) {
    if (!list?.length || !auth) return;
    setBusy(true); setMessage("กำลังอัปโหลดและตรวจความปลอดภัย...");
    try {
      const uploaded: UploadedFile[] = [];
      for (const file of Array.from(list)) uploaded.push(await uploadFile(file, auth));
      setFiles((old) => [...uploaded, ...old.filter((item) => !uploaded.some((fresh) => fresh.id === item.id))]);
      if (uploaded[0]) setTargetId(uploaded[0].id);
      setSignedUrl(null); setMessage(`อัปโหลดแล้ว ${uploaded.length} ไฟล์`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "อัปโหลดไม่สำเร็จ"); }
    finally { setBusy(false); }
  }

  async function submit(operation: string, payload: object) { if (!auth) return; setBusy(true); try { const job = await createJob(operation, payload, auth); setJobs((old) => [job, ...old]); setMessage(`ส่งงาน ${operation} แล้ว`); } catch (error) { setMessage(error instanceof Error ? error.message : "ทำรายการไม่สำเร็จ"); } finally { setBusy(false); } }

  async function run(operation: string) {
    if (!targetId && operation !== "merge" && operation !== "images-to-pdf") return setMessage("เลือกไฟล์เป้าหมายก่อน");
    switch (operation) {
      case "merge": if (pdfFiles.length < 2) return setMessage("Merge ต้องมี PDF อย่างน้อย 2 ไฟล์"); return submit("merge", { file_ids: pdfFiles.map((file) => file.id) });
      case "images-to-pdf": if (imageFiles.length < 1) return setMessage("ต้องมีไฟล์ภาพอย่างน้อย 1 ไฟล์"); return submit("images-to-pdf", { file_ids: imageFiles.map((file) => file.id), page_size: imagePageSize, fit: imageFit, margin: 18, dpi: imageDpi });
      case "pdf-to-images": if (!targetIsPdf) return setMessage("PDF → Images ต้องเลือกไฟล์ PDF"); return submit("pdf-to-images", { file_id: targetId, format: rasterFormat, dpi: rasterDpi, first_page: rasterFirstPage, last_page: rasterLastPage ? Number(rasterLastPage) : null });
      case "split": return submit("split", { file_id: targetId, pages: splitPages });
      case "rotate": return submit("rotate", { file_id: targetId, degrees: rotateDegrees, pages: rotatePages });
      case "ocr": return submit("ocr", { file_id: targetId, languages: "tha+eng", deskew: true, rotate_pages: true });
      case "compress": return submit("compress", { file_id: targetId });
      case "pdfa": return submit("pdfa", { file_id: targetId, languages: "tha+eng", deskew: false, rotate_pages: false });
      case "office-to-pdf": return submit("office-to-pdf", { file_id: targetId });
      case "watermark": return submit("watermark", { file_id: targetId, text: watermarkText, font_size: watermarkFontSize, opacity: watermarkOpacity, rotation: watermarkRotation, position: watermarkPosition, margin: 36 });
      case "page-numbers": return submit("page-numbers", { file_id: targetId, format: pageFormat, start_number: pageStart, font_size: 10, position: pagePosition, margin: 24 });
      case "stamp": if (!stampId) return setMessage("เลือกไฟล์ PDF ที่จะใช้เป็นตราประทับก่อน"); return submit("stamp", { file_id: targetId, stamp_file_id: stampId, position: stampPosition, scale: stampScale, margin: 24 });
      default: return setMessage("Unknown operation");
    }
  }

  async function preview() { if (!auth || !targetId) return; if (!targetIsPdf) return setMessage("Preview รองรับ PDF เท่านั้น"); try { const blob = await fetchPreview(targetId, auth, previewPage, 900); if (previewUrl) URL.revokeObjectURL(previewUrl); setPreviewUrl(URL.createObjectURL(blob)); setMessage(`Preview หน้า ${previewPage} พร้อมแล้ว`); } catch (error) { setMessage(error instanceof Error ? error.message : "Preview ไม่สำเร็จ"); } }
  async function download(fileId: string) { if (!auth) return; try { const blob = await fetchDownload(fileId, auth); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); const metadata = files.find((file) => file.id === fileId); anchor.href = url; anchor.download = metadata?.original_name || `pdfhub-${fileId}`; document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url); } catch (error) { setMessage(error instanceof Error ? error.message : "ดาวน์โหลดไม่สำเร็จ"); } }
  async function makeSignedLink() { if (!auth || !targetId) return; setBusy(true); try { const result = await createSignedDownload(targetId, auth, signedTtl); setSignedUrl(result.url); setMessage(`สร้าง signed URL ถึง ${new Date(result.expires_at).toLocaleTimeString("th-TH")} แล้ว`); } catch (error) { setMessage(error instanceof Error ? error.message : "สร้าง signed URL ไม่สำเร็จ"); } finally { setBusy(false); } }
  async function copySignedLink() { if (!signedUrl) return; try { await navigator.clipboard.writeText(signedUrl); setMessage("คัดลอก signed URL แล้ว"); } catch { setMessage("เบราว์เซอร์ไม่อนุญาต clipboard — คัดลอกจากลิงก์ที่แสดงได้โดยตรง"); } }
  async function archive() { if (!auth || !targetId) return; setBusy(true); try { const result = await archiveToPaperless(targetId, auth); setMessage(`ส่งเข้า Paperless แล้ว: ${result.external_id || result.status}`); } catch (error) { setMessage(error instanceof Error ? error.message : "Archive ไม่สำเร็จ"); } finally { setBusy(false); } }
  function jumpTo(id: string) { setTab("tools"); window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0); }

  const toolCards: Array<{ title: string; description: string; icon: ToolIconName; tone: string; disabled?: boolean; onClick: () => void; badge?: string }> = [
    { title: "สแกน / OCR", description: "อ่านเอกสารไทย + อังกฤษ และปรับหน้ากระดาษอัตโนมัติ", icon: "scan", tone: "rose", disabled: busy || !targetIsPdf, onClick: () => void run("ocr"), badge: "ยอดนิยม" },
    { title: "รวมไฟล์ PDF", description: "รวม PDF หลายไฟล์ใน Workspace ให้เป็นไฟล์เดียว", icon: "merge", tone: "blue", disabled: busy || pdfFiles.length < 2, onClick: () => void run("merge") },
    { title: "จัดหน้า PDF", description: "แยกหน้า เลือกหน้า และหมุนหน้าที่วางผิด", icon: "organize", tone: "violet", disabled: !targetIsPdf, onClick: () => jumpTo("split-rotate") },
    { title: "แยกไฟล์ PDF", description: "ดึงเฉพาะหน้าที่ต้องการออกมาเป็นไฟล์ใหม่", icon: "split", tone: "emerald", disabled: !targetIsPdf, onClick: () => jumpTo("split-rotate") },
    { title: "ลดขนาด PDF", description: "บีบอัดเอกสารให้ไฟล์เล็กลงสำหรับส่งหรือจัดเก็บ", icon: "compress", tone: "amber", disabled: busy || !targetIsPdf, onClick: () => void run("compress") },
    { title: "PDF → รูปภาพ", description: "แปลงหน้าของ PDF เป็น PNG หรือ JPEG และดาวน์โหลด ZIP", icon: "image", tone: "red", disabled: !targetIsPdf, onClick: () => jumpTo("pdf-to-images") },
    { title: "รูปภาพ → PDF", description: "รวม JPG, PNG, WebP และรูปเอกสารหลายรูปเป็น PDF", icon: "imagePdf", tone: "cyan", disabled: imageFiles.length < 1, onClick: () => jumpTo("images-to-pdf") },
    { title: "ใส่ลายน้ำ PDF", description: "เพิ่มข้อความลายน้ำภาษาไทย กำหนดตำแหน่งและความโปร่งใส", icon: "watermark", tone: "pink", disabled: !targetIsPdf, onClick: () => jumpTo("watermark") },
    { title: "ใส่เลขหน้า PDF", description: "เพิ่มเลขหน้าอัตโนมัติ พร้อมเลือกรูปแบบและตำแหน่ง", icon: "numbers", tone: "indigo", disabled: !targetIsPdf, onClick: () => jumpTo("page-numbers") },
    { title: "PDF/A-2", description: "แปลงเป็นเอกสารมาตรฐานสำหรับจัดเก็บระยะยาว", icon: "pdfa", tone: "green", disabled: busy || !targetIsPdf, onClick: () => void run("pdfa") },
    { title: "Office → PDF", description: "แปลง Word, Excel, PowerPoint และเอกสาร Office เป็น PDF", icon: "office", tone: "orange", disabled: busy || !targetId, onClick: () => void run("office-to-pdf") },
    { title: "ประทับ PDF", description: "ใช้ PDF อีกไฟล์เป็นตราประทับหรือ overlay บนเอกสาร", icon: "stamp", tone: "purple", disabled: !targetIsPdf, onClick: () => jumpTo("pdf-stamp") },
    { title: "ลิงก์ดาวน์โหลด", description: "สร้าง Signed URL อายุสั้นสำหรับแชร์ไฟล์อย่างปลอดภัย", icon: "link", tone: "sky", disabled: !targetId, onClick: () => jumpTo("workspace-target") },
    { title: "คลังเอกสาร", description: integrations?.paperless_enabled ? "ส่ง PDF เข้า Paperless-ngx เพื่อจัดเก็บและค้นหา" : "เปิด Paperless-ngx integration เพื่อใช้งานคลังเอกสาร", icon: "archive", tone: "teal", disabled: busy || !targetIsPdf || !integrations?.paperless_enabled, onClick: () => void archive() },
  ];

  return (
    <main className="shell" id="top">
      <header className="appHeader">
        <button className="brandButton" type="button" onClick={() => jumpTo("top")} aria-label="กลับด้านบน"><span className="brandLogo"><BrandGlyph /></span><span className="brandText"><strong>เครื่องมือ <em>PDF</em></strong><small>RCAT • ศูนย์กลางจัดการเอกสาร</small></span></button>
        <div className="headerActions"><div className="status"><span className="statusDot" />{message}</div><nav className="desktopTabs" aria-label="PDF Hub sections"><button className={tab === "tools" ? "active" : ""} onClick={() => setTab("tools")}>เครื่องมือ</button><button className={tab === "admin" ? "active" : ""} onClick={() => setTab("admin")}>ผู้ดูแล</button></nav></div>
      </header>

      {tab === "tools" && <section className="welcomeHero"><div className="welcomeCopy"><span className="eyebrow">PDF WORKSPACE • SELF-HOSTED</span><h1>จัดการเอกสารให้<br/><span>ง่ายกว่าเดิม</span></h1><p>รวม แยก OCR แปลงไฟล์ ใส่ลายน้ำ และจัดการ PDF จากพื้นที่ทำงานเดียว โดยข้อมูลยังอยู่ในระบบขององค์กร</p><div className="heroChips"><span>OCR ไทย + อังกฤษ</span><span>PDF/A</span><span>Secure download</span></div></div><div className="heroArt" aria-hidden="true"><span className="artOrb one"/><span className="artOrb two"/><div className="folderBack"/><div className="folderFront"/><div className="pdfSheet"><b>PDF</b><i/><i/><i/></div><div className="sparkle s1">✦</div><div className="sparkle s2">✦</div></div></section>}

      <section className={`authCard ${authenticated ? "connected" : ""}`}>
        {auth === SESSION_AUTH && identity ? <><div className="userIdentity"><span className="avatar">{(identity.display_name || identity.name || "U").slice(0, 1).toUpperCase()}</span><div><strong>{identity.display_name || identity.name}</strong><small>{identity.auth_source} • {identity.groups.join(", ") || "authenticated"}</small></div></div><div className="authActions"><button className="secondary" onClick={() => void loadWorkspace()} disabled={busy}>รีเฟรชข้อมูล</button><button className="ghost" onClick={logout}>ออกจากระบบ</button></div></> : <><div className="loginIntro"><span className="loginIcon">↗</span><div><strong>เชื่อมต่อ PDF Hub</strong><small>เข้าสู่ระบบเพื่อเปิด Workspace และเครื่องมือทั้งหมด</small></div></div><div className="apiLogin"><input aria-label="Service API Key" type="password" value={apiKeyDraft} onChange={(e) => setApiKeyDraft(e.target.value)} placeholder="Service API Key • pdfh_..." autoComplete="off"/><button className="primary" onClick={connectApiKey} disabled={!apiKeyDraft || busy}>เชื่อมต่อ</button></div>{authConfig?.oidc.enabled && authConfig.oidc.login_url && <button className="secondary" onClick={() => { window.location.href = `${authConfig.oidc.login_url}?return_to=/`; }}>SSO Login</button>}</>}
        {authConfig?.ldap.enabled && auth !== SESSION_AUTH && <div className="ldapLogin"><label>LDAP user<input value={ldapUser} onChange={(e) => setLdapUser(e.target.value)} autoComplete="username"/></label><label>LDAP password<input type="password" value={ldapPassword} onChange={(e) => setLdapPassword(e.target.value)} autoComplete="current-password"/></label><button className="secondary" onClick={loginLdap} disabled={!ldapUser || !ldapPassword || busy}>LDAP Login</button></div>}
      </section>

      {authenticated && integrations && tab === "tools" && <section className="platformStrip" aria-label="Platform status"><div><span className="platformIcon storage">▰</span><p><strong>Storage</strong><small>{integrations.storage_backend.toUpperCase()}</small></p></div><div><span className="platformIcon shield">✓</span><p><strong>Malware scan</strong><small>{integrations.clamav_enabled ? "ClamAV พร้อมใช้งาน" : "ไม่ได้เปิดใช้"}</small></p></div><div><span className="platformIcon secure">⌁</span><p><strong>Secure delivery</strong><small>Signed URL + webhook</small></p></div><div><span className="platformIcon archive">▣</span><p><strong>Archive</strong><small>{integrations.paperless_enabled ? "Paperless พร้อมใช้งาน" : "ไม่ได้เปิดใช้"}</small></p></div></section>}

      {tab === "admin" ? (authenticated ? <section className="adminPage"><div className="sectionIntro"><span className="sectionKicker">SYSTEM CONTROL</span><h2>จัดการระบบ</h2><p>API keys, quota, webhook และ audit trail สำหรับผู้ดูแล</p></div><AdminPanel apiKey={auth}/></section> : <section className="emptyState"><span>🔐</span><h2>เข้าสู่ระบบก่อนเปิดหน้าผู้ดูแล</h2><p>ใช้ Service API Key, OIDC SSO หรือ LDAP ตามที่ระบบเปิดใช้งาน</p></section>) : authenticated ? <>
        <section className="workspaceGrid" id="workspace"><div className="uploadCard"><input id="files" type="file" multiple onChange={(e) => void onFiles(e.target.files)} disabled={busy}/><label htmlFor="files"><span className="uploadIcon">＋</span><span className="uploadBadge">เริ่มที่นี่</span><strong>เพิ่มไฟล์เข้า Workspace</strong><span>เลือก PDF, รูปภาพ หรือเอกสาร Office ได้หลายไฟล์</span><em>แตะเพื่อเลือกไฟล์</em></label></div><div className="targetCard" id="workspace-target"><div className="panelTitle"><div><span className="sectionKicker">WORKSPACE</span><h2>ไฟล์ที่เลือก</h2></div><span className="countPill">{files.length} ไฟล์</span></div><select value={targetId} onChange={(e) => { setTargetId(e.target.value); setPreviewUrl(null); setSignedUrl(null); }}><option value="">— เลือกไฟล์ —</option>{files.map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select>{target ? <div className="selectedFile"><span className="fileGlyph">PDF</span><div><strong>{target.original_name}</strong><small>{(target.size / 1024 / 1024).toFixed(2)} MB • {target.content_type}</small></div></div> : <div className="noTarget">เลือกไฟล์เพื่อเริ่มใช้เครื่องมือ</div>}<div className="previewControls"><label>หน้า<input type="number" min="1" value={previewPage} onChange={(e) => setPreviewPage(Math.max(1, Number(e.target.value)))}/></label><button className="secondary" onClick={preview} disabled={!targetId || !targetIsPdf}>ดูตัวอย่าง PDF</button></div><div className="signedRow"><label>ลิงก์หมดอายุ (วินาที)<input type="number" min="30" max="3600" value={signedTtl} onChange={(e) => setSignedTtl(Math.max(30, Number(e.target.value)))}/></label><button className="secondary" onClick={makeSignedLink} disabled={!targetId || busy}>สร้าง Signed URL</button></div>{signedUrl && <div className="secretBox"><strong>ลิงก์ดาวน์โหลดชั่วคราว</strong><code>{signedUrl}</code><div className="rowActions"><a className="ghost" href={signedUrl} target="_blank" rel="noreferrer">เปิด</a><button className="ghost" onClick={copySignedLink}>คัดลอก</button></div></div>}</div></section>
        {previewUrl && <section className="previewPanel"><div className="panelTitle"><div><span className="sectionKicker">PREVIEW</span><h2>ตัวอย่างหน้า {previewPage}</h2></div><button className="ghost" onClick={() => setPreviewUrl(null)}>ปิด</button></div><div className="previewCanvas"><Image src={previewUrl} alt={`Preview page ${previewPage}`} width={900} height={1200} unoptimized/></div></section>}
        <section className="toolsSection" id="quick-tools"><div className="sectionIntro toolsIntro"><div><span className="sectionKicker">ALL TOOLS</span><h2>เครื่องมือทั้งหมด</h2><p>รวมเครื่องมือ PDF <strong>14 รายการ</strong> พร้อมคำอธิบายสั้น ๆ เลือกใช้ได้ทันที</p></div><span className="toolsBubble">PDF</span></div><div className="toolCardGrid">{toolCards.map((tool) => <button key={tool.title} className={`toolCard ${tool.tone}`} disabled={tool.disabled} onClick={tool.onClick}><span className="toolIcon"><ToolIcon name={tool.icon}/></span><span className="toolCopy">{tool.badge && <em>{tool.badge}</em>}<strong>{tool.title}</strong><small>{tool.description}</small></span><span className="toolArrow">›</span></button>)}</div></section>
        <section className="advancedSection" id="advanced-tools"><div className="sectionIntro"><span className="sectionKicker">FINE TUNE</span><h2>ตั้งค่าเครื่องมือ</h2><p>ปรับรายละเอียดก่อนประมวลผลสำหรับงานที่ต้องการความแม่นยำมากขึ้น</p></div><div className="advancedGrid">
          <div className="toolConfig" id="images-to-pdf"><div className="configHead"><span className="miniIcon cyan"><ToolIcon name="imagePdf"/></span><div><h3>รูปภาพ → PDF</h3><small>Pillow + ReportLab</small></div></div><div className="inlineFields three"><label>ขนาดหน้า<select value={imagePageSize} onChange={(e) => setImagePageSize(e.target.value)}><option value="auto">Auto</option><option value="a4">A4</option><option value="letter">Letter</option></select></label><label>การจัดวาง<select value={imageFit} onChange={(e) => setImageFit(e.target.value)}><option value="contain">Contain</option><option value="cover">Cover</option></select></label><label>DPI<input type="number" min="72" max="600" value={imageDpi} onChange={(e) => setImageDpi(Number(e.target.value))}/></label></div><small className="configHint">พบ {imageFiles.length} รูปใน Workspace</small><button className="primary full" onClick={() => void run("images-to-pdf")} disabled={busy || imageFiles.length < 1}>สร้าง PDF จากภาพ</button></div>
          <div className="toolConfig" id="pdf-to-images"><div className="configHead"><span className="miniIcon red"><ToolIcon name="image"/></span><div><h3>PDF → รูปภาพ</h3><small>Poppler ZIP</small></div></div><div className="inlineFields three"><label>Format<select value={rasterFormat} onChange={(e) => setRasterFormat(e.target.value)}><option value="png">PNG</option><option value="jpeg">JPEG</option></select></label><label>DPI<input type="number" min="72" max="600" value={rasterDpi} onChange={(e) => setRasterDpi(Number(e.target.value))}/></label><label>หน้าแรก<input type="number" min="1" value={rasterFirstPage} onChange={(e) => setRasterFirstPage(Math.max(1, Number(e.target.value)))}/></label></div><label>หน้าสุดท้าย (เว้นว่าง = สูงสุด 200 หน้า)<input type="number" min={rasterFirstPage} value={rasterLastPage} onChange={(e) => setRasterLastPage(e.target.value)}/></label><button className="primary full" onClick={() => void run("pdf-to-images")} disabled={busy || !targetIsPdf}>แปลงเป็น ZIP รูปภาพ</button></div>
          <div className="toolConfig" id="split-rotate"><div className="configHead"><span className="miniIcon violet"><ToolIcon name="organize"/></span><div><h3>แยกและหมุนหน้า</h3><small>qpdf</small></div></div><label>หน้าที่ต้องการ เช่น 1-3,5<input value={splitPages} onChange={(e) => setSplitPages(e.target.value)}/></label><button className="primary full" onClick={() => void run("split")} disabled={busy || !targetIsPdf}>แยก / เลือกหน้า</button><div className="separator"/><div className="inlineFields"><label>หมุน<select value={rotateDegrees} onChange={(e) => setRotateDegrees(Number(e.target.value))}><option value={90}>+90°</option><option value={180}>180°</option><option value={270}>+270°</option><option value={-90}>-90°</option></select></label><label>หน้า<input value={rotatePages} onChange={(e) => setRotatePages(e.target.value)}/></label></div><button className="secondary full" onClick={() => void run("rotate")} disabled={busy || !targetIsPdf}>หมุนหน้า</button></div>
          <div className="toolConfig" id="watermark"><div className="configHead"><span className="miniIcon pink"><ToolIcon name="watermark"/></span><div><h3>ลายน้ำ PDF</h3><small>รองรับภาษาไทย</small></div></div><label>ข้อความ<input value={watermarkText} onChange={(e) => setWatermarkText(e.target.value)}/></label><div className="inlineFields three"><label>ขนาด<input type="number" value={watermarkFontSize} onChange={(e) => setWatermarkFontSize(Number(e.target.value))}/></label><label>Opacity<input type="number" min="0.02" max="1" step="0.01" value={watermarkOpacity} onChange={(e) => setWatermarkOpacity(Number(e.target.value))}/></label><label>หมุน<input type="number" value={watermarkRotation} onChange={(e) => setWatermarkRotation(Number(e.target.value))}/></label></div><label>ตำแหน่ง<select value={watermarkPosition} onChange={(e) => setWatermarkPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><button className="primary full" onClick={() => void run("watermark")} disabled={busy || !targetIsPdf}>ใส่ลายน้ำ</button></div>
          <div className="toolConfig" id="page-numbers"><div className="configHead"><span className="miniIcon indigo"><ToolIcon name="numbers"/></span><div><h3>เลขหน้า PDF</h3><small>pypdf</small></div></div><label>รูปแบบ<input value={pageFormat} onChange={(e) => setPageFormat(e.target.value)}/></label><div className="inlineFields"><label>เริ่มเลข<input type="number" min="0" value={pageStart} onChange={(e) => setPageStart(Number(e.target.value))}/></label><label>ตำแหน่ง<select value={pagePosition} onChange={(e) => setPagePosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label></div><button className="primary full" onClick={() => void run("page-numbers")} disabled={busy || !targetIsPdf}>ใส่เลขหน้า</button></div>
          <div className="toolConfig" id="pdf-stamp"><div className="configHead"><span className="miniIcon purple"><ToolIcon name="stamp"/></span><div><h3>ประทับ PDF</h3><small>Overlay</small></div></div><label>ไฟล์ Stamp<select value={stampId} onChange={(e) => setStampId(e.target.value)}><option value="">— เลือก PDF —</option>{pdfFiles.filter((file) => file.id !== targetId).map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select></label><div className="inlineFields"><label>ตำแหน่ง<select value={stampPosition} onChange={(e) => setStampPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>Scale<input type="number" min="0.03" max="0.8" step="0.01" value={stampScale} onChange={(e) => setStampScale(Number(e.target.value))}/></label></div><button className="primary full" onClick={() => void run("stamp")} disabled={busy || !targetIsPdf || !stampId}>ประทับ PDF</button></div>
        </div></section>
        <section className="jobsSection" id="jobs"><div className="panelTitle"><div><span className="sectionKicker">RECENT</span><h2>งานล่าสุด</h2></div><button className="ghost" onClick={() => void loadWorkspace()} disabled={busy}>รีเฟรช</button></div><div className="jobList">{jobs.length ? jobs.map((job) => <div className="job" key={job.id}><span className={`jobStatusDot ${job.status}`}/><div className="jobInfo"><strong>{job.operation}</strong><code>{job.id}</code></div><span className={`badge ${job.status}`}>{job.status} • {job.progress}%</span>{job.output_file_id && <button className="downloadButton" onClick={() => void download(job.output_file_id!)}>ดาวน์โหลด</button>}{job.error && <small className="jobError">{job.error}</small>}</div>) : <div className="noJobs"><span>◷</span><p>ยังไม่มีงานประมวลผล</p></div>}</div></section>
      </> : <section className="emptyState"><span>📄</span><h2>พร้อมเริ่มจัดการ PDF</h2><p>เชื่อมต่อระบบด้านบน แล้วเพิ่มไฟล์เข้า Workspace เพื่อเปิดเครื่องมือทั้งหมด</p></section>}

      <nav className="mobileNav" aria-label="เมนูหลัก"><button onClick={() => jumpTo("top")}><span>⌂</span><small>หน้าแรก</small></button><button className={tab === "tools" ? "active" : ""} onClick={() => jumpTo("quick-tools")}><span>▦</span><small>เครื่องมือ</small></button><button className="navScan" onClick={() => jumpTo("workspace")}><span><ToolIcon name="scan"/></span><small>เพิ่มไฟล์</small></button><button onClick={() => jumpTo("jobs")}><span>◷</span><small>ล่าสุด</small></button><button className={tab === "admin" ? "active" : ""} onClick={() => { setTab("admin"); window.scrollTo({ top: 0, behavior: "smooth" }); }}><span>⚙</span><small>ตั้งค่า</small></button></nav>
    </main>
  );
}

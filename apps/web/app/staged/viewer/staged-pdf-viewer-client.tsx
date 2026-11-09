"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  fetchDownload, fetchPreview, getMe, getPageInfo, listFiles, SESSION_AUTH,
  type AuthMe, type UploadedFile,
} from "../../../lib/api";

const MAX_PAGES = 5000;
const RESOLUTIONS = [480, 720, 1080] as const;

function eligible(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner
    && file.content_type.toLowerCase() === "application/pdf"
    && file.original_name.toLowerCase().endsWith(".pdf")
    && file.size > 0
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}

function mayRead(identity: AuthMe | null): boolean {
  return Boolean(identity && (
    identity.scopes.includes("files:read") || identity.scopes.includes("*")
  ));
}

export function StagedPdfViewerClient({ requestedFileId }: { requestedFileId?: string }) {
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [pageCount, setPageCount] = useState(0);
  const [page, setPage] = useState(1);
  const [width, setWidth] = useState<number>(720);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [error, setError] = useState("");

  const canRead = mayRead(identity);
  const selected = useMemo(
    () => files.find((item) => item.id === selectedId),
    [files, selectedId],
  );

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const me = await getMe(SESSION_AUTH);
        if (!live) return;
        setIdentity(me);
        if (!mayRead(me)) return;
        const owned = (await listFiles(SESSION_AUTH))
          .filter((item) => eligible(item, me.name));
        if (!live) return;
        setFiles(owned);
        // A deep link to a foreign/expired file never triggers a fetch for it.
        setSelectedId(owned.find((item) => item.id === requestedFileId)?.id ?? owned[0]?.id ?? "");
      } catch {
        if (live) setError("ตรวจสอบบัญชีหรือไฟล์ไม่สำเร็จ กรุณาเข้าสู่ระบบอีกครั้ง");
      } finally {
        if (live) setLoading(false);
      }
    }
    void load();
    return () => { live = false; };
  }, [requestedFileId]);

  useEffect(() => {
    if (!canRead || !selected) return;
    let live = true;
    setPageCount(0);
    setError("");
    void getPageInfo(selected.id, SESSION_AUTH).then((info) => {
      if (!live) return;
      if (info.file_id !== selected.id || !Number.isSafeInteger(info.pages)
          || info.pages < 1 || info.pages > MAX_PAGES) {
        setError("จำนวนหน้า PDF ไม่ถูกต้องหรือเกินขอบเขตการดูตัวอย่าง");
        return;
      }
      setPageCount(info.pages);
    }).catch(() => {
      if (live) setError("ไม่สามารถอ่านจำนวนหน้า PDF ได้ โปรดตรวจสอบสิทธิ์หรืออายุไฟล์");
    });
    return () => { live = false; };
  }, [selected, canRead]);

  useEffect(() => {
    if (!canRead || !selected || pageCount < 1 || page > pageCount || page < 1) return;
    let live = true;
    let createdUrl: string | null = null;
    setPreviewUrl(null);
    setPreviewBusy(true);
    setError("");
    void fetchPreview(selected.id, SESSION_AUTH, page, width).then((blob) => {
      if (!live) return;
      if (!blob.size || blob.type !== "image/png") {
        setError("เซิร์ฟเวอร์ไม่ส่งภาพตัวอย่าง PNG ที่ถูกต้อง");
        return;
      }
      createdUrl = URL.createObjectURL(blob);
      setPreviewUrl(createdUrl);
    }).catch(() => {
      if (live) setError("เปิดภาพตัวอย่างไม่สำเร็จ อาจไม่มีสิทธิ์หรือไฟล์หมดอายุ");
    }).finally(() => {
      if (live) setPreviewBusy(false);
    });
    // Blob URLs are intentionally short-lived and never placed in shareable links.
    return () => {
      live = false;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [canRead, selected, pageCount, page, width]);

  function changeFile(id: string) {
    setSelectedId(id);
    setPage(1);
    setPageCount(0);
    setPreviewUrl(null);
    setError("");
  }

  async function download() {
    if (!canRead || !selected || downloadBusy || !eligible(selected, identity!.name)) return;
    setDownloadBusy(true);
    setError("");
    try {
      const blob = await fetchDownload(selected.id, SESSION_AUTH);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = selected.original_name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      setError("ดาวน์โหลด PDF ไม่สำเร็จ โปรดตรวจสอบสิทธิ์หรืออายุไฟล์");
    } finally {
      setDownloadBusy(false);
    }
  }

  return (
    <main className="t90DocumentStage t90PdfViewer">
      <header className="t90DocumentStageHeader">
        <a href="/" aria-label="กลับหน้า Workspace">← Workspace</a>
        <span>RCAT PDF Hub · M20 / STAGING ONLY</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">PDF VIEWER · READ ONLY</p>
        <h1>ดูเอกสาร PDF</h1>
        <p>เปิดดูทีละหน้า เลื่อนหน้า และปรับความละเอียดภาพโดยไม่แก้ไขต้นฉบับ
          เฉพาะ PDF ที่บัญชีของคุณมีสิทธิ์เข้าถึงเท่านั้น</p>
        {loading ? <p role="status">กำลังตรวจสอบบัญชีและรายการ PDF…</p> : (
          <>
            {!canRead && identity && <p role="alert" className="t90DocumentStageError">
              บัญชีนี้ไม่มีสิทธิ์ files:read</p>}
            {canRead && (
              <div className="t90DocumentStageField">
                <label htmlFor="m20-file">PDF ของฉัน</label>
                <select id="m20-file" value={selectedId} onChange={(event) => changeFile(event.target.value)}
                  disabled={!files.length} aria-label="PDF ของฉัน">
                  {!files.length && <option value="">ไม่มี PDF ที่ใช้งานได้</option>}
                  {files.map((item) =>
                    <option value={item.id} key={item.id}>{item.original_name}</option>)}
                </select>
              </div>
            )}
            {selected && canRead && (
              <>
                <div className="m20Toolbar" aria-label="ตัวควบคุม PDF">
                  <button type="button" disabled={page <= 1 || previewBusy}
                    onClick={() => setPage((old) => Math.max(1, old - 1))}>ก่อนหน้า</button>
                  <label>หน้า
                    <input type="number" min={1} max={pageCount || 1} value={page}
                      aria-label="หมายเลขหน้า"
                      onChange={(event) => {
                        const value = Number(event.target.value);
                        if (Number.isSafeInteger(value) && value >= 1
                            && value <= (pageCount || 1)) setPage(value);
                      }} disabled={!pageCount} />
                  </label>
                  <span aria-live="polite">จาก {pageCount || "…"} หน้า</span>
                  <button type="button" disabled={!pageCount || page >= pageCount || previewBusy}
                    onClick={() => setPage((old) => Math.min(pageCount, old + 1))}>ถัดไป</button>
                  <label>ความละเอียด
                    <select aria-label="ความละเอียดภาพ" value={width}
                      onChange={(event) => setWidth(Number(event.target.value))}>
                      {RESOLUTIONS.map((value) =>
                        <option key={value} value={value}>{value} px</option>)}
                    </select>
                  </label>
                </div>
                <div className="m20Preview" aria-live="polite">
                  {previewBusy && <p role="status">กำลังเปิดหน้า {page}…</p>}
                  {previewUrl && !previewBusy && (
                    <Image src={previewUrl} alt={"PDF หน้า " + page}
                      width={width} height={Math.round(width * 1.414)}
                      unoptimized style={{ maxWidth: "100%", height: "auto" }} />
                  )}
                </div>
                <div className="m20Footer">
                  <a href={"/files/" + encodeURIComponent(selected.id)}>รายละเอียดไฟล์</a>
                  <button type="button" onClick={() => { void download(); }}
                    disabled={downloadBusy}>{downloadBusy ? "กำลังดาวน์โหลด…" : "ดาวน์โหลด PDF ต้นฉบับ"}</button>
                </div>
              </>
            )}
          </>
        )}
        {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
      </section>
    </main>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { Eye, FileText } from "lucide-react";
import { fetchPreview, FileLookupError, getFile, UploadedFile } from "../../lib/api";
import { PDF_TOOLS } from "./tool-catalog";
import { isEligibleToolFile, TOOL_INPUT_RULES } from "./tool-input-rules";

function fileMessage(error: unknown): string {
  if (error instanceof FileLookupError) {
    if (error.status === 401) return "Session หมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง";
    if (error.status === 403) return "บัญชีนี้ไม่มีสิทธิ์ดูไฟล์ดังกล่าว";
    if (error.status === 404) return "ไม่พบไฟล์ หรือไฟล์ถูกลบแล้ว";
    if (error.status === 410) return "ไฟล์หมดอายุหรือไม่พร้อมใช้งานแล้ว";
  }
  return "ไม่สามารถโหลดไฟล์ได้ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่";
}

export function FileDetailScreen({ fileId, auth }: { fileId: string; auth: string }) {
  const [file, setFile] = useState<UploadedFile | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [previewBusy, setPreviewBusy] = useState(false);
  const previewRequestId = useRef(0);

  useEffect(() => {
    let live = true;
    setFile(null);
    setError("");
    setPreviewUrl(null);
    setPreviewError("");
    previewRequestId.current += 1;
    void getFile(fileId, auth).then((result) => {
      if (live) setFile(result);
    }).catch((failure) => {
      if (live) setError(fileMessage(failure));
    });
    return () => { live = false; };
  }, [fileId, auth, reload]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  async function openPreview() {
    if (!file || previewBusy) return;
    const request = ++previewRequestId.current;
    setPreviewBusy(true);
    setPreviewError("");
    try {
      const blob = await fetchPreview(file.id, auth, 1, 900);
      const url = URL.createObjectURL(blob);
      if (request !== previewRequestId.current) {
        URL.revokeObjectURL(url);
        return;
      }
      setPreviewUrl(url);
    } catch {
      if (request === previewRequestId.current) setPreviewError("ไม่สามารถแสดงตัวอย่าง PDF ได้ โปรดตรวจสอบสิทธิ์ไฟล์แล้วลองอีกครั้ง");
    } finally {
      if (request === previewRequestId.current) setPreviewBusy(false);
    }
  }

  const expired = Boolean(file?.expires_at && Date.parse(file.expires_at) <= Date.now());
  const eligibleTools = file && !expired ? PDF_TOOLS.filter((tool) => isEligibleToolFile(tool.id, file)) : [];

  return (
    <main className="v3Main v3FileDetail v4Main v4FileDetail" aria-label="รายละเอียดไฟล์ของฉัน">
      <section className="v3HomeTitle">
        <div><span className="v3Kicker">MY FILE</span><h1>รายละเอียดไฟล์</h1><p>ลิงก์ไฟล์นี้เปิดซ้ำได้ โดยระบบตรวจสิทธิ์ของบัญชีทุกครั้ง</p></div>
        <a className="v3TextLink" href="/files">← คลังไฟล์ของฉัน</a>
      </section>
      <section className="v3JobDetailCard" aria-live="polite">
        {!file && !error && <p role="status">กำลังตรวจสอบสิทธิ์ไฟล์…</p>}
        {error && <p role="alert" className="v3InfoBox">{error}</p>}
        {file && <>
          <div className="v3SectionHead"><div><span className="v3Kicker">DOCUMENT</span><h2>{file.original_name}</h2></div></div>
          <p><strong>ประเภท:</strong> {file.content_type}</p>
          <p><strong>ขนาด:</strong> {Math.ceil(file.size / 1024)} KB</p>
          <p><strong>การเก็บรักษา:</strong> {file.expires_at ? new Date(file.expires_at).toLocaleString("th-TH") : "ไม่มีวันหมดอายุ"}</p>
          <section className="v4DocumentPreview" aria-labelledby="v4-file-preview-title">
            <div className="v4DocumentPreviewHead">
              <span className="v4FilePreviewSymbol"><FileText aria-hidden="true" size={22}/></span>
              <div><h3 id="v4-file-preview-title">ตัวอย่างเอกสาร</h3><p>ดูหน้าแรกของ PDF โดยไม่ต้องดาวน์โหลด</p></div>
            </div>
            {file.content_type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf") ? (
              <>
                <button className="v4SecondaryButton" type="button" disabled={previewBusy || expired} onClick={() => void openPreview()}>
                  <Eye aria-hidden="true" size={18}/>{previewBusy ? "กำลังโหลดตัวอย่าง…" : "ดูตัวอย่าง PDF"}
                </button>
                {previewError && <p className="v3InfoBox" role="alert">{previewError}</p>}
                {previewUrl && <div className="v4DocumentPreviewCanvas">
                  <Image src={previewUrl} alt={`ตัวอย่างหน้าแรกของ ${file.original_name}`} width={900} height={1200} unoptimized/>
                </div>}
              </>
            ) : <p className="v4PreviewUnavailable">ไฟล์ชนิดนี้ยังไม่รองรับการแสดงตัวอย่างใน Browser สามารถเลือกเครื่องมือที่รองรับได้ด้านล่าง</p>}
          </section>
          {expired ? (
            <div role="status" className="v3InfoBox">ไฟล์หมดอายุแล้ว ไม่สามารถเริ่มงานใหม่จากไฟล์นี้ได้ กรุณาอัปโหลดใหม่หากยังมีต้นฉบับ</div>
          ) : eligibleTools.length ? (
            <section className="v3FollowOn" aria-label="เครื่องมือสำหรับไฟล์นี้">
              <div className="v3SectionHead"><div><span className="v3Kicker">NEXT TASK</span><h2>เลือกเครื่องมือสำหรับไฟล์นี้</h2></div></div>
              <div className="v3FollowOnGrid">
                {eligibleTools.map((tool) => (
                  <a key={tool.id} className="v3FollowOnTool" href={`/tools/${encodeURIComponent(tool.id)}?file=${encodeURIComponent(file.id)}`}>
                    <strong>{tool.title}</strong>
                    <small>{TOOL_INPUT_RULES[tool.id].min > 1 ? "เลือกไฟล์เพิ่มก่อนส่งงาน" : "ใช้ไฟล์นี้โดยตรง"}</small>
                    <span aria-hidden="true">→</span>
                  </a>
                ))}
              </div>
            </section>
          ) : <div className="v3InfoBox">ยังไม่มีเครื่องมือที่รองรับไฟล์นี้</div>}
        </>}
        <div className="v3JobDetailActions">
          <a className="v3TextLink" href="/jobs">งานของฉัน</a>
          <button type="button" className="v3MiniButton" onClick={() => setReload((value) => value + 1)}>ตรวจสอบใหม่</button>
        </div>
      </section>
    </main>
  );
}

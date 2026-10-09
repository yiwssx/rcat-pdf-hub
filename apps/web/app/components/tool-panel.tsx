"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { getPageInfo, IntegrationStatus, UploadedFile } from "../../lib/api";
import { ToolIcon, ToolIconName } from "./tool-icons";
import { ToolWorkspaceSettings } from "./tool-workspace-state";

const positionOptions = [
  ["center", "กลาง"],
  ["top-left", "บนซ้าย"], ["top-center", "บนกลาง"], ["top-right", "บนขวา"],
  ["bottom-left", "ล่างซ้าย"], ["bottom-center", "ล่างกลาง"], ["bottom-right", "ล่างขวา"],
] as const;

type ToolSettingSetter = <K extends keyof ToolWorkspaceSettings>(
  key: K,
  value: ToolWorkspaceSettings[K],
) => void;

type Props = {
  tool: string;
  auth: string;
  target: UploadedFile;
  pdfFiles: UploadedFile[];
  imageFiles: UploadedFile[];
  targetIsPdf: boolean;
  busy: boolean;
  integrations: IntegrationStatus | null;
  signedUrl: string | null;
  settings: ToolWorkspaceSettings;
  onSettingChange: ToolSettingSetter;
  onRun: (operation: string) => void;
  onSignedLink: () => void;
  onCopySignedLink: () => void;
  onArchive: () => void;
  onOrganize: (pages: Array<{ page: number; rotation: number }>) => void;
  onClose: () => void;
};
const meta: Record<string, { title: string; subtitle: string; icon: ToolIconName; tone: string }> = {
  ocr: { title: "สแกน / OCR", subtitle: "อ่านข้อความไทย + อังกฤษ", icon: "scan", tone: "rose" },
  "merge-pdf": { title: "รวมไฟล์ PDF", subtitle: "ตรวจรายการก่อนรวมเอกสาร", icon: "merge", tone: "blue" },
  "split-rotate": { title: "จัดหน้า PDF", subtitle: "เลือก แยก และหมุนหน้า", icon: "organize", tone: "violet" },
  compress: { title: "ลดขนาด PDF", subtitle: "บีบอัดโดยไม่แก้ไฟล์ต้นฉบับ", icon: "compress", tone: "amber" },
  "pdf-to-images": { title: "PDF → รูปภาพ", subtitle: "ส่งออก PNG หรือ JPEG", icon: "image", tone: "red" },
  "images-to-pdf": { title: "รูปภาพ → PDF", subtitle: "รวมรูปเป็นเอกสาร PDF", icon: "imagePdf", tone: "cyan" },
  watermark: { title: "ลายน้ำ PDF", subtitle: "ข้อความ ตำแหน่ง และความโปร่งใส", icon: "watermark", tone: "pink" },
  "page-numbers": { title: "เลขหน้า PDF", subtitle: "กำหนดรูปแบบและตำแหน่ง", icon: "numbers", tone: "indigo" },
  pdfa: { title: "PDF/A-2", subtitle: "จัดเก็บเอกสารระยะยาว", icon: "pdfa", tone: "green" },
  "office-to-pdf": { title: "Office → PDF", subtitle: "Word, Excel และ PowerPoint", icon: "office", tone: "orange" },
  "pdf-stamp": { title: "ประทับ PDF", subtitle: "วาง PDF อีกไฟล์เป็นตราประทับ", icon: "stamp", tone: "purple" },
  "signed-link": { title: "ลิงก์ดาวน์โหลด", subtitle: "ลิงก์ชั่วคราวสำหรับแชร์ไฟล์", icon: "link", tone: "sky" },
  archive: { title: "คลังเอกสาร", subtitle: "ส่งเอกสารเข้า Paperless", icon: "archive", tone: "teal" },
};

function Summary({ target, note }: { target: UploadedFile; note: string }) {
  return <div className="v3TaskSummary"><strong>{target.original_name}</strong><small>{note}</small></div>;
}

export function ToolPanel(props: Props) {
  const [pageItems, setPageItems] = useState<Array<{ page: number; rotation: number }>>([]);
  const [pagesLoading, setPagesLoading] = useState(false);
  const mergeFiles = useMemo(() => {
    const byId = new Map(props.pdfFiles.map((file) => [file.id, file]));
    return props.settings.mergeOrder.map((id) => byId.get(id)).filter((file): file is UploadedFile => Boolean(file));
  }, [props.pdfFiles, props.settings.mergeOrder]);
  const availableMergeFiles = useMemo(
    () => props.pdfFiles.filter((file) => !props.settings.mergeOrder.includes(file.id)),
    [props.pdfFiles, props.settings.mergeOrder],
  );

  useEffect(() => {
    if (props.tool !== "split-rotate" || !props.targetIsPdf) return;
    let live = true;
    setPagesLoading(true);
    void getPageInfo(props.target.id, props.auth)
      .then((info) => {
        if (live) setPageItems(Array.from({ length: info.pages }, (_, index) => ({ page: index + 1, rotation: 0 })));
      })
      .finally(() => { if (live) setPagesLoading(false); });
    return () => { live = false; };
  }, [props.tool, props.target.id, props.targetIsPdf, props.auth]);

  function moveMerge(draggedId: string, targetId: string) {
    if (!draggedId || draggedId === targetId) return;
    const ids = mergeFiles.map((file) => file.id);
    const from = ids.indexOf(draggedId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) return;
    const next = [...ids];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    props.onSettingChange("mergeOrder", next);
  }

  function movePage(fromPage: number, toPage: number) {
    if (fromPage === toPage) return;
    const from = pageItems.findIndex((item) => item.page === fromPage);
    const to = pageItems.findIndex((item) => item.page === toPage);
    if (from < 0 || to < 0) return;
    const next = [...pageItems];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setPageItems(next);
  }

  function rotatePage(page: number) {
    setPageItems((old) => old.map((item) => item.page === page ? { ...item, rotation: (item.rotation + 90) % 360 } : item));
  }

  const info = meta[props.tool] || { title: "เครื่องมือ", subtitle: "", icon: "organize" as ToolIconName, tone: "violet" };
  const {
    tool, target, pdfFiles, imageFiles, targetIsPdf, busy, integrations, signedUrl,
  } = props;

  return (
    <section className="v3ToolPanel" data-tone={info.tone}>
      <header className="v3ToolPanelHead">
        <button className="v3BackButton" type="button" onClick={props.onClose} aria-label="กลับไปเลือกเครื่องมือ">←</button>
        <span className="v3ToolPanelIcon"><ToolIcon name={info.icon}/></span>
        <div><h2>{info.title}</h2><p>{info.subtitle}</p></div>
      </header>

      <div className="v3ToolPanelBody">
        {(tool === "images-to-pdf" || tool === "pdf-stamp") && (
          <section className="v3InputReview" aria-label="ไฟล์ที่จะประมวลผล">
            <strong>ตรวจรายการไฟล์ที่เลือก</strong>
            <ol>
              {(tool === "images-to-pdf" ? imageFiles : [target, ...pdfFiles.filter((file) => file.id !== target.id)]).map((file) => (
                <li key={file.id}>{file.original_name}</li>
              ))}
            </ol>
          </section>
        )}
        {tool === "ocr" && <>
          <Summary target={target} note="ภาษาไทย + อังกฤษ • ปรับหน้าเอียงและตรวจทิศทางอัตโนมัติ"/>
          <div className="v3InfoBox">ระบบจะสร้าง PDF ที่ค้นหาข้อความได้ โดยเก็บไฟล์ต้นฉบับไว้เหมือนเดิม</div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("ocr")} disabled={busy || !targetIsPdf}>เริ่ม OCR</button>
        </>}

        {tool === "merge-pdf" && <>
          <div className="v3FieldNote">เลือกเฉพาะไฟล์ที่ต้องการ แล้วลากเพื่อจัดลำดับก่อนรวม</div>
          <div className="v3MergeList">{mergeFiles.map((file, index) => <div
            key={file.id}
            draggable
            onDragStart={(event) => event.dataTransfer.setData("text/plain", file.id)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => { event.preventDefault(); moveMerge(event.dataTransfer.getData("text/plain"), file.id); }}
          ><span>{index + 1}</span><strong>{file.original_name}</strong><b>⠿</b><button type="button" aria-label={`เอา ${file.original_name} ออกจากชุดรวม`} disabled={mergeFiles.length <= 2} onClick={() => props.onSettingChange("mergeOrder", props.settings.mergeOrder.filter((id) => id !== file.id))}>×</button></div>)}</div>
          {availableMergeFiles.length > 0 && <div className="v3MergeAvailable"><small>ไฟล์อื่นใน Workspace</small><div>{availableMergeFiles.map((file) => <button type="button" key={file.id} onClick={() => props.onSettingChange("mergeOrder", [...props.settings.mergeOrder, file.id])}>＋ {file.original_name}</button>)}</div></div>}
          <button className="v3PrimaryAction" onClick={() => props.onRun("merge")} disabled={busy || mergeFiles.length < 2}>รวม PDF {mergeFiles.length} ไฟล์</button>
        </>}

        {tool === "split-rotate" && <>
          <div className="v3FieldNote">ลาก thumbnail เพื่อเรียงหน้าใหม่ • ↻ เพื่อหมุน • × เพื่อตัดหน้าออก</div>
          {pagesLoading ? <div className="v3OrganizerLoading">กำลังอ่านจำนวนหน้า…</div> : <div className="v3PageOrganizer">
            {pageItems.map((item, index) => <div
              className="v3PageThumb"
              key={item.page}
              draggable
              onDragStart={(event) => event.dataTransfer.setData("text/plain", String(item.page))}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => { event.preventDefault(); movePage(Number(event.dataTransfer.getData("text/plain")), item.page); }}
            >
              <div className="v3PageImage" style={{ transform: `rotate(${item.rotation}deg)` }}>
                <Image src={`/api/v1/files/${target.id}/preview?page=${item.page}&width=180`} alt={`หน้า ${item.page}`} width={180} height={240} unoptimized/>
              </div>
              <div><strong>{index + 1}</strong><small>เดิม {item.page}</small></div>
              <button type="button" onClick={() => rotatePage(item.page)} aria-label={`หมุนหน้า ${item.page}`}>↻</button>
              <button type="button" className="danger" onClick={() => setPageItems((old) => old.filter((page) => page.page !== item.page))} aria-label={`ลบหน้า ${item.page}`}>×</button>
            </div>)}
          </div>}
          <button className="v3PrimaryAction" onClick={() => props.onOrganize(pageItems)} disabled={busy || pagesLoading || pageItems.length < 1}>บันทึกการจัดหน้า {pageItems.length} หน้า</button>
          <details className="v3AdvancedDetails"><summary>เลือกหน้าด้วยช่วงตัวเลข</summary>
            <label className="v3Field">หน้าที่ต้องการ<input value={props.settings.splitPages} onChange={(e) => props.onSettingChange("splitPages", e.target.value)} placeholder="1-3,5"/></label>
            <button className="v3SecondaryAction" onClick={() => props.onRun("split")} disabled={busy || !targetIsPdf}>สร้าง PDF จากหน้าที่เลือก</button>
          </details>
        </>}

        {tool === "compress" && <>
          <Summary target={target} note="เหมาะสำหรับส่งอีเมล อัปโหลด และจัดเก็บ"/>
          <button className="v3PrimaryAction" onClick={() => props.onRun("compress")} disabled={busy || !targetIsPdf}>บีบอัด PDF</button>
        </>}

        {tool === "pdf-to-images" && <>
          <div className="v3FieldRow three">
            <label className="v3Field">รูปแบบ<select value={props.settings.rasterFormat} onChange={(e) => props.onSettingChange("rasterFormat", e.target.value)}><option value="png">PNG</option><option value="jpeg">JPEG</option></select></label>
            <label className="v3Field">DPI<input type="number" min="72" max="600" value={props.settings.rasterDpi} onChange={(e) => props.onSettingChange("rasterDpi", Number(e.target.value))}/></label>
            <label className="v3Field">หน้าแรก<input type="number" min="1" value={props.settings.rasterFirstPage} onChange={(e) => props.onSettingChange("rasterFirstPage", Math.max(1, Number(e.target.value)))}/></label>
          </div>
          <label className="v3Field">หน้าสุดท้าย <small>เว้นว่างเพื่อแปลงต่อเนื่อง</small><input type="number" min={props.settings.rasterFirstPage} value={props.settings.rasterLastPage} onChange={(e) => props.onSettingChange("rasterLastPage", e.target.value)}/></label>
          <button className="v3PrimaryAction" onClick={() => props.onRun("pdf-to-images")} disabled={busy || !targetIsPdf}>แปลงเป็น ZIP รูปภาพ</button>
        </>}

        {tool === "images-to-pdf" && <>
          <div className="v3FieldNote">พบรูปภาพ {imageFiles.length} ไฟล์ใน Workspace</div>
          <div className="v3FieldRow three">
            <label className="v3Field">ขนาดหน้า<select value={props.settings.imagePageSize} onChange={(e) => props.onSettingChange("imagePageSize", e.target.value)}><option value="auto">Auto</option><option value="a4">A4</option><option value="letter">Letter</option></select></label>
            <label className="v3Field">การจัดวาง<select value={props.settings.imageFit} onChange={(e) => props.onSettingChange("imageFit", e.target.value)}><option value="contain">พอดีหน้า</option><option value="cover">เต็มหน้า</option></select></label>
            <label className="v3Field">DPI<input type="number" min="72" max="600" value={props.settings.imageDpi} onChange={(e) => props.onSettingChange("imageDpi", Number(e.target.value))}/></label>
          </div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("images-to-pdf")} disabled={busy || imageFiles.length < 1}>สร้าง PDF จากภาพ</button>
        </>}

        {tool === "watermark" && <>
          <label className="v3Field">ข้อความ<input value={props.settings.watermarkText} onChange={(e) => props.onSettingChange("watermarkText", e.target.value)}/></label>
          <div className="v3FieldRow three">
            <label className="v3Field">ขนาด<input type="number" value={props.settings.watermarkFontSize} onChange={(e) => props.onSettingChange("watermarkFontSize", Number(e.target.value))}/></label>
            <label className="v3Field">ความโปร่งใส<input type="number" min="0.02" max="1" step="0.01" value={props.settings.watermarkOpacity} onChange={(e) => props.onSettingChange("watermarkOpacity", Number(e.target.value))}/></label>
            <label className="v3Field">มุม<input type="number" value={props.settings.watermarkRotation} onChange={(e) => props.onSettingChange("watermarkRotation", Number(e.target.value))}/></label>
          </div>
          <label className="v3Field">ตำแหน่ง<select value={props.settings.watermarkPosition} onChange={(e) => props.onSettingChange("watermarkPosition", e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <button className="v3PrimaryAction" onClick={() => props.onRun("watermark")} disabled={busy || !targetIsPdf}>ใส่ลายน้ำ</button>
        </>}

        {tool === "page-numbers" && <>
          <label className="v3Field">รูปแบบ<input value={props.settings.pageFormat} onChange={(e) => props.onSettingChange("pageFormat", e.target.value)}/></label>
          <div className="v3FieldRow">
            <label className="v3Field">เริ่มเลข<input type="number" min="0" value={props.settings.pageStart} onChange={(e) => props.onSettingChange("pageStart", Number(e.target.value))}/></label>
            <label className="v3Field">ตำแหน่ง<select value={props.settings.pagePosition} onChange={(e) => props.onSettingChange("pagePosition", e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          </div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("page-numbers")} disabled={busy || !targetIsPdf}>ใส่เลขหน้า</button>
        </>}

        {tool === "pdfa" && <>
          <Summary target={target} note="แปลงเป็น PDF/A-2 สำหรับงานจัดเก็บระยะยาว"/>
          <button className="v3PrimaryAction" onClick={() => props.onRun("pdfa")} disabled={busy || !targetIsPdf}>แปลงเป็น PDF/A-2</button>
        </>}

        {tool === "office-to-pdf" && <>
          <Summary target={target} note="รองรับเอกสาร Office ที่ระบบประมวลผลได้"/>
          <button className="v3PrimaryAction" onClick={() => props.onRun("office-to-pdf")} disabled={busy}>แปลงเป็น PDF</button>
        </>}

        {tool === "pdf-stamp" && <>
          <label className="v3Field">ไฟล์ตราประทับ<select value={props.settings.stampId} onChange={(e) => props.onSettingChange("stampId", e.target.value)}><option value="">— เลือก PDF —</option>{pdfFiles.filter((file) => file.id !== target.id).map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select></label>
          <div className="v3FieldRow">
            <label className="v3Field">ตำแหน่ง<select value={props.settings.stampPosition} onChange={(e) => props.onSettingChange("stampPosition", e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
            <label className="v3Field">ขนาด<input type="number" min="0.03" max="0.8" step="0.01" value={props.settings.stampScale} onChange={(e) => props.onSettingChange("stampScale", Number(e.target.value))}/></label>
          </div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("stamp")} disabled={busy || !targetIsPdf || !props.settings.stampId}>ประทับ PDF</button>
        </>}

        {tool === "signed-link" && <>
          <Summary target={target} note="ลิงก์จะหมดอายุอัตโนมัติ"/>
          <label className="v3Field">อายุลิงก์ (วินาที)<input type="number" min="30" max="3600" value={props.settings.signedTtl} onChange={(e) => props.onSettingChange("signedTtl", Math.max(30, Number(e.target.value)))}/></label>
          <button className="v3PrimaryAction" onClick={props.onSignedLink} disabled={busy}>สร้างลิงก์ดาวน์โหลด</button>
          {signedUrl && <div className="v3Secret"><strong>ลิงก์พร้อมใช้งาน</strong><code>{signedUrl}</code><div><a href={signedUrl} target="_blank" rel="noreferrer">เปิด</a><button onClick={props.onCopySignedLink}>คัดลอก</button></div></div>}
        </>}

        {tool === "archive" && <>
          <Summary target={target} note={integrations?.paperless_enabled ? "Paperless พร้อมใช้งาน" : "Paperless ยังไม่ได้เปิดใช้"}/>
          <button className="v3PrimaryAction" onClick={props.onArchive} disabled={busy || !targetIsPdf || !integrations?.paperless_enabled}>ส่งเข้าคลังเอกสาร</button>
        </>}
      </div>
    </section>
  );
}

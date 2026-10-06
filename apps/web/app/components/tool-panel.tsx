"use client";

import { IntegrationStatus, UploadedFile } from "../../lib/api";
import { ToolIcon, ToolIconName } from "./tool-icons";

const positionOptions = [
  ["center", "กลาง"],
  ["top-left", "บนซ้าย"], ["top-center", "บนกลาง"], ["top-right", "บนขวา"],
  ["bottom-left", "ล่างซ้าย"], ["bottom-center", "ล่างกลาง"], ["bottom-right", "ล่างขวา"],
] as const;

type Props = {
  tool: string;
  target: UploadedFile;
  pdfFiles: UploadedFile[];
  imageFiles: UploadedFile[];
  targetIsPdf: boolean;
  busy: boolean;
  integrations: IntegrationStatus | null;
  signedUrl: string | null;
  signedTtl: number;
  splitPages: string;
  rotateDegrees: number;
  rotatePages: string;
  watermarkText: string;
  watermarkOpacity: number;
  watermarkRotation: number;
  watermarkFontSize: number;
  watermarkPosition: string;
  pageFormat: string;
  pageStart: number;
  pagePosition: string;
  stampId: string;
  stampPosition: string;
  stampScale: number;
  imagePageSize: string;
  imageFit: string;
  imageDpi: number;
  rasterFormat: string;
  rasterDpi: number;
  rasterFirstPage: number;
  rasterLastPage: string;
  setSignedTtl: (value: number) => void;
  setSplitPages: (value: string) => void;
  setRotateDegrees: (value: number) => void;
  setRotatePages: (value: string) => void;
  setWatermarkText: (value: string) => void;
  setWatermarkOpacity: (value: number) => void;
  setWatermarkRotation: (value: number) => void;
  setWatermarkFontSize: (value: number) => void;
  setWatermarkPosition: (value: string) => void;
  setPageFormat: (value: string) => void;
  setPageStart: (value: number) => void;
  setPagePosition: (value: string) => void;
  setStampId: (value: string) => void;
  setStampPosition: (value: string) => void;
  setStampScale: (value: number) => void;
  setImagePageSize: (value: string) => void;
  setImageFit: (value: string) => void;
  setImageDpi: (value: number) => void;
  setRasterFormat: (value: string) => void;
  setRasterDpi: (value: number) => void;
  setRasterFirstPage: (value: number) => void;
  setRasterLastPage: (value: string) => void;
  onRun: (operation: string) => void;
  onSignedLink: () => void;
  onCopySignedLink: () => void;
  onArchive: () => void;
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
        {tool === "ocr" && <>
          <Summary target={target} note="ภาษาไทย + อังกฤษ • ปรับหน้าเอียงและตรวจทิศทางอัตโนมัติ"/>
          <div className="v3InfoBox">ระบบจะสร้าง PDF ที่ค้นหาข้อความได้ โดยเก็บไฟล์ต้นฉบับไว้เหมือนเดิม</div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("ocr")} disabled={busy || !targetIsPdf}>เริ่ม OCR</button>
        </>}

        {tool === "merge-pdf" && <>
          <div className="v3FieldNote">จะรวม PDF {pdfFiles.length} ไฟล์ตามลำดับด้านล่าง</div>
          <div className="v3MergeList">{pdfFiles.map((file, index) => <div key={file.id}><span>{index + 1}</span><strong>{file.original_name}</strong></div>)}</div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("merge")} disabled={busy || pdfFiles.length < 2}>รวม PDF {pdfFiles.length} ไฟล์</button>
        </>}

        {tool === "split-rotate" && <>
          <label className="v3Field">หน้าที่ต้องการ<input value={props.splitPages} onChange={(e) => props.setSplitPages(e.target.value)} placeholder="1-3,5"/></label>
          <button className="v3PrimaryAction" onClick={() => props.onRun("split")} disabled={busy || !targetIsPdf}>สร้าง PDF จากหน้าที่เลือก</button>
          <div className="v3Divider"/>
          <div className="v3FieldRow">
            <label className="v3Field">หมุน<select value={props.rotateDegrees} onChange={(e) => props.setRotateDegrees(Number(e.target.value))}><option value={90}>+90°</option><option value={180}>180°</option><option value={270}>+270°</option><option value={-90}>-90°</option></select></label>
            <label className="v3Field">หน้า<input value={props.rotatePages} onChange={(e) => props.setRotatePages(e.target.value)}/></label>
          </div>
          <button className="v3SecondaryAction" onClick={() => props.onRun("rotate")} disabled={busy || !targetIsPdf}>หมุนหน้า</button>
        </>}

        {tool === "compress" && <>
          <Summary target={target} note="เหมาะสำหรับส่งอีเมล อัปโหลด และจัดเก็บ"/>
          <button className="v3PrimaryAction" onClick={() => props.onRun("compress")} disabled={busy || !targetIsPdf}>บีบอัด PDF</button>
        </>}

        {tool === "pdf-to-images" && <>
          <div className="v3FieldRow three">
            <label className="v3Field">รูปแบบ<select value={props.rasterFormat} onChange={(e) => props.setRasterFormat(e.target.value)}><option value="png">PNG</option><option value="jpeg">JPEG</option></select></label>
            <label className="v3Field">DPI<input type="number" min="72" max="600" value={props.rasterDpi} onChange={(e) => props.setRasterDpi(Number(e.target.value))}/></label>
            <label className="v3Field">หน้าแรก<input type="number" min="1" value={props.rasterFirstPage} onChange={(e) => props.setRasterFirstPage(Math.max(1, Number(e.target.value)))}/></label>
          </div>
          <label className="v3Field">หน้าสุดท้าย <small>เว้นว่างเพื่อแปลงต่อเนื่อง</small><input type="number" min={props.rasterFirstPage} value={props.rasterLastPage} onChange={(e) => props.setRasterLastPage(e.target.value)}/></label>
          <button className="v3PrimaryAction" onClick={() => props.onRun("pdf-to-images")} disabled={busy || !targetIsPdf}>แปลงเป็น ZIP รูปภาพ</button>
        </>}

        {tool === "images-to-pdf" && <>
          <div className="v3FieldNote">พบรูปภาพ {imageFiles.length} ไฟล์ใน Workspace</div>
          <div className="v3FieldRow three">
            <label className="v3Field">ขนาดหน้า<select value={props.imagePageSize} onChange={(e) => props.setImagePageSize(e.target.value)}><option value="auto">Auto</option><option value="a4">A4</option><option value="letter">Letter</option></select></label>
            <label className="v3Field">การจัดวาง<select value={props.imageFit} onChange={(e) => props.setImageFit(e.target.value)}><option value="contain">พอดีหน้า</option><option value="cover">เต็มหน้า</option></select></label>
            <label className="v3Field">DPI<input type="number" min="72" max="600" value={props.imageDpi} onChange={(e) => props.setImageDpi(Number(e.target.value))}/></label>
          </div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("images-to-pdf")} disabled={busy || imageFiles.length < 1}>สร้าง PDF จากภาพ</button>
        </>}

        {tool === "watermark" && <>
          <label className="v3Field">ข้อความ<input value={props.watermarkText} onChange={(e) => props.setWatermarkText(e.target.value)}/></label>
          <div className="v3FieldRow three">
            <label className="v3Field">ขนาด<input type="number" value={props.watermarkFontSize} onChange={(e) => props.setWatermarkFontSize(Number(e.target.value))}/></label>
            <label className="v3Field">ความโปร่งใส<input type="number" min="0.02" max="1" step="0.01" value={props.watermarkOpacity} onChange={(e) => props.setWatermarkOpacity(Number(e.target.value))}/></label>
            <label className="v3Field">มุม<input type="number" value={props.watermarkRotation} onChange={(e) => props.setWatermarkRotation(Number(e.target.value))}/></label>
          </div>
          <label className="v3Field">ตำแหน่ง<select value={props.watermarkPosition} onChange={(e) => props.setWatermarkPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <button className="v3PrimaryAction" onClick={() => props.onRun("watermark")} disabled={busy || !targetIsPdf}>ใส่ลายน้ำ</button>
        </>}

        {tool === "page-numbers" && <>
          <label className="v3Field">รูปแบบ<input value={props.pageFormat} onChange={(e) => props.setPageFormat(e.target.value)}/></label>
          <div className="v3FieldRow">
            <label className="v3Field">เริ่มเลข<input type="number" min="0" value={props.pageStart} onChange={(e) => props.setPageStart(Number(e.target.value))}/></label>
            <label className="v3Field">ตำแหน่ง<select value={props.pagePosition} onChange={(e) => props.setPagePosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
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
          <label className="v3Field">ไฟล์ตราประทับ<select value={props.stampId} onChange={(e) => props.setStampId(e.target.value)}><option value="">— เลือก PDF —</option>{pdfFiles.filter((file) => file.id !== target.id).map((file) => <option value={file.id} key={file.id}>{file.original_name}</option>)}</select></label>
          <div className="v3FieldRow">
            <label className="v3Field">ตำแหน่ง<select value={props.stampPosition} onChange={(e) => props.setStampPosition(e.target.value)}>{positionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
            <label className="v3Field">ขนาด<input type="number" min="0.03" max="0.8" step="0.01" value={props.stampScale} onChange={(e) => props.setStampScale(Number(e.target.value))}/></label>
          </div>
          <button className="v3PrimaryAction" onClick={() => props.onRun("stamp")} disabled={busy || !targetIsPdf || !props.stampId}>ประทับ PDF</button>
        </>}

        {tool === "signed-link" && <>
          <Summary target={target} note="ลิงก์จะหมดอายุอัตโนมัติ"/>
          <label className="v3Field">อายุลิงก์ (วินาที)<input type="number" min="30" max="3600" value={props.signedTtl} onChange={(e) => props.setSignedTtl(Math.max(30, Number(e.target.value)))}/></label>
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

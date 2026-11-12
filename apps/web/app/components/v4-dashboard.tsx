"use client";

import Link from "next/link";

import { ArrowRight, ArrowUpRight, Clock3, CloudUpload, FileText, FolderOpen, LayoutGrid, Sparkles, Workflow } from "lucide-react";
import type { Job, UploadedFile } from "../../lib/api";
import type { ToolDefinition } from "./v3-ui";
import { ToolIcon } from "./tool-icons";

function friendlySize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function V4Dashboard({
  files, jobs, tools, busy, onFiles, onSelectFile, onTool,
}: {
  files: UploadedFile[];
  jobs: Job[];
  tools: ToolDefinition[];
  busy: boolean;
  onFiles: (files: FileList | null) => void;
  onSelectFile: (id: string) => void;
  onTool: (tool: ToolDefinition) => void;
}) {
  const running = jobs.filter(job => job.status === "queued" || job.status === "running");
  const recentTools = tools.slice(0, 6);
  return (
    <main className="v3Main v4Main v4Dashboard" id="workspace">
      <section className="v4PageIntro">
        <div>
          <span className="v4Eyebrow"><Sparkles aria-hidden="true" size={15}/> RCAT DOCUMENT STUDIO</span>
          <h1>งานเอกสาร ง่ายขึ้นในที่เดียว</h1>
          <p>เลือกไฟล์ เลือกเครื่องมือ และจัดการงาน PDF ได้อย่างเป็นขั้นตอน</p>
        </div>
        <Link prefetch={false} className="v4SecondaryButton" href="/tools"><LayoutGrid aria-hidden="true" size={18}/> สำรวจเครื่องมือ <ArrowRight aria-hidden="true" size={17}/></Link>
      </section>

      <div className="v4OverviewStats" aria-label="ข้อมูลภาพรวมพื้นที่ทำงาน">
        <Link prefetch={false} href="/files" className="v4StatCard"><span><FolderOpen aria-hidden="true" size={20}/> ไฟล์ในรายการล่าสุด</span><strong>{files.length.toLocaleString("th-TH")}</strong><small>เปิดคลังไฟล์ <ArrowUpRight aria-hidden="true" size={14}/></small></Link>
        <Link prefetch={false} href="/jobs" className="v4StatCard"><span><Workflow aria-hidden="true" size={20}/> งานที่กำลังดำเนินการ</span><strong>{running.length.toLocaleString("th-TH")}</strong><small>ดูสถานะงาน <ArrowUpRight aria-hidden="true" size={14}/></small></Link>
        <Link prefetch={false} href="/jobs" className="v4StatCard"><span><Clock3 aria-hidden="true" size={20}/> ประวัติงานล่าสุด</span><strong>{jobs.length.toLocaleString("th-TH")}</strong><small>ดูประวัติ <ArrowUpRight aria-hidden="true" size={14}/></small></Link>
      </div>

      <section className="v4DashboardCore" aria-label="เริ่มใช้งาน">
        <div className="v4UploadPanel">
          <div className="v4PanelHeading">
            <span className="v4SectionOverline">START A WORKFLOW / 01</span>
            <h2>เริ่มจากไฟล์ของคุณ</h2>
            <p>เพิ่มไฟล์เพื่อเลือกขั้นตอนการจัดการเอกสารที่เหมาะสม</p>
          </div>
          <div className="v3Dropzone v4Dropzone" onDragOver={event => { event.preventDefault(); event.currentTarget.classList.add("isDragging"); }}
            onDragLeave={event => event.currentTarget.classList.remove("isDragging")}
            onDrop={event => { event.preventDefault(); event.currentTarget.classList.remove("isDragging"); onFiles(event.dataTransfer.files); }}>
            <input id="files" type="file" multiple disabled={busy} onChange={event => onFiles(event.target.files)}/>
            <label htmlFor="files">
              <span className="v4UploadIcon"><CloudUpload aria-hidden="true" size={32} strokeWidth={1.8}/></span>
              <strong>ลากไฟล์มาวาง หรือคลิกเพื่อเลือก</strong>
              <p>รองรับ PDF · Word · Excel · PowerPoint · รูปภาพ</p>
              <span className="v3UploadButton v4PrimaryButton">เลือกไฟล์จากเครื่อง <ArrowUpRight aria-hidden="true" size={15}/></span>
            </label>
          </div>
          <div className="v4FlowHint"><span>01 <strong>เพิ่มไฟล์</strong></span><ArrowRight aria-hidden="true" size={16}/><span>02 <strong>เลือกเครื่องมือ</strong></span><ArrowRight aria-hidden="true" size={16}/><span>03 <strong>รับผลลัพธ์</strong></span></div>
        </div>

        <section className="v4QuickPanel" aria-labelledby="v4-quick-heading">
          <div className="v4PanelHeading">
            <span className="v4SectionOverline">QUICK ACCESS / 02</span>
            <h2 id="v4-quick-heading">ทางลัดเครื่องมือ</h2>
            <p>เลือกการทำงานที่ใช้งานบ่อย</p>
          </div>
          <div className="v4QuickTools">
            {recentTools.map((tool) => (
              <button type="button" className="v4QuickTool" key={tool.id} onClick={() => onTool(tool)}>
                <span className="v4QuickIcon"><ToolIcon name={tool.icon}/></span>
                <span className="v4QuickToolCopy"><strong>{tool.title}</strong><small>{tool.description}</small></span>
                <ArrowUpRight aria-hidden="true" size={17} />
              </button>
            ))}
          </div>
          <Link prefetch={false} className="v4TextAction" href="/tools">เครื่องมือทั้งหมด <ArrowRight aria-hidden="true" size={16}/></Link>
        </section>
      </section>

      <section className="v4RecentSection" aria-labelledby="v4-recent-heading">
        <div className="v4SectionTitle"><div><span className="v4SectionOverline">YOUR DOCUMENTS</span><h2 id="v4-recent-heading">ไฟล์ล่าสุด</h2></div><Link prefetch={false} href="/files">ดูคลังไฟล์ <ArrowRight aria-hidden="true" size={17}/></Link></div>
        <div className="v4RecentList">
          {files.length === 0 && <div className="v4EmptyState"><FileText aria-hidden="true" size={28}/><strong>ยังไม่มีไฟล์ในพื้นที่ทำงาน</strong><p>เริ่มต้นโดยเพิ่มไฟล์ด้านบน</p></div>}
          {files.slice(0, 4).map(file => (
            <button type="button" className="v3RecentFile v4RecentFile" key={file.id} onClick={() => onSelectFile(file.id)}>
              <span className="v4FileIcon"><FileText aria-hidden="true" size={20}/></span>
              <span className="v4RecentFileName"><strong>{file.original_name}</strong><small>{friendlySize(file.size)} · {new Date(file.created_at).toLocaleDateString("th-TH")}</small></span>
              <ArrowUpRight aria-hidden="true" size={17}/>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

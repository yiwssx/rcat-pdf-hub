"use client";

import { useMemo, useState } from "react";
import type { UploadedFile } from "../../lib/api";
import type { ToolDefinition } from "./v3-ui";
import { isEligibleToolFile, TOOL_INPUT_RULES, validateToolInputs } from "./tool-input-rules";

type Props = {
  tool: ToolDefinition;
  files: UploadedFile[];
  selectedIds: string[];
  busy: boolean;
  onChange: (ids: string[]) => void;
  onUpload: (files: FileList | null) => void;
  onContinue: (ids: string[]) => void;
};

export function ToolFileIntake({ tool, files, selectedIds, busy, onChange, onUpload, onContinue }: Props) {
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const rule = TOOL_INPUT_RULES[tool.id];
  const eligible = useMemo(() => files.filter((file) => isEligibleToolFile(tool.id, file)), [files, tool.id]);
  const displayed = eligible.filter((file) => file.original_name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())).slice(0, 100);
  const selected = selectedIds.map((id) => files.find((file) => file.id === id)).filter((file): file is UploadedFile => Boolean(file));
  const multi = !rule.max || rule.max > 1;
  const validation = selected.length !== selectedIds.length ? "ไฟล์บางรายการไม่อยู่ในคลังไฟล์ที่คุณเข้าถึงได้" : validateToolInputs(tool.id, selected);

  function toggle(id: string) {
    setError("");
    if (!multi) {
      onChange([id]);
    } else {
      onChange(selectedIds.includes(id) ? selectedIds.filter((value) => value !== id) : [...selectedIds, id]);
    }
  }

  function reorder(id: string, step: number) {
    const from = selectedIds.indexOf(id);
    const to = from + step;
    if (from < 0 || to < 0 || to >= selectedIds.length) return;
    const copy = [...selectedIds];
    [copy[from], copy[to]] = [copy[to], copy[from]];
    onChange(copy);
  }

  function continueTask() {
    if (validation) {
      setError(validation);
      return;
    }
    onContinue(selectedIds);
  }

  return (
    <main className="v3Main" id="workspace">
      <section className="v3HomeTitle">
        <div>
          <span className="v3Kicker">ขั้นตอนที่ 1 · เลือกไฟล์</span>
          <h1>{tool.title}</h1>
          <p>{tool.description} — เลือกเฉพาะไฟล์ที่จะใช้ ระบบจะไม่เพิ่มไฟล์อื่นให้อัตโนมัติ</p>
        </div>
        <a className="v3TextLink" href="/">← เครื่องมือทั้งหมด</a>
      </section>
      <section className="v3StartGrid" aria-label="เลือกไฟล์สำหรับเครื่องมือ">
        <div className="v3Dropzone">
          <input id="files" type="file" accept={rule.accept} multiple={multi} disabled={busy} onChange={(event) => { onUpload(event.currentTarget.files); event.currentTarget.value = ""; }}/>
          <label htmlFor="files">
            <span className="v3DropIcon">＋</span>
            <strong>อัปโหลดไฟล์สำหรับ {tool.title}</strong>
            <p>ไฟล์ใหม่จะปรากฏในรายการเลือกด้านข้าง</p>
            <span className="v3UploadButton">เลือกไฟล์จากเครื่อง</span>
          </label>
        </div>
        <div className="v3RecentCard">
          <div className="v3SectionHead">
            <div><span className="v3Kicker">MY FILES</span><h2>เลือกจากคลังไฟล์</h2></div>
            <a href="/files">เปิดคลังไฟล์</a>
          </div>
          <label className="v3Field">
            ค้นหาชื่อไฟล์
            <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ค้นหาไฟล์ที่รองรับ" />
          </label>
          <div className="v3RecentList" aria-label="ไฟล์ที่รองรับ">
            {displayed.length === 0 && <p className="v3EmptyMini">ไม่พบไฟล์ที่รองรับเครื่องมือนี้</p>}
            {displayed.map((file) => (
              <label key={file.id} className="v3RecentFile">
                <input type={multi ? "checkbox" : "radio"} name={multi ? undefined : "tool-input"} checked={selectedIds.includes(file.id)} onChange={() => toggle(file.id)} aria-label={file.original_name} />
                <span><strong>{file.original_name}</strong><small>{file.content_type}</small></span>
              </label>
            ))}
          </div>
          {eligible.length > 100 && <small>แสดงสูงสุด 100 รายการจาก {eligible.length} รายการ · ใช้ช่องค้นหาเพื่อเลือกไฟล์อื่น</small>}
        </div>
      </section>
      <section className="v3RecentCard" aria-label="ตรวจรายการไฟล์ก่อนดำเนินการ">
        <div className="v3SectionHead"><div><span className="v3Kicker">REVIEW INPUTS</span><h2>ไฟล์ที่เลือก {selected.length} รายการ</h2></div></div>
        {selected.length === 0 && <p>ยังไม่ได้เลือกไฟล์</p>}
        <div className="v3RecentList">
          {selected.map((file, i) => (
            <div className="v3RecentFile" key={file.id}>
              <span>{i + 1}</span><span><strong>{file.original_name}</strong></span>
              {multi && <span>
                <button type="button" aria-label={`เลื่อน ${file.original_name} ขึ้น`} disabled={i === 0} onClick={() => reorder(file.id, -1)}>↑</button>
                <button type="button" aria-label={`เลื่อน ${file.original_name} ลง`} disabled={i === selected.length - 1} onClick={() => reorder(file.id, 1)}>↓</button>
              </span>}
              <button type="button" aria-label={`นำ ${file.original_name} ออก`} onClick={() => onChange(selectedIds.filter((id) => id !== file.id))}>×</button>
            </div>
          ))}
        </div>
        {(validation || error) && <p role="status">{error || validation}</p>}
        <button type="button" className="v3PrimaryAction" disabled={busy || Boolean(validation)} onClick={continueTask}>ตั้งค่าและดำเนินการ →</button>
      </section>
    </main>
  );
}

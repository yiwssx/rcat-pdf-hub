"use client";

import { useMemo, useState } from "react";
import { toolSearchTerms, FEATURED_T90_TOOL_IDS } from "./t90-search-metadata";
import {
  T90_DIRECTORY_COUNTS,
  T90_DIRECTORY_TOOLS,
  type T90DirectoryFamily,
} from "./t90-directory-catalog";

type DirectoryFilter = "all" | T90DirectoryFamily;

const GROUPS: ReadonlyArray<{ id: DirectoryFilter; title: string; count: number }> = [
  { id: "all", title: "ทั้งหมด", count: 90 },
  { id: "manage", title: "จัดการ PDF", count: T90_DIRECTORY_COUNTS.manage },
  { id: "to_pdf", title: "แปลงเป็น PDF", count: T90_DIRECTORY_COUNTS.to_pdf },
  { id: "from_pdf", title: "แปลงจาก PDF", count: T90_DIRECTORY_COUNTS.from_pdf },
];

const FAMILY_TITLES: Readonly<Record<T90DirectoryFamily, string>> = {
  manage: "จัดการ PDF",
  to_pdf: "แปลงเป็น PDF",
  from_pdf: "แปลงจาก PDF",
};

function destination(href: string, selectedFileId?: string): string {
  if (!selectedFileId) return href;
  return href + (href.includes("?") ? "&" : "?")
    + "file=" + encodeURIComponent(selectedFileId);
}

export function InstitutionalT90Directory({ selectedFileId }: {
  selectedFileId?: string;
}) {
  const [filter, setFilter] = useState<DirectoryFilter>("all");
  const [search, setSearch] = useState("");
  const visible = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return T90_DIRECTORY_TOOLS.filter((tool) =>
      (filter === "all" || tool.category === filter)
      && (!query || (tool.id + " " + tool.title + " " + FAMILY_TITLES[tool.category] + " " + toolSearchTerms(tool.id))
        .toLocaleLowerCase().includes(query))
    );
  }, [filter, search]);

  const featured = !search.trim() && filter === "all"
    ? T90_DIRECTORY_TOOLS.filter((tool) => FEATURED_T90_TOOL_IDS.includes(tool.id))
    : [];
  const sections = (filter === "all" && !search.trim())
    ? GROUPS.filter((group): group is typeof GROUPS[number] & { id: T90DirectoryFamily } => group.id !== "all")
    : [{ id: filter, title: "ผลการค้นหา", count: visible.length }] as const;

  function toolCard(tool: typeof T90_DIRECTORY_TOOLS[number]) {
    return (
      <a
        key={tool.id}
        className="v3ToolCard t90DirectoryTool"
        data-tone={tool.category === "manage" ? "blue" : tool.category === "to_pdf" ? "orange" : "violet"}
        href={destination(tool.href, selectedFileId)}
        aria-label={tool.title + " รหัส " + tool.id}
      >
        <span className="t90DirectoryCode" aria-hidden="true">{tool.id}</span>
        <span className="v3ToolCardText"><strong>{tool.title}</strong><small>{FAMILY_TITLES[tool.category]}</small></span>
        <b aria-hidden="true">›</b>
      </a>
    );
  }

  return (
    <section className="v3ToolsBlock t90Directory" id="t90-tools" aria-labelledby="t90-tools-heading">
      <div className="v3SectionHead">
        <div>
          <span className="v3Kicker">RCAT PDF HUB · T90</span>
          <h2 id="t90-tools-heading">เครื่องมือ PDF ทั้ง 90 รายการ</h2>
          <p>จัดการ PDF 33 · แปลงเป็น PDF 40 · แปลงจาก PDF 17 — เลือกเครื่องมือเพื่อเปิดขั้นตอนทำงาน</p>
        </div>
        <span className="t90DirectoryTotal" aria-label="จำนวนเครื่องมือในสารบัญ">90 เครื่องมือ</span>
      </div>
      <div className="t90DirectoryControls">
        <label className="t90DirectorySearch">
          <span>ค้นหาเครื่องมือ</span>
          <input
            aria-label="ค้นหาเครื่องมือ T90"
            type="search"
            value={search}
            maxLength={100}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="เช่น รวมไฟล์ ย่อ PDF Word เป็น PDF หรือ OCR…"
          />
        </label>
        {search && <button className="t90DirectoryClear" type="button" onClick={() => { setSearch(""); setFilter("all"); }}>ล้างคำค้นหา</button>}
        <div className="t90DirectoryFilters" role="group" aria-label="ประเภทเครื่องมือ PDF">
          {GROUPS.map((group) => (
            <button
              key={group.id}
              type="button"
              aria-pressed={filter === group.id}
              className={filter === group.id ? "isActive" : ""}
              onClick={() => setFilter(group.id)}
            >
              {group.title} <span>{group.count}</span>
            </button>
          ))}
        </div>
      </div>
      <p className="t90DirectoryFound" role="status">แสดง {visible.length} จาก 90 เครื่องมือ</p>
      {featured.length > 0 && (
        <section className="t90DirectorySection" aria-labelledby="t90-featured-heading">
          <h3 id="t90-featured-heading">งานที่ใช้บ่อย</h3>
          <div className="v3ToolGrid t90DirectoryGrid">{featured.map(toolCard)}</div>
        </section>
      )}
      {visible.length === 0 ? (
        <div className="v3EmptyMini" role="status">
          ไม่พบเครื่องมือที่ตรงกับคำค้นหา ลองชื่อประเภทไฟล์หรือคำอื่น
          <button type="button" className="t90DirectoryClear" onClick={() => { setSearch(""); setFilter("all"); }}>แสดงเครื่องมือทั้งหมด</button>
        </div>
      ) : sections.map((group) => {
        const groupTools = group.id === "all" ? visible : visible.filter((tool) => tool.category === group.id);
        if (!groupTools.length) return null;
        return (
          <section className="t90DirectorySection" key={group.id} aria-label={group.title}>
            <div className="t90DirectorySectionHeading"><h3>{group.title}</h3><span>{groupTools.length} เครื่องมือ</span></div>
            <div className="v3ToolGrid t90DirectoryGrid">{groupTools.map(toolCard)}</div>
          </section>
        );
      })}
      <p className="t90DirectoryNote">
        เครื่องมือใช้ Workflow ที่เปิดใช้สำหรับบัญชี RCAT ตามสิทธิ์ที่ได้รับ
        การรองรับแต่ละรูปแบบมีขอบเขตจำกัด และการตรวจรับรายเครื่องมือยังแยกจากการ Deploy
      </p>
    </section>
  );
}

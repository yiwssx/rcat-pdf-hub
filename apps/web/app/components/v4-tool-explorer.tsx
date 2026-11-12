"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, ChevronLeft, ChevronRight, FileText, LayoutGrid, Search, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { T90_DIRECTORY_TOOLS, T90_DIRECTORY_COUNTS, type T90DirectoryFamily } from "./t90-directory-catalog";
import { FEATURED_T90_TOOL_IDS, toolSearchTerms } from "./t90-search-metadata";
import { getT90Icon } from "./v4-tool-icons";
import { Input } from "@/components/ui/input";
import type { ToolDefinition } from "./v3-ui";
import { ToolIcon } from "./tool-icons";

type Group = "all" | T90DirectoryFamily;
const GROUPS: readonly { id: Group; label: string; count: number }[] = [
  { id: "all", label: "ทั้งหมด", count: 90 },
  { id: "manage", label: "จัดการ PDF", count: T90_DIRECTORY_COUNTS.manage },
  { id: "to_pdf", label: "แปลงเป็น PDF", count: T90_DIRECTORY_COUNTS.to_pdf },
  { id: "from_pdf", label: "แปลงจาก PDF", count: T90_DIRECTORY_COUNTS.from_pdf },
];
const FAMILY_LABELS: Record<T90DirectoryFamily, string> = {
  manage: "จัดการ PDF", to_pdf: "แปลงเป็น PDF", from_pdf: "แปลงจาก PDF",
};
const PAGE_SIZE = 12;
type ExplorerTool = (typeof T90_DIRECTORY_TOOLS)[number];
function ToolDetailContent({ tool }: { tool: ExplorerTool }) {
  const Icon = getT90Icon(tool.id);
  return <>
    <div className="v4DetailOverline">TOOL DETAIL <span>{tool.id}</span></div>
    <span className="v4DetailIcon" data-family={tool.category}><Icon aria-hidden="true" size={35} strokeWidth={1.6}/></span>
    <h2>{tool.title}</h2><p>{FAMILY_LABELS[tool.category]}</p>
    <div className="v4ToolNotice">การใช้งานจริงขึ้นอยู่กับสิทธิ์และสถานะที่ระบบอนุญาต ไม่รับรองว่าเครื่องมือนี้เปิดใช้งานแล้ว</div>
    <a className="v4PrimaryButton" href={tool.href}>เปิดหน้าเครื่องมือ <ArrowRight aria-hidden="true" size={18}/></a>
    <details className="v4ToolAdvanced"><summary>รายละเอียดเส้นทางและการเข้าถึง</summary>
      <p>รหัสเครื่องมือ: {tool.id}</p><p>เส้นทาง: <code>{tool.href}</code></p>
      <p>ยืนยันสิทธิ์จริงเมื่อเข้าสู่หน้าการทำงาน</p>
    </details>
  </>;
}

export function V4ToolExplorer({ catalogEnabled, tools }: { catalogEnabled: boolean; tools: ToolDefinition[] }) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<Group>("all");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const mobileDetailRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const sync = () => {
      const id = new URLSearchParams(window.location.search).get("tool");
      const valid = id && /^[MTF]\d{2}$/.test(id) ? id : null;
      setSelectedId(valid);
      const dialog = mobileDetailRef.current;
      if (valid && window.matchMedia("(max-width: 760px)").matches && !dialog?.open) dialog?.showModal();
      else if ((!valid || !window.matchMedia("(max-width: 760px)").matches) && dialog?.open) dialog.close();
    };
    sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const results = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    if (!catalogEnabled) return [];
    return T90_DIRECTORY_TOOLS.filter(tool =>
      (group === "all" || tool.category === group) &&
      (!term || `${tool.title} ${tool.id} ${FAMILY_LABELS[tool.category]} ${toolSearchTerms(tool.id)}`.toLocaleLowerCase().includes(term))
    );
  }, [catalogEnabled, group, query]);
  const featured = catalogEnabled
    ? FEATURED_T90_TOOL_IDS.map(id => T90_DIRECTORY_TOOLS.find(tool => tool.id === id)).filter((item): item is typeof T90_DIRECTORY_TOOLS[number] => Boolean(item))
    : [];
  const pages = Math.max(1, Math.ceil(results.length / PAGE_SIZE));
  const visible = results.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const selected = selectedId ? T90_DIRECTORY_TOOLS.find(item => item.id === selectedId) : null;
  const active = selected && catalogEnabled ? selected : visible[0] ?? null;

  function chooseTool(id: string) {
    setSelectedId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("tool", id);
    window.history.pushState({ tool: id }, "", url.pathname + url.search + url.hash);
    if (window.matchMedia("(max-width: 760px)").matches && !mobileDetailRef.current?.open) {
      mobileDetailRef.current?.showModal();
    }
  }
  function clearToolSelection() {
    setSelectedId(null);
    mobileDetailRef.current?.close();
    const url = new URL(window.location.href);
    if (url.searchParams.has("tool")) {
      url.searchParams.delete("tool");
      window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    }
  }
  function changeGroup(next: Group) { setGroup(next); setPage(1); clearToolSelection(); }
  function changeQuery(next: string) { setQuery(next); setPage(1); clearToolSelection(); }

  return (
    <main className="v4Main v4Explorer" id="workspace">
      <header className="v4PageIntro v4ExplorerIntro">
        <div>
          <span className="v4Eyebrow"><LayoutGrid aria-hidden="true" size={16}/> TOOL EXPLORER</span>
          <h1>ค้นหาเครื่องมือ PDF</h1>
          <p>{catalogEnabled ? "เลือกจากสารบัญ 90 เครื่องมือ แยกตามประเภทงานเพื่อให้หาได้เร็วขึ้น" : "เครื่องมือที่เปิดให้เลือกสำหรับพื้นที่ทำงานนี้"}</p>
        </div>
        <div className="v4ExplorerCounter"><strong>{catalogEnabled ? 90 : tools.length}</strong><span>รายการในสารบัญ</span></div>
      </header>

      {catalogEnabled ? (
        <>
          <div className="v4ExplorerSearch">
            <Search aria-hidden="true" size={21}/>
            <Input type="search" aria-label="ค้นหาเครื่องมือ T90" value={query} maxLength={100}
              onChange={event => changeQuery(event.target.value)}
              placeholder="ค้นหา เช่น OCR, รวมไฟล์, Word, ย่อ PDF..." />
            <span><SlidersHorizontal aria-hidden="true" size={17}/> ค้นหาตามงาน</span>
          </div>
          <div className="v4ExplorerLayout">
            <aside className="v4CategoryRail" aria-label="หมวดเครื่องมือ">
              <div className="v4SectionOverline">CATEGORIES</div>
              <nav className="v4CategoryNav" aria-label="ประเภทเครื่องมือ PDF">
                {GROUPS.map(item => <button key={item.id} type="button"
                  aria-pressed={group === item.id} onClick={() => changeGroup(item.id)}>
                  <span>{item.label}</span><em>{item.count}</em>
                </button>)}
              </nav>
              <p>รายการในสารบัญไม่ใช่การรับรองว่าเครื่องมือทุกตัวพร้อมใช้งาน สิทธิ์และเงื่อนไขกำหนดโดยระบบเดิม</p>
            </aside>

            <section className="v4ToolResults" aria-label="ผลการค้นหาเครื่องมือ">
              <div className="v4ResultsHead">
                <div><span className="v4SectionOverline">BROWSE TOOLS</span><h2>{group === "all" ? "รายการเครื่องมือ" : GROUPS.find(item => item.id === group)?.label}</h2></div>
                <span role="status">{results.length} รายการ</span>
              </div>
              {!query && group === "all" && <div className="v4FeaturedStrip" aria-label="ทางลัดที่แนะนำ">
                <Sparkles aria-hidden="true" size={17}/><span>ทางลัด:</span>
                {featured.slice(0, 4).map(tool => <button type="button" key={tool.id} onClick={() => { chooseTool(tool.id); setPage(Math.ceil((results.findIndex(x => x.id === tool.id) + 1) / PAGE_SIZE)); }}>{tool.title}</button>)}
              </div>}
              {results.length === 0 ? (
                <div className="v4EmptyState" role="status"><Search aria-hidden="true" size={28}/><strong>ไม่พบเครื่องมือที่ตรงกับคำค้น</strong><button type="button" onClick={() => { changeQuery(""); changeGroup("all"); }}>ล้างคำค้นหา</button></div>
              ) : (
                <div className="v4ToolList">
                  {visible.map(tool => {
                    const Icon = getT90Icon(tool.id);
                    return <button key={tool.id} type="button" className="v4ToolListItem"
                      aria-pressed={active?.id === tool.id} onClick={() => chooseTool(tool.id)}>
                      <span className="v4ToolSymbol" data-family={tool.category}><Icon aria-hidden="true" size={22} strokeWidth={1.8}/></span>
                      <span className="v4ToolListCopy"><strong>{tool.title}</strong><small>{FAMILY_LABELS[tool.category]} · {tool.id}</small></span>
                      <ArrowUpRight aria-hidden="true" size={17}/>
                    </button>;
                  })}
                </div>
              )}
              {results.length > PAGE_SIZE && <nav className="v4ToolPagination" aria-label="หน้ารายการเครื่องมือ">
                <button type="button" disabled={page <= 1} onClick={() => setPage(p => p - 1)} aria-label="หน้าก่อนหน้า"><ChevronLeft aria-hidden="true" size={18}/></button>
                <span>หน้า {page} / {pages}</span>
                <button type="button" disabled={page >= pages} onClick={() => setPage(p => p + 1)} aria-label="หน้าถัดไป"><ChevronRight aria-hidden="true" size={18}/></button>
              </nav>}
            </section>

            <aside className="v4ToolDetail" aria-label="รายละเอียดเครื่องมือที่เลือก">
              {active ? <ToolDetailContent tool={active} /> : <p>เลือกเครื่องมือจากรายการเพื่อดูรายละเอียด</p>}
            </aside>
            <dialog ref={mobileDetailRef} className="v4ToolDialog" aria-label="รายละเอียดเครื่องมือที่เลือก">
              <button className="v4ToolDialogClose" type="button" aria-label="ปิดรายละเอียด" onClick={() => mobileDetailRef.current?.close()}>
                <X aria-hidden="true" size={19}/>
              </button>
              {active && <ToolDetailContent tool={active} />}
            </dialog>
          </div>
        </>
      ) : (
        <section className="v4PilotTools" aria-label="เครื่องมือที่เปิดในพื้นที่ทำงานนี้">
          <p>สารบัญ T90 ยังไม่ได้เปิดในพื้นที่ทำงานนี้ แสดงเฉพาะรายการที่ระบบอนุญาตให้เลือกโดยไม่ข้าม Feature Flag</p>
          <div className="v4PilotGrid">
            {tools.map(tool => <a key={tool.id} href={`/tools/${encodeURIComponent(tool.id)}`} className="v4PilotCard">
              <span className="v4ToolSymbol"><ToolIcon name={tool.icon}/></span>
              <strong>{tool.title}</strong><small>{tool.description}</small><ArrowUpRight aria-hidden="true" size={17}/>
            </a>)}
          </div>
        </section>
      )}
    </main>
  );
}

import Image from "next/image";

export type ToolIconName =
  | "scan" | "merge" | "organize" | "split" | "compress" | "image" | "imagePdf"
  | "watermark" | "numbers" | "archive" | "office" | "stamp" | "link" | "pdfa";

export function ToolIcon({ name }: { name: ToolIconName }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

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

export function BrandGlyph() {
  return (
    <Image src="/assets/rcat-college-logo.webp" alt="" width={128} height={128} unoptimized />
  );
}

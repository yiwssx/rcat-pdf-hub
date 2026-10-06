export type ToolWorkspaceSettings = {
  signedUrl: string | null;
  signedTargetId: string | null;
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
  mergeOrder: string[];
};

export function createToolWorkspaceSettings(): ToolWorkspaceSettings {
  return {
    signedUrl: null,
    signedTargetId: null,
    signedTtl: 300,
    splitPages: "1-3",
    rotateDegrees: 90,
    rotatePages: "1-z",
    watermarkText: "เอกสารภายใน",
    watermarkOpacity: 0.18,
    watermarkRotation: 45,
    watermarkFontSize: 48,
    watermarkPosition: "center",
    pageFormat: "หน้า {page} / {total}",
    pageStart: 1,
    pagePosition: "bottom-center",
    stampId: "",
    stampPosition: "bottom-right",
    stampScale: 0.2,
    imagePageSize: "a4",
    imageFit: "contain",
    imageDpi: 150,
    rasterFormat: "png",
    rasterDpi: 150,
    rasterFirstPage: 1,
    rasterLastPage: "",
    mergeOrder: [],
  };
}

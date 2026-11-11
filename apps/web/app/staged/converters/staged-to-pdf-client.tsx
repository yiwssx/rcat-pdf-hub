"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createJob, getMe, listFiles, uploadFile, SESSION_AUTH,
  type AuthMe, type Job, type UploadedFile,
} from "../../../lib/api";
import {
  AVAILABLE_STAGED_TO_PDF_FORMATS,
  EXPERIMENTAL_TO_PDF_FORMATS,
  type StagedToPdfVariant,
} from "./catalog";

const IMAGE_VARIANTS = new Set(["jpg", "jpeg", "png", "webp", "bmp", "jfif", "gif", "tiff"]);

function ownedAndLive(file: UploadedFile, owner: string): boolean {
  return file.source_system === owner && file.size > 0
    && (!file.expires_at || (Number.isFinite(Date.parse(file.expires_at))
      && Date.parse(file.expires_at) > Date.now()));
}

function matchesVariant(file: UploadedFile, variant: StagedToPdfVariant): boolean {
  const name = file.original_name.toLowerCase();
  return file.content_type.toLowerCase() === variant.mime
    && variant.suffixes.some((suffix) => name.endsWith(suffix));
}

function variantFor(file: UploadedFile, variants: readonly StagedToPdfVariant[]) {
  return variants.find((variant) => matchesVariant(file, variant));
}

function hasScope(me: AuthMe | null, name: string): boolean {
  return Boolean(me && (me.scopes.includes("*") || me.scopes.includes(name)));
}

function looksLikePublicHttpsInput(value: string): boolean {
  // This is only a browser form sanity check, NOT an SSRF authorization.
  // The API, signed sidecar, DNS-pinned TLS and host firewall own that proof.
  if (value.length < 10 || value.length > 1800) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && Boolean(url.hostname)
      && !url.username && !url.password && !url.hash
      && (!url.port || url.port === "443");
  } catch {
    return false;
  }
}

export function StagedToPdfClient({
  requestedFileId, requestedToolId, enabledExperimentalIds = [],
}: {
  requestedFileId?: string;
  requestedToolId?: string;
  enabledExperimentalIds?: readonly string[];
}) {
  const availableFormats = [
    ...AVAILABLE_STAGED_TO_PDF_FORMATS,
    ...EXPERIMENTAL_TO_PDF_FORMATS.filter((item) =>
      enabledExperimentalIds.includes(item.id)),
  ];
  const initiallySelected = availableFormats.find(
    (item) => item.id === requestedToolId
  ) ?? availableFormats[0];
  const [formatId, setFormatId] = useState(initiallySelected.id);
  const [identity, setIdentity] = useState<AuthMe | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [uploadCandidate, setUploadCandidate] = useState<File | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState<Job | null>(null);

  const format = availableFormats.find((item) => item.id === formatId)
    ?? initiallySelected;
  const isUrl = format.id === "T33";
  const choices = useMemo(
    () => files.filter((file) => identity && ownedAndLive(file, identity.name)
      && variantFor(file, format.variants)),
    [files, identity, format],
  );
  const selected = choices.find((file) => file.id === selectedId);
  const route = selected ? variantFor(selected, format.variants) : undefined;
  const requiredScope = route && IMAGE_VARIANTS.has(route.route)
    ? "pdf:image-to-pdf" : "pdf:convert";
  const allowed = hasScope(identity, requiredScope);
  const canUpload = hasScope(identity, "files:write");
  const canDownload = hasScope(identity, "files:read") && hasScope(identity, "jobs:read");
  const accepting = [...new Set(format.variants.flatMap((variant) => variant.suffixes))].join(",");

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const me = await getMe(SESSION_AUTH);
        const owned = (await listFiles(SESSION_AUTH))
          .filter((file) => ownedAndLive(file, me.name));
        if (!active) return;
        setIdentity(me);
        setFiles(owned);
        setSelectedId(owned.find((file) => file.id === requestedFileId)?.id ?? "");
      } catch {
        if (active) setError("โปรดเข้าสู่ระบบด้วยบัญชีที่มีสิทธิ์ก่อนใช้งาน");
      } finally {
        if (active) setLoading(false);
      }
    }
    void initialize();
    return () => { active = false; };
  }, [requestedFileId]);

  // When changing formats, never submit a stale file from another MIME/tool.
  function changeFormat(value: string) {
    if (!availableFormats.some((item) => item.id === value)) return;
    setFormatId(value);
    setUrlInput("");
    setSelectedId("");
    setUploadCandidate(null);
    setSubmitted(null);
    setError("");
  }

  async function upload() {
    if (isUrl || !uploadCandidate || uploading || !identity || !canUpload) return;
    const name = uploadCandidate.name.toLowerCase();
    if (!format.variants.some((variant) =>
      variant.suffixes.some((suffix) => name.endsWith(suffix)))) {
      setError("ชนิดไฟล์ไม่ตรงกับเครื่องมือที่เลือก");
      return;
    }
    setUploading(true);
    setSubmitted(null);
    setError("");
    try {
      const stored = await uploadFile(uploadCandidate, SESSION_AUTH);
      if (!ownedAndLive(stored, identity.name) || !variantFor(stored, format.variants)) {
        setError("ไฟล์ที่เซิร์ฟเวอร์รับไว้ไม่ตรงกับรูปแบบที่เลือก กรุณาตรวจสอบ MIME");
        return;
      }
      setFiles((previous) => [stored, ...previous.filter((item) => item.id !== stored.id)]);
      setSelectedId(stored.id);
      setUploadCandidate(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถอัปโหลดไฟล์ได้");
    } finally {
      setUploading(false);
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || submitting || uploading || !identity
      || !allowed || !canDownload || format.withheld) return;
    if (!isUrl && (!selected || !route
      || !ownedAndLive(selected, identity.name)
      || !matchesVariant(selected, route))) return;
    const publicUrl = urlInput.trim();
    if (isUrl && !looksLikePublicHttpsInput(publicUrl)) {
      setError("ต้องเป็น URL แบบ HTTPS สาธารณะที่ถูกต้อง ไม่ใช่ไฟล์หรือที่อยู่ภายในเครือข่าย");
      return;
    }
    setSubmitting(true);
    setSubmitted(null);
    setError("");
    try {
      // The server revalidates ownership, MIME, suffix, scopes, stored
      // signature, active flags and quotas. Never pass a user-supplied owner.
      const job = isUrl
        ? await createJob("to-pdf/url", { url: publicUrl }, SESSION_AUTH)
        : await createJob("to-pdf/" + route!.route,
          { file_id: selected!.id }, SESSION_AUTH);
      setSubmitted(job);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ไม่สามารถสร้างงานได้");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="t90DocumentStage t90ConverterStage">
      <header className="t90DocumentStageHeader">
        <a href="/" aria-label="กลับไปหน้าหลัก">← Workspace</a>
        <span>RCAT PDF HUB · T90 CONVERTERS · ENGINEERING STAGING</span>
      </header>
      <section className="t90DocumentStageCard">
        <p className="t90DocumentStageKicker">SHARED CONVERTER WORKFLOW</p>
        <h1>แปลงไฟล์เป็น PDF</h1>
        <p>ใช้หน้าจอเดียวสำหรับตัวแปลงไฟล์ที่มี Backend อยู่แล้ว โดยรักษาไฟล์ต้นฉบับและสิทธิ์เจ้าของไฟล์</p>
        <p className="t90DocumentStageNotice" role="note">
          เป็นเครื่องมือระหว่างพัฒนา ไม่ใช่การรับรองรูปแบบไฟล์ทั้งหมดหรือการเปิดใช้งาน Production
          Native/URL จะแสดงเฉพาะเมื่อผู้ดูแลเปิด Development Flags แยกเป็นรายเครื่องมือ และยังต้องผ่านการตรวจ Runtime, Firewall และไฟล์ต้นฉบับจริง
        </p>
        {loading ? <p role="status">กำลังตรวจสอบสิทธิ์และไฟล์ที่มีอยู่…</p> : (
          <>
            <div className="t90DocumentStageField">
              <label htmlFor="t90-to-pdf-format">เครื่องมือแปลงไฟล์</label>
              <select id="t90-to-pdf-format" value={formatId}
                onChange={(event) => changeFormat(event.target.value)}
                disabled={uploading || submitting}>
                {availableFormats.map((item) => (
                  <option key={item.id} value={item.id}>{item.id} · {item.title}</option>
                ))}
              </select>
            </div>
            <p className="t90ConverterNote" role="note">ขอบเขตที่รองรับ: {format.limit}</p>
            {!isUrl && <p className="t90ConverterMeta">นามสกุลไฟล์: {accepting}</p>}
            {!isUrl && <div className="t90DocumentStageField">
              <label htmlFor="t90-to-pdf-upload">อัปโหลดไฟล์ต้นฉบับ</label>
              <input id="t90-to-pdf-upload" type="file" accept={accepting}
                disabled={!canUpload || uploading || submitting}
                onChange={(event) => setUploadCandidate(event.target.files?.[0] ?? null)} />
              <button type="button" className="t90DocumentStageSubmit"
                disabled={!uploadCandidate || !canUpload || uploading || submitting}
                onClick={() => { void upload(); }}>
                {uploading ? "กำลังอัปโหลด…" : "อัปโหลดไฟล์"}
              </button>
            </div>}
            <form onSubmit={(event) => { void submit(event); }}>
              {isUrl ? (
                <div className="t90DocumentStageField">
                  <label htmlFor="t90-to-pdf-url">URL เว็บไซต์สาธารณะ (HTTPS)</label>
                  <input id="t90-to-pdf-url" type="url" value={urlInput}
                    placeholder="https://example.org/article"
                    minLength={10} maxLength={1800} required
                    disabled={submitting || uploading}
                    onChange={(event) => { setUrlInput(event.target.value); setSubmitted(null); }} />
                  <p role="note">บริการจะโหลดเฉพาะเนื้อหาข้อความที่อนุญาต ไม่ใช่ภาพหน้าจอทั้งเว็บไซต์ และจะไม่เข้าถึงเครือข่ายภายใน</p>
                </div>
              ) : (
                <div className="t90DocumentStageField">
                  <label htmlFor="t90-to-pdf-source">ไฟล์ที่ผ่านการตรวจชนิดและเป็นของบัญชีนี้</label>
                  <select id="t90-to-pdf-source" value={selected?.id ?? ""}
                    onChange={(event) => { setSelectedId(event.target.value); setSubmitted(null); }}
                    disabled={uploading || submitting || !choices.length} required>
                    <option value="">เลือกไฟล์ที่ต้องการแปลง</option>
                    {choices.map((file) => <option key={file.id} value={file.id}>
                      {file.original_name}
                    </option>)}
                  </select>
                </div>
              )}
              {!isUrl && !canUpload && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ files:write สำหรับอัปโหลด</p>}
              {!allowed && identity && <p role="alert">บัญชีนี้ไม่มีสิทธิ์ {requiredScope}</p>}
              {!canDownload && identity && <p role="alert">ต้องมีสิทธิ์ files:read และ jobs:read เพื่อรับผลลัพธ์</p>}
              {error && <p role="alert" className="t90DocumentStageError">{error}</p>}
              <button type="submit" className="t90DocumentStageSubmit"
                disabled={uploading || submitting || !allowed || !canDownload || format.withheld
                  || (isUrl ? !looksLikePublicHttpsInput(urlInput.trim()) : !selected)}>
                {submitting ? "กำลังสร้างงาน…" : "แปลงเป็น PDF"}
              </button>
            </form>
          </>
        )}
        {submitted && (
          <div className="t90DocumentStageResult" role="status" aria-live="polite">
            <strong>รับงานแปลงไฟล์แล้ว</strong>
            <span>รหัสงาน: {submitted.id} · สถานะ: {submitted.status}</span>
            <a href={"/jobs/" + encodeURIComponent(submitted.id) + "/result"}>
              ดูผลลัพธ์และดาวน์โหลดไฟล์
            </a>
          </div>
        )}
        <p className="t90ConverterFooter">ผู้ใช้งาน Production ยังคงเห็นรายการ R1 เดิมเท่านั้น</p>
      </section>
    </main>
  );
}

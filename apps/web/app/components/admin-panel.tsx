"use client";

import { useState } from "react";
import {
  ApiKeyCreated,
  ApiKeyRecord,
  AuditEvent,
  createApiKey,
  listApiKeys,
  listAudit,
  revokeApiKey,
  ServicePolicy,
  updateServicePolicy,
} from "../../lib/api";

const scopeOptions = [
  "files:read", "files:write", "jobs:read",
  "pdf:merge", "pdf:split", "pdf:rotate", "pdf:compress",
  "pdf:ocr", "pdf:pdfa", "pdf:convert", "pdf:watermark",
  "pdf:page-number", "pdf:stamp",
];

export function AdminPanel({ apiKey }: { apiKey: string }) {
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [name, setName] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [scopes, setScopes] = useState<string[]>(scopeOptions);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [editing, setEditing] = useState<ServicePolicy | null>(null);
  const [message, setMessage] = useState("ใช้ Bootstrap Admin Key หรือ key ที่มี scope admin:keys");
  const [busy, setBusy] = useState(false);

  async function loadAdmin() {
    if (!apiKey) return;
    setBusy(true);
    try {
      const [keyRows, auditRows] = await Promise.all([listApiKeys(apiKey), listAudit(apiKey)]);
      setKeys(keyRows);
      setAudit(auditRows);
      setMessage("โหลดข้อมูลผู้ดูแลแล้ว");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "โหลดข้อมูล Admin ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  function toggleScope(scope: string) {
    setScopes((old) => old.includes(scope) ? old.filter((item) => item !== scope) : [...old, scope]);
  }

  async function createServiceKey() {
    if (!name.trim()) return;
    setBusy(true);
    setCreated(null);
    try {
      const result = await createApiKey({
        name: name.trim(),
        scopes,
        rate_limit_per_minute: 120,
        daily_job_limit: 1000,
        max_storage_mb: 2048,
        webhook_url: webhookUrl.trim() || null,
      }, apiKey);
      setCreated(result);
      setName("");
      setWebhookUrl("");
      setMessage("สร้าง service key แล้ว — plaintext key แสดงครั้งนี้ครั้งเดียว");
      setKeys(await listApiKeys(apiKey));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "สร้าง key ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(record: ApiKeyRecord) {
    setBusy(true);
    try {
      await revokeApiKey(record.id, apiKey);
      setKeys(await listApiKeys(apiKey));
      setMessage(`Revoke ${record.name} แล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Revoke ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  async function savePolicy() {
    if (!editing) return;
    setBusy(true);
    try {
      const result = await updateServicePolicy(editing, apiKey);
      setEditing(result);
      setKeys(await listApiKeys(apiKey));
      setMessage(`บันทึก policy ของ ${result.service_name} แล้ว`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "บันทึก policy ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="adminStack">
      <div className="panel panelHeader">
        <div>
          <span className="eyebrow">ADMINISTRATION</span>
          <h2>Service Keys, Quotas & Audit</h2>
          <p className="muted">{message}</p>
        </div>
        <button className="secondary" onClick={loadAdmin} disabled={!apiKey || busy}>โหลดข้อมูล Admin</button>
      </div>

      <div className="grid two">
        <div className="panel">
          <div className="panelTitle"><h2>สร้าง Service Key</h2><span>{scopes.length} scopes</span></div>
          <div className="formGrid">
            <label>Service name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="student-system" /></label>
            <label>Webhook URL<input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://system.example.org/pdfhub/webhook" /></label>
          </div>
          <div className="scopeGrid">
            {scopeOptions.map((scope) => (
              <label key={scope} className="check"><input type="checkbox" checked={scopes.includes(scope)} onChange={() => toggleScope(scope)} />{scope}</label>
            ))}
          </div>
          <button className="primary full" onClick={createServiceKey} disabled={!apiKey || !name.trim() || busy}>สร้าง API Key</button>
          {created && (
            <div className="secretBox">
              <strong>เก็บค่านี้ตอนนี้</strong>
              <code>{created.api_key}</code>
              {created.webhook_secret && <><small>Webhook signing secret</small><code>{created.webhook_secret}</code></>}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panelTitle"><h2>Service Keys</h2><span>{keys.length}</span></div>
          <div className="list compact">
            {keys.length === 0 && <p className="muted">กด “โหลดข้อมูล Admin”</p>}
            {keys.map((record) => (
              <div className="keyCard" key={record.id}>
                <div className="keyHead"><div><strong>{record.name}</strong><small>{record.active ? "active" : "revoked"} • {record.scopes.length} scopes</small></div><span className={record.active ? "pill ok" : "pill danger"}>{record.active ? "ACTIVE" : "REVOKED"}</span></div>
                <div className="quotaLine"><span>{record.policy.rate_limit_per_minute}/min</span><span>{record.policy.daily_job_limit}/day</span><span>{record.policy.max_storage_mb} MB</span></div>
                <div className="rowActions">
                  <button className="ghost" onClick={() => setEditing({ ...record.policy })}>Policy</button>
                  {record.active && <button className="dangerButton" onClick={() => revoke(record)} disabled={busy}>Revoke</button>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {editing && (
        <div className="panel">
          <div className="panelTitle"><h2>Policy: {editing.service_name}</h2><button className="ghost" onClick={() => setEditing(null)}>ปิด</button></div>
          <div className="formGrid four">
            <label>Requests/min<input type="number" min="0" value={editing.rate_limit_per_minute} onChange={(e) => setEditing({ ...editing, rate_limit_per_minute: Number(e.target.value) })} /></label>
            <label>Jobs/day<input type="number" min="0" value={editing.daily_job_limit} onChange={(e) => setEditing({ ...editing, daily_job_limit: Number(e.target.value) })} /></label>
            <label>Storage MB<input type="number" min="0" value={editing.max_storage_mb} onChange={(e) => setEditing({ ...editing, max_storage_mb: Number(e.target.value) })} /></label>
            <label>Webhook<input value={editing.webhook_url || ""} onChange={(e) => setEditing({ ...editing, webhook_url: e.target.value || null })} /></label>
          </div>
          <button className="primary" onClick={savePolicy} disabled={busy}>บันทึก Policy</button>
        </div>
      )}

      <div className="panel">
        <div className="panelTitle"><h2>Audit Trail</h2><span>{audit.length}</span></div>
        <div className="auditList">
          {audit.length === 0 && <p className="muted">ยังไม่มี audit ที่โหลดมา</p>}
          {audit.slice(0, 40).map((item, index) => (
            <div className="auditRow" key={`${item.timestamp}-${index}`}>
              <time>{new Date(item.timestamp).toLocaleString("th-TH")}</time>
              <strong>{item.event}</strong>
              <span>{item.actor}</span>
              <code>{item.resource_id?.slice(0, 8) || "—"}</code>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

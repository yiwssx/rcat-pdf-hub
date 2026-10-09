"use client";

import type { Job } from "../../lib/api";

export type TaskJourneyStage = "intake" | "configure" | "submitting" | "processing" | "result";
export type ToolFlowKind = "processing" | "sharing" | "archiving";

export function resolveTaskJourneyStage(
  hasInput: boolean,
  submitting: boolean,
  lastJob: Job | null,
): TaskJourneyStage {
  if (lastJob?.status === "completed") return "result";
  if (lastJob) return "processing";
  if (submitting) return "submitting";
  return hasInput ? "configure" : "intake";
}

export function TaskJourneyNav({ stage, kind }: { stage: TaskJourneyStage; kind: ToolFlowKind }) {
  const actionLabel = kind === "sharing" ? "สร้างลิงก์" : kind === "archiving" ? "จัดเก็บ" : "ประมวลผล";
  const progress = ["intake", "configure", "submitting", "processing", "result"];
  const position = progress.indexOf(stage);
  const steps = ["เลือกไฟล์", "ตั้งค่า", actionLabel, "ผลลัพธ์"];

  return (
    <nav className="v3Journey" aria-label="ขั้นตอนการทำงาน">
      <ol>
        {steps.map((label, index) => {
          const active = index === (position >= 4 ? 3 : position >= 2 ? 2 : position);
          const complete = index < (position >= 4 ? 3 : position >= 2 ? 2 : position);
          return (
            <li key={label} data-state={active ? "active" : complete ? "complete" : "upcoming"} aria-current={active ? "step" : undefined}>
              <span aria-hidden="true">{complete ? "✓" : index + 1}</span>
              <strong>{label}</strong>
            </li>
          );
        })}
      </ol>
      {stage === "submitting" && <p role="status">กำลังส่งคำขอประมวลผล…</p>}
    </nav>
  );
}

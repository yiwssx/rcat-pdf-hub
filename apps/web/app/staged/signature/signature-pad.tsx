"use client";

import { useRef, type PointerEvent as SignaturePointerEvent } from "react";

export function SignaturePad({
  onImage, disabled,
}: { onImage: (blob: Blob | null) => void; disabled: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const active = useRef<number | null>(null);

  function point(event: SignaturePointerEvent<HTMLCanvasElement>) {
    const target = canvas.current!;
    const bounds = target.getBoundingClientRect();
    return {
      x: (event.clientX - bounds.left) * target.width / bounds.width,
      y: (event.clientY - bounds.top) * target.height / bounds.height,
    };
  }
  function start(event: SignaturePointerEvent<HTMLCanvasElement>) {
    if (disabled || active.current !== null) return;
    const surface = canvas.current;
    const pen = surface?.getContext("2d");
    if (!surface || !pen) return;
    const startAt = point(event);
    active.current = event.pointerId;
    surface.setPointerCapture(event.pointerId);
    pen.strokeStyle = "#223044";
    pen.lineWidth = 3.4;
    pen.lineCap = "round";
    pen.lineJoin = "round";
    pen.beginPath();
    pen.moveTo(startAt.x, startAt.y);
    pen.lineTo(startAt.x + 0.01, startAt.y + 0.01);
    pen.stroke();
    onImage(null);
  }
  function move(event: SignaturePointerEvent<HTMLCanvasElement>) {
    if (disabled || active.current !== event.pointerId) return;
    const pen = canvas.current?.getContext("2d");
    if (!pen) return;
    const next = point(event);
    pen.lineTo(next.x, next.y);
    pen.stroke();
  }
  function stop(event: SignaturePointerEvent<HTMLCanvasElement>) {
    if (active.current !== event.pointerId) return;
    active.current = null;
    const surface = canvas.current;
    if (surface?.hasPointerCapture(event.pointerId)) {
      surface.releasePointerCapture(event.pointerId);
    }
    surface?.toBlob((blob) => {
      onImage(blob && blob.type === "image/png" ? blob : null);
    }, "image/png");
  }
  function reset() {
    const surface = canvas.current;
    surface?.getContext("2d")?.clearRect(0, 0, surface.width, surface.height);
    active.current = null;
    onImage(null);
  }
  return (
    <div className="t90DocumentStageField">
      <label htmlFor="m12-canvas">พื้นที่วาดลายเซ็น (ลากนิ้วหรือเมาส์)</label>
      <canvas id="m12-canvas" ref={canvas} width={720} height={220}
        role="img" aria-label="พื้นที่วาดลายเซ็น" className="m12SignatureCanvas"
        onPointerDown={start} onPointerMove={move}
        onPointerUp={stop} onPointerCancel={stop}/>
      <div className="m12SignatureActions">
        <button type="button" onClick={reset} disabled={disabled}>ล้างลายเซ็น</button>
        <small>ภาพที่วาดมีพื้นหลังโปร่งใส</small>
      </div>
    </div>
  );
}

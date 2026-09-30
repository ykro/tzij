"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";

// Rendered locally (no QR web service): works with Wi-Fi off.
export function QrCode({ value }: { value: string }) {
  const [svg, setSvg] = useState<string>("");
  useEffect(() => {
    QRCode.toString(value, { type: "svg", margin: 0, errorCorrectionLevel: "M", color: { dark: "#1F1A17", light: "#FBF9F4" } })
      .then(setSvg)
      .catch(() => setSvg(""));
  }, [value]);
  return (
    <div className="qr" role="img" aria-label={`Código QR: ${value}`}
      dangerouslySetInnerHTML={{ __html: svg }} />
  );
}

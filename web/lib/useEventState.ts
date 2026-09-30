"use client";

// Live state from the duel service over Server-Sent Events. EventSource reconnects by
// itself; we expose the connection status so screens can show a designed error state.

import { useEffect, useState } from "react";

export type Connection = "connecting" | "open" | "lost";

export function useEventState<T>(view: "presenter" | "validator", event: string) {
  const [data, setData] = useState<T | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");

  useEffect(() => {
    const source = new EventSource(`/api/events?view=${view}`);
    source.addEventListener(event, (e) => {
      setData(JSON.parse((e as MessageEvent).data) as T);
      setConnection("open");
    });
    source.onopen = () => setConnection("open");
    source.onerror = () => setConnection("lost");
    return () => source.close();
  }, [view, event]);

  return { data, connection };
}

export async function postJSON<T = unknown>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const payload = await res.json();
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      /* keep the status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

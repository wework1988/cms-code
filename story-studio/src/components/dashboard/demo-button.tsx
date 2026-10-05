"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function DemoProjectButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function loadDemo() {
    setLoading(true);
    try {
      const res = await fetch("/api/projects/demo", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed");
      router.push(`/projects/${data.id}`);
      router.refresh();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Failed to load demo");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button variant="outline" onClick={loadDemo} disabled={loading}>
      {loading ? "Loading demo…" : "Demo project"}
    </Button>
  );
}

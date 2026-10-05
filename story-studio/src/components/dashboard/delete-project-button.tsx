"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function DeleteProjectButton({ projectId, title }: { projectId: string; title: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function onDelete() {
    const label = title.trim() || "this project";
    if (!confirm(`Delete "${label}"? This cannot be undone.`)) return;

    setLoading(true);
    try {
      const res = await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error ?? "Delete failed");
      router.refresh();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="text-red-700 hover:bg-red-50 hover:text-red-800"
      onClick={onDelete}
      disabled={loading}
    >
      {loading ? "Deleting…" : "Delete"}
    </Button>
  );
}

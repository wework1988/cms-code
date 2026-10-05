import { isLLMConfigured } from "@/lib/llm/provider";
import { Card, CardContent } from "@/components/ui/card";

export function SetupBanner() {
  if (isLLMConfigured()) return null;

  return (
    <Card className="mb-6 border-amber-200 bg-amber-50">
      <CardContent className="py-4 text-sm text-amber-900">
        <strong>LLM not configured.</strong> Add <code>DEEPSEEK_API_KEY</code> or{" "}
        <code>OPENAI_API_KEY</code> to <code>.env</code>. You can still open the demo project and
        explore the workspace without live generation.
      </CardContent>
    </Card>
  );
}

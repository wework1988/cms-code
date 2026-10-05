import Link from "next/link";
import { cn } from "@/lib/utils";

export function AppShell({
  children,
  active,
}: {
  children: React.ReactNode;
  active?: "dashboard" | "settings" | "prompts" | "youtube";
}) {
  const links = [
    { href: "/", label: "Dashboard", key: "dashboard" as const },
    { href: "/settings/channel", label: "Channel Style", key: "settings" as const },
    { href: "/settings/prompts", label: "Prompt Profiles", key: "prompts" as const },
    { href: "/settings/youtube", label: "YouTube OAuth", key: "youtube" as const },
  ];

  return (
    <div className="min-h-screen bg-[#f6f7f9] text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <Link href="/" className="text-xl font-semibold tracking-tight">
              Story Studio
            </Link>
            <p className="text-sm text-slate-500">Source-to-original Hindi narration workspace</p>
          </div>
          <nav className="flex gap-4 text-sm">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-md px-3 py-2 hover:bg-slate-100",
                  active === link.key && "bg-slate-100 font-medium",
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}

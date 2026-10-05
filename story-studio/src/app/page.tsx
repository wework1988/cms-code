import Link from "next/link";
import { prisma } from "@/lib/db";
import { AppShell } from "@/components/layout/app-shell";
import { SetupBanner } from "@/components/setup-banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { DemoProjectButton } from "@/components/dashboard/demo-button";
import { DeleteProjectButton } from "@/components/dashboard/delete-project-button";

export default async function DashboardPage() {
  const projects = await prisma.project.findMany({
    orderBy: { updatedAt: "desc" },
    include: {
      sources: true,
      scriptVersions: { where: { isCurrent: true }, take: 1 },
    },
  });

  return (
    <AppShell active="dashboard">
      <SetupBanner />

      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-2 max-w-2xl text-slate-600">
            Turn pasted source transcripts into an original Hindi narration — YouTube URLs are references only —
            with fact isolation, narrative planning, and editorial originality checks.
          </p>
        </div>
        <div className="flex gap-3">
          <DemoProjectButton />
          <Button asChild>
            <Link href="/projects/new">New story</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4">
        {projects.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>No projects yet</CardTitle>
              <CardDescription>
                Start with a new story or load the demo project to explore the full workspace.
              </CardDescription>
            </CardHeader>
          </Card>
        ) : (
          projects.map((project) => (
            <Card key={project.id}>
              <CardContent className="flex items-center justify-between py-5">
                <div>
                  <div className="flex items-center gap-2">
                    <Link href={`/projects/${project.id}`} className="text-lg font-medium hover:underline">
                      {project.title}
                    </Link>
                    {project.isDemo && <Badge>Demo</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-slate-500">
                    {project.sources.length} sources · Last edited {formatDate(project.updatedAt)}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <Badge className="capitalize">{project.status.replaceAll("_", " ")}</Badge>
                  <p className="text-sm text-slate-500">
                    Script: {project.scriptVersions[0]?.charCount?.toLocaleString() ?? "—"} chars
                  </p>
                  <DeleteProjectButton projectId={project.id} title={project.title} />
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </AppShell>
  );
}

window.RV_DATA = {
  projectName: "Deep Research Engine",
  modules: [
    { "name": "app/main.py", "folder": "app/api", "loc": 120, "complexity": 5, "type": "code" },
    { "name": "app/api/middleware.py", "folder": "app/api", "loc": 180, "complexity": 8, "type": "security" },
    { "name": "app/agents/scout.py", "folder": "app/agents", "loc": 250, "complexity": 10, "type": "agent" },
    { "name": "app/agents/workers/historian.py", "folder": "app/agents/workers", "loc": 210, "complexity": 7, "type": "worker" },
    { "name": "app/agents/workers/skeptic.py", "folder": "app/agents/workers", "loc": 210, "complexity": 7, "type": "worker" },
    { "name": "app/agents/workers/pragmatist.py", "folder": "app/agents/workers", "loc": 210, "complexity": 7, "type": "worker" },
    { "name": "app/agents/workers/futurist.py", "folder": "app/agents/workers", "loc": 210, "complexity": 7, "type": "worker" },
    { "name": "app/tools/search_pipeline.py", "folder": "app/tools", "loc": 340, "complexity": 12, "type": "tool" },
    { "name": "app/agents/auditor.py", "folder": "app/agents", "loc": 290, "complexity": 11, "type": "auditor" },
    { "name": "app/agents/writer.py", "folder": "app/agents", "loc": 230, "complexity": 8, "type": "writer" },
    { "name": "app/db/repository.py", "folder": "app/db", "loc": 310, "complexity": 9, "type": "db" },
    { "name": "app/services/webhook.py", "folder": "app/services", "loc": 150, "complexity": 4, "type": "service" }
  ],
  deps: {
    nodes: [
      { id: "app/main.py", label: "FastAPI App / Router" },
      { id: "app/api/middleware.py", label: "Security & Auth Middleware" },
      { id: "app/agents/scout.py", label: "Briefing & Scout Agent" },
      { id: "app/agents/workers/historian.py", label: "Historiador Contextual" },
      { id: "app/agents/workers/skeptic.py", label: "Cético Analítico" },
      { id: "app/agents/workers/pragmatist.py", label: "Pragmático Aplicado" },
      { id: "app/agents/workers/futurist.py", label: "Visionário Futurista" },
      { id: "app/tools/search_pipeline.py", label: "Unified Search Subflow" },
      { id: "app/agents/auditor.py", label: "Auditor & Gatekeeper" },
      { id: "app/agents/writer.py", label: "Redator Editorial" },
      { id: "app/db/repository.py", label: "Async SQLAlchemy DB" },
      { id: "app/services/webhook.py", label: "Webhook Callback Service" }
    ],
    edges: [
      { from: "app/main.py", to: "app/api/middleware.py", weight: 2 },
      { from: "app/api/middleware.py", to: "app/agents/scout.py", weight: 2 },
      { from: "app/agents/scout.py", to: "app/db/repository.py", weight: 1 },
      { from: "app/agents/scout.py", to: "app/agents/workers/historian.py", weight: 2 },
      { from: "app/agents/scout.py", to: "app/agents/workers/skeptic.py", weight: 2 },
      { from: "app/agents/scout.py", to: "app/agents/workers/pragmatist.py", weight: 2 },
      { from: "app/agents/scout.py", to: "app/agents/workers/futurist.py", weight: 2 },
      { from: "app/agents/workers/historian.py", to: "app/tools/search_pipeline.py", weight: 3 },
      { from: "app/agents/workers/skeptic.py", to: "app/tools/search_pipeline.py", weight: 3 },
      { from: "app/agents/workers/pragmatist.py", to: "app/tools/search_pipeline.py", weight: 3 },
      { from: "app/agents/workers/futurist.py", to: "app/tools/search_pipeline.py", weight: 3 },
      { from: "app/agents/workers/historian.py", to: "app/db/repository.py", weight: 1 },
      { from: "app/agents/workers/skeptic.py", to: "app/db/repository.py", weight: 1 },
      { from: "app/agents/workers/pragmatist.py", to: "app/db/repository.py", weight: 1 },
      { from: "app/agents/workers/futurist.py", to: "app/db/repository.py", weight: 1 },
      { from: "app/agents/auditor.py", to: "app/db/repository.py", weight: 2 },
      { from: "app/agents/auditor.py", to: "app/agents/workers/historian.py", weight: 1 },
      { from: "app/agents/auditor.py", to: "app/agents/writer.py", weight: 3 },
      { from: "app/agents/writer.py", to: "app/db/repository.py", weight: 2 },
      { from: "app/agents/writer.py", to: "app/services/webhook.py", weight: 2 }
    ]
  },
  nav: [
    { id: "index", href: "index.html", label: "Visão Geral" },
    { id: "arquitetura", href: "arquitetura.html", label: "Arquitetura 3D" },
    { id: "workflow", href: "../workflow.md", label: "Workflow Spec" },
    { id: "readme", href: "../README.md", label: "README Spec" }
  ]
};

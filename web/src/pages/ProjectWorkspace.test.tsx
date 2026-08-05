/**
 * ProjectWorkspace 冒烟测试 — 三步流程（select → plan → results）。
 *
 * 覆盖：新建模式（_new）下渲染模块选择步骤；历史项目打开时按状态进入对应步骤。
 */

import { describe, expect, it, afterEach } from "vitest";
import { screen, waitFor, cleanup } from "@testing-library/react";
import { render } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { server } from "@/test/mocks/handlers";
import { AppProviders } from "@/app/AppProviders";
import { ProjectWorkspace } from "@/pages/ProjectWorkspace";

const PROJECT_ID = "00000000-0000-0000-0000-000000000001";

/** 渲染工作区：需要路由参数上下文（useParams） */
function renderWorkspace(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AppProviders>
        <Routes>
          <Route path="/app/project/:projectId" element={<ProjectWorkspace />} />
        </Routes>
      </AppProviders>
    </MemoryRouter>,
  );
}

describe("ProjectWorkspace", () => {
  afterEach(() => {
    cleanup();
    server.resetHandlers();
  });

  it("renders module selection step in new-project mode", async () => {
    renderWorkspace("/app/project/_new");

    await waitFor(() => {
      expect(screen.getByText("输入教学主题")).toBeInTheDocument();
    });
  });

  it("renders results step for a completed project", async () => {
    renderWorkspace(`/app/project/${PROJECT_ID}`);

    // 默认 MSW handler 返回 done 项目（无模块产出）→ 渲染成果空态
    await waitFor(() => {
      expect(screen.getByText("尚未生成模块产物")).toBeInTheDocument();
    });
  });
});

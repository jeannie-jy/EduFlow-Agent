import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { AccountSettingsPage } from "@/pages/AccountSettingsPage";
import { renderWithProviders } from "@/test/render";
import { server } from "@/test/mocks/handlers";

const activeCredential = {
  id: "credential-active",
  name: "主力 DeepSeek",
  provider: "deepseek",
  purpose: "generation",
  model: "deepseek-chat",
  base_url: "https://api.deepseek.com/v1",
  version: 2,
  status: "valid",
  is_active: true,
  key_last_four: "2222",
  validated_at: null,
  last_used_at: null,
  created_at: "2026-09-15T00:00:00Z",
};

const revokedCredential = {
  ...activeCredential,
  id: "credential-revoked",
  version: 1,
  status: "revoked",
  key_last_four: "1111",
};

beforeEach(() => {
  server.use(
    http.get("http://localhost:8000/api/me/provider-credentials", () => HttpResponse.json({
      // The client remains defensive if an older API still returns history.
      items: [activeCredential, revokedCredential],
    })),
    http.get("http://localhost:8000/api/me/usage", () => HttpResponse.json({
      resources: {
        generation: { day: { used: 5, limit: 5 }, month: { used: 8, limit: 50 } },
        video: { day: { used: 1, limit: 1 }, month: { used: 1, limit: 5 } },
      },
      limits: {},
      model_usage_month: {
        input_tokens: 0,
        output_tokens: 0,
        estimated_cost_usd: 0,
        notice: "",
      },
      llm_limits: { task_max_tokens: 1000 },
    })),
    http.get("http://localhost:8000/api/me/mfa/totp", () => HttpResponse.json({
      enabled: false,
      confirmed_at: null,
    })),
    http.delete("http://localhost:8000/api/me/provider-credentials/:id", () => (
      new HttpResponse(null, { status: 204 })
    )),
  );
});

it("hides count-limit summaries for BYOK generation and local video rendering", async () => {
  renderWithProviders(<AccountSettingsPage />);

  expect(await screen.findByRole("heading", { name: "API 使用情况" })).toBeVisible();
  expect(screen.queryByText("不限次数")).not.toBeInTheDocument();
  expect(screen.queryByText("今日 5/5 · 本月 8/50")).not.toBeInTheDocument();
  expect(screen.queryByText("今日 1/1 · 本月 1/5")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("本月参考费用上限（USD）")).not.toBeInTheDocument();
});

it("hides revoked credentials and removes a credential after revoke succeeds", async () => {
  const user = userEvent.setup();
  renderWithProviders(<AccountSettingsPage />);

  expect(await screen.findByText(/sk-\*\*\*\*2222/)).toBeVisible();
  expect(screen.queryByText(/sk-\*\*\*\*1111/)).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "删除" }));

  expect(await screen.findByText("接入已撤销。")).toBeVisible();
  expect(screen.queryByText(/sk-\*\*\*\*2222/)).not.toBeInTheDocument();
  expect(screen.getByText("尚未配置。开始生成前必须添加“内容生成”密钥。")).toBeVisible();
});

it("groups multiple saved credentials by purpose and marks one current connection", async () => {
  server.use(
    http.get("http://localhost:8000/api/me/provider-credentials", () => HttpResponse.json({
      items: [
        activeCredential,
        {
          ...activeCredential,
          id: "credential-backup",
          name: "备用 OpenAI",
          provider: "openai",
          model: "gpt-4.1-mini",
          base_url: "https://api.openai.com/v1",
          version: 1,
          is_active: false,
          key_last_four: "4444",
        },
        {
          ...activeCredential,
          id: "credential-embedding",
          name: "百炼向量",
          provider: "dashscope",
          purpose: "embedding",
          model: "text-embedding-v4",
          base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
          version: 1,
          key_last_four: "3333",
        },
      ],
    })),
  );
  renderWithProviders(<AccountSettingsPage />);

  expect(await screen.findByRole("heading", { name: "内容生成" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "语义检索" })).toBeVisible();
  expect(screen.getByText(/sk-\*\*\*\*2222/)).toBeVisible();
  expect(screen.getByText("备用 OpenAI")).toBeVisible();
  expect(screen.getByText(/sk-\*\*\*\*3333/)).toBeVisible();
  expect(screen.queryByText(/尚未选择语义检索连接/)).not.toBeInTheDocument();
});

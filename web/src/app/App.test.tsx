import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

function renderAt(path = "/") {
  window.history.pushState({}, "", path);
  render(<App />);
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
});

it("renders the EduFlow landing narrative and working primary routes", async () => {
  const user = userEvent.setup();
  renderAt();
  expect(screen.getAllByRole("link", { name: /EduFlow/ }).length).toBeGreaterThan(0);
  expect(
    screen.getByRole("heading", { name: /让知识动起来。\s*让理解自然发生。/ }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看如何工作" })).toHaveAttribute(
    "href",
    "#how-it-works",
  );

  await user.click(screen.getAllByRole("link", { name: "免费开始" })[0]);
  expect(screen.getByRole("heading", { name: "创建你的学习空间" })).toBeInTheDocument();
});

it("moves between login and registration", async () => {
  const user = userEvent.setup();
  renderAt("/login");
  expect(screen.getByRole("heading", { name: "欢迎回来" })).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "创建账号" }));
  expect(screen.getByRole("heading", { name: "创建你的学习空间" })).toBeInTheDocument();
});

it("shows accessible login errors and toggles password visibility", async () => {
  const user = userEvent.setup();
  renderAt("/login");
  await user.click(screen.getByRole("button", { name: "登录 EduFlow" }));
  expect(screen.getByText("请输入邮箱地址")).toBeInTheDocument();
  expect(screen.getByText("请输入密码")).toBeInTheDocument();

  const password = screen.getByLabelText("密码");
  expect(password).toHaveAttribute("type", "password");
  await user.click(screen.getByRole("button", { name: "显示密码" }));
  expect(password).toHaveAttribute("type", "text");
});

it("validates registration agreement and matching passwords", async () => {
  const user = userEvent.setup();
  renderAt("/register");
  await user.type(screen.getByLabelText("昵称"), "小流");
  await user.type(screen.getByLabelText("邮箱"), "learner@example.com");
  await user.type(screen.getByLabelText("密码"), "password1");
  await user.type(screen.getByLabelText("确认密码"), "password2");
  await user.click(screen.getByRole("button", { name: "创建免费账号" }));
  expect(screen.getByText("两次输入的密码不一致")).toBeInTheDocument();
  expect(screen.getByText("请阅读并同意服务条款")).toBeInTheDocument();
});

it("completes the mock login journey", async () => {
  const user = userEvent.setup();
  renderAt("/login");
  await user.type(screen.getByLabelText("邮箱"), "learner@example.com");
  await user.type(screen.getByLabelText("密码"), "password1");
  await user.click(screen.getByRole("button", { name: "登录 EduFlow" }));
  expect(screen.getByRole("button", { name: "正在进入…" })).toBeDisabled();
  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "准备开始一次新的推演" })).toBeInTheDocument();
  });
});

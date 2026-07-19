import { AuthShell } from "../components/auth/AuthShell";
import { LoginForm } from "../features/auth/LoginForm";

export function LoginPage() {
  return <AuthShell><LoginForm /></AuthShell>;
}

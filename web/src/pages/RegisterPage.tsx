import { AuthShell } from "../components/auth/AuthShell";
import { RegisterForm } from "../features/auth/RegisterForm";

export function RegisterPage() {
  return <AuthShell><RegisterForm /></AuthShell>;
}

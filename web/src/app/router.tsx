import { Route, Routes } from "react-router-dom";
import { AppEntryPlaceholder } from "../pages/AppEntryPlaceholder";
import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RegisterPage } from "../pages/RegisterPage";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/app" element={<AppEntryPlaceholder />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

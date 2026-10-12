import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { LandingPage } from "./pages/LandingPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { ParticipantsPage } from "./pages/ParticipantsPage";
import { ParticipantDetailPage } from "./pages/ParticipantDetailPage";
import { DatesPage } from "./pages/DatesPage";
import { DateDetailPage } from "./pages/DateDetailPage";
import { RankingsPage } from "./pages/RankingsPage";
import { RankingDetailPage } from "./pages/RankingDetailPage";
import { DemoPage } from "./pages/DemoPage";
import { SettingsPage } from "./pages/SettingsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 10_000, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<LandingPage />} />
            <Route path="app" element={<WorkspacePage />} />
            <Route path="participants" element={<ParticipantsPage />} />
            <Route path="participants/:id" element={<ParticipantDetailPage />} />
            <Route path="dates" element={<DatesPage />} />
            <Route path="dates/:id" element={<DateDetailPage />} />
            <Route path="rankings" element={<RankingsPage />} />
            <Route path="rankings/:participantId" element={<RankingDetailPage />} />
            <Route path="demo" element={<DemoPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

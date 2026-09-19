import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { AuthGuard } from "@/components/auth-guard";

export const metadata: Metadata = {
  title: "AI-Native ERP | Autonomous Multi-Agent Platform",
  description: "Autonomous event-driven Multi-Agent Enterprise Resource Planning system.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="bg-cream-50 text-cream-900 antialiased">
      <body className="min-h-screen flex flex-col font-sans">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">
          <AuthGuard>{children}</AuthGuard>
        </main>
        <footer className="border-t border-cream-300 py-4 text-center text-xs text-cream-700">
          AI-Native Multi-Agent ERP &bull; Deterministic Invariant Firewall Active &bull; Multi-Tenant Isolated
        </footer>
      </body>
    </html>
  );
}

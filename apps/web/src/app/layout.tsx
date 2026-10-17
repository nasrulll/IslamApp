import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Fikihmu — Studi Keislaman Berbasis Sumber", template: "%s | Fikihmu" },
  description: "Fondasi Fikihmu: rencana Maktabah, Fikih Muqaran, Sanad Kitab, dan Tafsir Ayat berbasis referensi kitab.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}

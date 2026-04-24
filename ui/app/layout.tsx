import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

const fontBody = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap"
});

const fontHeadline = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-headline",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Lead Catalyst Pro",
  description: "Signal-grounded enrichment dashboard"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fontBody.variable} ${fontHeadline.variable}`}>
      <body className="font-body antialiased">{children}</body>
    </html>
  );
}


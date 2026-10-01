import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk, Literata } from "next/font/google";
import "./globals.css";

// Self-hosted at build time by next/font: the stage has no internet.
// Literata's latin subset includes U+02BC (modifier letter apostrophe), the saltillo.
const literata = Literata({ subsets: ["latin", "latin-ext"], variable: "--font-display", display: "swap" });
const hanken = Hanken_Grotesk({ subsets: ["latin", "latin-ext"], variable: "--font-body", display: "swap" });

export const metadata: Metadata = {
  title: "Tzij",
  description: "Español ↔ Kʼicheʼ: un modelo pequeño sin internet contra un modelo frontera.",
  icons: { icon: "/brand/mark.svg" },
  // Browser auto-translation would "translate" the K'iche' output: never offer it.
  other: { google: "notranslate" },
};

export const viewport: Viewport = { themeColor: "#F4F0E8", colorScheme: "light" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-GT" translate="no" className={`${literata.variable} ${hanken.variable}`}>
      <body>{children}</body>
    </html>
  );
}

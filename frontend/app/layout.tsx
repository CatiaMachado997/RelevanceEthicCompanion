import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { Fraunces } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ethic Companion - AI with Trust over Engagement",
  description: "Your AI companion built on ethical principles. Assists without manipulating. Trust over engagement.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${GeistSans.className} ${fraunces.variable}`} suppressHydrationWarning>
      <body className="antialiased bg-background text-foreground">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: "var(--ec-card-bg)",
                color: "var(--ec-text)",
                border: "1px solid var(--ec-card-border)",
              },
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}

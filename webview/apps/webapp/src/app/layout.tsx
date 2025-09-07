import QueryProvider from "@/components/common/query-provider";
import { ThemeProvider } from "@/components/common/theme-provider";
import { ThemeSwitcher } from "@/components/common/theme-switcher";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sita",
  description: "Simplify developer onboarding",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/manifest.json",
  openGraph: {
    title: "Sita",
    description: "Simplify developer onboarding",
    url: "https://trysita.com",
    siteName: "Sita",
    images: [
      {
        url: "/hero.webp",
        width: 1200,
        height: 630,
        alt: "Sita - Simplify developer onboarding",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Sita",
    description: "Simplify developer onboarding",
    images: ["/hero.webp"],
  },
  robots: {
    index: true,
    googleBot: {
      index: true,
    },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`antialiased`}>
        <ThemeProvider
          attribute="class"
          enableColorScheme
          defaultTheme="dark"
          enableSystem
        >
          <QueryProvider>
            {children}
            <ThemeSwitcher />
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

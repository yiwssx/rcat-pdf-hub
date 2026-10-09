import "./globals.css";
import "./app-v3.css";

export const metadata = {
  title: "RCAT PDF Hub",
  description: "ศูนย์กลางเครื่องมือ PDF และเอกสารแบบ self-hosted",
  icons: { icon: [{ url: "/assets/rcat-college-logo.webp", type: "image/webp" }] },
};

export const viewport = {
  themeColor: "#f5f7ff",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>{children}</body>
    </html>
  );
}

import "./globals.css";
import "./app-v2.css";

export const metadata = {
  title: "RCAT PDF Hub",
  description: "ศูนย์กลางเครื่องมือ PDF และเอกสารแบบ self-hosted",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>{children}</body>
    </html>
  );
}

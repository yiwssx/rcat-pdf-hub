import "./globals.css";
import "./tailwind.css";
import "./app-v3.css";
import "./t90-directory.css";
import "./v4-application.css";
import { PdfHubAuthProvider } from "./components/pdf-hub-auth-provider";

export const metadata = {
  title: "RCAT PDF Hub",
  description: "ศูนย์กลางเครื่องมือ PDF และเอกสารแบบ self-hosted",
  icons: { icon: [{ url: "/assets/rcat-pdf-hub-logo.webp", type: "image/webp" }] },
};

export const viewport = {
  themeColor: "#121b31",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body><PdfHubAuthProvider>{children}</PdfHubAuthProvider></body>
    </html>
  );
}

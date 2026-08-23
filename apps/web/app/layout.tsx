import "./globals.css";

export const metadata = {
  title: "PDF Hub",
  description: "Centralized self-hosted PDF processing",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>{children}</body>
    </html>
  );
}

import "./globals.css";

export const metadata = {
  title: "GST AAR Search — India Rules-as-Code",
  description: "Full-text + semantic search over GST advance rulings (AAR/AAAR) with provenance",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

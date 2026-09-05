export const metadata = {
  title: "GST AAR Search — India Rules-as-Code",
  description: "Full-text search over GST advance rulings (AAR/AAAR) with provenance",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

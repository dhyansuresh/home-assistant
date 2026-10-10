import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "HomePilot starter",
  description: "Software-first grocery assistant starter",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

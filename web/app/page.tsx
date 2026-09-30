import Link from "next/link";
import { Wordmark } from "@/components/Brand";

// The duel service redirects "/" to /presentador/; this page covers `next dev` and direct visits.
export default function Home() {
  return (
    <main className="home">
      <Wordmark size="large" />
      <nav className="home__nav" aria-label="Vistas">
        <Link href="/presentador/">Vista del presentador</Link>
        <Link href="/validar/">Validar desde el teléfono</Link>
      </nav>
    </main>
  );
}

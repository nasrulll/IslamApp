import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SERVICE_CARDS, type ServiceSlug } from "@fikihmu/shared";
import { Pill } from "@fikihmu/ui";

type PageProps = { params: Promise<{ service: string }> };

const plannedFeatures: Record<ServiceSlug, string[]> = {
  fikih: [
    "Membandingkan pendapat Hanafi, Maliki, Syafi'i, dan Hanbali",
    "Menyajikan syarat, pengecualian, dan perbedaan pendapat",
    "Membuka rujukan kitab, edisi, dan teks yang mendasari jawaban",
  ],
  "sanad-kitab": [
    "Menerima teks Arab berharakat atau tanpa harakat",
    "Mencari kecocokan exact, normalized, fuzzy, dan semantic secara terpisah",
    "Menampilkan lokasi kutipan beserta konteks dan provenance",
  ],
  "tafsir-ayat": [
    "Memilih surah dan ayat dari teks Al-Qur'an terverifikasi",
    "Membaca kutipan tafsir pada edisi sumber yang sesuai",
    "Membandingkan penafsiran dari koleksi kitab terkurasi",
  ],
};

export function generateStaticParams() {
  return SERVICE_CARDS.map(({ slug }) => ({ service: slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { service } = await params;
  const item = SERVICE_CARDS.find((entry) => entry.slug === service);
  if (!item) return { title: "Halaman tidak ditemukan" };
  return { title: item.title, description: item.description };
}

export default async function PlannedServicePage({ params }: PageProps) {
  const { service } = await params;
  const item = SERVICE_CARDS.find((entry) => entry.slug === service);
  if (!item) notFound();
  return (
    <main className="service-page">
      <nav aria-label="Breadcrumb"><Link href="/">← Kembali ke beranda</Link></nav>
      <section className="detail-panel">
        <Pill>{item.stage}</Pill>
        <h1>{item.title}</h1>
        <p className="lead">{item.subtitle}</p>
        <p>{item.description}</p>
        <h2>Ruang lingkup yang direncanakan</h2>
        <ul>{plannedFeatures[item.slug].map((feature) => <li key={feature}>{feature}</li>)}</ul>
        <aside className="notice" role="note">
          Belum aktif. Tidak ada data kitab, hasil kutipan, analisis fikih, atau tafsir yang dipublikasikan pada tahap bootstrap ini.
        </aside>
      </section>
    </main>
  );
}

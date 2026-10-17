import Link from "next/link";
import { PLATFORM_NAME, SERVICE_CARDS } from "@fikihmu/shared";
import { Pill } from "@fikihmu/ui";

export default function HomePage() {
  return (
    <main>
      <header className="topbar" aria-label="Navigasi utama">
        <Link href="/" className="brand">{PLATFORM_NAME}<span className="brand-star" aria-hidden="true"> ✦</span></Link>
        <span className="topbar-note">Kitabku • Fase bootstrap</span>
      </header>
      <section className="hero" aria-labelledby="hero-title">
        <Pill>Tahap awal pengembangan</Pill>
        <h1 id="hero-title">Ilmu yang dapat ditelusuri kembali ke sumbernya.</h1>
        <p className="lead">Fikihmu dirancang untuk menghadirkan studi fikih empat mazhab, penelusuran kutipan kitab Arab, dan perbandingan tafsir ayat melalui satu perpustakaan digital.</p>
        <p className="muted">Fitur pencarian kitab, AI RAG, dan koleksi tafsir belum tersedia. Belum ada klaim akurasi maupun verifikasi keilmuan.</p>
      </section>
      <section className="service-section" aria-labelledby="services-title">
        <div className="section-heading">
          <h2 id="services-title">Tiga layanan Fikihmu</h2>
          <p>Jelajahi rancangan ruang lingkup setiap layanan.</p>
        </div>
        <div className="card-grid">
          {SERVICE_CARDS.map((service, idx) => (
            <article className="service-card" key={service.slug}>
              <span className="index-number">0{idx + 1}</span>
              <h3>{service.title}</h3>
              <p className="subtitle">{service.subtitle}</p>
              <p>{service.description}</p>
              <div className="card-footer">
                <Pill>{service.stage}</Pill>
                <Link href={`/${service.slug}`}>Baca rencana <span aria-hidden="true">→</span></Link>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="foundation" aria-label="Prinsip keilmuan">
        <h2>Maktabah sebagai fondasi</h2>
        <p>Setiap hasil AI yang nantinya ditampilkan harus ditautkan ke karya, edisi, passage, dan referensi yang sesuai. Tidak ada nomor halaman atau kutipan yang dihasilkan tanpa verifikasi sumber.</p>
      </section>
      <footer className="site-footer">Fikihmu v1.1 • Blueprint terkunci • Produk dalam pengembangan</footer>
    </main>
  );
}

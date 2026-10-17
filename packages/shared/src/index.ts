/** Planned Fikihmu feature registry, never a claim of deployed capability. */
export const PLATFORM_NAME = "Fikihmu";

export const SERVICE_CARDS = [
  {
    slug: "fikih",
    title: "Fikih Muqaran",
    subtitle: "Studi fikih lintas empat mazhab",
    description: "Hanafi, Maliki, Syafi'i, Hanbali — perbandingan pendapat berbasis kitab yang ditinjau.",
    stage: "Dalam pengembangan",
  },
  {
    slug: "sanad-kitab",
    title: "Sanad Kitab",
    subtitle: "Pelacak sumber kutipan Arab",
    description: "Pencocokan kutipan dengan karya, edisi, konteks, dan referensi yang dapat diperiksa.",
    stage: "Dalam pengembangan",
  },
  {
    slug: "tafsir-ayat",
    title: "Tafsir Ayat",
    subtitle: "Perbandingan kitab tafsir",
    description: "Telusuri ayat dan bandingkan tafsir berdasarkan sumber yang terverifikasi.",
    stage: "Dalam pengembangan",
  },
] as const;

export type ServiceSlug = (typeof SERVICE_CARDS)[number]["slug"];

import { notFound } from "next/navigation";
import { SectionPage } from "@/components/Sections";
import { editionBySlug, getPage, getSite } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return getSite().editions.map((e) => ({ edition: e.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ edition: string }> }) {
  const e = editionBySlug((await params).edition);
  return { title: e ? `ARTREND ${e.ko} — Artists` : "ARTREND" };
}

export default async function Page({ params }: { params: Promise<{ edition: string }> }) {
  const site = getSite();
  const edition = editionBySlug((await params).edition);
  const page = edition && getPage(edition.code, site.asof);
  if (!edition || !page) notFound();
  return <SectionPage site={site} edition={edition} page={page} section="artists" />;
}

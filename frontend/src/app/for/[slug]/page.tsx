import type { Metadata } from "next";
import { Suspense } from "react";

import { GridSkeleton } from "@/components/ProductCard";
import { findTag, TagProducts } from "@/components/TagPage";

export async function generateMetadata(props: PageProps<"/for/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const tag = await findTag("recipient", slug);
  return tag
    ? { title: `Gifts ${tag.name.toLowerCase()}`, description: `Gift ideas ${tag.name.toLowerCase()}, delivered across Sri Lanka.` }
    : {};
}

export default function RecipientPage(props: PageProps<"/for/[slug]">) {
  return (
    <Suspense fallback={<GridSkeleton />}>
      <Content params={props.params} />
    </Suspense>
  );
}

async function Content({ params }: { params: PageProps<"/for/[slug]">["params"] }) {
  const { slug } = await params;
  return <TagProducts kind="recipient" slug={slug} />;
}

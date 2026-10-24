import type { Metadata } from "next";
import { Suspense } from "react";

import { GridSkeleton } from "@/components/ProductCard";
import { findTag, TagProducts } from "@/components/TagPage";

export async function generateMetadata(props: PageProps<"/occasions/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const tag = await findTag("occasion", slug);
  return tag
    ? { title: `${tag.name} gifts`, description: `Gift ideas for ${tag.name.toLowerCase()}, delivered across Sri Lanka.` }
    : {};
}

export default function OccasionPage(props: PageProps<"/occasions/[slug]">) {
  return (
    <Suspense fallback={<GridSkeleton />}>
      <Content params={props.params} />
    </Suspense>
  );
}

async function Content({ params }: { params: PageProps<"/occasions/[slug]">["params"] }) {
  const { slug } = await params;
  return <TagProducts kind="occasion" slug={slug} />;
}

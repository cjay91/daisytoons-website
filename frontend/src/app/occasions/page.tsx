import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { getTags } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Shop by occasion",
  description: "Birthday, anniversary, wedding and more: gifts for every occasion.",
};

export default function OccasionsPage() {
  return (
    <>
      <h1 className="mb-6 text-2xl font-bold">Shop by occasion</h1>
      <Suspense fallback={null}>
        <AllTags />
      </Suspense>
    </>
  );
}

async function AllTags() {
  await connection();
  const tags = await getTags();
  const groups = [
    { title: "Occasions", base: "/occasions", tags: tags.filter((t) => t.kind === "occasion") },
    { title: "Who it's for", base: "/for", tags: tags.filter((t) => t.kind === "recipient") },
  ];
  return groups.map((group) => (
    <section key={group.base} className="mb-10">
      <h2 className="mb-3 text-lg font-semibold">{group.title}</h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {group.tags.map((tag) => (
          <li key={tag.slug}>
            <Link
              href={`${group.base}/${tag.slug}`}
              className="card flex h-20 items-center justify-center px-3 text-center font-medium hover:border-foreground"
            >
              {tag.name}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  ));
}

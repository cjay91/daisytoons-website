# Knowledge for agents

Markdown files the agents search with `search_knowledge` (Part 9). The worker indexes them within
a minute of a deploy that changes them.

- `policies/`: the shop's policies. Keep them in step with the storefront's policy pages
  (`frontend/src/app/<page>/page.tsx`); a test checks that the headings and numbers match.
- `faq/`: answers to common customer questions.
- `guides/`: gift guides by occasion and recipient.
- `suppliers/` (add when needed): supplier terms and product information.

Each file starts with `# Title`, and `## Headings` split it into passages. Write each passage so
it makes sense on its own, since an agent may read just that one.

Values in braces are filled in from the API's settings, so prices stay correct:
`{delivery_fee_colombo}`, `{delivery_fee_other}`, `{free_delivery_over}`, `{gift_wrap_fee}`,
`{reservation_minutes}` and `{shop_email}`. Lines starting with `<!--` are left out.

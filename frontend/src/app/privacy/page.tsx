import type { Metadata } from "next";

import { PolicyPage } from "@/components/PolicyPage";
import { SHOP } from "@/lib/shop";

export const metadata: Metadata = {
  title: "Privacy",
  description: `What personal information ${SHOP.name} keeps, why, and your choices.`,
};

export default function PrivacyPage() {
  return (
    <PolicyPage title="Privacy">
      <p>
        This explains what personal information {SHOP.name} collects when you shop with us, what we use it for, and your rights
        under Sri Lanka&apos;s Personal Data Protection Act, No. 9 of 2022.
      </p>
      <h2>What we collect</h2>
      <ul>
        <li>Your name, email address and phone number, and the delivery address and gift message you give us.</li>
        <li>What you ordered and when, and the status of each order.</li>
        <li>If you create an account: your login details (your password is stored scrambled, never as text) and saved addresses.</li>
        <li>Basic technical information, such as your IP address, to keep the site secure and stop abuse.</li>
      </ul>
      <p>
        We never see or store your card details. Payments are handled by PayHere, which tells us only whether a payment went
        through and its reference number.
      </p>
      <h2>What we use it for</h2>
      <ul>
        <li>To take, pack and deliver your order, and to email you about it.</li>
        <li>To answer your questions and handle returns.</li>
        <li>To keep records the law asks us to keep, such as sales records.</li>
      </ul>
      <p>We don&apos;t sell your information, and we only send marketing emails if you&apos;ve asked us to.</p>
      <h2>Who we share it with</h2>
      <ul>
        <li>The courier delivering your order: the recipient&apos;s name, address and phone number.</li>
        <li>PayHere, to take your payment.</li>
        <li>The companies that host our website and send our emails, only so they can do that for us.</li>
      </ul>
      <h2>Cookies</h2>
      <p>
        We use only the cookies the shop needs to work: one to keep your cart, and one to keep you logged in. We don&apos;t use
        advertising or tracking cookies.
      </p>
      <h2>How long we keep it</h2>
      <p>
        We keep order records for as long as tax law requires (currently up to 7 years). If you delete your account, we remove your
        saved addresses and login, and keep only what we need for past orders.
      </p>
      <h2>Your rights</h2>
      <p>
        You can ask us for a copy of the information we hold about you, to correct it, or to delete it where we don&apos;t need to
        keep it. Email {SHOP.email} and we&apos;ll reply within 21 days.
      </p>
    </PolicyPage>
  );
}

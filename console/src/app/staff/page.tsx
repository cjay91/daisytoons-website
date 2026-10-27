import type { Metadata } from "next";
import { Suspense } from "react";

import { createMember, resetTwoFactor } from "@/app/actions";
import { ActionForm } from "@/components/ActionForm";
import { Loading } from "@/components/Loading";
import { staffApi } from "@/lib/session";
import type { Staff } from "@/lib/types";

export const metadata: Metadata = { title: "Staff" };

const ROLES = [
  { value: "packer", label: "Packer: orders, packing, shipping and stock" },
  { value: "support", label: "Support: can see orders and clear attention flags" },
  { value: "admin", label: "Admin: everything, including prices and refunds" },
];

export default function StaffPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Staff</h1>
      <Suspense fallback={<Loading />}>
        <Members />
      </Suspense>
      <section className="card p-4">
        <h2 className="mb-3 font-semibold">Add someone</h2>
        <ActionForm action={createMember} submit="Add staff member">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="full_name" className="label">
                Name
              </label>
              <input id="full_name" name="full_name" required className="input" />
            </div>
            <div>
              <label htmlFor="email" className="label">
                Email
              </label>
              <input id="email" name="email" type="email" required className="input" />
            </div>
            <div>
              <label htmlFor="password" className="label">
                First password <span className="font-normal text-muted">(8 or more characters)</span>
              </label>
              <input id="password" name="password" type="password" minLength={8} required autoComplete="new-password" className="input" />
            </div>
            <div>
              <label htmlFor="role" className="label">
                Role
              </label>
              <select id="role" name="role" className="input">
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </ActionForm>
      </section>
    </div>
  );
}

async function Members() {
  const members = await staffApi<Staff[]>("/staff/members");
  return (
    <div className="card overflow-x-auto">
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Two-step login</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.id} className={m.is_active ? "" : "opacity-60"}>
              <td>{m.full_name}</td>
              <td>{m.email}</td>
              <td className="capitalize">{m.role}</td>
              <td>
                {m.two_factor_enabled ? (
                  <ActionForm
                    action={resetTwoFactor}
                    hidden={{ staff_id: m.id }}
                    submit="Reset"
                    variant="outline"
                    confirm={`Reset two-step login for ${m.full_name}? Use this when they've lost their phone.`}
                    className="flex items-center gap-3"
                  >
                    <span className="text-ok">On</span>
                  </ActionForm>
                ) : (
                  <span className="text-muted">Not set up</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

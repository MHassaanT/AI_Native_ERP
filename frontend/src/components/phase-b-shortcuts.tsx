import Link from "next/link";

const destinations: Record<string, { label: string; href: string }[]> = {
  buying: [
    { label: "Buying Masters & Tax Templates", href: "/master-data" },
    { label: "Stock & Buying Settings", href: "/operational-settings" },
  ],
  selling: [
    { label: "Selling Masters, Pricing & Promotions", href: "/master-data" },
    { label: "Delivery Notes", href: "/delivery-notes" },
    { label: "Customer Loyalty", href: "/loyalty" },
  ],
  stock: [
    { label: "Shipping & Manufacturer Masters", href: "/master-data" },
    { label: "Delivery Notes", href: "/delivery-notes" },
    { label: "Stock Settings", href: "/operational-settings" },
  ],
  pos: [
    { label: "Loyalty Programs", href: "/loyalty" },
    { label: "Pricing & Promotions", href: "/master-data" },
  ],
};

export function PhaseBShortcuts({ area }: { area: keyof typeof destinations }) {
  return (
    <nav aria-label="Buying and selling tools" className="flex flex-wrap gap-2">
      {destinations[area].map((destination) => (
        <Link
          key={destination.label}
          href={destination.href}
          className="rounded-full border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs font-medium text-cream-800 transition-colors hover:border-sage-400 hover:bg-sage-50"
        >
          {destination.label}
        </Link>
      ))}
    </nav>
  );
}

# TOKEN ZOMBIE — Design System

The product interface, website, README and launch assets should feel like one product. Use these rules for new UI and when refreshing existing screens.

## Brand foundation
- **Personality:** technical, confident, precise, slightly playful. Never noisy, childish or cluttered.
- **Canvas:** near-black `#050505`; primary surface `#101010`; raised surface `#171717`.
- **Borders:** restrained charcoal `#303030`.
- **Signature accent:** acid green `#7CFC00`, matching `docs/img/brand-hero.svg`.
- **Primary text:** `#F5F5F5`; secondary text: `#A3A3A3`.
- **Semantic colours:** amber `#FFB020` for warnings, red `#FF5B5B` for critical states, blue `#62C8F5` for information.
- Green is for brand emphasis and positive state—not every border, line or data point.

## Layout and spacing
- Use a readable maximum content width and consistent outer margins.
- Follow an 8 px spacing rhythm: 8 / 16 / 24 / 32 / 48.
- Group related metrics; align labels, values and helper text.
- Lead with one strong hero area, then clear sections. Avoid excessive nested cards and dividers.
- Stack metrics cleanly on mobile; prevent horizontal overflow and tiny text.

## Typography
- Use a clean system sans-serif for product UI. Reserve monospace for token values, logs, IDs and technical metadata.
- Use sentence case for explanatory copy and concise uppercase labels for metric headings.
- Give primary metrics clear hierarchy; keep supporting text muted but legible.
- Avoid unnecessary font families, weights and arbitrary sizes.

## Components and states
- Cards use dark surfaces, subtle borders and modest radii; avoid heavy shadows and glowing outlines.
- Buttons use clear verb-first labels, consistent sizing and visible focus states.
- Label values **MEASURED**, **EST**, **UNAVAILABLE** or **NOT YET SUPPORTED**. Never style an estimate like a measured result.
- Use text as well as colour for status. Colour must never be the only signal.
- Design empty, loading, offline and error states.
- Never invent counters: show “—” or “Unavailable” when the source is absent.

## Data visualisation
- Give each metric a name, unit, time window and provenance where relevant.
- Keep measured savings, estimated savings, gross savings and overhead separate.
- Do not use decorative charts to imply data the product does not collect.
- Keep gridlines restrained and highlight only meaningful series or thresholds.

## GitHub README and documentation
- Lead with the brand hero, one-line product description and a small set of useful links.
- Show one canonical screenshot per interface state; never render the same image twice.
- Use relative paths such as `docs/img/dashboard.png`. Inside centered HTML blocks, use HTML `<img>` elements—not Markdown image syntax.
- Give screenshots descriptive alt text and captions that identify live, demo or illustrative data.
- Keep heading hierarchy predictable. Use tables for comparisons, not long prose.
- Keep badges minimal. Avoid decorative emoji in every heading.
- Put one canonical quick-start near the top and link to the full install guide.
- Link status, limitations, security, metrics and roadmap so claims are easy to verify.

## Screenshot and release quality
- Capture the real interface at desktop and mobile widths.
- Use realistic, clearly labelled demo data when live data cannot be shown.
- Check wrapping, alignment, contrast, clipping and responsive layout before publishing.
- Never label a mockup as a live capture or demo data as benchmark evidence.
- Re-check image paths and rendered README after every visual change.

## Source of truth
`docs/img/brand-hero.svg` defines the signature green (`#7CFC00`) and black/white treatment. New assets should match it rather than introduce a competing palette.

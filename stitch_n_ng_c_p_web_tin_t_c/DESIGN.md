---
name: Modern Tech Pulse
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#4648d4'
  on-secondary: '#ffffff'
  secondary-container: '#6063ee'
  on-secondary-container: '#fffbff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002113'
  on-tertiary-container: '#009668'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-xl:
    fontFamily: Be Vietnam Pro
    fontSize: 48px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Be Vietnam Pro
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Be Vietnam Pro
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Be Vietnam Pro
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.7'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.4'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  section-gap: 80px
---

## Brand & Style

The design system is engineered for a premium technology news platform that prioritizes editorial clarity and future-forward aesthetics. The brand personality is **authoritative yet accessible**, functioning as a high-fidelity lens through which users consume complex technical information.

The visual direction follows a **Corporate Modern** style with **Minimalist** leanings. It leverages significant whitespace to reduce cognitive load, allowing high-quality editorial imagery and crisp typography to take center stage. Key characteristics include:
- **Clarity over Clutter:** Every element serves a functional purpose in the information hierarchy.
- **Precision:** Perfect grid alignment and consistent mathematical scaling.
- **Sophistication:** Subtly layered surfaces and refined transitions that evoke a sense of high-end software rather than a traditional legacy newspaper.

## Colors

The palette is anchored by **Deep Slate Blue** (Primary), providing a serious, trustworthy foundation for text and structural elements. 

- **Primary (#0F172A):** Used for headlines, navigation bars, and heavy-weight icons.
- **Accent - Startup/AI:** These categories utilize **Electric Indigo** and **Vibrant Purple** to signal innovation.
- **Functional Accents:** Neon Cyan is reserved for specific "Live" updates or high-tech breakthroughs.
- **Surface & Background:** The background uses a "Cool Gray 50" (#F8FAFC) to separate content sections without the harshness of pure white.
- **Status Colors:** Standardized success (Emerald), warning (Amber), and error (Rose) tokens are applied sparingly to UI feedback loops.

## Typography

This design system uses a dual-font approach. **Be Vietnam Pro** is utilized for headings to provide a modern, distinctive character with high legibility in Vietnamese and English. **Inter** is used for body copy and UI labels due to its neutral, highly functional nature and excellent rendering at small sizes.

Line heights are intentionally generous (1.6x - 1.7x) for long-form articles to prevent reader fatigue. Display styles use tighter leading and negative letter-spacing to create a "locked-in" editorial look for hero stories.

## Layout & Spacing

The system follows a **12-column fluid grid** for desktop and a **4-column grid** for mobile. 

- **Vertical Rhythm:** Built on an 8px base unit. Component heights and internal padding must always be multiples of 8.
- **Sectioning:** Large vertical gaps (80px+) are used between distinct content blocks (e.g., "Latest News" vs "AI Daily Brief") to signify a change in topic or format.
- **Content Density:** The layout is "airy." Cards should have internal padding of at least 24px to ensure the text does not feel crowded by the borders or images.

## Elevation & Depth

Visual hierarchy is established through **Ambient Shadows** and **Tonal Layering**. 

1. **Level 0 (Background):** #F8FAFC.
2. **Level 1 (Cards/Sidebar):** Pure white (#FFFFFF) with a very soft, diffused shadow: `0px 4px 20px rgba(15, 23, 42, 0.05)`.
3. **Level 2 (Hover States/Dropdowns):** Elevated shadow with increased spread and slightly higher opacity: `0px 10px 30px rgba(15, 23, 42, 0.08)`.

Avoid harsh borders. Instead, use thin 1px strokes in a light gray (#E2E8F0) only when elements need to be separated against a white background.

## Shapes

The shape language is defined by **Medium Roundedness**. 

- **Standard Elements:** News cards, input fields, and featured images use a 12px (`rounded-lg`) corner radius.
- **Interactive Elements:** Buttons and Category Chips use a 8px (`base`) radius for a slightly sharper, more "actionable" feel.
- **Special Containers:** Large featured hero sections may use up to 24px (`rounded-xl`) to create a soft, framed effect for immersive photography.

## Components

### News Cards
Cards are the primary molecule. They must feature a 16:9 aspect ratio image with 12px rounded corners. The category tag should be positioned above the headline, using a small, high-contrast label font.

### Buttons
- **Primary:** Deep Blue background with White text. Bold weight.
- **Secondary:** White background with 1px Slate border. 
- **Ghost:** Transparent background, used for "See all" or "Read more" links with a trailing arrow icon.

### Category Chips
Small, pill-shaped or slightly rounded indicators. Use a low-opacity version of the category color as the background and the full-saturation color for the text (e.g., Light Purple background with Deep Purple text for "AI").

### Input Fields
Search bars should be minimalist. Use a light gray background, 12px rounding, and a subtle inner shadow or stroke. Icons should be "Outline" style for a technical aesthetic.

### Lists (Trending/Sidebar)
Use a numbered system with high-contrast digits in the Primary color. Ensure consistent vertical padding between list items (16px) to maintain readability in dense information areas.
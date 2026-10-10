-- Private single-household demo schema. The API selects household_id from
-- server configuration; clients and LLM tool arguments never choose it.
create table if not exists public.households (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(trim(name)) > 0),
  created_at timestamptz not null default now()
);

create table if not exists public.inventory_items (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households(id) on delete cascade,
  name text not null check (char_length(trim(name)) > 0),
  brand text,
  size_label text,
  quantity integer not null check (quantity > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists inventory_items_household_idx
  on public.inventory_items(household_id);

create table if not exists public.grocery_list_items (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households(id) on delete cascade,
  name text not null check (char_length(trim(name)) > 0),
  quantity integer not null check (quantity > 0),
  created_at timestamptz not null default now()
);

create index if not exists grocery_list_items_household_idx
  on public.grocery_list_items(household_id);

-- No browser-facing policies are supplied. Service-role access is server-only.
-- Before public deployment, design auth/RLS and review the complete data path.
alter table public.households enable row level security;
alter table public.inventory_items enable row level security;
alter table public.grocery_list_items enable row level security;

create table if not exists public.conversations (
  id uuid primary key, user_id uuid not null references auth.users(id) on delete cascade,
  langgraph_thread_id text not null unique, title text not null default 'New chat',
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.chat_messages (
  id bigint generated always as identity primary key, conversation_id uuid not null references public.conversations(id) on delete cascade,
  role text not null check (role in ('user','assistant')), content text not null, created_at timestamptz not null default now()
);
create index if not exists conversations_user_updated_idx on public.conversations(user_id, updated_at desc);
create index if not exists chat_messages_conversation_idx on public.chat_messages(conversation_id, id);
alter table public.conversations enable row level security;
alter table public.chat_messages enable row level security;
-- FastAPI connects with DATABASE_URL; browser clients do not access these tables directly.

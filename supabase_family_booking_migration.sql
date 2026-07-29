-- Run once in Supabase SQL Editor before using family bookings.
-- Existing single-passenger ages remain unchanged, for example 26 becomes '26'.
ALTER TABLE public.bookings
  ALTER COLUMN age TYPE TEXT USING age::TEXT;

-- Associate future bookings with the signed-in account.
ALTER TABLE public.bookings
  ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS bookings_user_id_idx ON public.bookings(user_id);
